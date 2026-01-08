# 🚀 Деплой на VPS

Инструкция по развёртыванию Crypto Signal Bot на VPS сервере.

## 📋 Требования

- **VPS** с Ubuntu/Debian (минимум 1GB RAM)
- **Root доступ** или пользователь с sudo
- **Python 3.7+**
- **Интернет соединение**

## ✅ Предварительная проверка

Перед деплоем проверьте систему:

```bash
chmod +x check_system.sh
./check_system.sh
```

Этот скрипт проверит:
- ✅ Python и pip
- ✅ Необходимые файлы
- ✅ Конфигурацию
- ✅ Доступность API

---

## 🎯 Быстрый деплой

### Вариант 1: Автоматический (рекомендуется)

1. **Скачайте проект на VPS:**
```bash
cd /root
git clone <your-repo-url> tgBOT222igorkapa
cd tgBOT222igorkapa
```

2. **Настройте конфигурацию:**
```bash
cp config.example.py config.py
nano config.py  # Укажите ваши токены
```

3. **Запустите скрипт деплоя:**
```bash
chmod +x deploy.sh check_system.sh start.sh
sudo bash deploy.sh
```

**Готово!** Бот запущен как systemd сервис и будет работать 24/7.

**Проверка работоспособности:**
```bash
# Проверить статус
sudo systemctl status cryptobot

# Посмотреть логи
sudo journalctl -u cryptobot -f
```

---

### Вариант 2: Ручной деплой

#### Шаг 1: Подготовка

```bash
# Создать директорию
mkdir -p /root/tgBOT222igorkapa
cd /root/tgBOT222igorkapa

# Скопировать файлы проекта (через scp или git)
# Например:
git clone <your-repo-url> .
```

#### Шаг 2: Установка зависимостей

```bash
# Обновить систему
apt update
apt install -y python3 python3-pip

# Установить Python пакеты
pip3 install -r requirements.txt
```

#### Шаг 3: Настройка конфига

```bash
cp config.example.py config.py
nano config.py
```

Укажите:
- `TELEGRAM_BOT_TOKEN` - токен бота
- `TELEGRAM_CHAT_ID` - ID чата/канала
- `BIT2ME_API_KEY` - API ключ Bit2Me

#### Шаг 4: Установка systemd сервиса

```bash
# Скопировать service файл
cp cryptobot.service /etc/systemd/system/

# Перезагрузить systemd
systemctl daemon-reload

# Включить автозапуск
systemctl enable cryptobot

# Запустить бота
systemctl start cryptobot
```

#### Шаг 5: Проверка

```bash
# Статус
systemctl status cryptobot

# Логи
journalctl -u cryptobot -f
```

---

## 📊 Управление сервисом

### Просмотр статуса
```bash
sudo systemctl status cryptobot
```

### Просмотр логов
```bash
# В реальном времени
sudo journalctl -u cryptobot -f

# Последние 100 строк
sudo journalctl -u cryptobot -n 100

# За сегодня
sudo journalctl -u cryptobot --since today
```

### Управление
```bash
# Запустить
sudo systemctl start cryptobot

# Остановить
sudo systemctl stop cryptobot

# Перезапустить
sudo systemctl restart cryptobot

# Проверить статус
sudo systemctl status cryptobot
```

---

## 🔧 Конфигурация systemd

Файл сервиса: `/etc/systemd/system/cryptobot.service`

**Основные параметры:**
- `WorkingDirectory` - директория с ботом
- `ExecStart` - команда запуска
- `Restart=always` - автоперезапуск при падении
- `RestartSec=10` - пауза перед перезапуском

**Изменение пути:**
Если бот в другой директории, отредактируйте:
```bash
sudo nano /etc/systemd/system/cryptobot.service
# Измените WorkingDirectory и ExecStart
sudo systemctl daemon-reload
sudo systemctl restart cryptobot
```

---

## 📁 Структура на VPS

```
/root/tgBOT222igorkapa/
├── bot.py                  # Главный файл
├── config.py               # Конфигурация (НЕ коммитить!)
├── state_manager.py
├── market_monitor.py
├── telegram_sender.py
├── requirements.txt
├── pairs_state.json        # Состояния (создаётся автоматически)
├── cryptobot.service       # systemd service
├── start.sh                # Скрипт ручного запуска
└── deploy.sh               # Скрипт автоматического деплоя
```

---

## 🔒 Безопасность

1. **Защита конфига:**
```bash
chmod 600 config.py
```

2. **Firewall (опционально):**
Бот только делает исходящие запросы, входящие порты не нужны.

3. **Backup состояний:**
```bash
# Резервная копия состояний
cp pairs_state.json pairs_state.json.backup
```

---

## 🐛 Решение проблем

### Бот не запускается

```bash
# Проверить логи
sudo journalctl -u cryptobot -n 50

# Проверить конфиг
python3 -c "from config import *; print('Config OK')"

# Проверить зависимости
pip3 list | grep requests
```

### Ошибка "Permission denied"

```bash
# Проверить права
ls -la bot.py
chmod +x bot.py start.sh deploy.sh
```

### Бот падает

```bash
# Проверить логи на ошибки
sudo journalctl -u cryptobot -n 100 | grep ERROR

# Проверить доступность API
curl https://gateway.bit2me.com/v1/trading/ticker
```

### Не отправляются сигналы

1. Проверить токены в `config.py`
2. Проверить логи: `journalctl -u cryptobot -f`
3. Проверить, что есть падения > -4%

---

## 📈 Мониторинг

### Использование ресурсов

```bash
# CPU и память
ps aux | grep bot.py

# Дисковое пространство
du -sh /root/tgBOT222igorkapa
```

### Автоматический мониторинг (опционально)

Создайте скрипт для проверки статуса:
```bash
#!/bin/bash
if ! systemctl is-active --quiet cryptobot; then
    echo "Bot is down! Restarting..."
    systemctl restart cryptobot
fi
```

Добавьте в cron:
```bash
crontab -e
# Проверка каждые 5 минут
*/5 * * * * /root/check_bot.sh
```

---

## 🔄 Обновление бота

```bash
cd /root/tgBOT222igorkapa

# Остановить бота
sudo systemctl stop cryptobot

# Обновить код (через git или scp)
git pull
# или
# scp bot.py user@vps:/root/tgBOT222igorkapa/

# Установить новые зависимости (если есть)
pip3 install -r requirements.txt

# Запустить
sudo systemctl start cryptobot
```

---

## 📞 Поддержка

- Проверьте логи: `sudo journalctl -u cryptobot -f`
- Проверьте конфиг: `cat config.py`
- Проверьте состояния: `cat pairs_state.json | head -50`

---

## ✅ Готово!

Бот работает на VPS 24/7 и автоматически перезапускается при падении.

**Проверка работы:**
```bash
sudo systemctl status cryptobot
sudo journalctl -u cryptobot -f
```

Успешного деплоя! 🚀

