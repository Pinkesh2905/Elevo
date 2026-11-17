#!/usr/bin/env bash
# exit on error
set -o errexit

# --- Standard pip Installation ---
echo "---> Installing Python dependencies..."
pip install -r requirements.txt

# --- Frontend Build ---
echo "---> Installing Node.js dependencies..."
npm install

echo "---> Building frontend assets..."
npm run build

# --- Django Management Commands ---
echo "---> Collecting static files..."
python manage.py collectstatic --no-input

echo "---> Applying database migrations..."
python manage.py migrate

echo "---> Seeding subscription plans..."
python manage.py seed_subscription_plans

echo "---> Seeding coding problems..."
python manage.py seed_problems
