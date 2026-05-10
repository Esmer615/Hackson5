FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy backend files
COPY backend/ /app/backend/

# Install dependencies
WORKDIR /app/backend
RUN uv sync --frozen --no-dev
ENV PATH="/app/backend/.venv/bin:$PATH"

# Run migrations and start server
EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate && gunicorn config.wsgi:application --timeout 600 --bind 0.0.0.0:${PORT:-8000} --workers 2"]
