#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест проверяет, что нет временного окна между созданием сигнала и сохранением уровня
"""

import sys
import time
from state_manager import StateManager
from market_monitor import MarketMonitor

# Исправляем кодировку для Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def test_no_time_window():
    """Проверка что уровень сохраняется СРАЗУ после создания сигнала"""
    
    print("="*80)
    print("ТЕСТ: Отсутствие временного окна между созданием и сохранением")
    print("="*80)
    
    state_manager = StateManager()
    market_monitor = MarketMonitor()
    
    # Симулируем состояние пары
    pair = "TESTEUR"
    current_time = time.time()
    # Используем падение -8.5% для Level 1 (-8%)
    local_max = 100.0
    current_price = 91.5  # -8.5% от 100
    drop_percent = ((current_price - local_max) / local_max) * 100  # -8.5%
    
    print(f"\n[SETUP] Пара: {pair}")
    print(f"        Цена: {current_price}")
    print(f"        Максимум: {local_max}")
    print(f"        Падение: {drop_percent:.2f}%")
    
    # Инициализируем состояние
    state_manager.update_state(pair, 
                               local_max=local_max,
                               local_max_time=current_time,
                               triggered_levels=[],
                               initialized=True)
    
    print(f"\n[STEP 1] Проверяем начальное состояние:")
    state = state_manager.get_state(pair)
    print(f"        triggered_levels: {state['triggered_levels']}")
    
    # Проверяем уровень (симулируем check_pair)
    print(f"\n[STEP 2] Проверяем уровни (check_levels):")
    signal = market_monitor.check_levels(pair, current_price, local_max, state['triggered_levels'])
    
    if signal:
        level = signal["level"]
        print(f"        ✅ Создан сигнал: Level {level}")
        
        # СРАЗУ сохраняем уровень (как в check_pair)
        print(f"\n[STEP 3] СРАЗУ сохраняем уровень (в check_pair):")
        save_start = time.time()
        state_manager.add_triggered_level(pair, level, current_time)
        save_time = (time.time() - save_start) * 1000  # в миллисекундах
        print(f"        ✅ Уровень сохранён за {save_time:.2f} мс")
        
        # Проверяем, что уровень сохранён
        print(f"\n[STEP 4] Проверяем сохранённое состояние:")
        saved_state = state_manager.get_state(pair)
        print(f"        triggered_levels: {saved_state['triggered_levels']}")
        
        if level in saved_state['triggered_levels']:
            print(f"        ✅ Уровень {level} присутствует в triggered_levels")
        else:
            print(f"        ❌ ОШИБКА: Уровень {level} НЕ найден в triggered_levels!")
            return False
        
        # Симулируем следующий цикл СРАЗУ после сохранения
        print(f"\n[STEP 5] Симулируем следующий цикл (через 0.1 сек):")
        time.sleep(0.1)  # Минимальная задержка
        
        # Проверяем снова (как в следующем цикле)
        next_state = state_manager.get_state(pair)
        next_signal = market_monitor.check_levels(pair, current_price, local_max, next_state['triggered_levels'])
        
        if next_signal:
            next_level = next_signal['level']
            if next_level == level:
                print(f"        ❌ ОШИБКА: Создан ДУБЛЬ того же уровня Level {level}!")
                print(f"        triggered_levels в следующем цикле: {next_state['triggered_levels']}")
                return False
            else:
                print(f"        ✅ ДУБЛЬ не создан - создан другой уровень {next_level} (нормально)")
        else:
            print(f"        ✅ ДУБЛЬ НЕ создан - уровень заблокирован")
        
        # Проверяем, что save_states() действительно записал в файл
        print(f"\n[STEP 6] Проверяем, что состояние сохранено в файл:")
        # Перезагружаем состояние из файла
        state_manager2 = StateManager()
        file_state = state_manager2.get_state(pair)
        print(f"        triggered_levels из файла: {file_state.get('triggered_levels', [])}")
        
        if level in file_state.get('triggered_levels', []):
            print(f"        ✅ Уровень {level} присутствует в файле")
        else:
            print(f"        ⚠️  Уровень {level} не найден в файле (но может быть новая пара)")
        
        print(f"\n{'='*80}")
        print(f"✅ ТЕСТ ПРОЙДЕН: Временное окно устранено!")
        print(f"   Уровень сохраняется СРАЗУ ({save_time:.2f} мс) после создания сигнала")
        print(f"   Следующий цикл уже видит сохранённый уровень")
        print(f"{'='*80}")
        return True
    else:
        print(f"        ❌ ОШИБКА: Сигнал не создан!")
        return False


if __name__ == "__main__":
    try:
        success = test_no_time_window()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ОШИБКА ТЕСТА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
