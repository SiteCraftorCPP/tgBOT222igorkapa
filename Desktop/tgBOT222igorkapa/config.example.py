# Конфигурация бота (ШАБЛОН)
# 
# ИНСТРУКЦИЯ:
# 1. Скопируйте этот файл в config.py
# 2. Замените значения на свои
# 3. НЕ коммитьте config.py в Git!

# ============================================
# ОБЯЗАТЕЛЬНЫЕ ПАРАМЕТРЫ
# ============================================

# Telegram Bot токен (получить у @BotFather)
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

# Chat ID канала/группы (можно узнать через @getmyid_bot)
TELEGRAM_CHAT_ID = "-1003623062179"

# Bit2Me API ключ (получить на bit2me.com)
BIT2ME_API_KEY = "YOUR_BIT2ME_API_KEY_HERE"

# ============================================
# ПАРАМЕТРЫ МОНИТОРИНГА
# ============================================

# Интервал проверки рынка (в секундах)
CHECK_INTERVAL = 60

# ============================================
# НОВАЯ ЛОГИКА СИГНАЛОВ
# ============================================
# Первый сигнал: -8% от максимума
# Следующие сигналы: каждые -2% от цены последнего сигнала

FIRST_SIGNAL_DROP = -8.0  # Первый сигнал при -8% от максимума
NEXT_SIGNAL_DROP = -2.0   # Каждый следующий сигнал при -2% от цены последнего сигнала

# ============================================
# RESET ЛОГИКА
# ============================================
# RESET происходит если:
# 1. Прошло 24 часа с последнего сигнала
# 2. Цена выросла на +7% от локального минимума

RESET_TIME = 24 * 3600  # 24 часа с последнего сигнала
RESET_GROWTH_PERCENT = 7.0  # Рост на 7% от минимума для сброса

# ============================================
# ФАЙЛЫ И API
# ============================================

# Файл для сохранения состояний пар
STATE_FILE = "pairs_state.json"

# API endpoints (не менять)
BIT2ME_BASE_URL = "https://gateway.bit2me.com/v1/trading"

# Ссылка для покупки на Bit2Me
BUY_LINK_TEMPLATE = "https://bit2me.com/es/precio/{coin}"

# ============================================
# СПИСОК ПАР ДЛЯ МОНИТОРИНГА
# ============================================
# Формат: "COIN/EUR" (например, "BTC/EUR")
# Бот будет мониторить только пары из этого списка
# Пары должны быть доступны на Bit2Me бирже

MONITORED_PAIRS = [
    "BTC/EUR", "ETH/EUR", "BNB/EUR", "XRP/EUR", "SOL/EUR", "ADA/EUR",
    "DOGE/EUR", "DOT/EUR", "LINK/EUR", "AVAX/EUR", "TRX/EUR", "LTC/EUR",
    "BCH/EUR", "XLM/EUR", "ATOM/EUR", "NEAR/EUR", "FIL/EUR", "ETC/EUR",
    "UNI/EUR", "AAVE/EUR", "CRV/EUR", "RUNE/EUR", "GRT/EUR", "ALGO/EUR",
    "SAND/EUR", "MANA/EUR", "ARB/EUR", "STX/EUR", "KAS/EUR", "LDO/EUR",
    "DYDX/EUR", "COMP/EUR", "SNX/EUR", "GALA/EUR", "ENJ/EUR", "BAT/EUR",
    "APT/EUR", "SUI/EUR", "SEI/EUR", "PEPE/EUR", "SHIB/EUR", "FLOKI/EUR",
    "ONDO/EUR", "PENDLE/EUR", "PYTH/EUR", "AKT/EUR", "AIOZ/EUR", "TAO/EUR",
    "KSM/EUR", "NOT/EUR"
]

