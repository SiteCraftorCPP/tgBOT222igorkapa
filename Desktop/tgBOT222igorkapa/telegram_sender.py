import requests
from urllib.parse import quote
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


class TelegramSender:
    """Отправка сигналов в Telegram"""
    
    def __init__(self):
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
    
    def send_signals_batch(self, signals: list):
        """Отправить список сигналов одним сообщением"""
        if not signals:
            return
        
        try:
            # Формируем список сигналов в столбик
            signals_text = []
            
            for signal in signals:
                pair = signal["pair"]
                drop = signal["drop_percent"]
                
                # Реферальная ссылка для регистрации на Bit2Me
                buy_url = "https://bit2me.com/es/registro?prm=REFNAV25&utm_medium=app&utm_source=new_ref&utm_campaign=referidossnavidad25&mkt_kind=referral&code=OIA-CKO-CM5"
                
                # Форматируем пару: BTCEUR -> BTC/EUR
                formatted_pair = pair.replace("EUR", "") + "/EUR"
                
                # Формируем текст сигнала: 🚀 SOL/EUR | −11% | COMPRAR
                # drop уже отрицательный, используем длинный минус (U+2212)
                drop_abs = abs(drop)
                
                # Делаем COMPRAR кликабельной ссылкой
                signals_text.append(f"🚀 {formatted_pair} | −{drop_abs:.1f}% | [COMPRAR]({buy_url})")
            
            # Объединяем все сигналы
            message = "\n".join(signals_text)
            
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            
            response = requests.post(
                f"{self.base_url}/sendMessage",
                json=payload,
                timeout=3
            )
            response.raise_for_status()
            
            print(f"[BATCH SIGNALS SENT] {len(signals)} signals in one message")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to send batch signals: {e}")
            return False
    
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
