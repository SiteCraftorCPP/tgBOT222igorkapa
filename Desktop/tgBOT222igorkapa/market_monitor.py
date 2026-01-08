import requests
import time
from typing import List, Dict, Optional
from config import BIT2ME_BASE_URL, BIT2ME_API_KEY, LEVELS


class MarketMonitor:
    """Мониторинг рынка криптовалют через Bit2Me API"""
    
    def __init__(self):
        self.headers = {
            "X-Bit2Me-Key": BIT2ME_API_KEY,
            "Content-Type": "application/json"
        }
        self.available_pairs = []
        self.prices_cache = {}  # Кэш цен для текущего цикла
    
    def fetch_all_tickers(self) -> Dict:
        """Получить все тикеры с Bit2Me одним запросом"""
        try:
            # Добавляем timestamp для предотвращения кэширования
            import time
            # Добавляем timestamp для предотвращения кэширования
            url = f"{BIT2ME_BASE_URL}/ticker?t={int(time.time())}"
            response = requests.get(url, headers=self.headers, timeout=5)
            response.raise_for_status()
            
            # Проверяем что ответ не пустой
            if not response.text:
                print(f"[ERROR] API returned empty response. Status: {response.status_code}")
                return {}
            
            # Проверяем что это JSON
            try:
                data = response.json()
                if isinstance(data, dict) and len(data) > 0:
                    return data
                else:
                    print(f"[ERROR] API returned invalid data format. Response preview: {response.text[:200]}")
                    return {}
            except ValueError as json_err:
                print(f"[ERROR] API did not return valid JSON. Status: {response.status_code}")
                print(f"[ERROR] Response preview: {response.text[:200]}")
                print(f"[ERROR] JSON error: {json_err}")
                return {}
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Network error fetching tickers: {e}")
            return {}
        except Exception as e:
            print(f"[ERROR] Failed to fetch tickers: {e}")
            return {}
    
    def convert_pair_format(self, bit2me_pair: str) -> str:
        """Конвертировать BTC_EUR -> BTCEUR"""
        return bit2me_pair.replace("_", "")
    
    def get_all_eur_pairs(self) -> List[Dict]:
        """Получить все пары COIN/EUR с данными о объёме"""
        data = self.fetch_all_tickers()
        
        if not data:
            return []
        
        pairs_data = []
        
        # Bit2Me формат: {"BTC_EUR": {"last_price": ..., "quote_volume": ..., ...}, ...}
        for bit2me_symbol, info in data.items():
            if bit2me_symbol.endswith("_EUR") and isinstance(info, dict):
                # Конвертируем BTC_EUR -> BTCEUR
                symbol = self.convert_pair_format(bit2me_symbol)
                last_price = float(info.get("last_price", 0) or 0)
                quote_volume = float(info.get("quote_volume", 0) or 0)
                is_frozen = info.get("isFrozen", 0)
                
                # Пропускаем замороженные пары
                if is_frozen == 0 and last_price > 0:
                    pairs_data.append({
                        "symbol": symbol,
                        "bit2me_symbol": bit2me_symbol,  # Сохраняем оригинальный формат
                        "last": last_price,
                        "volume": quote_volume  # Объём в EUR
                    })
        
        print(f"[OK] Got {len(pairs_data)} COIN/EUR pairs from Bit2Me")
        return pairs_data
    
    def filter_pairs(self) -> List[str]:
        """Получить TOP пары по объёму торгов (ТОП-300)"""
        pairs_data = self.get_all_eur_pairs()
        
        if not pairs_data:
            print("[WARN] Could not get pairs, using fallback")
            return ["BTCEUR", "ETHEUR", "BNBEUR", "XRPEUR", "ADAEUR"]
        
        # Сортируем по объёму торгов в EUR
        sorted_pairs = sorted(
            pairs_data,
            key=lambda x: x["volume"],
            reverse=True
        )
        
        # Берём ТОП-300 (или сколько есть)
        top_pairs = sorted_pairs[:300]
        filtered = [p["symbol"] for p in top_pairs]
        
        print(f"[OK] Selected {len(filtered)} top pairs by volume")
        if len(filtered) > 0:
            print(f"     Top 10: {', '.join(filtered[:10])}")
        
        # Сохраняем маппинг для конвертации обратно в Bit2Me формат
        self.symbol_mapping = {p["symbol"]: p["bit2me_symbol"] for p in top_pairs}
        
        self.available_pairs = filtered
        return filtered
    
    def refresh_prices(self) -> bool:
        """Обновить кэш цен (один запрос на все пары)"""
        # Сохраняем старый кэш ДО очистки
        old_cache = {}
        if hasattr(self, 'prices_cache') and isinstance(self.prices_cache, dict):
            old_cache = self.prices_cache.copy()
        
        import time
        fetch_start = time.time()
        data = self.fetch_all_tickers()
        fetch_time = time.time() - fetch_start
        
        if not data or not isinstance(data, dict):
            print(f"[ERROR] API returned invalid data (fetch time: {fetch_time:.2f}s)")
            return False
        
        # Очищаем кэш для новых цен
        self.prices_cache = {}
        changes_count = 0
        same_count = 0
        new_pairs = 0
        
        # Bit2Me формат: {"BTC_EUR": {"last_price": ...}, ...}
        processed_count = 0
        skipped_no_price = 0
        skipped_invalid = 0
        
        for bit2me_symbol, info in data.items():
            if bit2me_symbol.endswith("_EUR") and isinstance(info, dict):
                symbol = self.convert_pair_format(bit2me_symbol)
                last_price = info.get("last_price")
                
                if last_price is not None:
                    try:
                        new_price = float(last_price)
                        if new_price > 0:  # Проверяем, что цена валидна
                            self.prices_cache[symbol] = new_price
                            processed_count += 1
                        else:
                            skipped_no_price += 1
                    except (ValueError, TypeError):
                        skipped_invalid += 1
                        
                        # ПРОВЕРКА: считаем изменения (используем относительное сравнение для точности)
                        if symbol in old_cache:
                            old_price = old_cache[symbol]
                            # Считаем изменение относительно старой цены (в процентах)
                            if old_price > 0:
                                change_pct = abs((new_price - old_price) / old_price) * 100
                                if change_pct > 0.0001:  # Изменение больше 0.0001% (очень маленький порог)
                                    changes_count += 1
                                else:
                                    same_count += 1
                            else:
                                if abs(old_price - new_price) > 0.00000001:
                                    changes_count += 1
                                else:
                                    same_count += 1
                        else:
                            # Новая пара (не было в предыдущем кэше)
                            new_pairs += 1
                    except (ValueError, TypeError):
                        pass
        
        # Собираем статистику для возврата
        total_checked = changes_count + same_count
        stats = {
            "changed": changes_count,
            "same": same_count,
            "new": new_pairs,
            "total": len(self.prices_cache),
            "fetch_time": fetch_time
        }
        
        if total_checked > 0:
            change_percent = (changes_count / total_checked) * 100
            stats["change_pct"] = change_percent
            
            # Логируем только предупреждения, основную статистику выведем в bot.py
            if changes_count == 0 and same_count > 0:
                print(f"[WARNING] API returned ZERO price changes! All {same_count} pairs have identical prices from previous cycle.")
                print(f"[WARNING] Possible causes: API caching, frozen market, or API not updating data.")
            elif changes_count < 10 and total_checked > 100:
                print(f"[WARNING] Very few price changes ({changes_count}/{total_checked}). Market might be low volatility or API has caching issues.")
        else:
            stats["change_pct"] = 0
            if new_pairs > 0:
                # Первый цикл или все пары новые
                pass
        
        # ДИАГНОСТИКА: показываем, сколько пар обработано
        if processed_count == 0:
            print(f"[ERROR] ZERO pairs processed from API! Skipped: no_price={skipped_no_price}, invalid={skipped_invalid}")
        elif len(self.prices_cache) < 100:
            print(f"[WARNING] Only {len(self.prices_cache)} pairs in cache! Processed: {processed_count}, Skipped: no_price={skipped_no_price}, invalid={skipped_invalid}")
        
        if len(self.prices_cache) > 0:
            return stats
        else:
            return False
    
    def get_current_price(self, pair: str) -> Optional[float]:
        """Получить текущую цену пары из кэша"""
        return self.prices_cache.get(pair)
    
    def check_levels(self, pair: str, current_price: float, local_max: float, triggered_levels: List[int]) -> Optional[Dict]:
        """Проверить, не пересечён ли новый уровень падения
        
        Args:
            pair: Название пары
            current_price: Текущая цена
            local_max: Локальный максимум
            triggered_levels: Список уже сработавших уровней
        """
        if local_max is None or local_max == 0:
            return None
        
        drop_percent = ((current_price - local_max) / local_max) * 100
        
        for level_info in LEVELS:
            level = level_info["level"]
            threshold = level_info["drop"]
            
            # Если уровень уже сработал, пропускаем
            if level in triggered_levels:
                continue
            
            # Если падение достигло этого уровня - возвращаем сигнал
            if drop_percent <= threshold:
                return {
                    "level": level,
                    "drop_percent": drop_percent,
                    "current_price": current_price,
                    "local_max": local_max
                }
        
        return None
