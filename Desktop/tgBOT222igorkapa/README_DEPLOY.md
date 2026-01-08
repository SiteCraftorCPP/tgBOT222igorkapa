# 🚀 Краткая инструкция по деплою

## Быстрый старт

1. **Загрузите проект на VPS:**
```bash
cd /root
git clone <your-repo> tgBOT222igorkapa
cd tgBOT222igorkapa
```

2. **Настройте конфиг:**
```bash
cp config.example.py config.py
nano config.py  # Укажите токены
```

3. **Запустите деплой:**
```bash
chmod +x deploy.sh check_system.sh start.sh
sudo bash deploy.sh
```

**Готово!** Бот работает 24/7 как systemd сервис.

---

## Управление

```bash
# Статус
sudo systemctl status cryptobot

# Логи
sudo journalctl -u cryptobot -f

# Перезапуск
sudo systemctl restart cryptobot

# Остановка
sudo systemctl stop cryptobot
```

---

Подробная инструкция: **DEPLOY.md**

