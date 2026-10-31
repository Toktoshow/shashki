#!/usr/bin/env bash
# Сборка проекта на Render: запускается при каждом деплое.
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

python manage.py collectstatic --no-input

# Если забыли закоммитить миграции, останавливаем сборку с понятным сообщением.
if ! python manage.py makemigrations --check --dry-run > /dev/null; then
  echo "ОШИБКА: в репозитории нет актуальных миграций." >&2
  echo "Выполните локально: python manage.py makemigrations game" >&2
  exit 1
fi

python manage.py migrate --no-input

# Необязательно: создаём администратора, если заданы переменные DJANGO_SUPERUSER_*.
if [[ -n "${DJANGO_SUPERUSER_USERNAME:-}" && -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]]; then
  python manage.py createsuperuser --no-input || true
fi