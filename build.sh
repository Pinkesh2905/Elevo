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

# --- NLTK Data Download ---
echo "---> Downloading NLTK data..."
# Directly specify the packages to download non-interactively
python -m nltk.downloader -d /opt/render/project/src/nltk_data punkt wordnet omw-1.4

# --- Django Management Commands ---
echo "---> Collecting static files..."
python manage.py collectstatic --no-input

echo "---> Applying database migrations..."
python manage.py migrate

echo "---> Seeding coding problems..."
python manage.py seed_problems
