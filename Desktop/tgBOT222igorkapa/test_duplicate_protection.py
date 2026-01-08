#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки защиты от дублирования сигналов
Проверяет, что один и тот же уровень не отправляется дважды
"""

import sys
import io
import json
import os
import time
import tempfile

# Исправляем кодировку для Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Импортируем модули бота
from market_monitor import MarketMonitor
from state_manager import StateManager


def test_duplicate_protection():
    """Тест защиты от дублей: один уровень не должен отправляться дважды"""
    print("\n" + "="*60)
    print("ТЕСТ ЗАЩИТЫ ОТ ДУБЛИРОВАНИЯ СИГНАЛОВ")
    print("="*60)
    
    # Создаём временный файл для состояний
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    temp_file.close()
    temp_state_file = temp_file.name
    
    try:
        # Переопределяем STATE_FILE для теста
        import config
        original_state_file = config.STATE_FILE
        config.STATE_FILE = temp_state_file
        
        # Создаём экземпляры
        state_manager = StateManager()
        market_monitor = MarketMonitor()
        
        # Тестовые данные
        test_pair = "BTCEUR"
        test_price_cycle1 = 40000.0  # Первый цикл
        test_local_max = 45000.0     # Локальный максимум
        test_drop_percent = -11.1    # Падение -11.1% (должно попасть на Level 2 = -12%)
        
        current_time = time.time()
        
        print(f"\nТестовая пара: {test_pair}")
        print(f"Local max: {test_local_max}")
        print(f"Цена в цикле 1: {test_price_cycle1}")
        print(f"Падение: {test_drop_percent:.2f}%")
        print()
        
        # ===== ЦИКЛ 1: Первая отправка сигнала =====
        print("="*60)
        print("ЦИКЛ 1: Создание первого сигнала")
        print("="*60)
        
        # Инициализируем состояние пары
        state_manager.update_state(
            test_pair,
            local_max=test_local_max,
            local_max_time=current_time - 100,
            local_min=test_price_cycle1,
            triggered_levels=[],
            last_price=test_price_cycle1,
            initialized=True,
            initialization_time=current_time - 1000
        )
        
        # Проверяем уровни (как в bot.py)
        state = state_manager.get_state(test_pair)
        triggered_levels = state.get("triggered_levels", [])
        
        print(f"Состояние пары: triggered_levels = {triggered_levels}")
        
        # Вызываем check_levels (как в bot.py)
        signal1 = market_monitor.check_levels(
            test_pair,
            test_price_cycle1,
            test_local_max,
            triggered_levels
        )
        
        if signal1:
            level1 = signal1["level"]
            drop1 = signal1["drop_percent"]
            print(f"\n✅ Сигнал создан!")
            print(f"   Level: {level1}")
            print(f"   Drop: {drop1:.2f}%")
            
            # Симулируем отправку и сохранение уровня (как в bot.py после отправки)
            state_manager.add_triggered_level(test_pair, level1, current_time)
            
            # Проверяем, что уровень добавлен
            state_after = state_manager.get_state(test_pair)
            triggered_after = state_after.get("triggered_levels", [])
            print(f"\n   Уровень {level1} добавлен в triggered_levels: {triggered_after}")
        else:
            print("\n❌ Сигнал НЕ создан (неожиданно для первого цикла)")
            return False
        
        # ===== ЦИКЛ 2: Попытка отправить тот же сигнал =====
        print("\n" + "="*60)
        print("ЦИКЛ 2: Попытка создать тот же сигнал (дубль)")
        print("="*60)
        
        # Та же цена, тот же уровень должен сработать
        test_price_cycle2 = test_price_cycle1  # Та же цена
        current_time_cycle2 = current_time + 60  # +1 минута
        
        # Получаем актуальное состояние (как в bot.py)
        state_cycle2 = state_manager.get_state(test_pair)
        triggered_levels_cycle2 = state_cycle2.get("triggered_levels", [])
        
        print(f"Состояние пары: triggered_levels = {triggered_levels_cycle2}")
        print(f"Цена в цикле 2: {test_price_cycle2}")
        
        # Проверяем уровни снова
        signal2 = market_monitor.check_levels(
            test_pair,
            test_price_cycle2,
            test_local_max,
            triggered_levels_cycle2
        )
        
        if signal2:
            level2 = signal2["level"]
            print(f"\n❌ ОШИБКА! Сигнал создан повторно!")
            print(f"   Level: {level2}")
            print(f"   Это означает, что защита от дублей НЕ РАБОТАЕТ!")
            return False
        else:
            print(f"\n✅ Сигнал НЕ создан - защита от дублей работает!")
            print(f"   Уровень {level1} уже в triggered_levels, повторный сигнал заблокирован")
        
        # ===== ЦИКЛ 3: Новый уровень (должен пройти) =====
        print("\n" + "="*60)
        print("ЦИКЛ 3: Проверка другого уровня (должен пройти)")
        print("="*60)
        
        # Более глубокое падение - должен сработать Level 2 (-12%)
        # Но Level 2 уже должен был сработать в цикле 1, т.к. падение было -11.1%
        # Поэтому используем падение, которое точно пройдёт Level 2, но не Level 1
        # Падение -13% должно дать Level 2 (так как -13% <= -12%)
        test_price_cycle3 = test_local_max * 0.87  # Падение -13% (Level 2 = -12%)
        current_time_cycle3 = current_time + 120
        
        state_cycle3 = state_manager.get_state(test_pair)
        triggered_levels_cycle3 = state_cycle3.get("triggered_levels", [])
        
        drop_pct_cycle3 = ((test_price_cycle3 - test_local_max) / test_local_max * 100)
        print(f"Состояние пары: triggered_levels = {triggered_levels_cycle3}")
        print(f"Цена в цикле 3: {test_price_cycle3:.2f}")
        print(f"Падение: {drop_pct_cycle3:.2f}%")
        print(f"Ожидается: Level 2 должен сработать (падение -13% >= -12%)")
        
        signal3 = market_monitor.check_levels(
            test_pair,
            test_price_cycle3,
            test_local_max,
            triggered_levels_cycle3
        )
        
        if signal3:
            level3 = signal3["level"]
            drop3 = signal3["drop_percent"]
            print(f"\n✅ Сигнал создан для нового уровня!")
            print(f"   Level: {level3}")
            print(f"   Drop: {drop3:.2f}%")
            print(f"   Это правильно - Level {level3} ещё не был отправлен")
            
            # Сохраняем Level
            state_manager.add_triggered_level(test_pair, level3, current_time_cycle3)
            saved_level = level3
        else:
            print(f"\n❌ Сигнал НЕ создан (неожиданно - новый уровень должен пройти)")
            return False
        
        # ===== ЦИКЛ 4: Повторная попытка того же уровня =====
        print("\n" + "="*60)
        print(f"ЦИКЛ 4: Попытка отправить Level {saved_level} повторно (дубль)")
        print("="*60)
        
        state_cycle4 = state_manager.get_state(test_pair)
        triggered_levels_cycle4 = state_cycle4.get("triggered_levels", [])
        
        print(f"Состояние пары: triggered_levels = {triggered_levels_cycle4}")
        print(f"Цена в цикле 4: {test_price_cycle3:.2f} (та же что в цикле 3)")
        
        # Пытаемся создать тот же сигнал снова
        signal4 = market_monitor.check_levels(
            test_pair,
            test_price_cycle3,  # Та же цена
            test_local_max,
            triggered_levels_cycle4
        )
        
        if signal4:
            print(f"\n❌ ОШИБКА! Level {signal4['level']} создан повторно!")
            print(f"   Это означает, что защита от дублей НЕ РАБОТАЕТ!")
            print(f"   Expected: Level {saved_level} должен быть заблокирован")
            print(f"   Got: Level {signal4['level']} создан")
            return False
        else:
            print(f"\n✅ Level {saved_level} заблокирован - защита работает!")
        
        # Итоги
        print("\n" + "="*60)
        print("ИТОГИ ТЕСТА")
        print("="*60)
        final_state = state_manager.get_state(test_pair)
        print(f"Финальное состояние для {test_pair}:")
        print(f"  triggered_levels: {final_state.get('triggered_levels', [])}")
        print(f"  local_max: {final_state.get('local_max')}")
        print(f"  local_min: {final_state.get('local_min')}")
        print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
        print(f"   - Level 1 отправлен в цикле 1")
        print(f"   - Level 1 заблокирован в цикле 2 (дубль)")
        print(f"   - Level {saved_level} отправлен в цикле 3 (новый уровень)")
        print(f"   - Level {saved_level} заблокирован в цикле 4 (дубль)")
        
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


def test_multiple_levels_one_cycle():
    """Тест: несколько уровней в одном цикле (все должны пройти)"""
    print("\n" + "="*60)
    print("ТЕСТ: Несколько уровней в одном цикле")
    print("="*60)
    
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    temp_file.close()
    temp_state_file = temp_file.name
    
    try:
        import config
        original_state_file = config.STATE_FILE
        config.STATE_FILE = temp_state_file
        
        state_manager = StateManager()
        market_monitor = MarketMonitor()
        
        test_pair = "ETHEUR"
        test_local_max = 3000.0
        current_time = time.time()
        
        # Инициализируем
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
        
        # Проверяем разные уровни падения
        test_cases = [
            (test_local_max * 0.92, -8.0, 1, "Level 1 (-8%)"),
            (test_local_max * 0.88, -12.0, 2, "Level 2 (-12%)"),
            (test_local_max * 0.84, -16.0, 3, "Level 3 (-16%)"),
        ]
        
        print(f"Тестовая пара: {test_pair}")
        print(f"Local max: {test_local_max}")
        print()
        
        triggered_levels = []
        
        for i, (price, expected_drop, expected_level, desc) in enumerate(test_cases, 1):
            print(f"Проверка {i}: {desc}")
            print(f"  Цена: {price:.2f}")
            print(f"  Ожидаемое падение: {expected_drop:.1f}%")
            
            signal = market_monitor.check_levels(
                test_pair,
                price,
                test_local_max,
                triggered_levels  # Передаём текущий список
            )
            
            if signal:
                level = signal["level"]
                drop = signal["drop_percent"]
                print(f"  ✅ Сигнал создан: Level {level}, Drop {drop:.2f}%")
                triggered_levels.append(level)
                print(f"  triggered_levels обновлён: {triggered_levels}")
            else:
                print(f"  ❌ Сигнал НЕ создан (неожиданно)")
                return False
            print()
        
        print("✅ Все уровни прошли проверку в одном цикле")
        print(f"Финальные triggered_levels: {triggered_levels}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        config.STATE_FILE = original_state_file
        try:
            if os.path.exists(temp_state_file):
                os.unlink(temp_state_file)
        except:
            pass


if __name__ == "__main__":
    print("\n" + "="*60)
    print("ТЕСТИРОВАНИЕ ЗАЩИТЫ ОТ ДУБЛИРОВАНИЯ СИГНАЛОВ")
    print("="*60)
    
    test1_ok = test_duplicate_protection()
    test2_ok = test_multiple_levels_one_cycle()
    
    print("\n" + "="*60)
    print("ФИНАЛЬНЫЕ ИТОГИ")
    print("="*60)
    print(f"Тест 1 (дубли между циклами): {'✅ PASS' if test1_ok else '❌ FAIL'}")
    print(f"Тест 2 (несколько уровней в одном цикле): {'✅ PASS' if test2_ok else '❌ FAIL'}")
    print("="*60)
    
    if test1_ok and test2_ok:
        print("\n✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Защита от дублей работает корректно")
        sys.exit(0)
    else:
        print("\n❌ ЕСТЬ ОШИБКИ! Проверьте логи выше")
        sys.exit(1)
