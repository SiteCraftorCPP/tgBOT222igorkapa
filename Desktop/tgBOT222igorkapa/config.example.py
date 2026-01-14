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

# Период локального максимума (4 часа в секундах)
LOCAL_MAX_PERIOD = 4 * 3600

# Время до автоматического RESET (2 часа в секундах)
RESET_TIME = 2 * 3600

# Процент роста для RESET (+2%)
RESET_GROWTH_PERCENT = 2.0

# ============================================
# УРОВНИ ПАДЕНИЯ ДЛЯ СИГНАЛОВ
# ============================================

LEVELS = [
    {"level": 1, "drop": -8.0},
    {"level": 2, "drop": -12.0},
    {"level": 3, "drop": -16.0},
    {"level": 4, "drop": -20.0},
    {"level": 5, "drop": -24.0}
]

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
    "BTC/EUR", "ETH/EUR", "XRP/EUR", "SOL/EUR", "ADA/EUR", "DOGE/EUR",
    "AVAX/EUR", "TAO/EUR", "GLMR/EUR", "MOVR/EUR", "KSM/EUR", "APT/EUR",
    "CELO/EUR", "JST/EUR", "RSR/EUR", "TRU/EUR", "FLR/EUR", "VELODROME/EUR",
    "ONDO/EUR", "PENDLE/EUR", "NOT/EUR", "PEAQ/EUR", "LSK/EUR", "KEEP/EUR",
    "MLN/EUR", "AR/EUR", "SWEAT/EUR", "JOE/EUR", "PYTH/EUR", "CFG/EUR",
    "ETHFI/EUR", "TNSR/EUR", "PUMP/EUR", "BNB/EUR", "DOT/EUR", "LINK/EUR",
    "TRX/EUR", "LTC/EUR", "BCH/EUR", "XLM/EUR", "ATOM/EUR", "ALGO/EUR",
    "NEAR/EUR", "FIL/EUR", "ETC/EUR", "XTZ/EUR", "UNI/EUR", "AAVE/EUR",
    "CRV/EUR", "RUNE/EUR", "GRT/EUR", "ENJ/EUR", "BAT/EUR", "SAND/EUR",
    "MANA/EUR", "AIOZ/EUR", "NPC/EUR", "CLANKER/EUR", "FLOKI/EUR", "METIS/EUR",
    "SEI/EUR", "SUI/EUR", "ARB/EUR", "KAS/EUR", "STX/EUR", "SNX/EUR",
    "COMP/EUR", "LDO/EUR", "DYDX/EUR", "AKT/EUR", "GALA/EUR", "SHIB/EUR",
    "PEPE/EUR"
]

