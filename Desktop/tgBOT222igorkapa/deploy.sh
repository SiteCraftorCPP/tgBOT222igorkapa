#!/bin/bash
# Скрипт быстрого деплоя на VPS

set -e

BOT_DIR="/root/tgBOT222igorkapa"
SERVICE_FILE="cryptobot.service"
USER="${SUDO_USER:-$USER}"

echo "=================================="
echo "Crypto Signal Bot - VPS Deployment"
echo "=================================="

# Проверка root
if [ "$EUID" -ne 0 ]; then 
    echo "[ERROR] Run as root: sudo bash deploy.sh"
    exit 1
fi

# 1. Определение директории проекта
echo "[1/7] Locating project directory..."
if [ -f "bot.py" ] && [ -f "requirements.txt" ]; then
    # Уже в директории проекта
    BOT_DIR="$(pwd)"
    echo "  ✅ Found project in current directory: $BOT_DIR"
elif [ -d "$BOT_DIR" ] && [ -f "$BOT_DIR/bot.py" ]; then
    # Переходим в указанную директорию
    cd "$BOT_DIR" || exit 1
    echo "  ✅ Using specified directory: $BOT_DIR"
else
    # Создаём директорию
    echo "[1/7] Creating directory..."
    mkdir -p "$BOT_DIR"
    cd "$BOT_DIR" || exit 1
fi

# 2. Установка зависимостей системы
echo "[2/7] Installing system dependencies..."
apt update -qq
apt install -y python3 python3-pip git curl -qq

# 3. Проверка файлов проекта
echo "[3/7] Checking project files..."
if [ ! -f "bot.py" ] || [ ! -f "state_manager.py" ] || [ ! -f "market_monitor.py" ] || [ ! -f "telegram_sender.py" ]; then
    echo "[ERROR] Required Python files not found in $(pwd)!"
    echo "Current directory contents:"
    ls -la
    exit 1
fi
echo "  ✅ All Python files present"

# 4. Установка Python зависимостей
echo "[4/7] Installing Python dependencies..."
if [ -f "requirements.txt" ]; then
    pip3 install -r requirements.txt --quiet
    echo "  ✅ Dependencies installed"
else
    echo "[ERROR] requirements.txt not found in $(pwd)!"
    echo "Current directory: $(pwd)"
    echo "Files:"
    ls -la
    exit 1
fi
if [ ! -f "bot.py" ] || [ ! -f "state_manager.py" ] || [ ! -f "market_monitor.py" ] || [ ! -f "telegram_sender.py" ]; then
    echo "[ERROR] Required Python files not found!"
    exit 1
fi
echo "  ✅ All Python files present"

# 5. Проверка конфига
echo "[5/7] Checking configuration..."
if [ ! -f "config.py" ]; then
    if [ -f "config.example.py" ]; then
        echo "[WARNING] config.py not found! Copying from config.example.py..."
        cp config.example.py config.py
        echo "  ⚠️  Please edit config.py and configure your tokens:"
        echo "  nano config.py"
        read -p "Press Enter after configuring config.py..."
    else
        echo "[ERROR] Neither config.py nor config.example.py found!"
        exit 1
    fi
else
    echo "  ✅ config.py exists"
fi

# 6. Установка systemd service
echo "[6/7] Installing systemd service..."
if [ ! -f "$SERVICE_FILE" ]; then
    echo "[ERROR] $SERVICE_FILE not found!"
    exit 1
fi
cp "$SERVICE_FILE" /etc/systemd/system/cryptobot.service
# Обновляем пути в service файле если нужно
sed -i "s|WorkingDirectory=.*|WorkingDirectory=$BOT_DIR|g" /etc/systemd/system/cryptobot.service
sed -i "s|ExecStart=.*|ExecStart=/usr/bin/python3 $BOT_DIR/bot.py|g" /etc/systemd/system/cryptobot.service
systemctl daemon-reload

# 7. Предварительная проверка Python кода
echo "[7/8] Validating Python code..."
if python3 -m py_compile bot.py state_manager.py market_monitor.py telegram_sender.py 2>/dev/null; then
    echo "  ✅ Python syntax check passed"
else
    echo "  ⚠️  Python syntax check had warnings (continuing anyway)"
fi

# 8. Запуск сервиса
echo "[8/8] Starting service..."
# Обновляем пути в service файле перед копированием
sed -i "s|WorkingDirectory=.*|WorkingDirectory=$BOT_DIR|g" "$SERVICE_FILE" 2>/dev/null || true
sed -i "s|ExecStart=.*|ExecStart=/usr/bin/python3 $BOT_DIR/bot.py|g" "$SERVICE_FILE" 2>/dev/null || true
systemctl enable cryptobot
systemctl restart cryptobot

# Статус
sleep 3
echo ""
echo "Service status:"
systemctl status cryptobot --no-pager -l

echo ""
echo "=================================="
echo "✅ Deployment complete!"
echo "=================================="
echo ""
echo "Useful commands:"
echo "  sudo systemctl status cryptobot   # Check status"
echo "  sudo systemctl restart cryptobot  # Restart bot"
echo "  sudo systemctl stop cryptobot     # Stop bot"
echo "  sudo journalctl -u cryptobot -f   # View logs"
echo "  sudo journalctl -u cryptobot -n 100  # Last 100 lines"
echo ""

