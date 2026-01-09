# Команды для обновления бота на VPS

## Быстрое обновление (без сброса состояния)

```bash
# 1. Остановить бота
systemctl stop cryptobot

# 2. Перейти в директорию проекта
cd ~/tgBOT222igorkapa/Desktop/tgBOT222igorkapa

# 3. Обновить код из Git
git pull origin main

# 4. Запустить бота
systemctl start cryptobot

# 5. Проверить статус
systemctl status cryptobot

# 6. Смотреть логи в реальном времени
journalctl -u cryptobot -f
```

---

## Полное обновление (со сбросом состояния)

**⚠️ ВНИМАНИЕ: Это удалит все сохранённые состояния пар и начнёт с чистого листа!**

```bash
# 1. Остановить бота
systemctl stop cryptobot

# 2. Перейти в директорию проекта
cd ~/tgBOT222igorkapa/Desktop/tgBOT222igorkapa

# 3. Обновить код из Git
git pull origin main

# 4. Удалить старый state (ВАЖНО для применения новых уровней!)
rm -f pairs_state.json

# 5. Проверить config.py (уровни должны быть -8%, -12%, -16%, -20%, -24%)
cat config.py | grep -A 6 "LEVELS ="

# Если уровни неправильные, обновить вручную:
nano config.py
# Заменить на:
# LEVELS = [
#     {"level": 1, "drop": -8.0},
#     {"level": 2, "drop": -12.0},
#     {"level": 3, "drop": -16.0},
#     {"level": 4, "drop": -20.0},
#     {"level": 5, "drop": -24.0}
# ]
# Сохранить: Ctrl+O, Enter, Ctrl+X

# 6. Запустить бота
systemctl start cryptobot

# 7. Проверить статус
systemctl status cryptobot

# 8. Смотреть логи
journalctl -u cryptobot -f
```

---

## Обновление только config.py (если изменения не применились)

```bash
# 1. Остановить бота
systemctl stop cryptobot

# 2. Перейти в директорию
cd ~/tgBOT222igorkapa/Desktop/tgBOT222igorkapa

# 3. Открыть config.py для редактирования
nano config.py

# 4. Убедиться что уровни правильные:
# LEVELS = [
#     {"level": 1, "drop": -8.0},
#     {"level": 2, "drop": -12.0},
#     {"level": 3, "drop": -16.0},
#     {"level": 4, "drop": -20.0},
#     {"level": 5, "drop": -24.0}
# ]

# 5. Сохранить: Ctrl+O, Enter, Ctrl+X

# 6. Запустить бота
systemctl start cryptobot

# 7. Проверить логи
journalctl -u cryptobot -f
```

---

## Полезные команды

### Проверить статус бота
```bash
systemctl status cryptobot
```

### Остановить бота
```bash
systemctl stop cryptobot
```

### Запустить бота
```bash
systemctl start cryptobot
```

### Перезапустить бота
```bash
systemctl restart cryptobot
```

### Смотреть логи (последние 100 строк)
```bash
journalctl -u cryptobot -n 100
```

### Смотреть логи в реальном времени
```bash
journalctl -u cryptobot -f
```

### Смотреть логи за последний час
```bash
journalctl -u cryptobot --since "1 hour ago"
```

### Проверить, что бот работает
```bash
ps aux | grep bot.py
```

### Проверить содержимое pairs_state.json
```bash
cat pairs_state.json | head -50
```

### Проверить версию кода (последний коммит)
```bash
cd ~/tgBOT222igorkapa/Desktop/tgBOT222igorkapa
git log --oneline -1
```

---

## После обновления проверь:

1. ✅ Бот запущен: `systemctl status cryptobot`
2. ✅ Логи без ошибок: `journalctl -u cryptobot -n 50`
3. ✅ Уровни правильные: в логах должно быть "Levels: -8%, -12%, -16%, -20%, -24%"
4. ✅ API работает: в логах должно быть "[OK] Got X COIN/EUR pairs from Bit2Me"
5. ✅ Сигналы отправляются: проверь канал Telegram

---

## Если что-то пошло не так:

```bash
# Посмотреть подробные логи ошибок
journalctl -u cryptobot -n 200 --no-pager

# Проверить синтаксис Python файлов
cd ~/tgBOT222igorkapa/Desktop/tgBOT222igorkapa
python3 -m py_compile bot.py
python3 -m py_compile market_monitor.py
python3 -m py_compile state_manager.py
python3 -m py_compile telegram_sender.py

# Проверить, что все зависимости установлены
./venv/bin/pip list | grep -E "requests|telegram"

# Запустить бота вручную для диагностики
cd ~/tgBOT222igorkapa/Desktop/tgBOT222igorkapa
./venv/bin/python3 bot.py
```
