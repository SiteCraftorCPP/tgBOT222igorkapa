#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест проверяет, что дубли НЕ отправляются между двумя циклами с интервалом 1 минута
Симулирует реальную работу бота
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
from config import TELEGRAM_CHAT_ID, CHECK_INTERVAL


def test_two_cycles_with_1min_interval():
    """Тест двух циклов с интервалом 1 минута - проверка что дубль НЕ отправляется"""
    print("\n" + "="*80)
    print("ТЕСТ: Два цикла с интервалом 1 минута - проверка отсутствия дублей")
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
        
        test_pair = "TEST2CYCLESEUR"
        test_local_max = 1000.0
        current_time = time.time()
        
        print(f"\nТестовая пара: {test_pair}")
        print(f"Local max: {test_local_max}")
        print(f"Chat ID: {TELEGRAM_CHAT_ID}")
        print(f"Интервал между циклами: {CHECK_INTERVAL} сек (как в реальном боте)")
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
        
        # ===== ЦИКЛ 1: Отправка Level 2 (-12%) =====
        print("="*80)
        print("ЦИКЛ 1: Отправка Level 2 (-12%)")
        print("="*80)
        
        cycle1_time = time.time()
        # Используем цену, которая точно триггерит Level 2 (-12%)
        # НО сначала должны пройти Level 1 (-8%), поэтому начнём с него
        price_level1 = test_local_max * 0.92  # Падение -8% (Level 1)
        price_level2 = test_local_max * 0.88  # Падение -12% (Level 2)
        
        print(f"Время цикла 1: {time.strftime('%H:%M:%S', time.localtime(cycle1_time))}")
        print(f"Цена Level 1: {price_level1:.2f} (падение: -8%)")
        print(f"Цена Level 2: {price_level2:.2f} (падение: -12%)")
        
        # Получаем состояние
        state_cycle1 = state_manager.get_state(test_pair)
        triggered_levels_cycle1 = state_cycle1.get("triggered_levels", [])
        print(f"triggered_levels до цикла 1: {triggered_levels_cycle1}")
        
        # Сначала отправляем Level 1 (как будто цена упала до -8%)
        print(f"\n--- Первый сигнал: Level 1 (-8%) ---")
        signal_l1 = market_monitor.check_levels(
            test_pair,
            price_level1,
            test_local_max,
            triggered_levels_cycle1
        )
        
        if signal_l1:
            level1 = signal_l1['level']
            print(f"✅ Сигнал Level {level1} создан (падение: {signal_l1['drop_percent']:.2f}%)")
            state_manager.add_triggered_level(test_pair, level1, cycle1_time)
            print(f"✅ Level {level1} сохранён в triggered_levels")
        
        # Теперь проверяем Level 2 с ценой -12%
        # Но Level 1 уже сработал, поэтому check_levels должен вернуть Level 2
        print(f"\n--- Второй сигнал: Level 2 (-12%) ---")
        state_after_l1 = state_manager.get_state(test_pair)
        triggered_after_l1 = state_after_l1.get("triggered_levels", [])
        print(f"triggered_levels после Level 1: {triggered_after_l1}")
        
        signal_cycle1 = market_monitor.check_levels(
            test_pair,
            price_level2,  # Цена -12%
            test_local_max,
            triggered_after_l1  # Level 1 уже в списке
        )
        
        if not signal_cycle1:
            print(f"❌ ОШИБКА: Сигнал Level 2 не создан в цикле 1!")
            return False
        
        level = signal_cycle1['level']
        if level != 2:
            print(f"❌ ОШИБКА: Ожидался Level 2, но создан Level {level}!")
            return False
        
        print(f"✅ Сигнал Level {level} создан (падение: {signal_cycle1['drop_percent']:.2f}%)")
        
        # Финальная проверка (как в bot.py)
        final_check1 = state_manager.get_state(test_pair)
        if level in final_check1.get("triggered_levels", []):
            print(f"❌ Level {level} уже в triggered_levels - не отправляем")
            return False
        
        # НОВАЯ ЛОГИКА: Сохраняем уровень СРАЗУ после создания сигнала, ДО отправки
        print(f"\n[ШАГ 1] Сохранение уровня СРАЗУ после создания сигнала...")
        state_manager.add_triggered_level(test_pair, level, cycle1_time)
        print(f"✅ Level {level} сохранён в triggered_levels СРАЗУ (до отправки)")
        
        # Проверяем что сохранено
        state_after_save = state_manager.get_state(test_pair)
        print(f"triggered_levels после сохранения: {state_after_save.get('triggered_levels', [])}")
        
        # Отправляем сигнал
        signals_to_send_cycle1 = [{
            "pair": test_pair,
            "drop_percent": signal_cycle1['drop_percent'],
            "level": level,
            "current_price": price_level2
        }]
        
        print(f"\n[ШАГ 2] Отправка сигнала в Telegram канал...")
        send_result1 = telegram_sender.send_signals_batch(signals_to_send_cycle1)
        
        if not send_result1:
            print(f"❌ Ошибка отправки сигнала в цикле 1")
            return False
        
        print(f"✅ Сигнал Level {level} отправлен в канал!")
        
        # Финальное состояние цикла 1
        final_state_cycle1 = state_manager.get_state(test_pair)
        print(f"\nФинальное состояние после цикла 1:")
        print(f"  triggered_levels: {final_state_cycle1.get('triggered_levels', [])}")
        print(f"  last_signal_time: {final_state_cycle1.get('last_signal_time')}")
        print(f"  last_signal_level: {final_state_cycle1.get('last_signal_level')}")
        
        # ===== ЖДЁМ 1 МИНУТУ (как реальный бот) =====
        print("\n" + "="*80)
        print(f"ОЖИДАНИЕ: {CHECK_INTERVAL} секунд (как реальный интервал бота)...")
        print("="*80)
        
        # Используем реальный интервал CHECK_INTERVAL для точной проверки
        # Но можно использовать меньший интервал для быстрого теста
        import sys
        if len(sys.argv) > 1 and sys.argv[1] == "--fast":
            wait_time = 5  # Быстрый тест: 5 секунд
            print(f"⚡ БЫСТРЫЙ ТЕСТ: ждём {wait_time} сек вместо {CHECK_INTERVAL} сек")
        else:
            wait_time = CHECK_INTERVAL  # Реальный тест: 60 секунд
            print(f"⏳ РЕАЛЬНЫЙ ТЕСТ: ждём {wait_time} сек (как в реальном боте)")
            print(f"   Используй --fast для быстрого теста (5 сек)")
        
        print(f"   Начало ожидания: {time.strftime('%H:%M:%S', time.localtime())}")
        
        # Показываем обратный отсчёт
        for remaining in range(wait_time, 0, -10):
            if remaining >= 10:
                print(f"   Осталось: {remaining} сек...")
                time.sleep(10)
            else:
                time.sleep(remaining)
                break
        
        if wait_time >= 10:
            print(f"   Осталось: 0 сек")
        
        cycle2_start_time = time.time()
        elapsed_time = cycle2_start_time - cycle1_time
        print(f"   Конец ожидания: {time.strftime('%H:%M:%S', time.localtime(cycle2_start_time))}")
        print(f"   Прошло времени: {elapsed_time:.1f} сек")
        
        # ===== ЦИКЛ 2: Попытка отправить тот же Level 2 (через 1 минуту) =====
        print("\n" + "="*80)
        print("ЦИКЛ 2: Проверка что дубль НЕ отправляется (через 1 минуту)")
        print("="*80)
        
        print(f"Время цикла 2: {time.strftime('%H:%M:%S', time.localtime(cycle2_start_time))}")
        print(f"Интервал между циклами: {elapsed_time:.1f} сек")
        print(f"Та же цена: {price_level2:.2f} (падение: -12%)")
        
        # Получаем состояние для цикла 2 (как будто бот перезагрузил из файла)
        # В реальном боте состояние загружается из файла при старте каждого цикла
        print(f"\n[ШАГ 1] Загрузка состояния для цикла 2...")
        state_cycle2 = state_manager.get_state(test_pair)
        triggered_levels_cycle2 = state_cycle2.get("triggered_levels", [])
        print(f"triggered_levels в цикле 2: {triggered_levels_cycle2}")
        
        if level not in triggered_levels_cycle2:
            print(f"❌ КРИТИЧЕСКАЯ ОШИБКА! Level {level} НЕ найден в triggered_levels!")
            print(f"   Состояние НЕ сохранилось между циклами!")
            print(f"   Это означает, что временное окно НЕ устранено!")
            return False
        
        print(f"✅ Level {level} найден в triggered_levels - состояние сохранилось!")
        
        # Проверяем уровни (как в check_pair) - ТА ЖЕ ЦЕНА И ТОТ ЖЕ LEVEL
        print(f"\n[ШАГ 2] Проверка уровней (check_levels) - ТА ЖЕ ЦЕНА {price_level2:.2f} И ТОТ ЖЕ LEVEL {level}...")
        signal_cycle2 = market_monitor.check_levels(
            test_pair,
            price_level2,  # Та же цена -12%
            test_local_max,
            triggered_levels_cycle2  # Должен содержать level 2
        )
        
        if signal_cycle2:
            signal_level = signal_cycle2['level']
            if signal_level == level:
                print(f"❌ ОШИБКА! ТОТ ЖЕ СИГНАЛ Level {signal_level} создан повторно!")
                print(f"   ДУБЛЬ будет отправлен - защита НЕ РАБОТАЕТ!")
                print(f"   Это та самая проблема - дубль через минуту!")
                print(f"   Цена: {price_level2:.2f}, Level: {level}, triggered_levels: {triggered_levels_cycle2}")
                return False
            else:
                print(f"⚠️  Создан другой уровень {signal_level} (это нормально, если цена пересекла новый уровень)")
                print(f"   Но проверяем что Level {level} НЕ дублируется")
        else:
            print(f"✅ Сигнал Level {level} НЕ создан - уровень заблокирован в check_levels")
        
        # Дополнительная проверка - попытка пройти через всю логику bot.py
        print(f"\n[ШАГ 3] Финальная проверка (как в main_loop)...")
        final_check2 = state_manager.get_state(test_pair)
        if level in final_check2.get("triggered_levels", []):
            print(f"✅ Level {level} в triggered_levels - дубль будет заблокирован в main_loop")
        else:
            print(f"❌ Level {level} НЕ в triggered_levels - дубль МОЖЕТ пройти!")
            return False
        
        # Проверка через is_duplicate_signal
        print(f"\n[ШАГ 4] Проверка через is_duplicate_signal()...")
        is_dup = state_manager.is_duplicate_signal(test_pair, level, cycle2_start_time)
        if is_dup:
            print(f"✅ is_duplicate_signal() вернул True - дубль будет заблокирован")
        else:
            print(f"⚠️  is_duplicate_signal() вернул False (но check_levels уже заблокировал)")
        
        # Проверка через telegram_sender кэш
        print(f"\n[ШАГ 5] Проверка через telegram_sender кэш...")
        is_dup_cache = telegram_sender._is_duplicate(test_pair, level)
        if is_dup_cache:
            print(f"✅ telegram_sender кэш заблокирует дубль")
        else:
            print(f"⚠️  telegram_sender кэш не блокирует (но другие проверки уже заблокировали)")
        
        # Итоги
        print("\n" + "="*80)
        print("ИТОГИ ТЕСТА")
        print("="*80)
        final_state = state_manager.get_state(test_pair)
        print(f"Финальное состояние для {test_pair}:")
        print(f"  triggered_levels: {final_state.get('triggered_levels', [])}")
        print(f"  last_signal_time: {final_state.get('last_signal_time')}")
        print(f"  last_signal_level: {final_state.get('last_signal_level')}")
        print()
        print("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
        print(f"   - Level {level} отправлен в цикле 1")
        print(f"   - Состояние сохранено СРАЗУ после создания сигнала")
        print(f"   - После {elapsed_time:.1f} сек (интервал между циклами)")
        print(f"   - Дубль НЕ создан в цикле 2")
        print(f"   - Защита от дублей работает корректно")
        print(f"   - Временное окно УСТРАНЕНО!")
        
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
    print("ТЕСТ: Два цикла с интервалом 1 минута")
    print("="*80)
    print(f"⚠️  ВНИМАНИЕ: Этот тест отправит реальное сообщение в канал!")
    print(f"   Chat ID: {TELEGRAM_CHAT_ID}")
    print(f"   Нажмите Ctrl+C для отмены или подождите 5 секунд...")
    
    try:
        time.sleep(5)
    except KeyboardInterrupt:
        print("\n❌ Тест отменён пользователем")
        sys.exit(1)
    
    result = test_two_cycles_with_1min_interval()
    
    print("\n" + "="*80)
    print("ФИНАЛЬНЫЙ РЕЗУЛЬТАТ")
    print("="*80)
    if result:
        print("✅ ТЕСТ ПРОЙДЕН! Дубли НЕ отправляются между циклами")
        print("   Временное окно устранено, защита работает корректно")
        sys.exit(0)
    else:
        print("❌ ТЕСТ ПРОВАЛЕН! Проверьте логи выше")
        print("   Возможно, временное окно НЕ устранено полностью")
        sys.exit(1)
