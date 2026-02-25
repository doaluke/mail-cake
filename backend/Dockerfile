FROM python:3.11-slim

WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 安裝 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# ── Layer cache 技巧 ──────────────────────────────────────
# 先複製 pyproject.toml，建一個假的 app/__init__.py
# 讓 hatchling 能找到 packages = ["app"] 並完成 wheel build
# 這樣 pyproject.toml 沒改變時，依賴層可以直接用 cache
COPY pyproject.toml .
RUN mkdir -p app && touch app/__init__.py
RUN uv pip install --system ".[dev]"

# ── 覆蓋成真正的應用程式碼 ─────────────────────────────────
COPY . .

# 讓 Python 能找到 /app/app 模組
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]
