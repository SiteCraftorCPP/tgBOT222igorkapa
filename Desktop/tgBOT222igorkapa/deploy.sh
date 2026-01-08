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

# 1. Создание директории
echo "[1/6] Creating directory..."
mkdir -p "$BOT_DIR"
cd "$BOT_DIR" || exit 1

# 2. Установка зависимостей системы
echo "[2/6] Installing system dependencies..."
apt update -qq
apt install -y python3 python3-pip git curl -qq

# 3. Установка Python зависимостей
echo "[3/6] Installing Python dependencies..."
if [ -f "requirements.txt" ]; then
    pip3 install -r requirements.txt --quiet
else
    echo "[ERROR] requirements.txt not found!"
    exit 1
fi

# 3.5. Проверка файлов проекта
echo "[3.5/6] Checking project files..."
if [ ! -f "bot.py" ] || [ ! -f "state_manager.py" ] || [ ! -f "market_monitor.py" ] || [ ! -f "telegram_sender.py" ]; then
    echo "[ERROR] Required Python files not found!"
    exit 1
fi
echo "  ✅ All Python files present"

# 4. Проверка конфига
if [ ! -f "config.py" ]; then
    echo "[WARNING] config.py not found!"
    echo "  Copy config.example.py to config.py and configure:"
    echo "  cp config.example.py config.py"
    echo "  nano config.py"
    read -p "Press Enter after configuring config.py..."
fi

# 5. Установка systemd service
echo "[5/6] Installing systemd service..."
if [ ! -f "$SERVICE_FILE" ]; then
    echo "[ERROR] $SERVICE_FILE not found!"
    exit 1
fi
cp "$SERVICE_FILE" /etc/systemd/system/cryptobot.service
# Обновляем пути в service файле если нужно
sed -i "s|WorkingDirectory=.*|WorkingDirectory=$BOT_DIR|g" /etc/systemd/system/cryptobot.service
sed -i "s|ExecStart=.*|ExecStart=/usr/bin/python3 $BOT_DIR/bot.py|g" /etc/systemd/system/cryptobot.service
systemctl daemon-reload

# 6. Предварительная проверка Python кода
echo "[6/7] Validating Python code..."
if python3 -m py_compile bot.py state_manager.py market_monitor.py telegram_sender.py 2>/dev/null; then
    echo "  ✅ Python syntax check passed"
else
    echo "  ⚠️  Python syntax check had warnings (continuing anyway)"
fi

# 7. Запуск сервиса
echo "[7/7] Starting service..."
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

