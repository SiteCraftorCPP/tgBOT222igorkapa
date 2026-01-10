#!/bin/bash
# Скрипт для сброса всех данных о парах и кэша сообщений

echo "=========================================="
echo "  СБРОС ДАННЫХ БОТА"
echo "=========================================="

# Остановка бота
echo ""
echo "[1/5] Остановка бота..."
systemctl stop cryptobot
sleep 2

# Переход в директорию проекта
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR" || exit 1

# Удаление файлов состояний
echo ""
echo "[2/5] Удаление файлов состояний..."

FILES_TO_REMOVE=(
    "pairs_state.json"
    "pairs_state.json.tmp"
    "sent_messages_cache.json"
    "sent_messages_cache.json.tmp"
)

REMOVED_COUNT=0
for file in "${FILES_TO_REMOVE[@]}"; do
    if [ -f "$file" ]; then
        rm -f "$file"
        echo "  ✅ Удалён: $file"
        REMOVED_COUNT=$((REMOVED_COUNT + 1))
    else
        echo "  ⚠️  Не найден: $file (уже удалён или не существует)"
    fi
done

echo ""
echo "  Удалено файлов: $REMOVED_COUNT из ${#FILES_TO_REMOVE[@]}"

# Проверка что файлы действительно удалены
echo ""
echo "[3/5] Проверка удаления..."
REMAINING=0
for file in "${FILES_TO_REMOVE[@]}"; do
    if [ -f "$file" ]; then
        echo "  ❌ ОШИБКА: $file всё ещё существует!"
        REMAINING=$((REMAINING + 1))
    fi
done

if [ $REMAINING -eq 0 ]; then
    echo "  ✅ Все файлы успешно удалены"
else
    echo "  ⚠️  Осталось файлов: $REMAINING"
fi

# Запуск бота
echo ""
echo "[4/5] Запуск бота..."
systemctl start cryptobot
sleep 2

# Проверка статуса
echo ""
echo "[5/5] Проверка статуса бота..."
systemctl status cryptobot --no-pager -l

echo ""
echo "=========================================="
echo "  ✅ СБРОС ЗАВЕРШЁН"
echo "=========================================="
echo ""
echo "Бот перезапущен. Все данные о парах и кэш сообщений очищены."
echo "При следующем запуске бот получит новый список пар и начнёт мониторинг с нуля."
echo ""
echo "Для просмотра логов:"
echo "  journalctl -u cryptobot -f"
echo ""
