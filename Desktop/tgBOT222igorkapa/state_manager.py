import json
import os
import time
from typing import Dict, Optional
from config import STATE_FILE

# Получаем абсолютный путь к файлу состояний для надёжности
def get_state_file_path():
    """Получить абсолютный путь к файлу состояний"""
    if os.path.isabs(STATE_FILE):
        return STATE_FILE
    # Если относительный путь, используем рабочую директорию
    return os.path.join(os.getcwd(), STATE_FILE)


class StateManager:
    """Управление состояниями торговых пар"""
    
    def __init__(self):
        self.states: Dict[str, dict] = {}
        self.load_states()
    
    def load_states(self):
        """Загрузка состояний из файла"""
        state_file_path = get_state_file_path()
        if os.path.exists(state_file_path):
            try:
                with open(state_file_path, 'r', encoding='utf-8') as f:
                    self.states = json.load(f)
                print(f"[OK] Loaded {len(self.states)} pair states from {state_file_path}")
            except Exception as e:
                print(f"[ERROR] Failed to load states: {e}")
                self.states = {}
        else:
            print(f"[INFO] State file not found at {state_file_path}, starting fresh")
            self.states = {}
    
    def save_states(self):
        """Сохранение состояний в файл"""
        try:
            state_file_path = get_state_file_path()
            # Создаём директорию если её нет (для абсолютных путей)
            state_dir = os.path.dirname(state_file_path)
            if state_dir and not os.path.exists(state_dir):
                os.makedirs(state_dir, exist_ok=True)
            with open(state_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.states, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[ERROR] Failed to save states to {state_file_path}: {e}")
    
    def get_state(self, pair: str) -> dict:
        """Получить состояние пары"""
        if pair not in self.states:
            self.states[pair] = {
                "local_max": None,
                "local_max_time": None,  # Время установки локального максимума
                "local_min": None,
                "triggered_levels": [],
                "last_signal_time": None,
                "last_signal_level": None,  # Последний отправленный уровень (для защиты от дублей)
                "last_price": None,
                "last_update": time.time(),
                "initialized": False,  # Флаг инициализации (не отправлять сигналы сразу)
                "initialization_time": None
            }
        return self.states[pair]
    
    def update_state(self, pair: str, **kwargs):
        """Обновить состояние пары"""
        state = self.get_state(pair)
        state.update(kwargs)
        state["last_update"] = time.time()
        self.save_states()
    
    def reset_state(self, pair: str, new_price: float):
        """Сброс состояния пары"""
        print(f"[RESET] {pair}: new local max = {new_price}")
        current_time = time.time()
        self.states[pair] = {
            "local_max": new_price,
            "local_max_time": current_time,  # Время установки нового максимума
            "local_min": new_price,
            "triggered_levels": [],
            "last_signal_time": None,
            "last_signal_level": None,  # Сбрасываем последний отправленный уровень
            "last_price": new_price,
            "last_update": current_time,
            "initialized": True,  # После RESET считаем инициализированным
            "initialization_time": current_time
        }
        self.save_states()
    
    def check_local_max_age(self, pair: str, current_time: float) -> bool:
        """Проверить, не устарел ли локальный максимум (4 часа)"""
        state = self.get_state(pair)
        local_max_time = state.get("local_max_time")
        
        if local_max_time is None:
            return False
        
        from config import LOCAL_MAX_PERIOD
        age = current_time - local_max_time
        
        if age >= LOCAL_MAX_PERIOD:
            print(f"[RESET] {pair}: local max expired ({age/3600:.1f}h old)")
            return True
        
        return False
    
    def get_reset_percent_for_level(self, max_level: int) -> float:
        """Получить процент отскока для RESET в зависимости от максимального достигнутого уровня"""
        # Чем глубже падение, тем больший отскок нужен:
        # Level 1 (-8%): RESET на +3%
        # Level 2 (-12%): RESET на +4%
        # Level 3 (-16%): RESET на +5%
        # Level 4 (-20%): RESET на +6%
        # Level 5 (-24%): RESET на +7%
        reset_map = {
            1: 3.0,
            2: 4.0,
            3: 5.0,
            4: 6.0,
            5: 7.0
        }
        return reset_map.get(max_level, 3.0)  # По умолчанию 3% если уровни не сработали
    
    def should_reset(self, pair: str, current_price: float, current_time: float) -> bool:
        """Проверка условий для сброса состояния"""
        state = self.get_state(pair)
        
        # Условие 1: прошло 2 часа с последнего сигнала
        if state["last_signal_time"] is not None:
            from config import RESET_TIME
            if current_time - state["last_signal_time"] >= RESET_TIME:
                print(f"[RESET] {pair}: 2 hours since last signal")
                return True
        
        # Условие 2: цена выросла на нужный процент от локального минимума
        # Процент зависит от максимального достигнутого уровня падения
        if state["local_min"] is not None and state["local_min"] > 0:
            triggered_levels = state.get("triggered_levels", [])
            
            # Определяем максимальный достигнутый уровень (самый глубокий уровень падения)
            max_triggered_level = max(triggered_levels) if triggered_levels else 0
            
            # Получаем нужный процент отскока для RESET
            required_growth_percent = self.get_reset_percent_for_level(max_triggered_level)
            
            # Считаем фактический рост от минимума
            growth = ((current_price - state["local_min"]) / state["local_min"]) * 100
            
            if growth >= required_growth_percent:
                level_info = f" (max level={max_triggered_level}, required={required_growth_percent}%)" if max_triggered_level > 0 else ""
                print(f"[RESET] {pair}: +{growth:.2f}% growth from min{level_info}")
                return True
        
        return False
    
    def is_duplicate_signal(self, pair: str, level: int, current_time: float) -> bool:
        """Проверить, не является ли сигнал дубликатом
        
        Блокирует если:
        1. Уровень уже в triggered_levels
        2. Тот же уровень отправлялся менее 10 минут назад
        """
        state = self.get_state(pair)
        
        # Проверка 1: уровень уже сработал
        if level in state.get("triggered_levels", []):
            print(f"[DUPLICATE CHECK] {pair}: Level {level} already in triggered_levels")
            return True
        
        # Проверка 2: тот же уровень отправлялся недавно (защита от race condition)
        last_level = state.get("last_signal_level")
        last_time = state.get("last_signal_time")
        
        if last_level == level and last_time is not None:
            elapsed = current_time - last_time
            if elapsed < 600:  # 10 минут
                print(f"[DUPLICATE CHECK] {pair}: Level {level} was sent {elapsed:.0f}s ago (< 600s)")
                return True
        
        return False
    
    def add_triggered_level(self, pair: str, level: int, current_time: float):
        """Добавить сработавший уровень"""
        state = self.get_state(pair)
        if level not in state["triggered_levels"]:
            state["triggered_levels"].append(level)
            state["last_signal_time"] = current_time
            state["last_signal_level"] = level  # Сохраняем последний отправленный уровень
            # НЕМЕДЛЕННО сохраняем в файл
            self.save_states()
            print(f"[STATE SAVED] {pair}: Level {level} saved to triggered_levels, file updated")