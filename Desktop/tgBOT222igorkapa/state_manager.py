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
                        self.states[pair]["last_signal_drop_percent"] = state.get("last_signal_drop_percent")
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
                "local_max_time": None,
                "local_min": None,
                "last_signal_price": None,  # Цена последнего сигнала (для расчёта следующего -2%)
                "last_signal_time": None,
                "last_signal_level": None,  # Номер последнего сигнала (1, 2, 3, ...)
                "last_signal_drop_percent": None,  # Процент падения от local_max при последнем сигнале
                "last_price": None,
                "last_update": time.time(),
                "initialized": False,
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
        """Сброс состояния пары - обнуляет всё кроме local_max"""
        current_time = time.time()
        old_state = self.get_state(pair)
        
        # Устанавливаем новый local_max (текущая цена)
        print(f"[RESET] {pair}: Setting new local_max={new_price:.4f}")
        
        self.states[pair] = {
            "local_max": new_price,
            "local_max_time": current_time,
            "local_min": new_price,
            "last_signal_price": None,  # Обнуляем цену последнего сигнала
            "last_signal_time": None,
            "last_signal_level": None,
            "last_signal_drop_percent": None,  # Обнуляем процент падения последнего сигнала
            "last_price": new_price,
            "last_update": current_time,
            "initialized": True,
            "initialization_time": current_time
        }
        self.save_states()
    
    
    def should_reset(self, pair: str, current_price: float, current_time: float) -> bool:
        """Проверка условий для сброса состояния
        
        RESET происходит если:
        1. Прошло 24 часа с последнего сигнала
        2. Цена выросла на +7% от локального минимума
        """
        state = self.get_state(pair)
        
        # Условие 1: прошло 24 часа с последнего сигнала
        if state["last_signal_time"] is not None:
            from config import RESET_TIME
            elapsed = current_time - state["last_signal_time"]
            if elapsed >= RESET_TIME:
                print(f"[RESET] {pair}: 24 hours ({elapsed/3600:.1f}h) since last signal")
                return True
        
        # Условие 2: цена выросла на +7% от локального минимума
        if state["local_min"] is not None and state["local_min"] > 0:
            from config import RESET_GROWTH_PERCENT
            growth = ((current_price - state["local_min"]) / state["local_min"]) * 100
            
            if growth >= RESET_GROWTH_PERCENT:
                print(f"[RESET] {pair}: +{growth:.2f}% growth from min (required: {RESET_GROWTH_PERCENT}%)")
                return True
        
        return False
    
    def update_signal(self, pair: str, level: int, signal_price: float, current_time: float, drop_percent: float):
        """Обновить информацию о последнем сигнале
        
        Args:
            pair: Торговая пара
            level: Номер уровня сигнала
            signal_price: Цена при сигнале
            current_time: Время сигнала
            drop_percent: Процент падения от local_max при этом сигнале
        """
        state = self.get_state(pair)
        state["last_signal_level"] = level
        state["last_signal_price"] = signal_price
        state["last_signal_time"] = current_time
        state["last_signal_drop_percent"] = drop_percent  # Сохраняем процент падения
        self.save_states()
        print(f"[STATE SAVED] {pair}: Level {level} saved, signal_price={signal_price:.4f}, drop={drop_percent:.2f}%")