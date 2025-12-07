#!/bin/bash

# Скрипт для конвертации UI файла Qt Designer в Python модуль
# Конвертирует ui/cnc_control.ui в ui/generated/mainwindow_ui_v2.py
#
# Использование:
#   ./convert_ui.sh
#   или
#   bash convert_ui.sh

set -e  # Остановка при ошибке

# Получаем директорию скрипта (корень репозитория)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# cd "$SCRIPT_DIR"

# Проверка наличия pyuic6
if ! command -v pyuic6 &> /dev/null; then
    echo "Ошибка: pyuic6 не найден. Установите PyQt6:"
    echo "  pip install PyQt6"
    exit 1
fi

echo "$(pwd)"
# Пути к файлам
UI_FILE="ui/cnc_control.ui"
OUTPUT_FILE="ui/generated/mainwindow_ui_v2.py"
OUTPUT_DIR="ui/generated"

# Проверка существования исходного UI файла
if [ ! -f "$UI_FILE" ]; then
    echo "Ошибка: UI файл не найден: $UI_FILE"
    exit 1
fi

# Создание директории для выходного файла, если её нет
mkdir -p "$OUTPUT_DIR"

# Конвертация UI файла в Python модуль
echo "Конвертация $UI_FILE -> $OUTPUT_FILE"
pyuic6 -o "$OUTPUT_FILE" "$UI_FILE"

# Проверка успешности конвертации
if [ $? -eq 0 ]; then
    echo "✓ Успешно: $OUTPUT_FILE создан"
    
    # Показываем информацию о файле
    if [ -f "$OUTPUT_FILE" ]; then
        LINES=$(wc -l < "$OUTPUT_FILE")
        echo "  Размер: $LINES строк"
    fi
else
    echo "✗ Ошибка при конвертации"
    exit 1
fi
