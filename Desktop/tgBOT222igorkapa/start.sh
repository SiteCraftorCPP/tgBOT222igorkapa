#!/bin/bash
# Скрипт запуска бота на Linux

cd "$(dirname "$0")" || exit 1

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 not found. Install: apt install python3 python3-pip"
    exit 1
fi

# Проверка зависимостей
if [ ! -f "config.py" ]; then
    echo "[ERROR] config.py not found. Copy from config.example.py and configure."
    exit 1
fi

# Установка зависимостей
echo "[INFO] Installing dependencies..."
pip3 install -r requirements.txt --quiet

# Запуск бота
echo "[INFO] Starting bot..."
python3 bot.py

