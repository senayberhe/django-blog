#!/usr/bin/env bash
# Render runs this on every deploy. `set -o errexit` stops the deploy if any step fails,
# so a broken migration never goes live.
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input

# The free plan has no shell, so the admin account is created from environment
# variables (DJANGO_SUPERUSER_USERNAME / _EMAIL / _PASSWORD) set in the Render dashboard.
if [ -n "$DJANGO_SUPERUSER_USERNAME" ]; then
  python manage.py createsuperuser --no-input || echo "Superuser already exists — skipping."
fi
