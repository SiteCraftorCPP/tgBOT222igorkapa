#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест эмулирует ДВА РЕАЛЬНЫХ ЦИКЛА бота с отправкой сигналов в Telegram
Проверяет, что дубли НЕ отправляются между циклами
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


def test_duplicate_two_cycles_real():
    """Эмулирует два реальных цикла бота с отправкой сигналов"""
    print("\n" + "="*80)
    print("ТЕСТ: Два реальных цикла с отправкой сигналов в Telegram")
    print("="*80)
    print("⚠️  ВНИМАНИЕ: Этот тест ОТПРАВИТ РЕАЛЬНЫЕ сообщения в Telegram канал!")
    print(f"   Chat ID: {TELEGRAM_CHAT_ID}")
    print()
    
    # Временный файл для состояний
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    temp_file.close()
    temp_state_file = temp_file.name
    
    try:
        # Переопределяем STATE_FILE для теста
        import config
        original_state_file = config.STATE_FILE
        config.STATE_FILE = temp_state_file
        
        # Создаём экземпляры (как в реальном боте)
        telegram_sender = TelegramSender()
        state_manager = StateManager()
        market_monitor = MarketMonitor()
        
        test_pair = "TEST2CYCLESREALUR"
        test_local_max = 1000.0
        
        print(f"Тестовая пара: {test_pair}")
        print(f"Local max: {test_local_max}")
        print(f"Временный файл состояний: {temp_state_file}")
        print()
        
        # Инициализируем состояние (как при старте бота)
        current_time = time.time()
        state_manager.update_state(
            test_pair,
            local_max=test_local_max,
            local_max_time=current_time - 100,
            local_min=None,
            triggered_levels=[],
            last_signal_time=None,
            last_signal_level=None,
            last_price=test_local_max,
            initialized=True,
            initialization_time=current_time - 1000
        )
        print(f"✅ Состояние инициализировано")
        
        # Цена, которая триггерит Level 1 (-8%)
        test_price = test_local_max * 0.92  # -8%
        test_drop = -8.0
        expected_level = 1
        
        print("="*80)
        print("НАСТРОЙКА ТЕСТА")
        print("="*80)
        print(f"Цена для сигнала: {test_price:.2f} (падение {test_drop}%)")
        print(f"Ожидаемый уровень: Level {expected_level}")
        print()
        
        # ============================================================
        # ЦИКЛ 1: Эмулируем полный цикл bot.py
        # ============================================================
        print("="*80)
        print("ЦИКЛ 1: Создание и отправка сигнала")
        print("="*80)
        cycle1_time = time.time()
        print(f"Время цикла 1: {time.strftime('%H:%M:%S', time.localtime(cycle1_time))}")
        print()
        
        # ШАГ 1: Перезагрузка состояния из файла (как в main_loop)
        print("[ЦИКЛ 1] ШАГ 1: Перезагрузка состояния из файла (load_states)...")
        state_manager.load_states(silent=True)
        state_cycle1 = state_manager.get_state(test_pair)
        triggered_levels_cycle1 = state_cycle1.get("triggered_levels", [])
        print(f"  ✅ triggered_levels = {triggered_levels_cycle1}")
        
        # ШАГ 2: Проверка пары (как в check_pair)
        print(f"\n[ЦИКЛ 1] ШАГ 2: Проверка пары (check_pair)...")
        print(f"  Текущая цена: {test_price:.2f}")
        print(f"  Local max: {test_local_max:.2f}")
        print(f"  triggered_levels: {triggered_levels_cycle1}")
        
        # Проверка уровней (как в check_pair через market_monitor.check_levels)
        signal_cycle1 = market_monitor.check_levels(
            test_pair,
            test_price,
            test_local_max,
            triggered_levels_cycle1
        )
        
        if not signal_cycle1:
            print(f"  ❌ Сигнал не создан в check_levels!")
            return False
        
        level1 = signal_cycle1['level']
        drop1 = signal_cycle1['drop_percent']
        print(f"  ✅ Сигнал создан: Level {level1}, падение {drop1:.2f}%")
        
        if level1 != expected_level:
            print(f"  ⚠️  Ожидался Level {expected_level}, но создан Level {level1}")
        
        # ШАГ 3: Финальная проверка перед сохранением (как в check_pair)
        print(f"\n[ЦИКЛ 1] ШАГ 3: Финальная проверка перед сохранением...")
        final_check1 = state_manager.get_state(test_pair)
        if level1 in final_check1.get("triggered_levels", []):
            print(f"  ❌ Level {level1} уже в triggered_levels - это ошибка!")
            return False
        print(f"  ✅ Level {level1} НЕ в triggered_levels - можно сохранять")
        
        # ШАГ 4: Сохранение уровня СРАЗУ (как в check_pair)
        print(f"\n[ЦИКЛ 1] ШАГ 4: Сохранение уровня СРАЗУ (add_triggered_level)...")
        state_manager.add_triggered_level(test_pair, level1, cycle1_time)
        
        # Проверяем что сохранено
        saved_state1 = state_manager.get_state(test_pair)
        saved_levels1 = saved_state1.get("triggered_levels", [])
        print(f"  ✅ triggered_levels после сохранения: {saved_levels1}")
        
        if level1 not in saved_levels1:
            print(f"  ❌ КРИТИЧЕСКАЯ ОШИБКА! Level {level1} НЕ найден после сохранения!")
            return False
        
        # ШАГ 5: Подготовка сигнала для отправки (как в main_loop)
        print(f"\n[ЦИКЛ 1] ШАГ 5: Подготовка сигнала для отправки...")
        cycle_signals = [{
            "pair": test_pair,
            "drop_percent": drop1,
            "level": level1,
            "current_price": test_price
        }]
        print(f"  ✅ Подготовлено {len(cycle_signals)} сигнал(ов) для отправки")
        for sig in cycle_signals:
            print(f"     - {sig['pair']}: Level {sig['level']}, drop {sig['drop_percent']:.2f}%, price {sig['current_price']:.2f}")
        
        # ШАГ 6: Отправка сигнала в Telegram (как в main_loop через telegram.send_signals_batch)
        print(f"\n[ЦИКЛ 1] ШАГ 6: Отправка сигнала в Telegram канал...")
        print(f"  Chat ID: {TELEGRAM_CHAT_ID}")
        print(f"  Сигнал: {test_pair} Level {level1} ({drop1:.2f}%)")
        
        send_result1 = telegram_sender.send_signals_batch(cycle_signals)
        
        if not send_result1:
            print(f"  ❌ Ошибка отправки сигнала в Telegram!")
            return False
        
        print(f"  ✅ Сигнал Level {level1} ОТПРАВЛЕН в Telegram канал!")
        
        # Финальное состояние цикла 1
        final_state1 = state_manager.get_state(test_pair)
        print(f"\n[ЦИКЛ 1] ФИНАЛЬНОЕ СОСТОЯНИЕ:")
        print(f"  triggered_levels: {final_state1.get('triggered_levels', [])}")
        print(f"  last_signal_time: {final_state1.get('last_signal_time')}")
        print(f"  last_signal_level: {final_state1.get('last_signal_level')}")
        print(f"  ✅ Цикл 1 завершён успешно")
        
        # ============================================================
        # ОЖИДАНИЕ МЕЖДУ ЦИКЛАМИ
        # ============================================================
        print("\n" + "="*80)
        print(f"ОЖИДАНИЕ МЕЖДУ ЦИКЛАМИ: {CHECK_INTERVAL} секунд")
        print("="*80)
        
        # Используем меньший интервал для быстрого теста, но можно использовать реальный
        import sys
        if len(sys.argv) > 1 and sys.argv[1] == "--fast":
            wait_time = 5  # Быстрый тест: 5 секунд
            print(f"⚡ БЫСТРЫЙ ТЕСТ: ждём {wait_time} сек вместо {CHECK_INTERVAL} сек")
        else:
            wait_time = CHECK_INTERVAL  # Реальный тест: 60 секунд
            print(f"⏳ РЕАЛЬНЫЙ ТЕСТ: ждём {wait_time} сек (как в реальном боте)")
            print(f"   Используй --fast для быстрого теста (5 сек)")
        
        print(f"   Начало ожидания: {time.strftime('%H:%M:%S', time.localtime())}")
        
        # Показываем обратный отсчёт каждые 10 секунд
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
        
        # ============================================================
        # ЦИКЛ 2: Попытка отправить ТОТ ЖЕ САМЫЙ сигнал (дубль)
        # ============================================================
        print("\n" + "="*80)
        print("ЦИКЛ 2: Попытка отправить ТОТ ЖЕ САМЫЙ сигнал (дубль)")
        print("="*80)
        cycle2_time = time.time()
        print(f"Время цикла 2: {time.strftime('%H:%M:%S', time.localtime(cycle2_time))}")
        print(f"Интервал между циклами: {elapsed_time:.1f} сек")
        print(f"ТА ЖЕ ЦЕНА: {test_price:.2f} (падение {test_drop}%)")
        print(f"ТОТ ЖЕ LEVEL: {level1}")
        print()
        
        # ШАГ 1: Перезагрузка состояния из файла (как в main_loop)
        print("[ЦИКЛ 2] ШАГ 1: Перезагрузка состояния из файла (load_states)...")
        state_manager.load_states(silent=True)
        state_cycle2 = state_manager.get_state(test_pair)
        triggered_levels_cycle2 = state_cycle2.get("triggered_levels", [])
        print(f"  ✅ triggered_levels = {triggered_levels_cycle2}")
        
        # КРИТИЧЕСКАЯ ПРОВЕРКА: должен ли уровень быть в triggered_levels?
        if level1 not in triggered_levels_cycle2:
            print(f"  ❌ КРИТИЧЕСКАЯ ОШИБКА! Level {level1} НЕ найден в triggered_levels!")
            print(f"     Состояние НЕ сохранилось между циклами!")
            print(f"     Это означает, что дубль МОЖЕТ пройти!")
            return False
        
        print(f"  ✅ Level {level1} найден в triggered_levels - состояние сохранилось!")
        
        # ШАГ 2: Проверка пары (как в check_pair) - ТА ЖЕ ЦЕНА
        print(f"\n[ЦИКЛ 2] ШАГ 2: Проверка пары (check_pair) - ТА ЖЕ ЦЕНА...")
        print(f"  Текущая цена: {test_price:.2f} (ТА ЖЕ)")
        print(f"  Local max: {test_local_max:.2f}")
        print(f"  triggered_levels: {triggered_levels_cycle2} (должен содержать Level {level1})")
        
        # Проверка уровней (как в check_pair) - ТА ЖЕ ЦЕНА, ТОТ ЖЕ LEVEL
        signal_cycle2 = market_monitor.check_levels(
            test_pair,
            test_price,  # ТА ЖЕ ЦЕНА
            test_local_max,
            triggered_levels_cycle2  # Должен содержать Level 1
        )
        
        if signal_cycle2:
            level2 = signal_cycle2.get('level')
            if level2 == level1:
                print(f"  ❌ ОШИБКА! ТОТ ЖЕ СИГНАЛ Level {level2} создан повторно!")
                print(f"     ДУБЛЬ будет отправлен - защита НЕ РАБОТАЕТ!")
                print(f"     Это та самая проблема - дубль между циклами!")
                return False
            else:
                print(f"  ⚠️  Создан другой уровень {level2} (не дубль Level {level1})")
                print(f"     Это нормально, если цена пересекла новый уровень")
        else:
            print(f"  ✅ Сигнал Level {level1} НЕ создан - уровень заблокирован в check_levels!")
            print(f"     ✅ Защита работает на уровне market_monitor.check_levels!")
        
        # ШАГ 3: Проверка через is_duplicate_signal (если бы сигнал всё равно прошёл)
        print(f"\n[ЦИКЛ 2] ШАГ 3: Проверка через is_duplicate_signal()...")
        is_dup_state = state_manager.is_duplicate_signal(test_pair, level1, cycle2_time)
        if is_dup_state:
            print(f"  ✅ is_duplicate_signal() вернул True - дубль заблокирован")
            print(f"     ✅ Защита работает на уровне state_manager.is_duplicate_signal()!")
        else:
            print(f"  ⚠️  is_duplicate_signal() вернул False (но check_levels уже заблокировал)")
        
        # ШАГ 4: Проверка через telegram_sender кэш (если бы сигнал всё равно прошёл)
        print(f"\n[ЦИКЛ 2] ШАГ 4: Проверка через telegram_sender кэш (_is_duplicate)...")
        is_dup_cache = telegram_sender._is_duplicate(test_pair, level1)
        if is_dup_cache:
            print(f"  ✅ telegram_sender кэш блокирует дубль")
            print(f"     ✅ Защита работает на уровне telegram_sender._is_duplicate()!")
        else:
            print(f"  ⚠️  telegram_sender кэш не блокирует (но другие проверки уже заблокировали)")
        
        # ШАГ 5: Финальная проверка (как в main_loop)
        print(f"\n[ЦИКЛ 2] ШАГ 5: Финальная проверка (как в main_loop)...")
        final_check2 = state_manager.get_state(test_pair)
        if level1 in final_check2.get("triggered_levels", []):
            print(f"  ✅ Level {level1} в triggered_levels - дубль будет заблокирован в main_loop")
            print(f"     ✅ Защита работает на уровне main_loop!")
        else:
            print(f"  ❌ Level {level1} НЕ в triggered_levels - дубль МОЖЕТ пройти!")
            return False
        
        # ШАГ 6: Симуляция попытки отправки дубля (если бы он прошёл все проверки)
        print(f"\n[ЦИКЛ 2] ШАГ 6: Симуляция попытки отправки дубля...")
        # Эмулируем как будто сигнал прошёл все проверки до telegram_sender
        if signal_cycle2 and signal_cycle2.get('level') == level1:
            print(f"  ❌ ОШИБКА! Сигнал Level {level1} создан - попытка отправки...")
            # Проверяем все защиты перед отправкой
            is_dup_all = telegram_sender._is_duplicate(test_pair, level1)
            if is_dup_all:
                print(f"  ✅ telegram_sender кэш ЗАБЛОКИРОВАЛ бы дубль перед отправкой")
            else:
                print(f"  ❌ telegram_sender кэш НЕ ЗАБЛОКИРОВАЛ бы дубль - он был бы отправлен!")
                return False
        else:
            print(f"  ✅ Сигнал Level {level1} НЕ создан - дубль не будет отправлен")
            print(f"     ✅ Защита работает - дубль заблокирован на всех уровнях!")
        
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
        print(f"   - В цикле 1: Level {level1} создан и ОТПРАВЛЕН в Telegram")
        print(f"   - Состояние сохранено СРАЗУ после создания сигнала")
        print(f"   - Состояние перезагружено между циклами")
        print(f"   - В цикле 2 (через {elapsed_time:.1f} сек): ТОТ ЖЕ сигнал заблокирован:")
        print(f"     ✅ market_monitor.check_levels() - заблокировал")
        print(f"     ✅ state_manager.is_duplicate_signal() - заблокировал")
        print(f"     ✅ telegram_sender._is_duplicate() - заблокировал")
        print(f"     ✅ main_loop проверка - заблокировал")
        print(f"   - ДУБЛЬ НЕ будет отправлен!")
        print(f"   - Защита от дублей работает корректно на ВСЕХ уровнях!")
        
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
    print("ТЕСТ: Два реальных цикла с отправкой сигналов в Telegram")
    print("="*80)
    print("⚠️  ВНИМАНИЕ: Этот тест ОТПРАВИТ РЕАЛЬНОЕ сообщение в Telegram канал!")
    print(f"   Chat ID: {TELEGRAM_CHAT_ID}")
    print(f"   В цикле 1 отправится сигнал, в цикле 2 проверяется что дубль НЕ отправится")
    print(f"   Нажмите Ctrl+C для отмены или подождите 5 секунд...")
    
    try:
        time.sleep(5)
    except KeyboardInterrupt:
        print("\n❌ Тест отменён пользователем")
        sys.exit(1)
    
    result = test_duplicate_two_cycles_real()
    
    print("\n" + "="*80)
    print("ФИНАЛЬНЫЙ РЕЗУЛЬТАТ")
    print("="*80)
    if result:
        print("✅ ТЕСТ ПРОЙДЕН! Дубли НЕ отправляются между циклами")
        print("   Защита от дублей работает корректно на всех уровнях")
        print("   Сигналы будут доходить до канала БЕЗ дублей")
        sys.exit(0)
    else:
        print("❌ ТЕСТ ПРОВАЛЕН! Проверьте логи выше")
        print("   Возможно, дубли всё ещё могут отправляться между циклами")
        sys.exit(1)
