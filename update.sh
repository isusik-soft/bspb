#!/usr/bin/env bash
set -euo pipefail

# --------------------------------------------
# Настройки по умолчанию
# --------------------------------------------
BRANCH="main"
SERVICE_NAME="bspb.service"
UPDATE_METHOD="pull"
DO_CLEAN=false
VENV_DIR=".venv"
# --------------------------------------------

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]
Options:
  -b BRANCH        Git-ветка (default: $BRANCH)
  -s SERVICE       systemd-сервис (default: $SERVICE_NAME)
  -m METHOD        update method: pull|reset (default: $UPDATE_METHOD)
  -c               clean untracked files after reset
  -h               help
EOF
  exit 1
}

while getopts "b:s:m:ch" opt; do
  case $opt in
    b) BRANCH="$OPTARG" ;;
    s) SERVICE_NAME="$OPTARG" ;;
    m) UPDATE_METHOD="$OPTARG" ;;
    c) DO_CLEAN=true ;;
    h|*) usage ;;
  esac
done

echo "🚀 Обновляем ветку: $BRANCH"
cd "$(dirname "$0")"

echo "📥 git fetch origin"
git fetch origin

echo "🧹 Удаление локальных ссылок на удалённые ветки, которых больше нет"
git remote prune origin

if [[ $UPDATE_METHOD == "reset" ]]; then
  echo "🔄 reset --hard origin/$BRANCH"
  git reset --hard "origin/$BRANCH"
  if [[ $DO_CLEAN == "true" ]]; then
    echo "🧹 Очистка неотслеживаемых файлов (кроме $VENV_DIR)"
    git clean -fd -e "$VENV_DIR"
  fi
elif [[ $UPDATE_METHOD == "pull" ]]; then
  echo "🔄 git pull origin $BRANCH"
  git pull origin "$BRANCH"
else
  echo "❌ Неизвестный метод обновления: $UPDATE_METHOD"
  exit 1
fi

echo "🔧 Делаем скрипт исполняемым"
chmod +x "$0"

echo "🐍 Проверка виртуального окружения ($VENV_DIR)"
if [[ ! -f "$VENV_DIR/bin/activate" ]]; then
  echo "🐍 Создаём окружение"
  python3 -m venv "$VENV_DIR"
fi

echo "🐍 Активируем окружение"
source "$VENV_DIR/bin/activate"

if [[ -f "requirements.txt" ]]; then
  echo "📦 Установка зависимостей"
  pip install --upgrade pip setuptools wheel
  pip install -r requirements.txt
fi

# Перезапуск сервиса
echo "🔄 Перезапускаем $SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo "✅ Обновление завершено: $(date '+%Y-%m-%d %H:%M:%S')"
