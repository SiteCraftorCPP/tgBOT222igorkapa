#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Полный тест срабатывания сигнала с реальной отправкой в Telegram канал
Эмулирует весь процесс как в реальном боте
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


def test_full_signal_cycle():
    """Полный тест: симулирует срабатывание сигнала и отправку в канал"""
    print("\n" + "="*80)
    print("ПОЛНЫЙ ТЕСТ: Срабатывание сигнала с реальной отправкой в Telegram канал")
    print("="*80)
    
    # Временный файл для состояний
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    temp_file.close()
    temp_state_file = temp_file.name
    
    try:
        # Переопределяем STATE_FILE для теста ДО создания StateManager
        import config
        original_state_file = config.STATE_FILE
        config.STATE_FILE = temp_state_file
        
        # Создаём экземпляры (как в реальном боте) - ПОСЛЕ переопределения STATE_FILE
        telegram_sender = TelegramSender()
        state_manager = StateManager()  # Теперь будет использовать temp_state_file
        market_monitor = MarketMonitor()
        
        test_pair = "TESTFULLSIGNALEUR"
        initial_max = 100.0
        
        print(f"\nТестовая пара: {test_pair}")
        print(f"Начальный максимум: {initial_max}")
        print(f"Chat ID: {TELEGRAM_CHAT_ID}")
        print(f"Цель: Полная симуляция срабатывания сигнала и отправки в канал")
        print(f"Временный файл состояний: {temp_state_file}")
        print()
        
        # Очищаем состояние для тестовой пары (на случай если она была в основном файле)
        # Инициализируем состояние с нуля (как при старте бота)
        current_time = time.time()
        
        # Получаем состояние (создаст новое если нет)
        state = state_manager.get_state(test_pair)
        # Перезаписываем полностью чтобы убрать старые данные
        state_manager.states[test_pair] = {
            "local_max": initial_max,
            "local_max_time": current_time - 100,
            "local_min": None,
            "triggered_levels": [],
            "last_signal_time": None,  # Важно! Нет предыдущих сигналов
            "last_signal_level": None,
            "last_price": initial_max,
            "last_update": current_time - 100,
            "initialized": True,
            "initialization_time": current_time - 1000
        }
        state_manager.save_states()
        print(f"✅ Состояние инициализировано (очищено от старых данных)")
        
        # ===== ПОЛНЫЙ ЦИКЛ: Симулируем работу bot.py =====
        print("="*80)
        print("ЭТАП 1: Перезагрузка состояния (как в начале цикла)")
        print("="*80)
        
        # Перезагрузка состояния (как в main_loop)
        state_manager.load_states(silent=True)
        print("✅ Состояние перезагружено из файла")
        
        # ===== ЭТАП 2: Получение цены (как refresh_prices) =====
        print("\n" + "="*80)
        print("ЭТАП 2: Получение цены (симуляция refresh_prices)")
        print("="*80)
        
        # Симулируем падение -12.5% (должно сработать Level 2)
        current_price = initial_max * 0.875  # -12.5%
        drop_percent = ((current_price - initial_max) / initial_max) * 100
        
        print(f"Текущая цена: {current_price:.4f}")
        print(f"Локальный максимум: {initial_max:.4f}")
        print(f"Падение от максимума: {drop_percent:.2f}%")
        print(f"Ожидаемый уровень: Level 2 (-12%)")
        
        # ===== ЭТАП 3: Проверка пары (как check_pair) =====
        print("\n" + "="*80)
        print("ЭТАП 3: Проверка пары (check_pair)")
        print("="*80)
        
        state = state_manager.get_state(test_pair)
        print(f"Состояние пары:")
        print(f"  local_max: {state.get('local_max')}")
        print(f"  local_min: {state.get('local_min')}")
        print(f"  triggered_levels: {state.get('triggered_levels')}")
        
        # Проверка уровней (как в check_pair)
        triggered_levels = state.get("triggered_levels", [])
        signal = market_monitor.check_levels(
            test_pair,
            current_price,
            state.get("local_max"),
            triggered_levels
        )
        
        if not signal:
            print("  ❌ Сигнал не создан!")
            return False
        
        level = signal['level']
        drop = signal['drop_percent']
        print(f"\n✅ Сигнал создан:")
        print(f"   Level: {level}")
        print(f"   Падение: {drop:.2f}%")
        print(f"   Цена: {current_price:.4f}")
        
        # Финальная проверка (как в check_pair) - ДО сохранения
        final_check = state_manager.get_state(test_pair)
        if level in final_check.get("triggered_levels", []):
            print(f"  ❌ Level {level} уже в triggered_levels - не отправляем")
            return False
        
        # ===== ЭТАП 4: Проверки перед сохранением (как в main_loop) =====
        print("\n" + "="*80)
        print("ЭТАП 4: Финальные проверки перед отправкой (как в main_loop)")
        print("="*80)
        
        # Проверка 1: is_duplicate_signal (как в main_loop перед отправкой)
        print(f"[ПРОВЕРКА 1] is_duplicate_signal()...")
        is_dup_state = state_manager.is_duplicate_signal(test_pair, level, current_time)
        if is_dup_state:
            print(f"  ❌ is_duplicate_signal() заблокировал - не отправляем")
            return False
        print(f"  ✅ is_duplicate_signal() пропустил")
        
        # Проверка 2: telegram_sender кэш
        print(f"[ПРОВЕРКА 2] telegram_sender кэш...")
        is_dup_cache = telegram_sender._is_duplicate(test_pair, level)
        if is_dup_cache:
            print(f"  ❌ telegram_sender кэш заблокировал - не отправляем")
            return False
        print(f"  ✅ telegram_sender кэш пропустил")
        
        # ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ - сохраняем уровень СРАЗУ (как в check_pair)
        print(f"\n[СОХРАНЕНИЕ] Сохранение уровня СРАЗУ (все проверки прошли)...")
        state_manager.add_triggered_level(test_pair, level, current_time)
        print(f"✅ Level {level} сохранён в triggered_levels")
        
        # Обновляем local_min (как в check_pair)
        state_manager.update_state(test_pair, local_min=current_price)
        
        # ===== ЭТАП 5: Отправка в Telegram канал =====
        print("\n" + "="*80)
        print("ЭТАП 5: Отправка сигнала в Telegram канал")
        print("="*80)
        
        signals_to_send = [{
            "pair": test_pair,
            "drop_percent": drop,
            "level": level,
            "current_price": current_price
        }]
        
        print(f"Подготовка к отправке:")
        print(f"  Пара: {test_pair}")
        print(f"  Уровень: {level}")
        print(f"  Падение: {drop:.2f}%")
        print(f"  Цена: {current_price:.4f}")
        print(f"  Канал: {TELEGRAM_CHAT_ID}")
        
        # РЕАЛЬНАЯ отправка в Telegram канал
        print(f"\n[ОТПРАВКА] Отправка сигнала в Telegram канал...")
        send_result = telegram_sender.send_signals_batch(signals_to_send)
        
        if not send_result:
            print(f"  ❌ Ошибка отправки сигнала в Telegram!")
            return False
        
        print(f"  ✅ Сигнал успешно отправлен в Telegram канал!")
        
        # Проверяем что состояние сохранилось после отправки
        final_state = state_manager.get_state(test_pair)
        print(f"\n[ПРОВЕРКА] Финальное состояние после отправки:")
        print(f"  triggered_levels: {final_state.get('triggered_levels')}")
        print(f"  local_min: {final_state.get('local_min')}")
        print(f"  last_signal_time: {final_state.get('last_signal_time')}")
        print(f"  last_signal_level: {final_state.get('last_signal_level')}")
        
        if level not in final_state.get('triggered_levels', []):
            print(f"  ❌ Level {level} НЕ найден в triggered_levels после отправки!")
            return False
        
        print(f"  ✅ Level {level} сохранён в triggered_levels")
        
        # ===== ЭТАП 6: Проверка что сигнал реально дошёл до канала =====
        print("\n" + "="*80)
        print("ЭТАП 6: Проверка получения сигнала")
        print("="*80)
        print(f"⚠️  Проверь в канале Telegram ({TELEGRAM_CHAT_ID}):")
        print(f"   Должно быть сообщение:")
        print(f"   💎 {test_pair.replace('EUR', '')}/EUR | −{abs(drop):.1f}% | {current_price:.4f}€")
        print(f"   С кнопкой: 🚀 COMPRAR")
        print()
        print(f"✅ Если сообщение в канале - тест пройден!")
        
        # Итоги
        print("\n" + "="*80)
        print("ИТОГИ ПОЛНОГО ТЕСТА")
        print("="*80)
        print("✅ ВСЕ ЭТАПЫ ПРОЙДЕНЫ:")
        print(f"   ✅ Состояние перезагружено")
        print(f"   ✅ Цена получена: {current_price:.4f}")
        print(f"   ✅ Сигнал создан: Level {level} ({drop:.2f}%)")
        print(f"   ✅ Уровень сохранён СРАЗУ")
        print(f"   ✅ Все защиты проверены")
        print(f"   ✅ Сигнал ОТПРАВЛЕН в Telegram канал")
        print(f"   ✅ Состояние сохранено корректно")
        print(f"   📱 Проверь канал Telegram - сообщение должно быть там!")
        
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
    print("ПОЛНЫЙ ТЕСТ: Срабатывание сигнала с отправкой в канал")
    print("="*80)
    print(f"⚠️  ВНИМАНИЕ: Этот тест ОТПРАВИТ РЕАЛЬНОЕ сообщение в Telegram канал!")
    print(f"   Chat ID: {TELEGRAM_CHAT_ID}")
    print(f"   Симулируется полный цикл работы бота")
    print(f"   Нажмите Ctrl+C для отмены или подождите 5 секунд...")
    
    try:
        time.sleep(5)
    except KeyboardInterrupt:
        print("\n❌ Тест отменён пользователем")
        sys.exit(1)
    
    result = test_full_signal_cycle()
    
    print("\n" + "="*80)
    print("ФИНАЛЬНЫЙ РЕЗУЛЬТАТ")
    print("="*80)
    if result:
        print("✅ ТЕСТ ПРОЙДЕН! Сигнал успешно отправлен в Telegram канал")
        print("   Проверь канал - сообщение должно быть там!")
        sys.exit(0)
    else:
        print("❌ ТЕСТ ПРОВАЛЕН! Проверьте логи выше")
        sys.exit(1)
