.PHONY: help up up-local down logs build restart clean setup migrate shell-api shell-db

# 自動從 .env 載入並 export，確保 shell 的空變數不會覆蓋 .env 的值
ifneq (,$(wildcard .env))
  include .env
  export
endif

help:
	@echo "MailCake - 可用指令："
	@echo ""
	@echo "  make setup    - 初始化環境（複製 .env）"
	@echo "  make up       - 啟動所有服務"
	@echo "  make down     - 停止所有服務"
	@echo "  make logs     - 查看 log"
	@echo "  make build    - 重新 build 映像"
	@echo "  make restart  - 重新啟動"
	@echo "  make clean    - 清除 volumes（重置資料）"
	@echo ""
	@echo "  make up-local - 啟動含本地 Ollama（需要較多記憶體）"

setup:
	@if [ ! -f .env ]; then cp .env.example .env && echo "✅ .env 已建立，請填入你的 API Keys"; else echo "⚠️  .env 已存在"; fi

up: setup
	docker compose up -d
	@echo ""
	@echo "✅ MailCake 啟動中..."
	@echo "   📊 Frontend:      http://localhost:3000"
	@echo "   🔌 API:           http://localhost:8000"
	@echo "   🤖 LiteLLM UI:    http://localhost:4000/ui"
	@echo "   📚 API Docs:      http://localhost:8000/docs"

up-local: setup
	docker compose --profile local-llm up -d

down:
	docker compose down

logs:
	docker compose logs -f

logs-api:
	docker compose logs -f api

logs-worker:
	docker compose logs -f worker

build:
	docker compose build --no-cache

restart:
	docker compose restart

clean:
	docker compose down -v
	@echo "⚠️  已清除所有資料"

migrate:
	docker compose exec api alembic upgrade head

shell-api:
	docker compose exec api bash

shell-db:
	docker compose exec postgres psql -U mailcake mailcake
