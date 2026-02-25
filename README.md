# 📬 MailCake

> AI 驅動的電子信件智慧統整平台

## 功能

- 🤖 **LiteLLM 多模型支援**：Claude / GPT / Gemini / Ollama 本地模型一鍵切換
- 📧 **Gmail OAuth 接入**：安全的 read-only 授權
- ⚡ **智慧分流**：自動評分緊急程度與重要性
- 💬 **Smart Reply**：AI 生成 3 個回覆選項，一鍵複製
- 📬 **每日 Digest**：定時發送 AI 摘要信
- 🔒 **隱私優先**：選擇本地 Ollama，信件不離開你的伺服器

## 快速啟動

### 1. 設定環境變數

```bash
cp .env.example .env
```

編輯 `.env`，至少填入以下其中一個 LLM API Key：
- `ANTHROPIC_API_KEY` - Claude 系列
- `OPENAI_API_KEY` - GPT 系列

Gmail OAuth 需要：
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`

> 📌 Gmail OAuth 設定教學：https://console.cloud.google.com/apis/credentials
> 建立 OAuth 2.0 Client ID，類型選「Web 應用程式」
> 新增 Authorized redirect URI：`http://localhost:8000/api/v1/auth/gmail/callback`

### 2. 啟動

```bash
make up
```

### 3. 開啟

- 前台：http://localhost:3000
- API 文件：http://localhost:8000/docs
- LiteLLM 監控：http://localhost:4000/ui

## 本地 LLM（完全私有）

```bash
make up-local  # 啟動含 Ollama
```

首次啟動會自動下載 llama3.2 和 mistral 模型（約 4-8GB）

## 服務架構

```
Frontend (Next.js :3000)
    ↓
Backend API (FastAPI :8000)
    ↓
LiteLLM Proxy (:4000) → OpenAI / Claude / Gemini / Ollama
    ↓
PostgreSQL + Redis
    ↓
Worker (Email Sync + Digest)
```

## 技術棧

| 層次 | 技術 |
|------|------|
| Frontend | Next.js 15 + Tailwind CSS |
| Backend | FastAPI (Python 3.11) |
| LLM 抽象 | LiteLLM Proxy |
| 本地 LLM | Ollama |
| 資料庫 | PostgreSQL 16 |
| 快取/佇列 | Redis 7 |
| 容器化 | Docker Compose |
