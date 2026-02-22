# Elevo

Elevo is an AI-powered placement preparation platform built with Django. It combines coding practice, aptitude preparation, social learning, and resume-driven mock interviews in one system.

## Core Features

- Coding practice with problem lists, submissions, and tutor-managed content
- Aptitude module with categories, topics, practice sets, and quiz sessions
- AI mock interviews with Technical and HR tracks
- Resume analysis with ATS-style score, breakdown, and improvement suggestions
- Interview reports with transcript and performance insights
- User system with student/tutor/admin roles and profile management
- Social feed (posts, comments, likes, repost/share, follow)

## Tech Stack

- Backend: Django 5
- Database: PostgreSQL (production-ready)
- AI: Gemini with OpenAI fallback
- Frontend: Django templates + Tailwind-style utility classes

## Local Setup

1. Clone and enter project:
```bash
git clone https://github.com/Pinkesh2905/Elevo.git
cd Elevo/elevo
```

2. Create and activate virtualenv:
```bash
python -m venv ..\\.venv
..\\.venv\\Scripts\\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure `.env` (example):
```env
SECRET_KEY=your_secret
DEBUG=True
DATABASE_URL=postgres://postgres:password@localhost:5432/Elevo
GEMINI_API_KEY=your_gemini_key
OPENAI_API_KEY=your_openai_key
AI_PROVIDER=gemini
APTITUDE_DATA_DIR=private_data/aptitude
PRACTICE_DATA_DIR=private_data/practice
ELEVO_CONTENT_CSV=private_data/elevo_content.csv
```

5. Run migrations and start:
```bash
python manage.py migrate
python manage.py runserver
```

## Data Privacy (Important)

- This repository keeps only sample datasets:
  - `data/*_sample.csv`
  - `practice_data/*_sample.csv`
  - `elevo_content_sample.csv`
- Real production datasets must stay outside Git in a private location.
- Set private paths in `.env`:
```env
APTITUDE_DATA_DIR=private_data/aptitude
PRACTICE_DATA_DIR=private_data/practice
ELEVO_CONTENT_CSV=private_data/elevo_content.csv
```

Import commands:
```bash
python manage.py import_aptitude_data
python manage.py import_problems --clear
python manage.py import_csv
```

The commands first use private files (`*.csv`) and automatically fall back to sample files (`*_sample.csv`) if private files are not present.

## Production Notes

- Set `DEBUG=False`
- Use managed PostgreSQL and set `DATABASE_URL`
- Set secure `SECRET_KEY` and allowed hosts
- Run:
```bash
python manage.py check --deploy
python manage.py collectstatic --noinput
```

## Repository

Main remote: `https://github.com/Pinkesh2905/Elevo.git`
