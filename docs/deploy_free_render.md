# Deploying Elevo for free (Render + Neon + Cloudinary) on elevo.life

| Piece | Service | Free plan |
|---|---|---|
| Django app | Render web service | 750 h/month, sleeps after 15 min idle (~1 min to wake) |
| Database | Neon Postgres | 1 GB per project, 100 compute-hours/month, data never deleted |
| Uploads | Cloudinary | 25 credits/month (1 credit = 1 GB storage, 1 GB bandwidth or 1K transforms) |
| Domain | Hostinger (registrar + DNS) | already owned until 2027-04-02 |

None of these need a credit card.

What the code already handles (branch `deploy/render-neon-cloudinary`):
- `DJANGO_Q_SYNC=true` runs django-q2 tasks (mock-interview feedback) inside the web
  request, because the free plan has no background worker.
- `CLOUDINARY_URL` switches uploads to `elevo/storage.py` (Cloudinary). Without it,
  uploads stay on the local disk as before.
- `render.yaml` describes the web service; secrets are entered in the dashboard.

Do the steps in order. Total time is about 45 minutes, plus DNS propagation.

---

## 1. Neon: create the database

1. Sign up at https://neon.com and create a project.
   - **Region:** AWS Asia Pacific (Singapore), the same region as the Render service.
   - **Postgres version:** 18 if offered (matches your local DB), otherwise the newest.
2. On the project dashboard, click **Connect** and copy two connection strings:
   - **Pooled** (host contains `-pooler`). This is `DATABASE_URL` for Render.
   - **Direct** (no `-pooler`). Use this one only for the copy in step 2.

   Both end with `?sslmode=require`; keep that.

## 2. Copy your local database into Neon (one time)

This brings over all your content (90 coding problems, 464 aptitude questions,
plans, users). Run in PowerShell from any folder:

```powershell
$pg = "C:\Program Files\PostgreSQL\18\bin"
& "$pg\pg_dump.exe" --no-owner --no-privileges --format=custom `
  --file "$env:TEMP\elevo.dump" "postgres://postgres:<local-password>@localhost:5432/Elevo"
& "$pg\pg_restore.exe" --no-owner --no-privileges --dbname "<NEON DIRECT CONNECTION STRING>" "$env:TEMP\elevo.dump"
```

A few "already exists" warnings on the `public` schema are harmless. Skip this
step if you want production to start empty; the build seeds plans and a starter
problem set either way.

## 3. Cloudinary: create the media store

1. Sign up at https://cloudinary.com (free plan).
2. Dashboard → **API Keys**: copy the **API environment variable**. It looks like
   `cloudinary://<api_key>:<api_secret>@<cloud_name>`. This is `CLOUDINARY_URL`.
3. Settings → **Security**: turn on **Allow delivery of PDF and ZIP files**.
   Resumes are PDFs, and free accounts block their delivery by default.
4. Copy your existing uploads (avatars, resumes, chat files) so the links in the
   copied database keep working. Temporarily add `CLOUDINARY_URL=...` to
   `elevo/.env`, then:

   ```powershell
   cd C:\Projects\4thSemProject\Elevo\elevo
   ..\.venv\Scripts\python.exe manage.py upload_media_to_cloudinary --dry-run
   ..\.venv\Scripts\python.exe manage.py upload_media_to_cloudinary
   ```

   **Then remove `CLOUDINARY_URL` from `.env` again.** While it's set, local
   development also uploads to Cloudinary.

## 4. Render: create the web service

1. Make sure this branch is merged into `main` on GitHub.
2. Sign in at https://render.com with GitHub → **New** → **Blueprint** → pick
   `Pinkesh2905/Elevo`. Render reads `render.yaml`.
3. Fill in the secrets it asks for:

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | Neon **pooled** connection string |
   | `CLOUDINARY_URL` | from step 3 |
   | `GEMINI_API_KEY` | your Gemini key |
   | `OPENAI_API_KEY` | optional fallback, can be empty |
   | `JDOODLE_CLIENT_ID` / `JDOODLE_CLIENT_SECRET` | your JDoodle keys |
   | `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` / `DEFAULT_FROM_EMAIL` | Gmail address + app password |

4. **Apply**. The first build installs packages, builds CSS, collects static
   files, runs migrations on Neon and seeds plans/problems (safe to re-run).
5. Open `https://elevo-web.onrender.com` and check that it loads.

## 5. Point elevo.life at Render

1. Render → `elevo-web` → **Settings** → **Custom Domains** → add `elevo.life`,
   then add `www.elevo.life`. Render shows the DNS records to create.
2. Hostinger hPanel → **Domains** → `elevo.life` → **DNS / Nameservers** → DNS records:
   - **Delete** the old `A` record `@ → 16.171.7.231` (the suspended AWS server),
     and any `AAAA` record or `www` record pointing at AWS.
   - **Add** `A` `@` → the IP Render shows (at the time of writing `216.24.57.1`).
   - **Add** `CNAME` `www` → `elevo-web.onrender.com`.
3. Back in Render, click **Verify** on both domains. Render issues HTTPS
   certificates automatically. DNS changes usually take minutes, up to a few hours.

## 6. Optional: avoid the cold start

Free services sleep after 15 minutes without traffic, so the first visitor
waits about a minute. A free pinger keeps it awake: create a job at
https://cron-job.org that requests `https://elevo.life/` every 10 minutes.
One service running all month is about 744 hours, inside the 750 free hours.

---

## Known limits on the free setup

- **Mock-interview feedback** is generated during the request (inline task), so
  ending an interview can take up to ~60 s. Gunicorn's timeout is 120 s.
- **Hourly "missed chat message" emails** (`chat.tasks.send_missed_message_emails`)
  need a django-q worker (`python manage.py qcluster`), which the free plan doesn't
  have. Everything else works without it.
- **Neon** suspends idle compute after 5 minutes; the first query afterwards takes
  about a second longer.
- **Region**: Render's free web services can't move regions later without
  recreating the service.
