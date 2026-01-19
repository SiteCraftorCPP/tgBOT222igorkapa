import requests
import time
from typing import List, Dict, Optional
from config import BIT2ME_BASE_URL, BIT2ME_API_KEY, MONITORED_PAIRS


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
        
        print(f"[OK] Got {len(pairs_data)} COIN/EUR pairs from Bit2Me API (will filter to MONITORED_PAIRS)")
        return pairs_data
    
    def convert_pair_to_internal(self, pair_str: str) -> str:
        """Конвертировать BTC/EUR -> BTCEUR"""
        return pair_str.replace("/", "").replace("_", "")
    
    def convert_pair_to_bit2me(self, internal_pair: str) -> str:
        """Конвертировать BTCEUR -> BTC_EUR"""
        # Ищем последние 3 символа "EUR" и заменяем на "_EUR"
        if internal_pair.endswith("EUR"):
            coin = internal_pair[:-3]
            return f"{coin}_EUR"
        return internal_pair
    
    def filter_pairs(self) -> List[str]:
        """Получить пары из заданного списка MONITORED_PAIRS"""
        # Получаем все доступные пары с API
        pairs_data = self.get_all_eur_pairs()
        
        if not pairs_data:
            print("[WARN] Could not get pairs from API, using fallback")
            # Конвертируем MONITORED_PAIRS в внутренний формат
            fallback = [self.convert_pair_to_internal(p) for p in MONITORED_PAIRS]
            return fallback[:5]  # Только первые 5 как fallback
        
        # Создаём словарь для быстрого поиска: BTCEUR -> {symbol, bit2me_symbol, ...}
        available_pairs_dict = {p["symbol"]: p for p in pairs_data}
        
        # Конвертируем MONITORED_PAIRS в внутренний формат и фильтруем
        filtered = []
        symbol_mapping_dict = {}
        missing_pairs = []
        
        for pair_str in MONITORED_PAIRS:
            internal_pair = self.convert_pair_to_internal(pair_str)
        
            # Проверяем, есть ли пара в данных API
            if internal_pair in available_pairs_dict:
                filtered.append(internal_pair)
                symbol_mapping_dict[internal_pair] = available_pairs_dict[internal_pair]["bit2me_symbol"]
            else:
                missing_pairs.append(pair_str)
        
        print(f"[OK] Selected {len(filtered)}/{len(MONITORED_PAIRS)} pairs from configured list")
        if len(filtered) > 0:
            print(f"     First 10: {', '.join(filtered[:10])}")
        
        if missing_pairs:
            print(f"[WARNING] {len(missing_pairs)} pairs not found in API:")
            # Показываем все отсутствующие пары, по 10 в строке
            for i in range(0, len(missing_pairs), 10):
                chunk = missing_pairs[i:i+10]
                print(f"     Missing: {', '.join(chunk)}")
        
        # Сохраняем маппинг для конвертации обратно в Bit2Me формат
        self.symbol_mapping = symbol_mapping_dict
        
        self.available_pairs = filtered
        return filtered
    
    def refresh_prices(self) -> bool:
        """Обновить кэш цен только для пар из MONITORED_PAIRS"""
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
        
        # Получаем список пар для мониторинга (только из MONITORED_PAIRS)
        monitored_pairs_set = set(self.available_pairs) if hasattr(self, 'available_pairs') and self.available_pairs else set()
        
        # Очищаем кэш для новых цен
        self.prices_cache = {}
        changes_count = 0
        same_count = 0
        new_pairs = 0
        
        # Bit2Me формат: {"BTC_EUR": {"last_price": ...}, ...}
        processed_count = 0
        skipped_no_price = 0
        skipped_invalid = 0
        skipped_not_monitored = 0
        
        for bit2me_symbol, info in data.items():
            if bit2me_symbol.endswith("_EUR") and isinstance(info, dict):
                symbol = self.convert_pair_format(bit2me_symbol)
                
                # КРИТИЧЕСКИ ВАЖНО: обрабатываем только пары из MONITORED_PAIRS
                if monitored_pairs_set and symbol not in monitored_pairs_set:
                    skipped_not_monitored += 1
                    continue
                
                last_price = info.get("last_price")
                
                if last_price is not None:
                    try:
                        new_price = float(last_price)
                        if new_price > 0:  # Проверяем, что цена валидна
                            self.prices_cache[symbol] = new_price
                            processed_count += 1
                            
                            # Считаем изменения (используем относительное сравнение для точности)
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
                        else:
                            skipped_no_price += 1
                    except (ValueError, TypeError):
                        skipped_invalid += 1
        
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
            elif changes_count < 5 and total_checked > 20:
                print(f"[WARNING] Very few price changes ({changes_count}/{total_checked} monitored pairs). Market might be low volatility or API has caching issues.")
        else:
            stats["change_pct"] = 0
            if new_pairs > 0:
                # Первый цикл или все пары новые
                pass
        
        # ДИАГНОСТИКА: показываем, сколько пар обработано (только из MONITORED_PAIRS)
        if processed_count == 0:
            print(f"[ERROR] ZERO monitored pairs processed from API! Skipped: no_price={skipped_no_price}, invalid={skipped_invalid}, not_monitored={skipped_not_monitored}")
        elif len(self.prices_cache) < len(monitored_pairs_set) * 0.8:  # Меньше 80% от ожидаемого количества
            print(f"[WARNING] Only {len(self.prices_cache)}/{len(monitored_pairs_set)} monitored pairs in cache! Processed: {processed_count}, Skipped: no_price={skipped_no_price}, invalid={skipped_invalid}")
        
        if len(self.prices_cache) > 0:
            return stats
        else:
            return False
    
    def get_current_price(self, pair: str) -> Optional[float]:
        """Получить текущую цену пары из кэша"""
        return self.prices_cache.get(pair)
    
