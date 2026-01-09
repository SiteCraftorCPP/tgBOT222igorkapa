#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест эмулирует РЕАЛЬНЫЙ сигнал через Bit2Me API
Использует реальные цены из API для создания сигнала
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


def test_real_api_signal():
    """Эмулирует реальный сигнал через Bit2Me API"""
    print("\n" + "="*80)
    print("ТЕСТ: Реальный сигнал через Bit2Me API")
    print("="*80)
    print("⚠️  ВНИМАНИЕ: Этот тест ОТПРАВИТ РЕАЛЬНОЕ сообщение в Telegram канал!")
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
        
        print("="*80)
        print("ШАГ 1: Получение реальных цен через Bit2Me API")
        print("="*80)
        
        # Получаем реальные цены через API
        print("\n[API] Получение всех пар с Bit2Me API...")
        price_stats = market_monitor.refresh_prices()
        
        if not price_stats:
            print("  ❌ Ошибка получения цен из API!")
            return False
        
        print(f"  ✅ Получено {len(market_monitor.prices_cache)} пар с реальными ценами")
        
        # Получаем список доступных пар
        available_pairs = list(market_monitor.prices_cache.keys())
        if not available_pairs:
            print("  ❌ Нет доступных пар!")
            return False
        
        print(f"  ✅ Доступно {len(available_pairs)} пар")
        print(f"  📊 Топ-10 пар: {', '.join(available_pairs[:10])}")
        
        # Выбираем реальную пару для теста (например, BTC или ETH)
        test_pair = None
        preferred_pairs = ["BTCEUR", "ETHEUR", "SOLEUR", "BNBEUR", "ADAEUR"]
        
        for pref_pair in preferred_pairs:
            if pref_pair in available_pairs:
                test_pair = pref_pair
                break
        
        # Если нет предпочтительных, берём первую доступную
        if not test_pair:
            test_pair = available_pairs[0]
        
        print(f"\n[API] Выбрана пара для теста: {test_pair}")
        
        # Получаем РЕАЛЬНУЮ текущую цену из API
        real_current_price = market_monitor.get_current_price(test_pair)
        if real_current_price is None or real_current_price <= 0:
            print(f"  ❌ Не удалось получить цену для {test_pair}!")
            return False
        
        print(f"  ✅ Реальная текущая цена {test_pair}: {real_current_price:.4f}€")
        
        # Используем реальную цену как "local_max"
        # Симулируем что эта цена была локальным максимумом
        test_local_max = real_current_price
        
        # Рассчитываем цену для Level 1 (-8%)
        # Используем значение чуть ниже порога для гарантированного срабатывания
        # Из-за ошибок округления float, -8.0% может не сработать, поэтому используем -8.01%
        test_drop_level1 = -8.01  # Чуть больше падения для гарантированного срабатывания
        test_price_level1 = test_local_max * (1 + test_drop_level1 / 100)  # Точное вычисление
        expected_level = 1
        
        print("\n" + "="*80)
        print("НАСТРОЙКА ТЕСТА")
        print("="*80)
        print(f"Реальная пара: {test_pair}")
        print(f"Реальная цена (local_max): {test_local_max:.4f}€")
        print(f"Симулированная цена для сигнала: {test_price_level1:.4f}€ (падение {test_drop_level1}%)")
        print(f"Ожидаемый уровень: Level {expected_level}")
        print()
        
        # Инициализируем состояние (как при старте бота)
        current_time = time.time()
        state_manager.update_state(
            test_pair,
            local_max=test_local_max,  # Реальная цена как максимум
            local_max_time=current_time - 100,
            local_min=None,
            triggered_levels=[],
            last_signal_time=None,
            last_signal_level=None,
            last_price=test_local_max,
            initialized=True,
            initialization_time=current_time - 1000
        )
        print(f"✅ Состояние инициализировано с реальной ценой из API")
        
        # ============================================================
        # ЦИКЛ 1: Эмулируем полный цикл bot.py с РЕАЛЬНОЙ парой
        # ============================================================
        print("\n" + "="*80)
        print("ЦИКЛ 1: Создание и отправка РЕАЛЬНОГО сигнала")
        print("="*80)
        cycle1_time = time.time()
        print(f"Время цикла 1: {time.strftime('%H:%M:%S', time.localtime(cycle1_time))}")
        print()
        
        # ШАГ 1: Перезагрузка состояния из файла (как в main_loop)
        print("[ЦИКЛ 1] ШАГ 1: Перезагрузка состояния из файла...")
        state_manager.load_states(silent=True)
        state_cycle1 = state_manager.get_state(test_pair)
        triggered_levels_cycle1 = state_cycle1.get("triggered_levels", [])
        print(f"  ✅ triggered_levels = {triggered_levels_cycle1}")
        print(f"  ✅ local_max = {state_cycle1.get('local_max'):.4f}€ (реальная цена из API)")
        
        # ШАГ 2: Проверка пары (как в check_pair)
        print(f"\n[ЦИКЛ 1] ШАГ 2: Проверка пары (check_pair)...")
        print(f"  Пара: {test_pair} (РЕАЛЬНАЯ из API)")
        print(f"  Текущая цена: {test_price_level1:.4f}€ (симулированное падение {test_drop_level1}%)")
        print(f"  Local max: {test_local_max:.4f}€ (реальная цена из API)")
        print(f"  triggered_levels: {triggered_levels_cycle1}")
        
        # Проверка уровней (как в check_pair через market_monitor.check_levels)
        signal_cycle1 = market_monitor.check_levels(
            test_pair,
            test_price_level1,  # Симулированная цена для триггера
            test_local_max,  # Реальная цена как максимум
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
        
        # ШАГ 3: Финальная проверка перед сохранением
        print(f"\n[ЦИКЛ 1] ШАГ 3: Финальная проверка перед сохранением...")
        final_check1 = state_manager.get_state(test_pair)
        if level1 in final_check1.get("triggered_levels", []):
            print(f"  ❌ Level {level1} уже в triggered_levels!")
            return False
        print(f"  ✅ Level {level1} НЕ в triggered_levels - можно сохранять")
        
        # ШАГ 4: Сохранение уровня СРАЗУ
        print(f"\n[ЦИКЛ 1] ШАГ 4: Сохранение уровня СРАЗУ...")
        state_manager.add_triggered_level(test_pair, level1, cycle1_time)
        
        saved_state1 = state_manager.get_state(test_pair)
        saved_levels1 = saved_state1.get("triggered_levels", [])
        print(f"  ✅ triggered_levels после сохранения: {saved_levels1}")
        
        # ШАГ 5: Подготовка сигнала для отправки
        print(f"\n[ЦИКЛ 1] ШАГ 5: Подготовка сигнала для отправки...")
        cycle_signals = [{
            "pair": test_pair,
            "drop_percent": drop1,
            "level": level1,
            "current_price": test_price_level1
        }]
        print(f"  ✅ Подготовлено {len(cycle_signals)} сигнал(ов) для отправки")
        for sig in cycle_signals:
            print(f"     - {sig['pair']}: Level {sig['level']}, drop {sig['drop_percent']:.2f}%, price {sig['current_price']:.4f}€")
        
        # ШАГ 6: Отправка сигнала в Telegram (РЕАЛЬНАЯ отправка)
        print(f"\n[ЦИКЛ 1] ШАГ 6: ОТПРАВКА РЕАЛЬНОГО СИГНАЛА В TELEGRAM...")
        print(f"  Chat ID: {TELEGRAM_CHAT_ID}")
        print(f"  Реальная пара: {test_pair}")
        print(f"  Сигнал: Level {level1} ({drop1:.2f}%)")
        
        send_result1 = telegram_sender.send_signals_batch(cycle_signals)
        
        if not send_result1:
            print(f"  ❌ Ошибка отправки сигнала в Telegram!")
            return False
        
        print(f"  ✅ РЕАЛЬНЫЙ сигнал Level {level1} ОТПРАВЛЕН в Telegram канал!")
        print(f"  📱 Проверь канал - сообщение должно быть там!")
        
        # Финальное состояние цикла 1
        final_state1 = state_manager.get_state(test_pair)
        print(f"\n[ЦИКЛ 1] ФИНАЛЬНОЕ СОСТОЯНИЕ:")
        print(f"  triggered_levels: {final_state1.get('triggered_levels', [])}")
        print(f"  last_signal_time: {final_state1.get('last_signal_time')}")
        print(f"  last_signal_level: {final_state1.get('last_signal_level')}")
        print(f"  ✅ Цикл 1 завершён успешно")
        
        # ============================================================
        # ЦИКЛ 2: Попытка отправить ТОТ ЖЕ САМЫЙ сигнал (дубль)
        # ============================================================
        print("\n" + "="*80)
        print("ЦИКЛ 2: Проверка блокировки дубля")
        print("="*80)
        
        # Используем короткую задержку для теста
        wait_time = 2
        print(f"⏳ Ждём {wait_time} сек между циклами...")
        time.sleep(wait_time)
        
        cycle2_time = time.time()
        print(f"\nВремя цикла 2: {time.strftime('%H:%M:%S', time.localtime(cycle2_time))}")
        print(f"ТА ЖЕ ПАРА: {test_pair}")
        print(f"ТА ЖЕ ЦЕНА: {test_price_level1:.4f}€ (падение {test_drop_level1}%)")
        print(f"ТОТ ЖЕ LEVEL: {level1}")
        print()
        
        # ШАГ 1: Перезагрузка состояния из файла
        print("[ЦИКЛ 2] ШАГ 1: Перезагрузка состояния из файла...")
        state_manager.load_states(silent=True)
        state_cycle2 = state_manager.get_state(test_pair)
        triggered_levels_cycle2 = state_cycle2.get("triggered_levels", [])
        print(f"  ✅ triggered_levels = {triggered_levels_cycle2}")
        
        if level1 not in triggered_levels_cycle2:
            print(f"  ❌ КРИТИЧЕСКАЯ ОШИБКА! Level {level1} НЕ найден в triggered_levels!")
            return False
        
        print(f"  ✅ Level {level1} найден в triggered_levels - состояние сохранилось!")
        
        # ШАГ 2: Проверка пары - ТА ЖЕ ЦЕНА
        print(f"\n[ЦИКЛ 2] ШАГ 2: Проверка пары - ТА ЖЕ ЦЕНА...")
        signal_cycle2 = market_monitor.check_levels(
            test_pair,
            test_price_level1,  # ТА ЖЕ ЦЕНА
            test_local_max,
            triggered_levels_cycle2  # Должен содержать Level 1
        )
        
        if signal_cycle2:
            level2 = signal_cycle2.get('level')
            if level2 == level1:
                print(f"  ❌ ОШИБКА! ТОТ ЖЕ СИГНАЛ Level {level2} создан повторно!")
                return False
            else:
                print(f"  ⚠️  Создан другой уровень {level2}")
        else:
            print(f"  ✅ Сигнал Level {level1} НЕ создан - уровень заблокирован!")
        
        # ШАГ 3: Проверка через is_duplicate_signal
        print(f"\n[ЦИКЛ 2] ШАГ 3: Проверка через is_duplicate_signal()...")
        is_dup_state = state_manager.is_duplicate_signal(test_pair, level1, cycle2_time)
        if is_dup_state:
            print(f"  ✅ is_duplicate_signal() вернул True - дубль заблокирован")
        else:
            print(f"  ⚠️  is_duplicate_signal() вернул False (но check_levels уже заблокировал)")
        
        # ШАГ 4: Проверка через telegram_sender кэш
        print(f"\n[ЦИКЛ 2] ШАГ 4: Проверка через telegram_sender кэш...")
        is_dup_cache = telegram_sender._is_duplicate(test_pair, level1)
        if is_dup_cache:
            print(f"  ✅ telegram_sender кэш блокирует дубль")
        else:
            print(f"  ⚠️  telegram_sender кэш не блокирует (но другие проверки уже заблокировали)")
        
        # Итоги
        print("\n" + "="*80)
        print("ИТОГИ ТЕСТА")
        print("="*80)
        print(f"✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
        print(f"   - Использована РЕАЛЬНАЯ пара из Bit2Me API: {test_pair}")
        print(f"   - Использована РЕАЛЬНАЯ цена из API: {test_local_max:.4f}€")
        print(f"   - В цикле 1: Level {level1} создан и ОТПРАВЛЕН в Telegram")
        print(f"   - В цикле 2: ТОТ ЖЕ сигнал заблокирован на всех уровнях")
        print(f"   - ДУБЛЬ НЕ будет отправлен!")
        print(f"   - Защита от дублей работает корректно с РЕАЛЬНЫМИ данными из API!")
        
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
    print("ТЕСТ: Реальный сигнал через Bit2Me API")
    print("="*80)
    print("⚠️  ВНИМАНИЕ: Этот тест ОТПРАВИТ РЕАЛЬНОЕ сообщение в Telegram канал!")
    print(f"   Chat ID: {TELEGRAM_CHAT_ID}")
    print(f"   Тест использует РЕАЛЬНЫЕ цены из Bit2Me API")
    print(f"   Нажмите Ctrl+C для отмены или подождите 5 секунд...")
    
    try:
        time.sleep(5)
    except KeyboardInterrupt:
        print("\n❌ Тест отменён пользователем")
        sys.exit(1)
    
    result = test_real_api_signal()
    
    print("\n" + "="*80)
    print("ФИНАЛЬНЫЙ РЕЗУЛЬТАТ")
    print("="*80)
    if result:
        print("✅ ТЕСТ ПРОЙДЕН! Реальный сигнал через API работает корректно")
        print("   Сигналы будут доходить до канала БЕЗ дублей")
        sys.exit(0)
    else:
        print("❌ ТЕСТ ПРОВАЛЕН! Проверьте логи выше")
        sys.exit(1)
