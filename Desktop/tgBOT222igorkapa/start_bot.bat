@echo off
chcp 65001 >nul
cd /d "C:\Users\MOD PC COMPANY\Desktop\tgBOT222igorkapa"
echo ============================================
echo   Запуск Crypto Signal Bot
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден!
    echo Установите Python 3.8+ с python.org
    pause
    exit /b 1
)

echo [1/2] Проверка зависимостей...
pip install -r requirements.txt --quiet

if errorlevel 1 (
    echo [ОШИБКА] Не удалось установить зависимости
    pause
    exit /b 1
)

echo [2/2] Запуск бота...
echo.
python bot.py

if errorlevel 1 (
    echo.
    echo [ОШИБКА] Бот завершился с ошибкой
    pause
)

