@echo off
chcp 65001 >nul
cd /d "C:\Users\MOD PC COMPANY\Desktop\tgBOT222igorkapa"
echo Запуск бота с логированием...
python -u bot.py 2>&1 | tee bot.log

