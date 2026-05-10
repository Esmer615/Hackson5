# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Snapshot

Hackson5 is a 5-hour hackathon full-stack project. The scaffold is complete and deployed; business functionality has not started yet.

Production URLs:
- Frontend: `https://hackson5.vercel.app`
- Backend: `https://hackson5-production.up.railway.app`
- Health checks:
  - `https://hackson5.vercel.app/api/health` -> `{"status": "ok"}`
  - `https://hackson5-production.up.railway.app/api/health` -> `{"status": "ok"}`

Feishu docs:
- Project overview: `https://www.feishu.cn/wiki/YkCHwgrwCikkDakWa7kcTLYJnsh`
- Deployment notes: `https://www.feishu.cn/wiki/Y6C2wbfcRiqOCRkTqHCcgW7in4c`

## Tech Stack

- **Frontend**: Next.js 16 App Router + React 19 + Tailwind CSS v4 + shadcn/ui + pnpm
- **Backend**: Python 3.12 target + Django 6 + Django Ninja + uv
- **Database**: SQLite fallback locally; Railway PostgreSQL in production via `DATABASE_URL`
- **Deployment**: Vercel frontend, Railway backend + PostgreSQL
- **Docs**: Feishu/Lark via `lark-cli`

## Commands

```bash
# Frontend
cd frontend && pnpm dev
cd frontend && pnpm build
cd frontend && pnpm lint
cd frontend && pnpm format
cd frontend && pnpx shadcn@latest add <component>

# Backend
cd backend && uv run python manage.py runserver
cd backend && uv run python manage.py migrate
cd backend && uv run python manage.py makemigrations
cd backend && uv run pytest
cd backend && uv run pytest path/to/test.py::test_name
cd backend && uv run ruff check .
cd backend && uv run ruff format .

# Deploy/ops
vercel --prod --yes --token "$VERCEL_TOKEN"
railway logs --service Hackson5 --deployment --latest --lines 100
railway logs --service Hackson5 --build --latest --lines 100
```

## Architecture

```
Hackson5/
├── frontend/                 # Next.js App Router frontend
│   ├── app/                  # routes, layout, pages
│   ├── components/           # React components
│   │   └── ui/               # shadcn/ui components (CLI-managed)
│   ├── lib/utils.ts          # cn() and shared frontend helpers
│   ├── next.config.ts        # /api/* rewrite to NEXT_PUBLIC_API_URL
│   └── vercel.json           # Vercel frontend config
├── backend/                  # Django backend
│   ├── Dockerfile            # Railway Docker deployment
│   ├── config/
│   │   ├── api.py            # Ninja API root, registers app routers
│   │   ├── settings.py       # env-based settings, DB, CORS
│   │   ├── urls.py           # /api/ -> Ninja API
│   │   └── wsgi.py           # gunicorn entrypoint
│   ├── apps/
│   │   └── core/
│   │       ├── api.py        # currently GET /health
│   │       ├── models.py
│   │       ├── schemas.py
│   │       └── services.py
│   └── tests/test_health.py
├── docs/                     # local Markdown source for Feishu docs
├── railway.json              # Railway Dockerfile config
├── vercel.json               # minimal Vercel root config
└── CLAUDE.md
```

Runtime request flow:

```text
Browser -> Vercel frontend -> /api/* rewrite -> Railway Django backend -> Railway PostgreSQL
```

## Code Conventions

### TypeScript / React

- Use Server Components by default; add `"use client"` only for state/effects/events/browser APIs.
- Use `export default function PageName()` for page components.
- Use named exports for reusable components.
- Use `cn()` from `@/lib/utils` for class merging.
- Import shadcn/ui from `@/components/ui/`; do not hand-edit generated ui components unless unavoidable.
- Tailwind CSS only; no CSS modules or styled-components.
- Responsive mobile-first with `sm:`, `md:`, `lg:`.

### Python / Django

- Use Django Ninja, not DRF.
- Each backend app should use:
  - `api.py` for endpoints
  - `schemas.py` for Pydantic request/response schemas
  - `services.py` for business logic
  - `models.py` for database models
- Register app routers in `backend/config/api.py`.
- Type hints required on function signatures.
- Use `uv add <package>`, not `pip install`.
- Use `uv run ...` for Python commands locally.
- Model names are singular (`User`, `Project`).

### API

- API prefix is `/api/`.
- RESTful routes use plural nouns: `/api/resources/`, `/api/resources/{id}/`.
- Standard response shape: `{"data": ..., "message": ...}` unless a simple health/status endpoint.
- Status codes: 200 OK, 201 Created, 400 Bad Request, 404 Not Found.

## Quality Gates

- Frontend: ESLint 9 + Prettier + Tailwind class sorting.
- Backend: Ruff lint/format with `E`, `F`, `I`, `N`, `W`, `UP`.
- Git pre-commit: husky + lint-staged.
- Do not skip hooks unless explicitly requested.

## Deployment Notes

Railway backend:
- Project: `hackson5`
- Service: `Hackson5`
- Public domain: `https://hackson5-production.up.railway.app`
- Uses `backend/Dockerfile` via `railway.json`.
- Docker runtime puts `/app/backend/.venv/bin` on PATH and runs:
  - `python manage.py migrate`
  - `gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2`
- Important env vars:
  - `DATABASE_URL=${{Postgres.DATABASE_URL}}`
  - `DEBUG=False`
  - `ALLOWED_HOSTS=hackson5-production.up.railway.app,hackson5.vercel.app`
  - `CORS_ALLOWED_ORIGINS=https://hackson5.vercel.app`
  - `CSRF_TRUSTED_ORIGINS=https://hackson5.vercel.app`

Vercel frontend:
- Project: `hackson5`
- Production alias: `https://hackson5.vercel.app`
- Root Directory: `frontend`
- Build Command: `pnpm build`
- Install Command: `pnpm install`
- Output Directory: `.next`
- Env var: `NEXT_PUBLIC_API_URL=https://hackson5-production.up.railway.app`

## AI / Tooling

- superpowers plugin is enabled for brainstorming/planning/debugging/verification workflows.
- Context7 MCP is available for current docs lookup.
- SQLite MCP is available for local DB inspection.
- Railway MCP/CLI is available for Railway status/logs/variables.
- Lark skills are installed via `.agents/skills/*`; `.claude/skills/*` are symlinks to them, so do not delete `.agents/` unless reinstalling skills.

## Documentation Rule

After completing any feature, model, or API endpoint, update the corresponding Feishu documentation using `lark-cli`.

Documentation should cover:
- What was built
- API endpoints
- Data models
- Key design decisions
- Deployment/config changes, if any

## Gotchas

- Current business functionality is empty: frontend is default page, backend only has `GET /api/health`.
- Do not delete `.agents/` casually; Lark Claude skills symlink to it.
- `.vercel/` is local Vercel state and should stay ignored.
- Local backend defaults to SQLite when `DATABASE_URL` is unset.
- Production uses PostgreSQL through Railway `DATABASE_URL`.
- After model changes, run migrations locally and let Railway run migrations on deploy.
- Next.js generated `frontend/AGENTS.md` warns this Next version has breaking changes; check local Next docs if using unfamiliar APIs.
