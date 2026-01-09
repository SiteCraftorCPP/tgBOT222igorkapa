#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест проверяет логику RESET:
- После первого сигнала рост от минимума должен вызвать RESET
- После RESET новый сигнал должен пройти (это новая сессия, не дубль)
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


def test_reset_logic():
    """Тест логики RESET: проверка что рост от минимума вызывает RESET и новый сигнал проходит"""
    print("\n" + "="*80)
    print("ТЕСТ: Логика RESET - проверка что сигнал после RESET проходит")
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
        
        test_pair = "TESTRESETEUR"
        initial_max = 0.0110  # Начальный максимум
        
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
        print("ЭТАП 1: Первый сигнал -11.8% (Level 2)")
        print("="*80)
        
        # Цена падает до -11.8% от максимума
        price_signal1 = 0.0097  # -11.8% от 0.0110
        drop_percent1 = ((price_signal1 - initial_max) / initial_max) * 100
        print(f"Цена: {price_signal1} (падение: {drop_percent1:.2f}%)")
        print(f"Ожидаемый уровень: Level 2 (-12%)")
        
        state1 = state_manager.get_state(test_pair)
        triggered1 = state1.get("triggered_levels", [])
        print(f"triggered_levels до сигнала: {triggered1}")
        
        # Проверяем уровни
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
        
        # Сохраняем уровень СРАЗУ
        state_manager.add_triggered_level(test_pair, level1, current_time)
        print(f"  ✅ Level {level1} сохранён в triggered_levels")
        
        # Обновляем local_min (как в реальном боте)
        state_manager.update_state(test_pair, local_min=price_signal1)
        print(f"  ✅ local_min обновлён: {price_signal1}")
        
        # Проверяем состояние после первого сигнала
        state_after_signal1 = state_manager.get_state(test_pair)
        print(f"\nСостояние после первого сигнала:")
        print(f"  local_max: {state_after_signal1.get('local_max')}")
        print(f"  local_min: {state_after_signal1.get('local_min')}")
        print(f"  triggered_levels: {state_after_signal1.get('triggered_levels')}")
        print(f"  Максимальное падение: {((state_after_signal1.get('local_min') - state_after_signal1.get('local_max')) / state_after_signal1.get('local_max') * 100):.2f}%")
        
        # ===== ЭТАП 2: Рост от минимума на нужный процент для RESET =====
        print("\n" + "="*80)
        print("ЭТАП 2: Рост от минимума для RESET")
        print("="*80)
        
        # Для падения -11.8% нужно +4% для RESET
        local_min = state_after_signal1.get('local_min')
        max_drop = ((local_min - initial_max) / initial_max) * 100
        print(f"Максимальное падение: {max_drop:.2f}%")
        
        # Вычисляем нужный процент для RESET
        reset_percent = state_manager.get_reset_percent_for_drop(max_drop)
        print(f"Требуемый рост от минимума для RESET: +{reset_percent}%")
        
        # Цена растёт от минимума на нужный процент
        price_reset = local_min * (1 + reset_percent / 100)
        growth_from_min = ((price_reset - local_min) / local_min) * 100
        print(f"Цена после роста: {price_reset:.6f}")
        print(f"Фактический рост от минимума: {growth_from_min:.2f}%")
        
        # Проверяем should_reset
        print(f"\nПроверка should_reset()...")
        should_reset_result = state_manager.should_reset(test_pair, price_reset, current_time + 100)
        
        if not should_reset_result:
            print(f"  ❌ should_reset() вернул False - RESET НЕ произойдёт!")
            print(f"     Но рост {growth_from_min:.2f}% >= требуемый {reset_percent}%")
            return False
        
        print(f"  ✅ should_reset() вернул True - RESET произойдёт!")
        
        # Выполняем RESET
        print(f"\nВыполнение RESET...")
        state_manager.reset_state(test_pair, price_reset)
        
        state_after_reset = state_manager.get_state(test_pair)
        print(f"\nСостояние после RESET:")
        print(f"  local_max: {state_after_reset.get('local_max')} (новый максимум = цена после роста)")
        print(f"  local_min: {state_after_reset.get('local_min')} (новый минимум = новый максимум)")
        print(f"  triggered_levels: {state_after_reset.get('triggered_levels')} (обнулены)")
        print(f"  last_signal_time: {state_after_reset.get('last_signal_time')}")
        
        if state_after_reset.get('triggered_levels') != []:
            print(f"  ❌ triggered_levels НЕ обнулены после RESET!")
            return False
        
        print(f"  ✅ triggered_levels обнулены - RESET выполнен корректно!")
        
        # ===== ЭТАП 3: Новый сигнал -8.1% после RESET (должен пройти) =====
        print("\n" + "="*80)
        print("ЭТАП 3: Новый сигнал -8.1% после RESET (должен пройти как новая сессия)")
        print("="*80)
        
        new_max = state_after_reset.get('local_max')  # Новый максимум после RESET
        price_signal2 = new_max * 0.919  # -8.1% от нового максимума
        drop_percent2 = ((price_signal2 - new_max) / new_max) * 100
        print(f"Новый максимум: {new_max:.6f}")
        print(f"Новая цена: {price_signal2:.6f} (падение: {drop_percent2:.2f}%)")
        print(f"Ожидаемый уровень: Level 1 (-8%)")
        
        state_before_signal2 = state_manager.get_state(test_pair)
        triggered2 = state_before_signal2.get("triggered_levels", [])
        print(f"triggered_levels до нового сигнала: {triggered2}")
        
        if triggered2 != []:
            print(f"  ❌ triggered_levels не пусты после RESET!")
            return False
        
        # Проверяем уровни
        signal2 = market_monitor.check_levels(
            test_pair,
            price_signal2,
            new_max,
            triggered2
        )
        
        if not signal2:
            print(f"  ❌ Сигнал НЕ создан после RESET!")
            print(f"     Это означает, что новый сигнал заблокирован (неправильно!)")
            return False
        
        level2 = signal2['level']
        if level2 != 1:
            print(f"  ⚠️  Создан Level {level2} вместо Level 1 (но продолжим)")
        
        print(f"  ✅ Сигнал Level {level2} создан (падение: {signal2['drop_percent']:.2f}%)")
        print(f"     Это НЕ дубль - это новая сессия после RESET!")
        
        # Проверяем что это не дубль через is_duplicate_signal
        is_dup = state_manager.is_duplicate_signal(test_pair, level2, current_time + 200)
        if is_dup:
            print(f"  ❌ is_duplicate_signal() вернул True - сигнал заблокирован как дубль!")
            print(f"     Но это НЕ дубль - это новая сессия после RESET!")
            return False
        
        print(f"  ✅ is_duplicate_signal() вернул False - сигнал НЕ дубль, проходит!")
        
        # Итоги
        print("\n" + "="*80)
        print("ИТОГИ ТЕСТА")
        print("="*80)
        print("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
        print(f"   - Первый сигнал -11.8% (Level {level1}) отправлен")
        print(f"   - Рост от минимума на {growth_from_min:.2f}% вызвал RESET")
        print(f"   - triggered_levels обнулены после RESET")
        print(f"   - Новый сигнал -8.1% (Level {level2}) проходит как новая сессия")
        print(f"   - Логика RESET работает корректно!")
        
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
    print("ТЕСТ: Логика RESET")
    print("="*80)
    print("Проверка что после RESET новый сигнал проходит (не блокируется как дубль)")
    
    result = test_reset_logic()
    
    print("\n" + "="*80)
    print("ФИНАЛЬНЫЙ РЕЗУЛЬТАТ")
    print("="*80)
    if result:
        print("✅ ТЕСТ ПРОЙДЕН! Логика RESET работает корректно")
        print("   Сигнал после RESET проходит как новая сессия")
        sys.exit(0)
    else:
        print("❌ ТЕСТ ПРОВАЛЕН! Проверьте логи выше")
        print("   Возможно, логика RESET работает неправильно")
        sys.exit(1)
