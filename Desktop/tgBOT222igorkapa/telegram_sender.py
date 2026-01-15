import requests
import time
import json
import os
from urllib.parse import quote
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


class TelegramSender:
    """Отправка сигналов в Telegram"""
    
    # Время блокировки дублей по (pair, level) - 10 минут (для защиты от race condition)
    # Одинаковые сообщения блокируются на 24 часа (проверка по тексту)
    DUPLICATE_BLOCK_TIME = 600  # Для (pair, level) - временная защита (10 минут)
    MESSAGE_BLOCK_TIME = 86400  # Для одинаковых сообщений - 24 часа
    
    def __init__(self):
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
    
        # КЭШ ОТПРАВЛЕННЫХ СИГНАЛОВ - последняя линия защиты от дублей
        # Формат: {"msg:текст": timestamp (блок на 24ч), (pair, level): timestamp (блок на 10мин)}
        self.cache_file = "sent_messages_cache.json"
        self.sent_signals_cache = self._load_cache()
    
    def _is_duplicate(self, pair: str, level: int, drop_percent: float = None, current_price: float = None) -> bool:
        """Проверить, не был ли этот сигнал уже отправлен
        
        Одинаковые сообщения блокируются на 24 часа.
        Если изменился уровень падения (процент) или цена, то это уже другое сообщение и оно пройдёт.
        """
        current_time = time.time()
        
        # Проверка 1: по тексту сообщения (ГЛАВНАЯ ПРОВЕРКА - блокирует одинаковые сообщения на 24 часа)
        # Если уровень падения или цена изменились, текст изменится, и сообщение пройдёт
        if drop_percent is not None and current_price is not None:
            # Формируем текст сообщения ТОЧНО так же, как в send_signals_batch
            formatted_pair = pair.replace("EUR", "") + "/EUR"
            drop_abs = abs(drop_percent)
            # ВАЖНО: Форматирование должно быть ИДЕНТИЧНЫМ с send_signals_batch!
            # Проверяем на None, <= 0, или очень маленькое значение (близко к 0)
            if current_price is None or current_price <= 0 or current_price < 0.0001:
                price_str = "N/A"
            else:
                price_str = f"{current_price:.4f}€" if current_price < 1 else f"{current_price:.2f}€"
            message_text = f"💎 {formatted_pair} | −{drop_abs:.1f}% | {price_str}"
            
            # Проверяем по тексту сообщения - если уже было, блокируем на 24 часа
            message_key = f"msg:{message_text}"
            print(f"[DUPLICATE CHECK] {pair}: checking message_text='{message_text}', cache_size={len(self.sent_signals_cache)}")
            
            if message_key in self.sent_signals_cache:
                cache_value = self.sent_signals_cache[message_key]
                print(f"[DUPLICATE CHECK] {pair}: FOUND in cache! cache_value={cache_value}")
                
                # Обрабатываем старые записи с float('inf') - конвертируем в timestamp
                if cache_value == float('inf'):
                    # Старые записи "навсегда" считаем как блокировку на 24 часа от текущего времени
                    # Но лучше просто разрешим их через 24 часа от времени создания
                    print(f"[DUPLICATE CHECK] {pair}: old 'inf' entry found, allowing after 24h check")
                    # Удаляем старую запись с 'inf' и разрешаем отправку
                    del self.sent_signals_cache[message_key]
                    print(f"[DUPLICATE CHECK] {pair}: NOT in cache (removed old 'inf'), will send")
                elif isinstance(cache_value, (int, float)):
                    elapsed = current_time - cache_value
                    if elapsed < self.MESSAGE_BLOCK_TIME:  # 24 часа
                        hours_left = (self.MESSAGE_BLOCK_TIME - elapsed) / 3600
                        print(f"[DUPLICATE BLOCKED] ❌ {pair}: ОДИНАКОВОЕ сообщение уже отправлено {elapsed/3600:.1f}ч назад (блок на {hours_left:.1f}ч): {message_text}")
                        return True
                    else:
                        # Время истекло, удаляем запись
                        del self.sent_signals_cache[message_key]
                        print(f"[DUPLICATE CHECK] {pair}: cache expired (>{self.MESSAGE_BLOCK_TIME/3600:.0f}h), will send")
            else:
                print(f"[DUPLICATE CHECK] {pair}: NOT in cache, will send")
        
        # Проверка 2: по ключу (pair, level) - временная защита от race condition (10 минут)
        key = (pair, level)
        if key in self.sent_signals_cache:
            last_sent = self.sent_signals_cache[key]
            elapsed = current_time - last_sent
            
            if elapsed < self.DUPLICATE_BLOCK_TIME:
                minutes = elapsed / 60
                print(f"[DUPLICATE BLOCKED] ❌ {pair} Level {level}: уже отправлен {minutes:.1f} мин назад (временная защита)")
                return True
        
        return False
    
    def _load_cache(self) -> dict:
        """Загрузить кэш отправленных сообщений из файла"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                    # Конвертируем ключи обратно (JSON не поддерживает tuple, сохраняем как строки)
                    result = {}
                    for k, v in cache.items():
                        if k.startswith("msg:"):
                            # Старые записи с 'inf' конвертируем в 0 (разрешаем сразу)
                            result[k] = 0 if v == 'inf' else v
                        elif k.startswith("tuple:"):
                            # Восстанавливаем tuple из строки "tuple:(pair,level)"
                            key_str = k.replace("tuple:", "")
                            try:
                                pair, level_str = key_str.strip("()").split(",")
                                level = int(level_str.strip())
                                result[(pair.strip("'\" "), level)] = v
                            except:
                                pass
                        else:
                            result[k] = v
                    print(f"[CACHE] Loaded {len(result)} entries from {self.cache_file}")
                    return result
            except Exception as e:
                print(f"[CACHE ERROR] Failed to load cache: {e}")
        return {}
    
    def _save_cache(self):
        """Сохранить кэш отправленных сообщений в файл"""
        try:
            # Конвертируем для JSON (tuple -> строка)
            cache_to_save = {}
            for k, v in self.sent_signals_cache.items():
                if isinstance(k, tuple):
                    cache_to_save[f"tuple:{k}"] = v
                elif isinstance(k, str):
                    # Сохраняем timestamp (не используем 'inf' больше)
                    cache_to_save[k] = v
                else:
                    cache_to_save[str(k)] = v
            
            temp_file = self.cache_file + ".tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(cache_to_save, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            
            if os.path.exists(self.cache_file):
                os.replace(temp_file, self.cache_file)
            else:
                os.rename(temp_file, self.cache_file)
        except Exception as e:
            print(f"[CACHE ERROR] Failed to save cache: {e}")
    
    def clear_cache_for_pair(self, pair: str):
        """Очистить кэш сообщений для конкретной пары (вызывается при RESET)"""
        removed_count = 0
        
        # Удаляем все записи по ключу (pair, level)
        keys_to_remove = [k for k in self.sent_signals_cache.keys() 
                         if isinstance(k, tuple) and k[0] == pair]
        for k in keys_to_remove:
            del self.sent_signals_cache[k]
            removed_count += 1
        
        # Удаляем все записи по тексту сообщения для этой пары
        formatted_pair = pair.replace("EUR", "") + "/EUR"
        message_keys_to_remove = [k for k in self.sent_signals_cache.keys() 
                                  if isinstance(k, str) and k.startswith("msg:") 
                                  and formatted_pair in k]
        for k in message_keys_to_remove:
            del self.sent_signals_cache[k]
            removed_count += 1
        
        if removed_count > 0:
            print(f"[CACHE CLEARED] {pair}: removed {removed_count} cache entries (RESET)")
            self._save_cache()
    
    def _mark_as_sent(self, pair: str, level: int, message_text: str = None):
        """Отметить сигнал как отправленный
        
        Args:
            pair: Название пары
            level: Уровень сигнала
            message_text: Текст сообщения (для блокировки одинаковых сообщений на 24 часа)
        """
        current_time = time.time()
        
        # Сохраняем по ключу (pair, level) - временная защита (10 минут)
        key = (pair, level)
        self.sent_signals_cache[key] = current_time
        
        # Сохраняем по тексту сообщения - БЛОКИРОВКА НА 24 ЧАСА
        if message_text:
            message_key = f"msg:{message_text}"
            # Сохраняем timestamp для блокировки на 24 часа
            self.sent_signals_cache[message_key] = current_time
            # НЕМЕДЛЕННО сохраняем в файл
            self._save_cache()
        
        # Очистка старых записей по (pair, level) (старше 1 часа) - только для временных записей
        # Ключи могут быть строками (начинающимися с "msg:") или tuple (для (pair, level))
        expired_keys = [k for k, v in self.sent_signals_cache.items() 
                       if isinstance(k, tuple) and isinstance(v, (int, float)) and v != float('inf') and current_time - v > 3600]
        for k in expired_keys:
            del self.sent_signals_cache[k]
        
        # Ограничиваем размер кэша сообщений (максимум 5000 записей)
        # Удаляем только те, что старше 24 часов
        # Ключи могут быть строками или кортежами - проверяем тип
        message_keys = [k for k in self.sent_signals_cache.keys() if isinstance(k, str) and k.startswith("msg:")]
        if len(message_keys) > 5000:
            current_time = time.time()
            regular_message_keys = [k for k in message_keys 
                                   if isinstance(self.sent_signals_cache[k], (int, float)) 
                                   and current_time - self.sent_signals_cache[k] > self.MESSAGE_BLOCK_TIME]
            if len(regular_message_keys) > 0:
                sorted_items = sorted([(k, self.sent_signals_cache[k]) for k in regular_message_keys], 
                                     key=lambda x: x[1])
                # Удаляем только устаревшие записи (старше 24 часов)
                for k, _ in sorted_items:
                    if current_time - _ > self.MESSAGE_BLOCK_TIME:
                        del self.sent_signals_cache[k]
            # Ограничиваем размер кэша (если всё ещё много, удаляем самые старые)
            remaining_message_keys = [k for k in self.sent_signals_cache.keys() if isinstance(k, str) and k.startswith("msg:")]
            if len(remaining_message_keys) > 5000:
                sorted_all = sorted([(k, self.sent_signals_cache[k]) for k in remaining_message_keys], 
                                   key=lambda x: x[1])
                # Удаляем самые старые записи
                for k, _ in sorted_all[:len(remaining_message_keys) - 5000]:
                    del self.sent_signals_cache[k]
    
    def send_signals_batch(self, signals: list, market_monitor=None):
        """Отправить список сигналов - каждый отдельным сообщением с инлайн кнопкой
        
        Args:
            signals: Список сигналов для отправки
            market_monitor: Опционально, объект MarketMonitor для получения актуальной цены
        """
        if not signals:
            return
        
        sent_count = 0
        failed_count = 0
        blocked_count = 0
        
        # Отправляем каждый сигнал отдельным сообщением
        for signal in signals:
            try:
                pair = signal["pair"]
                level = signal.get("level", 0)
                drop = signal["drop_percent"]
                current_price = signal.get("current_price")
                
                # КРИТИЧЕСКИ ВАЖНО: Получаем АКТУАЛЬНУЮ цену из кэша перед отправкой!
                # Цена могла измениться между созданием сигнала и отправкой
                if market_monitor is not None:
                    actual_price = market_monitor.get_current_price(pair)
                    if actual_price is not None and actual_price > 0:
                        current_price = actual_price
                        print(f"[TELEGRAM] {pair}: Updated price from {signal.get('current_price', 'N/A')} to {actual_price:.4f}")
                
                print(f"[TELEGRAM] Processing signal: {pair}, level={level}, drop={drop:.2f}%, price={current_price}")
                
                # ПРОВЕРКА ДУБЛИКАТА (последняя линия защиты) - проверяем по ключу И по тексту сообщения
                if self._is_duplicate(pair, level, drop, current_price):
                    print(f"[TELEGRAM BLOCKED] {pair} Level {level}: blocked by _is_duplicate() cache")
                    blocked_count += 1
                    continue
                
                print(f"[TELEGRAM] {pair} Level {level}: passed duplicate check, sending...")
                
                # Проверяем что цена передана
                # Проверяем на None, <= 0, или очень маленькое значение (близко к 0)
                if current_price is None or current_price <= 0 or current_price < 0.0001:
                    print(f"[WARNING] {pair}: current_price not provided or invalid ({current_price}), skipping price in message")
                    price_str = "N/A"
                else:
                    # Форматируем цену: если < 1, показываем 4 знака после запятой, иначе 2
                    price_str = f"{current_price:.4f}€" if current_price < 1 else f"{current_price:.2f}€"
                
                # Форматируем пару: BTCEUR -> BTC/EUR
                formatted_pair = pair.replace("EUR", "") + "/EUR"
                
                # Формируем текст сигнала: 💎 FARTCOIN/EUR | −4.6% | 0.0874€
                # drop уже отрицательный, используем длинный минус (U+2212)
                drop_abs = abs(drop)
                message = f"💎 {formatted_pair} | −{drop_abs:.1f}% | {price_str}"
                
                # Создаём инлайн кнопку для этого сигнала
                buy_url = "https://now.bit2me.com/tradingmegabot"
                
                payload = {
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": True,
                    "reply_markup": {
                        "inline_keyboard": [[{
                            "text": "🚀 COMPRAR + 20€ GRATIS",
                            "url": buy_url
                        }]]
                    }
                }
                
                print(f"[TELEGRAM] Sending to {self.chat_id}: {message}")
                response = requests.post(
                    f"{self.base_url}/sendMessage",
                    json=payload,
                    timeout=3
                )
                
                print(f"[TELEGRAM] Response status: {response.status_code}")
                
                if response.status_code != 200:
                    error_text = response.text
                    print(f"[TELEGRAM ERROR] HTTP {response.status_code}: {error_text}")
                    raise Exception(f"HTTP {response.status_code}: {error_text}")
                
                result = response.json()
                if not result.get("ok"):
                    error_desc = result.get("description", "Unknown error")
                    print(f"[TELEGRAM ERROR] API returned error: {error_desc}")
                    raise Exception(f"API error: {error_desc}")
                
                # ОТМЕЧАЕМ КАК ОТПРАВЛЕННЫЙ (для защиты от дублей)
                # Сохраняем и по ключу (pair, level), и по тексту сообщения
                self._mark_as_sent(pair, level, message)
                
                sent_count += 1
                message_id = result.get("result", {}).get("message_id", "N/A")
                print(f"[SIGNAL SENT] ✅ {formatted_pair}: {message} | Message ID: {message_id}")
                
            except Exception as e:
                failed_count += 1
                print(f"[ERROR] ❌ Failed to send signal for {pair} Level {level}: {e}")
                import traceback
                print(f"[ERROR] Traceback:")
                traceback.print_exc()
        
        if sent_count > 0 or blocked_count > 0:
            print(f"[BATCH COMPLETE] Sent {sent_count}/{len(signals)} signals (failed: {failed_count}, blocked duplicates: {blocked_count})")
        
        return sent_count > 0
    
    def send_signal(self, pair: str, drop_percent: float):
        """Отправить одиночный BUY-сигнал (deprecated, используй send_signals_batch)"""
        return self.send_signals_batch([{"pair": pair, "drop_percent": drop_percent}])
    
    def send_status(self, message: str):
        """Отправить статусное сообщение"""
        try:
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            
            response = requests.post(
                f"{self.base_url}/sendMessage",
                json=payload,
                timeout=3
            )
            response.raise_for_status()
            result = response.json()
            if result.get("ok"):
                print(f"[STATUS SENT] Status message sent to chat {self.chat_id}")
                return True
            else:
                error_desc = result.get("description", "Unknown error")
                print(f"[ERROR] Failed to send status: {error_desc}")
                return False
        except Exception as e:
            error_msg = str(e).encode('ascii', errors='ignore').decode('ascii')
            print(f"[ERROR] Failed to send status: {error_msg}")
            return False
    
    def send_promo_message(self):
        """Отправить промо-сообщение с кнопкой"""
        try:
            message = """🎉 Gana 20€ GRATIS con Bit2Me

✨ Oferta exclusiva para nuestra comunidad

Regístrate ahora, haz tu primera compra de +100€ y recibe 20€ de regalo 💸

⚡️ Rápido · Fácil · Seguro"""
            
            buy_url = "https://now.bit2me.com/tradingmegabot"
            
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
                "reply_markup": {
                    "inline_keyboard": [[{
                        "text": "👉 REGÍSTRATE YA 🚀",
                        "url": buy_url
                    }]]
                }
            }
            
            response = requests.post(
                f"{self.base_url}/sendMessage",
                json=payload,
                timeout=3
            )
            response.raise_for_status()
            result = response.json()
            if result.get("ok"):
                message_id = result.get("result", {}).get("message_id")
                print(f"[PROMO SENT] Promo message sent to chat {self.chat_id}, message_id={message_id}")
                return message_id
            else:
                error_desc = result.get("description", "Unknown error")
                print(f"[ERROR] Failed to send promo: {error_desc}")
                return None
        except Exception as e:
            error_msg = str(e).encode('ascii', errors='ignore').decode('ascii')
            print(f"[ERROR] Failed to send promo: {error_msg}")
            return None
    
    def delete_message(self, message_id: int):
        """Удалить сообщение по message_id"""
        try:
            payload = {
                "chat_id": self.chat_id,
                "message_id": message_id
            }
            
            response = requests.post(
                f"{self.base_url}/deleteMessage",
                json=payload,
                timeout=3
            )
            response.raise_for_status()
            result = response.json()
            if result.get("ok"):
                print(f"[MESSAGE DELETED] Message {message_id} deleted from chat {self.chat_id}")
                return True
            else:
                error_desc = result.get("description", "Unknown error")
                print(f"[ERROR] Failed to delete message {message_id}: {error_desc}")
                return False
        except Exception as e:
            error_msg = str(e).encode('ascii', errors='ignore').decode('ascii')
            print(f"[ERROR] Failed to delete message {message_id}: {error_msg}")
            return False
