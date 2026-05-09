FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy backend files
COPY backend/ /app/backend/

# Install dependencies
WORKDIR /app/backend
RUN uv sync --frozen --no-dev

# Run migrations and start server
EXPOSE 8000
CMD ["sh", "-c", "uv run python manage.py migrate && uv run gunicorn config.asgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2"]
