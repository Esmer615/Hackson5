# Hackson5 Knowledge Integration Agent

Hackson5 is a full-stack teaching assistant for multi-textbook knowledge integration. Teachers upload textbook PDFs or text files, run an AI-assisted pipeline, inspect the generated knowledge graph, ask RAG questions with citations, and provide feedback that can override integration decisions.

## Tech Stack

- Frontend: Next.js App Router, React, Tailwind CSS, shadcn/ui, ECharts, pnpm
- Backend: Django, Django Ninja, LangGraph, uv
- AI: DeepSeek chat API with deterministic fallback when `DEEPSEEK_API_KEY` is not configured
- Storage: SQLite locally; PostgreSQL on Railway through `DATABASE_URL`
- Deployment: Vercel frontend and Railway backend

## Environment Variables

Backend variables:

```bash
SECRET_KEY=change-me
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:3000
CSRF_TRUSTED_ORIGINS=http://localhost:3000
DATABASE_URL=sqlite:///db.sqlite3
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
DEMO_MAX_PAGES=12
QUALITY_MAX_PAGES=80
```

Frontend variables:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

`DEEPSEEK_API_KEY` is optional for local demos. Without it, graph extraction and RAG answers use the built-in fallback logic so the workflow remains testable.

## Local Run

Backend:

```bash
cd backend
uv run python manage.py migrate
uv run python manage.py runserver
```

Frontend:

```bash
cd frontend
pnpm install
pnpm dev
```

Open `http://localhost:3000`. The frontend calls `/api/*` through the configured API base URL.

## Tests and Checks

Backend:

```bash
cd backend
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Frontend:

```bash
cd frontend
pnpm lint
pnpm format:check
pnpm build
```

## Usage Flow

1. Select Demo Mode for a fast run or Quality Mode for deeper parsing and extraction.
2. Upload PDF, Markdown, or text textbook files.
3. Run the LangGraph pipeline: parse chapters, build textbook graphs, integrate nodes, build the RAG index, and generate a report.
4. Inspect the ECharts knowledge graph and node details.
5. Ask questions in the RAG panel and review citations from the indexed chunks.
6. Send teacher feedback when a merge or keep decision needs correction.
7. Read the generated integration report for summary, risks, and next-step suggestions.

## Deployment Notes

Production frontend: `https://hackson5.vercel.app`

Production backend: `https://hackson5-production.up.railway.app`

Railway runs the Django backend with PostgreSQL through `DATABASE_URL`. Vercel serves the frontend and should set `NEXT_PUBLIC_API_URL` to the Railway backend URL. Production should set `DEBUG=False`, restrict `ALLOWED_HOSTS`, and configure CORS/CSRF origins for the Vercel domain.

## Data and PDF Warning

Uploaded textbooks are stored as media files and parsed into local database records. Do not commit raw textbooks, PDFs, generated media, or local data exports. The repository ignores `media/`, `backend/media/`, `.superpowers/`, `*.pdf`, and `data/textbooks/*.pdf` to keep private teaching materials out of source control.
