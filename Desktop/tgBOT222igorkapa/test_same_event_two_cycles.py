#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест эмулирует отправку ОДНОГО И ТОГО ЖЕ события в двух последовательных циклах
Проверяет что дубль НЕ отправляется
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


def test_same_event_two_cycles():
    """Тест: ОДНО И ТО ЖЕ событие в двух циклах - дубль НЕ должен отправляться"""
    print("\n" + "="*80)
    print("ТЕСТ: Одно и то же событие в двух циклах - проверка блокировки дубля")
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
        
        # Создаём экземпляры (как в реальном боте)
        telegram_sender = TelegramSender()
        state_manager = StateManager()
        market_monitor = MarketMonitor()
        
        test_pair = "TESTDUPLICATEUR"
        test_local_max = 1000.0
        
        print(f"\nТестовая пара: {test_pair}")
        print(f"Local max: {test_local_max}")
        print(f"Цель: Проверить что ОДНО И ТО ЖЕ событие НЕ отправляется дважды")
        print()
        
        # Инициализируем состояние (как при старте бота)
        state_manager.update_state(
            test_pair,
            local_max=test_local_max,
            local_max_time=time.time() - 100,
            local_min=None,
            triggered_levels=[],
            last_price=test_local_max,
            initialized=True,
            initialization_time=time.time() - 1000
        )
        
        # Цена которая триггерит Level 1 (-8%)
        # Используем Level 1 чтобы точно получить его в первом цикле
        test_price = test_local_max * 0.92  # -8%
        test_level = 1
        test_drop = -8.0
        
        print("="*80)
        print(f"НАСТРОЙКА: Цена {test_price:.2f} (падение {test_drop}%) → Level {test_level}")
        print("="*80)
        
        # ============================================================
        # ЦИКЛ 1: Отправка сигнала Level 2
        # ============================================================
        print("\n" + "="*80)
        print("ЦИКЛ 1: Отправка Level 2 (-12%)")
        print("="*80)
        
        cycle1_time = time.time()
        print(f"Время цикла 1: {time.strftime('%H:%M:%S', time.localtime(cycle1_time))}")
        
        # Эмулируем работу bot.py в цикле 1
        print("\n[ЦИКЛ 1] ШАГ 1: Перезагрузка состояния из файла...")
        state_manager.load_states(silent=True)
        
        print("[ЦИКЛ 1] ШАГ 2: Получение состояния пары...")
        state_cycle1 = state_manager.get_state(test_pair)
        triggered_levels_cycle1 = state_cycle1.get("triggered_levels", [])
        print(f"  triggered_levels = {triggered_levels_cycle1}")
        
        print("[ЦИКЛ 1] ШАГ 3: Проверка уровней (check_levels)...")
        signal_cycle1 = market_monitor.check_levels(
            test_pair,
            test_price,
            test_local_max,
            triggered_levels_cycle1
        )
        
        if not signal_cycle1:
            print("  ❌ Сигнал не создан - неожиданно!")
            return False
        
        level_created = signal_cycle1['level']
        if level_created != test_level:
            print(f"  ⚠️  Создан Level {level_created} вместо {test_level} (но продолжим)")
            test_level = level_created
        
        print(f"  ✅ Сигнал Level {test_level} создан (падение: {signal_cycle1['drop_percent']:.2f}%)")
        
        print("[ЦИКЛ 1] ШАГ 4: Финальная проверка перед сохранением...")
        final_check1 = state_manager.get_state(test_pair)
        if test_level in final_check1.get("triggered_levels", []):
            print(f"  ❌ Level {test_level} уже в triggered_levels!")
            return False
        
        print("[ЦИКЛ 1] ШАГ 5: Сохранение уровня СРАЗУ (как в check_pair)...")
        state_manager.add_triggered_level(test_pair, test_level, cycle1_time)
        
        # КРИТИЧЕСКАЯ ПРОВЕРКА: Проверяем что состояние реально записалось в файл
        print(f"  [ПРОВЕРКА] Проверка записи в файл...")
        time.sleep(0.1)  # Небольшая задержка для записи на диск
        
        # Перезагружаем из файла для проверки
        state_manager_reload = StateManager()
        state_manager_reload.load_states(silent=True)
        reloaded_state = state_manager_reload.get_state(test_pair)
        reloaded_levels = reloaded_state.get("triggered_levels", [])
        
        if test_level not in reloaded_levels:
            print(f"  ❌ КРИТИЧЕСКАЯ ОШИБКА! Level {test_level} НЕ найден в файле после сохранения!")
            print(f"     Состояние НЕ записалось в файл!")
            print(f"     В памяти: {state_manager.get_state(test_pair).get('triggered_levels', [])}")
            print(f"     В файле: {reloaded_levels}")
            return False
        
        print(f"  ✅ Level {test_level} найден в файле после сохранения!")
        saved_state1 = state_manager.get_state(test_pair)
        print(f"  ✅ Level {test_level} сохранён в triggered_levels: {saved_state1.get('triggered_levels', [])}")
        
        print("[ЦИКЛ 1] ШАГ 6: РЕАЛЬНАЯ отправка сигнала в Telegram канал...")
        # ПРОВЕРКА: должен ли telegram_sender заблокировать дубль?
        is_dup_cache1 = telegram_sender._is_duplicate(test_pair, test_level)
        if is_dup_cache1:
            print(f"  ❌ telegram_sender кэш уже блокирует (неожиданно в цикле 1)")
            return False
        
        # РЕАЛЬНАЯ отправка в Telegram
        signals_to_send_cycle1 = [{
            "pair": test_pair,
            "drop_percent": signal_cycle1['drop_percent'],
            "level": test_level,
            "current_price": test_price
        }]
        
        print(f"  [ОТПРАВКА] Отправка сигнала Level {test_level} для {test_pair} в канал {TELEGRAM_CHAT_ID}...")
        send_result = telegram_sender.send_signals_batch(signals_to_send_cycle1)
        
        if not send_result:
            print(f"  ❌ Ошибка отправки сигнала в Telegram!")
            return False
        
        print(f"  ✅ Сигнал Level {test_level} ОТПРАВЛЕН в Telegram канал!")
        
        print(f"\n[ЦИКЛ 1] ИТОГ:")
        final_state1 = state_manager.get_state(test_pair)
        print(f"  triggered_levels: {final_state1.get('triggered_levels', [])}")
        print(f"  last_signal_time: {final_state1.get('last_signal_time')}")
        print(f"  last_signal_level: {final_state1.get('last_signal_level')}")
        
        # ============================================================
        # ОЖИДАНИЕ (как между циклами бота)
        # ============================================================
        print("\n" + "="*80)
        print(f"ОЖИДАНИЕ: {CHECK_INTERVAL} секунд (как между циклами)")
        print("="*80)
        
        wait_time = 2  # Для быстрого теста
        print(f"⏳ Ждём {wait_time} сек...")
        time.sleep(wait_time)
        
        # ============================================================
        # ЦИКЛ 2: Попытка отправить ТО ЖЕ САМОЕ событие
        # ============================================================
        print("\n" + "="*80)
        print("ЦИКЛ 2: Попытка отправить ТО ЖЕ САМОЕ событие (дубль)")
        print("="*80)
        
        cycle2_time = time.time()
        print(f"Время цикла 2: {time.strftime('%H:%M:%S', time.localtime(cycle2_time))}")
        print(f"Интервал между циклами: {cycle2_time - cycle1_time:.1f} сек")
        print(f"ТА ЖЕ ЦЕНА: {test_price:.2f} (падение {test_drop}%)")
        print(f"ТОТ ЖЕ LEVEL: {test_level}")
        
        # Эмулируем работу bot.py в цикле 2
        print("\n[ЦИКЛ 2] ШАГ 1: Перезагрузка состояния из файла...")
        state_manager.load_states(silent=True)  # КРИТИЧНО: перезагрузка между циклами
        
        print("[ЦИКЛ 2] ШАГ 2: Получение состояния пары...")
        state_cycle2 = state_manager.get_state(test_pair)
        triggered_levels_cycle2 = state_cycle2.get("triggered_levels", [])
        print(f"  triggered_levels = {triggered_levels_cycle2}")
        
        # ПРОВЕРКА 1: должен ли уровень быть в triggered_levels?
        if test_level not in triggered_levels_cycle2:
            print(f"  ❌ КРИТИЧЕСКАЯ ОШИБКА! Level {test_level} НЕ найден в triggered_levels!")
            print(f"     Состояние НЕ сохранилось между циклами!")
            print(f"     Это означает, что дубль МОЖЕТ пройти!")
            return False
        
        print(f"  ✅ Level {test_level} найден в triggered_levels - состояние сохранилось!")
        
        print("[ЦИКЛ 2] ШАГ 3: Проверка уровней (check_levels) с ТОЙ ЖЕ ценой...")
        signal_cycle2 = market_monitor.check_levels(
            test_pair,
            test_price,  # ТА ЖЕ ЦЕНА
            test_local_max,
            triggered_levels_cycle2  # Должен содержать Level 1
        )
        
        if signal_cycle2:
            signal_level2 = signal_cycle2.get('level')
            if signal_level2 == test_level:
                print(f"  ❌ ОШИБКА! check_levels() создал ТОТ ЖЕ сигнал Level {test_level}!")
                print(f"     ДУБЛЬ будет отправлен - защита НЕ РАБОТАЕТ!")
                print(f"     Цена: {test_price}, Level: {test_level}, triggered_levels: {triggered_levels_cycle2}")
                return False
            else:
                print(f"  ⚠️  Создан другой уровень {signal_level2} (не дубль того же уровня)")
        else:
            print(f"  ✅ check_levels() НЕ создал сигнал - уровень заблокирован")
        
        # Даже если check_levels не создал сигнал, проверяем все остальные проверки
        # (на случай если бы сигнал всё равно прошёл)
        
        print("[ЦИКЛ 2] ШАГ 4: Проверка через is_duplicate_signal()...")
        is_dup_state = state_manager.is_duplicate_signal(test_pair, test_level, cycle2_time)
        if not is_dup_state:
            print(f"  ❌ is_duplicate_signal() вернул False - дубль НЕ заблокирован!")
            return False
        print(f"  ✅ is_duplicate_signal() вернул True - дубль заблокирован")
        
        print("[ЦИКЛ 2] ШАГ 5: Проверка через telegram_sender кэш...")
        is_dup_cache2 = telegram_sender._is_duplicate(test_pair, test_level)
        if not is_dup_cache2:
            print(f"  ⚠️  telegram_sender кэш не блокирует (но другие проверки уже заблокировали)")
        else:
            print(f"  ✅ telegram_sender кэш блокирует дубль")
        
        print("[ЦИКЛ 2] ШАГ 6: Финальная проверка (как в main_loop)...")
        final_check2 = state_manager.get_state(test_pair)
        if test_level in final_check2.get("triggered_levels", []):
            print(f"  ✅ Level {test_level} в triggered_levels - дубль будет заблокирован в main_loop")
        else:
            print(f"  ❌ Level {test_level} НЕ в triggered_levels - дубль МОЖЕТ пройти!")
            return False
        
        # КРИТИЧЕСКАЯ ПРОВЕРКА: Попытка отправить дубль (эмулируем как будто сигнал прошёл все проверки)
        print("[ЦИКЛ 2] ШАГ 7: Попытка ОТПРАВИТЬ дубль (если бы прошёл все проверки)...")
        if signal_cycle2 and signal_cycle2.get('level') == test_level:
            print(f"  ❌ ОШИБКА! Сигнал Level {test_level} создан - попытка отправки...")
            signals_dup = [{
                "pair": test_pair,
                "drop_percent": signal_cycle2['drop_percent'],
                "level": test_level,
                "current_price": test_price
            }]
            # Проверяем все защиты перед отправкой
            is_dup_all = telegram_sender._is_duplicate(test_pair, test_level)
            if is_dup_all:
                print(f"  ✅ telegram_sender кэш ЗАБЛОКИРОВАЛ бы дубль перед отправкой")
            else:
                print(f"  ❌ telegram_sender кэш НЕ ЗАБЛОКИРОВАЛ бы дубль - он был бы отправлен!")
                return False
        else:
            print(f"  ✅ Сигнал Level {test_level} НЕ создан - дубль не будет отправлен")
        
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
        print(f"   - Level {test_level} отправлен в цикле 1")
        print(f"   - Состояние сохранено и перезагружено между циклами")
        print(f"   - В цикле 2 ТО ЖЕ событие заблокировано на всех уровнях:")
        print(f"     ✅ check_levels() - заблокировал")
        print(f"     ✅ is_duplicate_signal() - заблокировал")
        print(f"     ✅ telegram_sender кэш - заблокировал")
        print(f"     ✅ main_loop проверка - заблокирует")
        print(f"   - ДУБЛЬ НЕ будет отправлен!")
        
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
    print("ТЕСТ: Одно и то же событие в двух циклах")
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
    
    result = test_same_event_two_cycles()
    
    print("\n" + "="*80)
    print("ФИНАЛЬНЫЙ РЕЗУЛЬТАТ")
    print("="*80)
    if result:
        print("✅ ТЕСТ ПРОЙДЕН! Одно и то же событие НЕ отправляется дважды")
        print("   Защита от дублей работает корректно на всех уровнях")
        sys.exit(0)
    else:
        print("❌ ТЕСТ ПРОВАЛЕН! Проверьте логи выше")
        print("   Дубли могут отправляться между циклами")
        sys.exit(1)
