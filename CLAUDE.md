# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Tech Stack

- **Frontend**: Next.js 15 (App Router) + Tailwind CSS + shadcn/ui + pnpm
- **Backend**: Python 3.12 + Django 5 + Django Ninja + uv
- **Database**: SQLite (development)

## Build & Run Commands

```bash
# Frontend
cd frontend && pnpm dev          # Start dev server
cd frontend && pnpm build        # Production build
cd frontend && pnpm lint         # Lint

# Backend
cd backend && uv run python manage.py runserver    # Start dev server
cd backend && uv run python manage.py migrate       # Run migrations
cd backend && uv run python manage.py makemigrations # Create migrations
cd backend && uv run pytest                          # Run tests
cd backend && uv run pytest path/to/test.py::test_name  # Run single test
```

## Architecture

```
Hackson5/
├── frontend/           # Next.js 15 App Router
│   ├── app/           # Pages and layouts (App Router)
│   ├── components/    # React components
│   │   └── ui/       # shadcn/ui components (do NOT manually edit)
│   ├── lib/           # Utilities, helpers, configs
│   └── public/        # Static assets
├── backend/            # Django project
│   ├── config/        # Django settings, urls, wsgi
│   ├── apps/          # Django apps (each app = one domain)
│   │   └── <app>/
│   │       ├── api.py     # Django Ninja API endpoints
│   │       ├── models.py  # Database models
│   │       ├── schemas.py # Pydantic schemas (request/response)
│   │       └── services.py# Business logic
│   └── tests/         # Test files
└── CLAUDE.md
```

- Frontend runs on `localhost:3000`, Backend on `localhost:8000`
- Backend API prefix: `/api/`
- Frontend proxies `/api/*` to backend via Next.js rewrites in `next.config.js`

## Code Conventions

### TypeScript / React

- Use `export default function ComponentName()` for page components
- Use named exports `export function Xxx()` for reusable components
- Use `cn()` from `@/lib/utils` for conditional class merging
- Import shadcn/ui components from `@/components/ui/` — do NOT manually edit these files, use `pnpx shadcn@latest add <component>` instead
- Server Components by default, add `"use client"` only when needed (state, effects, event handlers, browser APIs)
- Use `async/await` in Server Components for data fetching
- Path aliases: `@/` maps to `frontend/`

### Python / Django

- Use Django Ninja (not DRF) for all API endpoints — define in each app's `api.py`
- Use Pydantic schemas in `schemas.py` for request/response validation
- Keep business logic in `services.py`, not in views or models
- Type hints required on all function signatures
- Use `uv add <package>` to install dependencies (NOT `pip install`)
- Use `uv run` prefix for all Python commands in this project
- Model naming: singular, e.g. `User`, `Project` (not `Users`, `Projects`)

### Styling

- Tailwind CSS only — no CSS modules, no styled-components
- Follow shadcn/ui theming conventions (CSS variables in `globals.css`)
- Responsive: mobile-first, use `sm:` `md:` `lg:` breakpoints

### API Conventions

- RESTful: `GET /api/resources/`, `POST /api/resources/`, `GET /api/resources/{id}/`
- Use plural nouns for resource names
- Return consistent response format: `{"data": ..., "message": ...}`
- HTTP status codes: 200 OK, 201 Created, 400 Bad Request, 404 Not Found

## Documentation Rule

- **After completing any feature, model, or API endpoint**, you MUST create or update the corresponding project documentation to Feishu (Lark)
- Use `lark-cli` commands to push documentation (prefer `lark-cli markdown` for technical docs)
- Documentation should cover: what was built, API endpoints, data models, key design decisions
- If a Feishu doc already exists for the project, update it; otherwise create a new one
- This is mandatory — do not skip documentation after code changes

## Gotchas

- Always run `uv run python manage.py migrate` after model changes
- shadcn/ui components are managed by CLI — don't hand-edit `components/ui/`
- Next.js App Router: page components must be in `app/` directory with `page.tsx`
- Django Ninja: register API routers in `config/api.py`
- Use `uv run` not `python` directly — uv manages the virtual environment
