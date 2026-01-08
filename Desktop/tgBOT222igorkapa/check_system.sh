#!/bin/bash
# Скрипт проверки системы перед деплоем

echo "=================================="
echo "System Check for Crypto Signal Bot"
echo "=================================="
echo ""

# Проверка Python
echo "[1] Checking Python..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo "  ✅ Python: $PYTHON_VERSION"
else
    echo "  ❌ Python3 not found!"
    exit 1
fi

# Проверка pip
echo "[2] Checking pip..."
if command -v pip3 &> /dev/null; then
    echo "  ✅ pip3: $(pip3 --version)"
else
    echo "  ❌ pip3 not found!"
    exit 1
fi

# Проверка зависимостей
echo "[3] Checking Python packages..."
if pip3 show requests &> /dev/null; then
    echo "  ✅ requests: installed"
else
    echo "  ⚠️  requests: not installed (will be installed during deploy)"
fi

# Проверка файлов проекта
echo "[4] Checking project files..."
REQUIRED_FILES=("bot.py" "config.py" "market_monitor.py" "state_manager.py" "telegram_sender.py" "requirements.txt")
MISSING_FILES=()

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✅ $file"
    else
        echo "  ❌ $file - MISSING!"
        MISSING_FILES+=("$file")
    fi
done

if [ ${#MISSING_FILES[@]} -gt 0 ]; then
    echo ""
    echo "❌ Missing files: ${MISSING_FILES[*]}"
    exit 1
fi

# Проверка конфига
echo "[5] Checking configuration..."
if [ -f "config.py" ]; then
    if grep -q "YOUR_BOT_TOKEN_HERE" config.py || grep -q "YOUR_BIT2ME_API_KEY_HERE" config.py; then
        echo "  ⚠️  config.py contains placeholder values!"
        echo "     Please edit config.py and set your tokens."
    else
        echo "  ✅ config.py configured"
    fi
else
    echo "  ⚠️  config.py not found (copy from config.example.py)"
fi

# Проверка systemd (для VPS)
echo "[6] Checking systemd..."
if command -v systemctl &> /dev/null; then
    echo "  ✅ systemctl: available"
    if systemctl is-system-running &> /dev/null; then
        echo "  ✅ systemd: running"
    else
        echo "  ⚠️  systemd: not running (might not be needed for manual run)"
    fi
else
    echo "  ⚠️  systemctl not found (not critical for manual run)"
fi

# Проверка интернета
echo "[7] Checking internet connection..."
if ping -c 1 -W 2 8.8.8.8 &> /dev/null; then
    echo "  ✅ Internet: connected"
else
    echo "  ⚠️  Internet: no connection (might fail API requests)"
fi

# Проверка API доступности
echo "[8] Checking Bit2Me API..."
if curl -s --max-time 5 "https://gateway.bit2me.com/v1/trading/ticker" &> /dev/null; then
    echo "  ✅ Bit2Me API: accessible"
else
    echo "  ⚠️  Bit2Me API: not accessible (check firewall/network)"
fi

echo ""
echo "=================================="
if [ ${#MISSING_FILES[@]} -eq 0 ]; then
    echo "✅ System check complete!"
    echo "   Ready for deployment."
else
    echo "❌ System check failed!"
    echo "   Fix issues above before deployment."
fi
echo "=================================="

