@echo off
chcp 65001 >nul
cd /d "C:\Users\MOD PC COMPANY\Desktop\tgBOT222igorkapa"
if not exist bot.log (
    echo Файл bot.log не найден. Запустите бота сначала.
    pause
    exit
)
echo Просмотр логов (Ctrl+C для выхода)...
powershell -Command "Get-Content bot.log -Wait -Tail 50"

