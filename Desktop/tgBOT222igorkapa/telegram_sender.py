import requests
import time
from urllib.parse import quote
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


class TelegramSender:
    """Отправка сигналов в Telegram"""
    
    # Время блокировки дублей (в секундах) - 10 минут
    DUPLICATE_BLOCK_TIME = 600
    
    def __init__(self):
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        
        # КЭШ ОТПРАВЛЕННЫХ СИГНАЛОВ - последняя линия защиты от дублей
        # Формат: {(pair, level): timestamp}
        self.sent_signals_cache = {}
    
    def _is_duplicate(self, pair: str, level: int) -> bool:
        """Проверить, не был ли этот сигнал уже отправлен недавно"""
        key = (pair, level)
        current_time = time.time()
        
        if key in self.sent_signals_cache:
            last_sent = self.sent_signals_cache[key]
            elapsed = current_time - last_sent
            
            if elapsed < self.DUPLICATE_BLOCK_TIME:
                minutes = elapsed / 60
                print(f"[DUPLICATE BLOCKED] {pair} Level {level}: уже отправлен {minutes:.1f} мин назад (блок на {self.DUPLICATE_BLOCK_TIME/60:.0f} мин)")
                return True
        
        return False
    
    def _mark_as_sent(self, pair: str, level: int):
        """Отметить сигнал как отправленный"""
        key = (pair, level)
        self.sent_signals_cache[key] = time.time()
        
        # Очистка старых записей (старше 1 часа)
        current_time = time.time()
        expired_keys = [k for k, v in self.sent_signals_cache.items() if current_time - v > 3600]
        for k in expired_keys:
            del self.sent_signals_cache[k]
    
    def send_signals_batch(self, signals: list):
        """Отправить список сигналов - каждый отдельным сообщением с инлайн кнопкой"""
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
                
                # ПРОВЕРКА ДУБЛИКАТА (последняя линия защиты)
                if self._is_duplicate(pair, level):
                    blocked_count += 1
                    continue
                
                # Проверяем что цена передана
                if current_price is None or current_price <= 0:
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
                coin = pair.replace("EUR", "").lower()
                buy_url = f"https://bit2me.com/es/precio/{coin}"
                
                payload = {
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": True,
                    "reply_markup": {
                        "inline_keyboard": [[{
                            "text": "🚀 COMPRAR",
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
                
                # ОТМЕЧАЕМ КАК ОТПРАВЛЕННЫЙ (для защиты от дублей)
                self._mark_as_sent(pair, level)
                
                sent_count += 1
                print(f"[SIGNAL SENT] {formatted_pair}: {message}")
                
            except Exception as e:
                failed_count += 1
                print(f"[ERROR] Failed to send signal for {pair}: {e}")
        
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
            return True
        except Exception as e:
            print(f"[ERROR] Failed to send status: {e}")
            return False
