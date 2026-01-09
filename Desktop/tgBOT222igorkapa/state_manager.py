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
    
    def load_states(self, silent: bool = False):
        """Загрузка состояний из файла
        
        Args:
            silent: Если True, не выводит сообщения (для перезагрузки между циклами)
        """
        state_file_path = get_state_file_path()
        if os.path.exists(state_file_path):
            try:
                with open(state_file_path, 'r', encoding='utf-8') as f:
                    loaded_states = json.load(f)
                    
                # КРИТИЧЕСКИ ВАЖНО: Полностью перезагружаем triggered_levels из файла
                # Это гарантирует синхронизацию между циклами
                for pair, state in loaded_states.items():
                    if pair in self.states:
                        # Полностью обновляем ключевые поля для защиты от дублей
                        self.states[pair]["triggered_levels"] = state.get("triggered_levels", [])
                        self.states[pair]["last_signal_time"] = state.get("last_signal_time")
                        self.states[pair]["last_signal_level"] = state.get("last_signal_level")
                    else:
                        # Новая пара - добавляем полностью
                        self.states[pair] = state
                
                if not silent:
                    print(f"[OK] Loaded {len(loaded_states)} pair states from {state_file_path}")
            except Exception as e:
                if not silent:
                    print(f"[ERROR] Failed to load states: {e}")
                # Не очищаем self.states при ошибке - сохраняем текущее состояние в памяти
        else:
            if not silent:
                print(f"[INFO] State file not found at {state_file_path}, starting fresh")
            # Не очищаем self.states если файла нет - может быть первая загрузка
    
    def save_states(self):
        """Сохранение состояний в файл с принудительной синхронизацией"""
        try:
            state_file_path = get_state_file_path()
            # Создаём директорию если её нет (для абсолютных путей)
            state_dir = os.path.dirname(state_file_path)
            if state_dir and not os.path.exists(state_dir):
                os.makedirs(state_dir, exist_ok=True)
            
            # Записываем во временный файл, потом переименовываем (атомарная операция)
            temp_file_path = state_file_path + ".tmp"
            with open(temp_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.states, f, indent=2, ensure_ascii=False)
                f.flush()  # Принудительно сбрасываем буфер в ОС
                os.fsync(f.fileno())  # Принудительно синхронизируем с диском
            
            # Атомарное переименование (защита от race condition)
            if os.path.exists(state_file_path):
                os.replace(temp_file_path, state_file_path)
            else:
                os.rename(temp_file_path, state_file_path)
                
        except Exception as e:
            print(f"[ERROR] Failed to save states to {state_file_path}: {e}")
            # Пытаемся удалить временный файл при ошибке
            try:
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
            except:
                pass
    
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
    
    def get_reset_percent_for_drop(self, max_drop_percent: float) -> float:
        """Получить процент отскока для RESET в зависимости от максимального падения
        
        Правила RESET:
        - если падение было −5% → RESET при росте +2%
        - если падение было −9% → RESET при росте +3%
        - если падение было −13% → RESET при росте +4%
        - если падение было −17% → RESET при росте +5%
        - если падение было −21% → RESET при росте +6%
        """
        if max_drop_percent >= -5.0:
            return 2.0  # Падение от 0% до -5% → RESET при +2%
        elif max_drop_percent >= -9.0:
            return 3.0  # Падение от -5% до -9% → RESET при +3%
        elif max_drop_percent >= -13.0:
            return 4.0  # Падение от -9% до -13% → RESET при +4%
        elif max_drop_percent >= -17.0:
            return 5.0  # Падение от -13% до -17% → RESET при +5%
        elif max_drop_percent >= -21.0:
            return 6.0  # Падение от -17% до -21% → RESET при +6%
        else:
            return 7.0  # Падение глубже -21% → RESET при +7%
    
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
        # Процент зависит от максимального падения (не уровня, а процента!)
        if state["local_min"] is not None and state["local_min"] > 0 and state["local_max"] is not None and state["local_max"] > 0:
            # Считаем максимальное падение от максимума до минимума
            max_drop_percent = ((state["local_min"] - state["local_max"]) / state["local_max"]) * 100
            
            # Получаем нужный процент отскока для RESET в зависимости от максимального падения
            required_growth_percent = self.get_reset_percent_for_drop(max_drop_percent)
            
            # Считаем фактический рост от минимума
            growth = ((current_price - state["local_min"]) / state["local_min"]) * 100
            
            if growth >= required_growth_percent:
                drop_info = f" (max drop={max_drop_percent:.2f}%, required={required_growth_percent}%)"
                print(f"[RESET] {pair}: +{growth:.2f}% growth from min{drop_info}")
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