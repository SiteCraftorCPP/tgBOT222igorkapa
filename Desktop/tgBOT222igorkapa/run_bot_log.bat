@echo off
chcp 65001 >nul
cd /d "C:\Users\MOD PC COMPANY\Desktop\tgBOT222igorkapa"
echo Запуск бота с логированием в файл bot.log...
python -u bot.py > bot.log 2>&1

