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
   - `NEXT_PUBLIC_API_URL=https://virtual-signals-backend.onrender.com`
   - `NEXT_PUBLIC_OPEN_ACCESS=false`
3. Deploy. Live site: https://virtual-signals-frontend.vercel.app

## Deploy backend (Railway or Render)

1. Set the service **root directory** to `backend` (skip this if the Git repo is only the backend folder).
2. Set **Start Command** to:

```
gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
```

Do not use `gunicorn backend:app`. There is no `backend` Python module; the WSGI app is `config.wsgi:application`.
3. Add environment variables:
   - `DJANGO_SECRET_KEY` — a long random string
   - `DJANGO_DEBUG=false`
   - `ALLOWED_HOSTS=virtual-signals-backend.onrender.com`
   - `FRONTEND_ORIGIN=https://virtual-signals-frontend.vercel.app`
   - `CORS_ALLOWED_ORIGINS=https://virtual-signals-frontend.vercel.app`
   - `GEMINI_API_KEY`
   - `OPEN_ACCESS=false` — users wait for admin payment confirmation
   - `DATABASE_URL` — Postgres URL from the host (recommended). SQLite is local-only.

Live API: https://virtual-signals-backend.onrender.com

After both are live, the browser talks to Django directly. CORS will fail until `FRONTEND_ORIGIN` matches the exact Vercel origin (including `https://`).

Payment screenshots are stored on the API disk (`backend/media/`). On Railway/Render that disk is ephemeral unless you attach a volume or object storage.
