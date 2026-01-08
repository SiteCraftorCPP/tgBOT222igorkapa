#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Комплексный тест отправки сигналов в Telegram канал с проверкой защиты от дублей
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


def test_signals_with_duplicate_protection():
    """Тест отправки сигналов в канал с проверкой защиты от дублей"""
    print("\n" + "="*60)
    print("ТЕСТ: Отправка сигналов в Telegram канал + защита от дублей")
    print("="*60)
    
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
        
        test_pair = "TESTEUR"
        test_local_max = 1000.0
        current_time = time.time()
        
        print(f"\nТестовая пара: {test_pair}")
        print(f"Local max: {test_local_max}")
        print(f"Chat ID: {TELEGRAM_CHAT_ID}")
        print()
        
        # Инициализируем состояние
        state_manager.update_state(
            test_pair,
            local_max=test_local_max,
            local_max_time=current_time - 100,
            local_min=None,
            triggered_levels=[],
            last_price=test_local_max,
            initialized=True,
            initialization_time=current_time - 1000
        )
        
        # ===== ЦИКЛ 1: Отправка Level 1 =====
        print("="*60)
        print("ЦИКЛ 1: Отправка Level 1 (-8%)")
        print("="*60)
        
        price_level1 = test_local_max * 0.92  # Падение -8%
        state = state_manager.get_state(test_pair)
        
        signal1 = market_monitor.check_levels(
            test_pair,
            price_level1,
            test_local_max,
            state.get("triggered_levels", [])
        )
        
        if signal1:
            print(f"✅ Сигнал Level {signal1['level']} создан (падение: {signal1['drop_percent']:.2f}%)")
            
            # Финальная проверка перед отправкой (как в bot.py)
            final_check = state_manager.get_state(test_pair)
            if signal1['level'] in final_check.get("triggered_levels", []):
                print(f"❌ Level {signal1['level']} уже в triggered_levels - не отправляем")
                return False
            
            # Отправляем сигнал в Telegram
            signals_to_send = [{
                "pair": test_pair,
                "drop_percent": signal1['drop_percent'],
                "level": signal1['level'],
                "current_price": price_level1
            }]
            
            print(f"Отправка сигнала в Telegram канал...")
            send_result = telegram_sender.send_signals_batch(signals_to_send)
            
            if send_result:
                print(f"✅ Сигнал Level {signal1['level']} отправлен в канал!")
                # Сохраняем уровень после отправки
                state_manager.add_triggered_level(test_pair, signal1['level'], current_time)
                print(f"   Level {signal1['level']} добавлен в triggered_levels")
            else:
                print(f"❌ Ошибка отправки сигнала")
                return False
        else:
            print(f"❌ Сигнал не создан")
            return False
        
        # ===== ЦИКЛ 2: Попытка отправить тот же Level 1 (дубль) =====
        print("\n" + "="*60)
        print("ЦИКЛ 2: Попытка отправить Level 1 повторно (ДУБЛЬ)")
        print("="*60)
        
        time.sleep(2)  # Небольшая задержка между циклами
        current_time_cycle2 = time.time()
        
        state_cycle2 = state_manager.get_state(test_pair)
        triggered_levels_cycle2 = state_cycle2.get("triggered_levels", [])
        
        print(f"triggered_levels = {triggered_levels_cycle2}")
        
        # Проверяем, создастся ли сигнал
        signal2 = market_monitor.check_levels(
            test_pair,
            price_level1,  # Та же цена
            test_local_max,
            triggered_levels_cycle2
        )
        
        if signal2:
            print(f"❌ ОШИБКА! Сигнал Level {signal2['level']} создан повторно!")
            print(f"   Защита от дублей НЕ РАБОТАЕТ!")
            return False
        else:
            print(f"✅ Сигнал НЕ создан - защита от дублей работает!")
            print(f"   Level 1 уже в triggered_levels, повторный сигнал заблокирован")
        
        # ===== ЦИКЛ 3: Отправка Level 2 (новый уровень) =====
        print("\n" + "="*60)
        print("ЦИКЛ 3: Отправка Level 2 (-12%) - новый уровень")
        print("="*60)
        
        time.sleep(2)
        current_time_cycle3 = time.time()
        price_level2 = test_local_max * 0.88  # Падение -12%
        
        state_cycle3 = state_manager.get_state(test_pair)
        triggered_levels_cycle3 = state_cycle3.get("triggered_levels", [])
        
        print(f"triggered_levels = {triggered_levels_cycle3}")
        print(f"Цена: {price_level2:.2f} (падение: -12%)")
        
        signal3 = market_monitor.check_levels(
            test_pair,
            price_level2,
            test_local_max,
            triggered_levels_cycle3
        )
        
        if signal3:
            print(f"✅ Сигнал Level {signal3['level']} создан (падение: {signal3['drop_percent']:.2f}%)")
            
            # Финальная проверка
            final_check3 = state_manager.get_state(test_pair)
            if signal3['level'] in final_check3.get("triggered_levels", []):
                print(f"❌ Level {signal3['level']} уже в triggered_levels - не отправляем")
                return False
            
            # Отправляем в Telegram
            signals_to_send3 = [{
                "pair": test_pair,
                "drop_percent": signal3['drop_percent'],
                "level": signal3['level'],
                "current_price": price_level2
            }]
            
            print(f"Отправка сигнала в Telegram канал...")
            send_result3 = telegram_sender.send_signals_batch(signals_to_send3)
            
            if send_result3:
                print(f"✅ Сигнал Level {signal3['level']} отправлен в канал!")
                state_manager.add_triggered_level(test_pair, signal3['level'], current_time_cycle3)
                print(f"   Level {signal3['level']} добавлен в triggered_levels")
            else:
                print(f"❌ Ошибка отправки сигнала")
                return False
        else:
            print(f"❌ Сигнал не создан (неожиданно - новый уровень должен пройти)")
            return False
        
        # ===== ЦИКЛ 4: Попытка отправить Level 2 повторно (дубль) =====
        print("\n" + "="*60)
        print("ЦИКЛ 4: Попытка отправить Level 2 повторно (ДУБЛЬ)")
        print("="*60)
        
        time.sleep(2)
        
        state_cycle4 = state_manager.get_state(test_pair)
        triggered_levels_cycle4 = state_cycle4.get("triggered_levels", [])
        
        print(f"triggered_levels = {triggered_levels_cycle4}")
        
        signal4 = market_monitor.check_levels(
            test_pair,
            price_level2,  # Та же цена
            test_local_max,
            triggered_levels_cycle4
        )
        
        if signal4:
            print(f"❌ ОШИБКА! Сигнал Level {signal4['level']} создан повторно!")
            return False
        else:
            print(f"✅ Сигнал НЕ создан - защита от дублей работает!")
            print(f"   Level 2 уже в triggered_levels, повторный сигнал заблокирован")
        
        # ===== ЦИКЛ 5: Отправка нескольких сигналов в одном цикле =====
        print("\n" + "="*60)
        print("ЦИКЛ 5: Отправка нескольких сигналов (Level 3, 4, 5)")
        print("="*60)
        
        time.sleep(2)
        current_time_cycle5 = time.time()
        
        # Симулируем глубокое падение - должны сработать Level 3, 4, 5
        price_level5 = test_local_max * 0.75  # Падение -25% (пройдёт все уровни)
        
        state_cycle5 = state_manager.get_state(test_pair)
        triggered_levels_cycle5 = state_cycle5.get("triggered_levels", [])
        
        print(f"triggered_levels = {triggered_levels_cycle5}")
        print(f"Цена: {price_level5:.2f} (падение: -25%)")
        
        # Проверяем уровни по порядку (как в реальном боте)
        signals_batch = []
        current_triggered = triggered_levels_cycle5.copy()
        
        # Проверяем Level 3
        signal_l3 = market_monitor.check_levels(
            test_pair,
            price_level5,
            test_local_max,
            current_triggered
        )
        if signal_l3:
            signals_batch.append({
                "pair": test_pair,
                "drop_percent": signal_l3['drop_percent'],
                "level": signal_l3['level'],
                "current_price": price_level5
            })
            current_triggered.append(signal_l3['level'])
            print(f"✅ Level {signal_l3['level']} добавлен в батч")
        
        # Но в реальном боте check_levels возвращает только первый достигнутый уровень
        # Поэтому проверим, что Level 3 сработал
        
        if signals_batch:
            print(f"\nОтправка {len(signals_batch)} сигнала(ов) в Telegram канал...")
            send_result5 = telegram_sender.send_signals_batch(signals_batch)
            
            if send_result5:
                print(f"✅ Сигнал(ы) отправлены в канал!")
                for sig in signals_batch:
                    state_manager.add_triggered_level(test_pair, sig['level'], current_time_cycle5)
                    print(f"   Level {sig['level']} добавлен в triggered_levels")
            else:
                print(f"❌ Ошибка отправки")
                return False
        else:
            print(f"⚠️  Сигнал не создан (возможно, все уровни уже сработали)")
        
        # Итоги
        print("\n" + "="*60)
        print("ИТОГИ ТЕСТА")
        print("="*60)
        final_state = state_manager.get_state(test_pair)
        print(f"Финальное состояние для {test_pair}:")
        print(f"  triggered_levels: {final_state.get('triggered_levels', [])}")
        print(f"  local_max: {final_state.get('local_max')}")
        print()
        print("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
        print("   - Level 1 отправлен и заблокирован от дублей")
        print("   - Level 2 отправлен и заблокирован от дублей")
        print("   - Сигналы реально отправляются в Telegram канал")
        print("   - Защита от дублей работает корректно")
        
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
    print("\n" + "="*60)
    print("КОМПЛЕКСНЫЙ ТЕСТ: Отправка сигналов в Telegram + защита от дублей")
    print("="*60)
    print(f"⚠️  ВНИМАНИЕ: Этот тест отправит реальные сообщения в канал!")
    print(f"   Chat ID: {TELEGRAM_CHAT_ID}")
    print(f"   Нажмите Ctrl+C для отмены или подождите 5 секунд...")
    
    try:
        time.sleep(5)
    except KeyboardInterrupt:
        print("\n❌ Тест отменён пользователем")
        sys.exit(1)
    
    result = test_signals_with_duplicate_protection()
    
    print("\n" + "="*60)
    print("ФИНАЛЬНЫЙ РЕЗУЛЬТАТ")
    print("="*60)
    if result:
        print("✅ ТЕСТ ПРОЙДЕН! Сигналы отправляются в канал, дубли блокируются")
        sys.exit(0)
    else:
        print("❌ ТЕСТ ПРОВАЛЕН! Проверьте логи выше")
        sys.exit(1)
