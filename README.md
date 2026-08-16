# Vitauls Signals

Frontend (Next.js) and backend (Django) are separate apps so they can be deployed independently.

```
frontend/   Next.js UI  → Vercel (or similar)
backend/    Django API  → Railway / Render / any Python host
```

## Local development

**Backend** (http://localhost:8000, admin at `/admin/`):

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add GEMINI_API_KEY
python manage.py migrate
python manage.py runserver 8000
```

**Frontend** (http://localhost:3000):

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

`frontend/.env.local` must point at the API:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_OPEN_ACCESS=false
```

## Deploy frontend (Vercel)

1. Set the Vercel **Root Directory** to `frontend`.
2. Add environment variables:
   - `NEXT_PUBLIC_API_URL` — your live Django URL, e.g. `https://api.example.com`
   - `NEXT_PUBLIC_OPEN_ACCESS` — keep `false` so access waits for admin approval
3. Deploy.

## Deploy backend (Railway or Render)

1. Set the service **root directory** to `backend`.
2. Add environment variables:
   - `DJANGO_SECRET_KEY` — a long random string
   - `DJANGO_DEBUG=false`
   - `ALLOWED_HOSTS` — your API hostname
   - `FRONTEND_ORIGIN` — your Vercel URL, e.g. `https://your-app.vercel.app`
   - `CORS_ALLOWED_ORIGINS` — same as `FRONTEND_ORIGIN`
   - `GEMINI_API_KEY`
   - `OPEN_ACCESS=false` — users wait for admin payment confirmation
   - `DATABASE_URL` — Postgres URL from the host (recommended). SQLite is local-only.
3. The `Procfile` runs migrate, collectstatic, and gunicorn.

After both are live, the browser talks to Django directly. CORS will fail until `FRONTEND_ORIGIN` matches the exact Vercel origin (including `https://`).

Payment screenshots are stored on the API disk (`backend/media/`). On Railway/Render that disk is ephemeral unless you attach a volume or object storage.
