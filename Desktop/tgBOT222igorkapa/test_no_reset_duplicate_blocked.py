#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест проверяет что если рост НЕДОСТАТОЧЕН для RESET, то дубль НЕ пройдёт
"""

import sys
import io
import time
import tempfile
import os

# Исправляем кодировку для Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from telegram_sender import TelegramSender
from state_manager import StateManager
from market_monitor import MarketMonitor
from config import TELEGRAM_CHAT_ID


def test_no_reset_duplicate_blocked():
    """Тест: если рост недостаточен для RESET, то дубль должен быть заблокирован"""
    print("\n" + "="*80)
    print("ТЕСТ: Недостаточный рост для RESET - дубль должен быть заблокирован")
    print("="*80)
    
    # Временный файл для состояний
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    temp_file.close()
    temp_state_file = temp_file.name
    
    try:
        # Переопределяем STATE_FILE для теста
        import config
        original_state_file = config.STATE_FILE
        config.STATE_FILE = temp_state_file
        
        # Создаём экземпляры
        telegram_sender = TelegramSender()
        state_manager = StateManager()
        market_monitor = MarketMonitor()
        
        test_pair = "TESTNORESETUR"
        initial_max = 0.0110
        
        print(f"\nТестовая пара: {test_pair}")
        print(f"Начальный максимум: {initial_max}")
        print()
        
        # Инициализируем состояние
        current_time = time.time()
        state_manager.update_state(
            test_pair,
            local_max=initial_max,
            local_max_time=current_time - 100,
            local_min=None,
            triggered_levels=[],
            last_price=initial_max,
            initialized=True,
            initialization_time=current_time - 1000
        )
        
        # ===== ЭТАП 1: Первый сигнал -11.8% (Level 2) =====
        print("="*80)
        print("ЭТАП 1: Первый сигнал -11.8%")
        print("="*80)
        
        price_signal1 = 0.0097  # -11.8% от 0.0110
        drop_percent1 = ((price_signal1 - initial_max) / initial_max) * 100
        print(f"Цена: {price_signal1} (падение: {drop_percent1:.2f}%)")
        
        state1 = state_manager.get_state(test_pair)
        triggered1 = state1.get("triggered_levels", [])
        
        signal1 = market_monitor.check_levels(
            test_pair,
            price_signal1,
            initial_max,
            triggered1
        )
        
        if not signal1:
            print("  ❌ Сигнал не создан!")
            return False
        
        level1 = signal1['level']
        print(f"  ✅ Сигнал Level {level1} создан (падение: {signal1['drop_percent']:.2f}%)")
        
        # Сохраняем уровень
        state_manager.add_triggered_level(test_pair, level1, current_time)
        state_manager.update_state(test_pair, local_min=price_signal1)
        
        state_after_signal1 = state_manager.get_state(test_pair)
        max_drop = ((state_after_signal1.get('local_min') - initial_max) / initial_max) * 100
        print(f"  Максимальное падение: {max_drop:.2f}%")
        print(f"  triggered_levels: {state_after_signal1.get('triggered_levels')}")
        
        # ===== ЭТАП 2: НЕДОСТАТОЧНЫЙ рост для RESET =====
        print("\n" + "="*80)
        print("ЭТАП 2: НЕДОСТАТОЧНЫЙ рост для RESET")
        print("="*80)
        
        local_min = state_after_signal1.get('local_min')
        reset_percent = state_manager.get_reset_percent_for_drop(max_drop)
        print(f"Требуемый рост от минимума для RESET: +{reset_percent}%")
        
        # Цена растёт НЕДОСТАТОЧНО для RESET (только +2% вместо требуемых +4%)
        insufficient_growth = 2.0  # Меньше чем требуется
        price_partial = local_min * (1 + insufficient_growth / 100)
        growth_from_min = ((price_partial - local_min) / local_min) * 100
        
        print(f"Цена после роста: {price_partial:.6f}")
        print(f"Фактический рост от минимума: {growth_from_min:.2f}% (НЕДОСТАТОЧНО! Нужно +{reset_percent}%)")
        
        # Проверяем should_reset
        print(f"\nПроверка should_reset()...")
        should_reset_result = state_manager.should_reset(test_pair, price_partial, current_time + 100)
        
        if should_reset_result:
            print(f"  ❌ should_reset() вернул True - RESET произойдёт!")
            print(f"     Но рост {growth_from_min:.2f}% < требуемый {reset_percent}%")
            print(f"     RESET НЕ должен происходить!")
            return False
        
        print(f"  ✅ should_reset() вернул False - RESET НЕ произойдёт!")
        print(f"     Рост {growth_from_min:.2f}% недостаточен (нужно +{reset_percent}%)")
        
        # Обновляем максимум (но НЕ RESET!)
        state_manager.update_state(test_pair, local_max=price_partial, local_max_time=current_time + 100)
        
        state_after_partial = state_manager.get_state(test_pair)
        print(f"\nСостояние после недостаточного роста:")
        print(f"  local_max: {state_after_partial.get('local_max')} (обновлён, но это НЕ RESET)")
        print(f"  local_min: {state_after_partial.get('local_min')} (сохранён)")
        print(f"  triggered_levels: {state_after_partial.get('triggered_levels')} (НЕ обнулены!)")
        
        if state_after_partial.get('triggered_levels') == []:
            print(f"  ❌ triggered_levels обнулены - это неправильно! RESET не должен был произойти!")
            return False
        
        print(f"  ✅ triggered_levels сохранены - RESET не произошёл!")
        
        # ===== ЭТАП 3: Попытка отправить дубль (должен быть заблокирован) =====
        print("\n" + "="*80)
        print("ЭТАП 3: Попытка отправить ТОТ ЖЕ сигнал (дубль должен быть заблокирован)")
        print("="*80)
        
        # Пытаемся создать тот же сигнал с той же ценой
        print(f"Попытка создать сигнал с ценой {price_signal1} (падение {drop_percent1:.2f}%)")
        
        state_before_duplicate = state_manager.get_state(test_pair)
        triggered_dup = state_before_duplicate.get("triggered_levels", [])
        print(f"triggered_levels: {triggered_dup}")
        print(f"local_max: {state_before_duplicate.get('local_max')}")
        
        # Вычисляем падение от нового максимума
        new_max = state_before_duplicate.get('local_max')
        drop_from_new_max = ((price_signal1 - new_max) / new_max) * 100
        print(f"Падение от нового максимума: {drop_from_new_max:.2f}%")
        
        # Проверяем уровни с новой ценой (но тот же уровень должен быть заблокирован)
        signal_duplicate = market_monitor.check_levels(
            test_pair,
            price_signal1,
            new_max,
            triggered_dup
        )
        
        if signal_duplicate:
            dup_level = signal_duplicate.get('level')
            if dup_level == level1:
                print(f"  ❌ ОШИБКА! Создан ТОТ ЖЕ сигнал Level {dup_level}!")
                print(f"     ДУБЛЬ будет отправлен - защита НЕ РАБОТАЕТ!")
                return False
            else:
                print(f"  ⚠️  Создан другой уровень {dup_level} (но проверяем основной уровень)")
        
        # Проверяем основной уровень напрямую
        print(f"\nПроверка уровня {level1} через is_duplicate_signal()...")
        is_dup = state_manager.is_duplicate_signal(test_pair, level1, current_time + 200)
        if not is_dup:
            print(f"  ❌ is_duplicate_signal() вернул False - дубль НЕ заблокирован!")
            print(f"     Level {level1} должен быть заблокирован, так как он в triggered_levels!")
            return False
        
        print(f"  ✅ is_duplicate_signal() вернул True - дубль заблокирован!")
        
        # Проверяем через telegram_sender кэш
        print(f"\nПроверка через telegram_sender кэш...")
        # Сначала нужно отметить как отправленный (эмуляция)
        telegram_sender._mark_as_sent(test_pair, level1)
        is_dup_cache = telegram_sender._is_duplicate(test_pair, level1)
        if not is_dup_cache:
            print(f"  ⚠️  telegram_sender кэш не блокирует (но другие проверки уже заблокировали)")
        else:
            print(f"  ✅ telegram_sender кэш блокирует дубль")
        
        # Итоги
        print("\n" + "="*80)
        print("ИТОГИ ТЕСТА")
        print("="*80)
        print("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
        print(f"   - Первый сигнал -11.8% (Level {level1}) отправлен")
        print(f"   - Рост от минимума на {growth_from_min:.2f}% (недостаточно для RESET)")
        print(f"   - RESET НЕ произошёл (нужно было +{reset_percent}%)")
        print(f"   - triggered_levels сохранены: {triggered_dup}")
        print(f"   - Дубль Level {level1} заблокирован корректно")
        print(f"   - Логика работает: недостаточный рост НЕ вызывает RESET, дубль блокируется")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ОШИБКА ТЕСТА: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Восстанавливаем оригинальный STATE_FILE
        config.STATE_FILE = original_state_file
        
        # Удаляем временный файл
        try:
            if os.path.exists(temp_state_file):
                os.unlink(temp_state_file)
        except:
            pass


if __name__ == "__main__":
    print("\n" + "="*80)
    print("ТЕСТ: Недостаточный рост для RESET")
    print("="*80)
    print("Проверка что если рост недостаточен для RESET, то дубль заблокируется")
    
    result = test_no_reset_duplicate_blocked()
    
    print("\n" + "="*80)
    print("ФИНАЛЬНЫЙ РЕЗУЛЬТАТ")
    print("="*80)
    if result:
        print("✅ ТЕСТ ПРОЙДЕН! Недостаточный рост не вызывает RESET, дубль блокируется")
        sys.exit(0)
    else:
        print("❌ ТЕСТ ПРОВАЛЕН! Проверьте логи выше")
        sys.exit(1)
