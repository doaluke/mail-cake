# MailCake — 詳細操作手冊

> 本手冊涵蓋從環境建置到日常維運的所有操作步驟。

---

## 目錄

1. [系統架構總覽](#1-系統架構總覽)
2. [前置需求](#2-前置需求)
3. [首次安裝與設定](#3-首次安裝與設定)
4. [環境變數說明](#4-環境變數說明)
5. [啟動、停止與重啟服務](#5-啟動停止與重啟服務)
6. [Gmail OAuth 設定流程](#6-gmail-oauth-設定流程)
7. [監控與日誌](#7-監控與日誌)
8. [LLM 模型管理與除錯](#8-llm-模型管理與除錯)
9. [資料庫操作](#9-資料庫操作)
10. [Worker 與郵件同步機制](#10-worker-與郵件同步機制)
11. [常見問題排除](#11-常見問題排除)
12. [常用 Make 指令速查](#12-常用-make-指令速查)
13. [本機 Ollama（離線 LLM）](#13-本機-ollama離線-llm)

---

## 1. 系統架構總覽

```
瀏覽器
  │
  ▼
Next.js Frontend (:3000)
  │  HTTP / REST
  ▼
FastAPI Backend API (:8000)
  │                    │
  ▼                    ▼
PostgreSQL (:5432)   Redis (:6379)
  │
  ▼
LiteLLM Proxy (:4000)
  │
  ├── Anthropic Claude (claude-haiku / claude-sonnet)
  ├── OpenAI GPT (gpt-4o-mini / gpt-4o)
  ├── Google Gemini (gemini-flash)
  └── Ollama 本地模型 (llama3.2 / mistral)  ← 選配

背景 Worker (email_sync + digest)
  ├── 每 2 分鐘同步 Gmail 新信件
  └── 每小時整點檢查是否發送 Digest
```

### 服務清單

| 服務 | Container 名稱 | 對外 Port | 說明 |
|------|---------------|-----------|------|
| Frontend | `mailcake-frontend` | 3000 | Next.js UI |
| Backend API | `mailcake-api` | 8000 | FastAPI REST |
| Worker | `mailcake-worker` | — | 郵件同步 + 摘要生成 |
| LiteLLM Proxy | `mailcake-litellm` | 4000 | LLM 統一代理 |
| PostgreSQL | `mailcake-postgres` | 5432 | 主資料庫 |
| Redis | `mailcake-redis` | 6379 | 快取 / 佇列 |
| Ollama | `mailcake-ollama` | 11434 | 本機 LLM（選配） |

---

## 2. 前置需求

| 工具 | 最低版本 | 說明 |
|------|---------|------|
| Docker | 24.x | 容器執行環境 |
| Docker Compose | 2.x (`docker compose`) | 多服務管理 |
| Make | 任意 | 快捷指令 |
| Git | 任意 | 版本控制 |

> **macOS 使用者**：安裝 Docker Desktop，內含 Docker Compose v2。

---

## 3. 首次安裝與設定

### 3.1 Clone 專案

```bash
git clone <repo-url> mail-cake
cd mail-cake
```

### 3.2 建立 `.env`

```bash
make setup
# 等同於: cp .env.example .env
```

接著編輯 `.env`，填入下列必要欄位（詳見 [第 4 節](#4-環境變數說明)）：

```
ANTHROPIC_API_KEY=sk-ant-...     # 至少填一個 LLM Key
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
SECRET_KEY=<隨機 32 字元以上字串>
LITELLM_MASTER_KEY=sk-mailcake-...
```

### 3.3 啟動所有服務

```bash
make up
```

首次啟動會自動：
- 拉取所有 Docker image
- 建立 PostgreSQL / Redis volumes
- 執行資料庫 migration（`alembic upgrade head`）
- 建立所有 DB 資料表

啟動完成後可訪問：
- **前端**：http://localhost:3000
- **API 文件**：http://localhost:8000/docs
- **LiteLLM 管理介面**：http://localhost:4000/ui

---

## 4. 環境變數說明

> `.env` 中的變數會在 `make up` 時自動注入所有容器。

### 4.1 必填項目

```dotenv
# ── 應用程式 ──────────────────────────────────────────────────
APP_ENV=development                    # production 時改為 production
SECRET_KEY=<至少 32 字元的隨機字串>     # JWT 簽名用；不可洩漏！

# ── 資料庫 ───────────────────────────────────────────────────
POSTGRES_USER=mailcake
POSTGRES_PASSWORD=mailcake_password
POSTGRES_DB=mailcake
DATABASE_URL=postgresql://mailcake:mailcake_password@postgres:5432/mailcake

# ── Redis ───────────────────────────────────────────────────
REDIS_URL=redis://redis:6379

# ── LiteLLM Proxy ────────────────────────────────────────────
LITELLM_MASTER_KEY=sk-mailcake-master-key   # 呼叫 Proxy 的認證 Key
LITELLM_PROXY_URL=http://litellm:4000       # API 內部呼叫位址

# ── Gmail OAuth ─────────────────────────────────────────────
GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxx
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/gmail/callback
FRONTEND_URL=http://localhost:3000
```

### 4.2 選填項目（依需求填入）

```dotenv
# ── LLM API Keys（至少一個）──────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-...      # Claude 模型
OPENAI_API_KEY=sk-...             # GPT 模型
GEMINI_API_KEY=AIzaSy...          # Gemini 模型

# ── Digest 郵件（用 SMTP 寄送每日摘要）────────────────────────
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASSWORD=<Gmail App Password>

# ── 監控（Grafana）───────────────────────────────────────────
GRAFANA_PASSWORD=admin
```

### 4.3 ⚠️ 注意事項

- **`SECRET_KEY` 必須在 API 和 Worker 中保持一致**，兩個 container 使用同一個 `.env`，正常情況下不需額外處理。
- 修改 `.env` 後，**必須執行 `make up`（而非 `make restart`）** 才能讓容器讀到新的環境變數。`restart` 只重啟 process，不重新載入 env。

---

## 5. 啟動、停止與重啟服務

### 5.1 完整啟動（最常用）

```bash
make up
# 等同於: docker compose up -d --build
```

會重新建置 image 並以 detached 模式啟動所有服務。

### 5.2 停止所有服務

```bash
make down
# 等同於: docker compose down
```

> 資料不會遺失，volumes 保留。

### 5.3 重置所有資料（清除 Volume）

```bash
make clean
# 等同於: docker compose down -v
```

> ⚠️ 這會刪除所有 PostgreSQL 資料、Redis 快取、Ollama 模型。

### 5.4 重啟單一服務

```bash
docker compose restart api
docker compose restart worker
docker compose restart litellm
docker compose restart frontend
```

> 適用於：程式碼已透過 volume mount 更新（如修改 Python 檔案後），不需重新 build image 時。
> ⚠️ **`.env` 修改不適用**，必須用 `make up`。

### 5.5 重新 build 並啟動單一服務

```bash
docker compose up -d --build api
docker compose up -d --build worker
```

### 5.6 查看所有容器狀態

```bash
docker compose ps
```

---

## 6. Gmail OAuth 設定流程

### 6.1 在 Google Cloud Console 建立 OAuth 應用程式

1. 前往 [Google Cloud Console](https://console.cloud.google.com/)
2. 建立新專案（或選擇現有專案）
3. 啟用 **Gmail API**：APIs & Services → Library → 搜尋 "Gmail API" → Enable
4. 建立 OAuth 2.0 憑證：
   - APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID
   - Application type：**Web application**
   - Authorized redirect URIs：`http://localhost:8000/api/v1/auth/gmail/callback`
5. 下載 Client ID 和 Client Secret，填入 `.env`

### 6.2 設定 OAuth Consent Screen

1. APIs & Services → OAuth consent screen
2. User Type：**External**（個人帳戶）或 Internal（Google Workspace）
3. 必填範圍（Scopes）：
   - `https://www.googleapis.com/auth/gmail.readonly`
   - `https://www.googleapis.com/auth/gmail.modify`（如需標記已讀）
4. 測試帳號：加入你要測試的 Gmail 帳號

> **注意**：App 未驗證前，Consent Screen 會出現警告，點選「進階 → 前往」即可繼續。

### 6.3 連結 Gmail 帳戶（使用者操作流程）

1. 前往 http://localhost:3000
2. 點擊「連結 Gmail 帳戶」
3. 選擇 Google 帳號並授權
4. 授權完成後自動跳回前端，開始同步信件

### 6.4 確認 OAuth Token 已儲存

```bash
make shell-db
# 進入 psql 後：
SELECT id, email, provider, is_active, last_synced_at
FROM email_accounts;
```

---

## 7. 監控與日誌

### 7.1 即時查看所有服務日誌

```bash
make logs
# 等同於: docker compose logs -f
```

### 7.2 只看特定服務

```bash
make logs-api       # FastAPI 後端
make logs-worker    # Email 同步 Worker

# 或直接用 docker compose：
docker compose logs -f worker
docker compose logs -f litellm
docker compose logs -f postgres
```

### 7.3 Worker 日誌解讀

正常運作時應看到：

```
✅ Worker 啟動，排程任務已設定
  - Email 同步: 每 2 分鐘
  - Digest 發送: 每小時整點檢查
...
[INFO] 開始同步帳號 user@gmail.com
[INFO] Gmail 新信件: 3 封
[INFO] 開始並行分析 3 封信件（concurrency=5）
[INFO] ✅ 信件摘要完成: <message-id>
[INFO] ✅ 信件摘要完成: <message-id>
```

⚠️ 需注意的警告訊息：

| 日誌訊息 | 意義 | 處理方式 |
|---------|------|---------|
| `模型 'llama3.2-local' 是本地模型，自動改用 'claude-haiku'` | Ollama 未啟動 | 正常（自動降級）；如需本地模型見 [第 13 節](#13-本機-ollama離線-llm) |
| `PendingRollbackError` | 資料庫寫入失敗 | 查看上一行的 `DataError` 或 `IntegrityError` |
| `OllamaException - model not found` | Ollama Container 未啟動 | 改用 `make up-local` 或換用雲端模型 |
| `LiteLLM RateLimitError` | API Key 超出用量 | 等待或換用備援模型 |

### 7.4 LiteLLM 管理介面

訪問 http://localhost:4000/ui（需設定 `LITELLM_MASTER_KEY`）
可查看：
- 每個模型的呼叫次數與 Tokens 用量
- 失敗率與 Fallback 觸發紀錄
- 即時請求日誌

---

## 8. LLM 模型管理與除錯

### 8.1 可用模型清單

| 模型 ID（前端選項）| 實際模型 | API 來源 |
|------------------|---------|---------|
| `claude-haiku` | claude-3-haiku-20240307 | Anthropic |
| `claude-haiku-3-5` | claude-3-5-haiku-20241022 | Anthropic（需較高 Tier）|
| `claude-sonnet` | claude-3-5-sonnet-20241022 | Anthropic |
| `gpt-4o-mini` | gpt-4o-mini | OpenAI |
| `gpt-4o` | gpt-4o | OpenAI |
| `gemini-flash` | gemini-1.5-flash | Google |
| `llama3.2-local` | ollama/llama3.2 | 本機 Ollama |
| `mistral-local` | ollama/mistral | 本機 Ollama |

### 8.2 Fallback 鏈

當主要模型失敗時，LiteLLM 會自動嘗試：

```
claude-sonnet → claude-haiku → gpt-4o
claude-haiku  → gpt-4o-mini
gpt-4o        → claude-sonnet → claude-haiku
gpt-4o-mini   → claude-haiku
llama3.2-local → claude-haiku → gpt-4o-mini
mistral-local  → claude-haiku → gpt-4o-mini
```

### 8.3 修改模型設定後如何生效

1. 修改 `litellm_config.yaml`
2. 重啟 LiteLLM 容器（不需 `--build`，config 是 volume mount）：

```bash
docker compose restart litellm
```

3. 驗證：

```bash
curl http://localhost:4000/models \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY"
```

### 8.4 修改使用者預設模型（資料庫層）

```sql
-- 修改所有使用者
UPDATE users SET default_model = 'claude-haiku';

-- 修改特定使用者
UPDATE users SET default_model = 'gpt-4o-mini'
WHERE email = 'user@example.com';

-- 重置所有設定了本地模型的使用者
UPDATE users SET default_model = 'claude-haiku'
WHERE default_model LIKE '%local%';
```

### 8.5 測試 LLM 是否正常運作

```bash
curl http://localhost:4000/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -d '{
    "model": "claude-haiku",
    "messages": [{"role": "user", "content": "Say hello"}]
  }'
```

---

## 9. 資料庫操作

### 9.1 進入 PostgreSQL Shell

```bash
make shell-db
# 等同於: docker compose exec postgres psql -U mailcake -d mailcake
```

### 9.2 常用查詢

```sql
-- 查看所有使用者
SELECT id, email, name, default_model, created_at FROM users;

-- 查看已連結的信箱帳戶
SELECT id, user_id, email, provider, is_active, last_synced_at
FROM email_accounts;

-- 查看信件與摘要統計
SELECT
  COUNT(DISTINCT m.id) AS total_emails,
  COUNT(DISTINCT s.id) AS emails_with_summary,
  COUNT(DISTINCT m.id) - COUNT(DISTINCT s.id) AS pending_summary
FROM email_messages m
LEFT JOIN email_summaries s ON s.message_id = m.id;

-- 查看最新 10 封信件的摘要
SELECT
  m.subject,
  m.sender,
  m.received_at,
  m.urgency_score,
  s.text AS summary
FROM email_messages m
LEFT JOIN email_summaries s ON s.message_id = m.id
ORDER BY m.received_at DESC
LIMIT 10;

-- 查看還沒有摘要的信件（等待 Worker 處理）
SELECT m.id, m.subject, m.received_at
FROM email_messages m
LEFT JOIN email_summaries s ON s.message_id = m.id
WHERE s.id IS NULL
ORDER BY m.received_at DESC;
```

### 9.3 資料庫 Migration

專案使用 Alembic 管理 Schema 版本。

```bash
# 執行所有待套用的 migration
make migrate
# 等同於: docker compose exec api alembic upgrade head

# 查看目前版本
docker compose exec api alembic current

# 查看 migration 歷史
docker compose exec api alembic history

# 建立新的 migration（修改 models 後）
docker compose exec api alembic revision --autogenerate -m "add new column"
```

### 9.4 備份與還原

```bash
# 備份
docker compose exec postgres pg_dump -U mailcake mailcake > backup_$(date +%Y%m%d).sql

# 還原
cat backup_20240101.sql | docker compose exec -T postgres psql -U mailcake -d mailcake
```

---

## 10. Worker 與郵件同步機制

### 10.1 Worker 運作流程

```
每 2 分鐘（IntervalTrigger）
  │
  ▼
sync_all_accounts()
  │
  ├─ 對每個 active=True, is_enabled=True 的 EmailAccount：
  │
  ├─ _sync_gmail(db, account)
  │   ├── 解密 OAuth Token
  │   ├── 呼叫 Gmail API（History API）
  │   ├── 取得自上次 last_history_id 以來的新信件
  │   ├── 儲存 EmailMessage 到 DB
  │   └── 更新 last_history_id
  │
  ├─ Backfill（補漏）查詢：
  │   └── 找出最多 20 封「沒有 EmailSummary」的信件
  │       （確保過去未分析的信件也會被處理）
  │
  └─ analyze_new_messages(message_ids)
      ├── 建立 asyncio.Semaphore(5)（最多 5 個並行 LLM 呼叫）
      └─ 對每封信：
          ├── 獨立 DB Session
          ├── 呼叫 LiteLLM Proxy → LLM 分析
          ├── 更新 EmailMessage（urgency, importance, category...）
          └── 建立 EmailSummary 記錄
```

### 10.2 觸發手動立即同步

有兩種方式：

**方式 1：REST API**

```bash
# 需先取得 JWT Token（登入後從前端 Cookie 取得）
curl -X POST http://localhost:8000/api/v1/emails/sync \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

**方式 2：直接執行 Worker**

```bash
docker compose exec worker python -c "
import asyncio
from app.workers.email_sync import sync_all_accounts
asyncio.run(sync_all_accounts())
"
```

### 10.3 Backfill 機制

Backfill 確保以下情況下信件仍能被分析：

- 系統剛佈署時 DB 已有信件但 Worker 尚未運行
- LLM 呼叫失敗導致某些信件漏掉摘要
- Worker 長時間停機後重啟

每次 Worker 運行，會自動找最多 **20 封**沒有摘要的信件補充分析。
若積壓大量信件（如首次同步 100 封），需等待多次 Worker 週期（每 2 分鐘）才能全部完成。

### 10.4 修改 Worker 排程頻率

編輯 `backend/app/workers/main.py`：

```python
# 調整同步頻率（當前：2 分鐘）
scheduler.add_job(
    sync_all_accounts,
    trigger=IntervalTrigger(minutes=2),  # ← 修改這裡
    ...
)

# 調整 Digest 發送時間（當前：每小時整點）
scheduler.add_job(
    send_digest_for_all_users,
    trigger=CronTrigger(minute=0),  # ← 修改 cron 表達式
    ...
)
```

修改後重啟 Worker：

```bash
docker compose restart worker
```

---

## 11. 常見問題排除

### ❶ 摘要一直不出現（前端顯示「摘要生成中...」）

**排查步驟：**

```bash
# 1. 查看 Worker 是否在運行
docker compose ps worker

# 2. 查看 Worker 日誌是否有錯誤
make logs-worker

# 3. 直接查資料庫
make shell-db
# 執行：
SELECT COUNT(*) FROM email_summaries;

# 4. 查看是否有待處理信件
SELECT COUNT(*) FROM email_messages m
LEFT JOIN email_summaries s ON s.message_id = m.id
WHERE s.id IS NULL;
```

**常見原因與解法：**

| 原因 | 跡象 | 解法 |
|------|------|------|
| Worker 停止 | `docker compose ps` 顯示 Exited | `docker compose up -d worker` |
| LiteLLM 無法連線 | Worker 日誌有 `Connection refused :4000` | `docker compose restart litellm` |
| API Key 失效 | 日誌有 `AuthenticationError` | 更新 `.env` 中的 API Key，執行 `make up` |
| 所有信件已有 history_id 記錄但無摘要 | DB 有信件但無摘要 | 等待 Backfill（最多 2 分鐘）|

---

### ❷ `PendingRollbackError` / `DataError`

```
DataError: invalid input for query argument: expected str, got list
```

**原因**：LLM 回傳 `summary` 為 JSON 陣列而非字串。
**解法**：已在 `llm_service.py` 中修正（型別正規化）。若仍發生，查看 LLM 的原始輸出：

```bash
docker compose logs -f worker | grep -A5 "LLM 原始"
```

---

### ❸ Ollama / 本地模型錯誤

```
OllamaException - model 'llama3.2' not found
No fallback model group found for original model_group=llama3.2-local
```

**原因**：使用者 `default_model` 設為 `llama3.2-local` 但 Ollama 未啟動。

**解法 A（快速）**：Worker 已內建 `_resolve_model()` 自動降級，應自動使用 `claude-haiku`。若沒有，重啟 Worker：

```bash
docker compose restart worker
```

**解法 B（根本）**：重置資料庫中的本地模型設定：

```bash
make shell-db
# 執行：
UPDATE users SET default_model = 'claude-haiku'
WHERE default_model LIKE '%local%';
```

**解法 C**：啟動 Ollama（見 [第 13 節](#13-本機-ollama離線-llm)）

---

### ❹ `litellm.NotFoundError: model not found`

```
AnthropicException - model: claude-3-5-haiku-20241022 not found
```

**原因**：使用的模型版本需要更高的 API Tier。
**解法**：在 `litellm_config.yaml` 中確認 `claude-haiku` 對應的是 `claude-3-haiku-20240307`：

```yaml
- model_name: claude-haiku
  litellm_params:
    model: anthropic/claude-3-haiku-20240307  # ← 確認是這個版本
    api_key: os.environ/ANTHROPIC_API_KEY
```

修改後：`docker compose restart litellm`

---

### ❺ Gmail OAuth 授權失敗

**`redirect_uri_mismatch`**：Google Console 中的 Redirect URI 與 `.env` 中的 `GOOGLE_REDIRECT_URI` 不一致。
→ 確保兩者完全相符，包含 `http/https` 和 port。

**`invalid_client`**：Client ID / Secret 錯誤或已過期。
→ 重新到 Google Console 複製憑證。

**`access_denied`**：使用者帳號不在測試白名單。
→ 在 OAuth Consent Screen 中加入該帳號。

---

### ❻ `.env` 修改後沒有生效

**症狀**：修改了 API Key 或 SECRET_KEY，但容器還是用舊值。

**原因**：`docker compose restart` 不重新讀取 `.env`。

**解法**：必須完整重建容器：

```bash
make up
# 或針對特定服務：
docker compose up -d api worker litellm
```

---

### ❼ 前端顯示「載入中...」一直不消失

```bash
# 查看 API 是否正常
curl http://localhost:8000/health

# 查看 API 日誌
make logs-api

# 查看前端是否能打到 API（瀏覽器 DevTools → Network）
```

---

## 12. 常用 Make 指令速查

```bash
# ─── 服務管理 ────────────────────────────────────────────────
make setup          # 建立 .env（首次安裝）
make up             # 啟動所有服務並重新 build
make down           # 停止所有服務（保留資料）
make clean          # 停止並清除所有 Volumes（資料重置）
make build          # 重新 build 所有 Image
make restart        # 重啟所有服務（不 build）
make up-local       # 啟動含 Ollama 的完整環境

# ─── 日誌 ───────────────────────────────────────────────────
make logs           # 所有服務日誌（跟蹤模式）
make logs-api       # API 日誌
make logs-worker    # Worker 日誌

# ─── Shell 進入 ─────────────────────────────────────────────
make shell-api      # 進入 API 容器 bash
make shell-db       # 進入 PostgreSQL shell

# ─── 資料庫 ─────────────────────────────────────────────────
make migrate        # 執行 DB Migration
```

---

## 13. 本機 Ollama（離線 LLM）

> 使用本地 LLM 讓信件不離開你的設備，完全保護隱私。

### 13.1 啟動含 Ollama 的環境

```bash
make up-local
# 等同於: docker compose --profile local-llm up -d --build
```

首次啟動會自動下載模型（需要時間和磁碟空間）：
- `llama3.2`：約 2GB
- `mistral`：約 4GB

### 13.2 確認 Ollama 運作正常

```bash
curl http://localhost:11434/api/tags
# 應回傳已下載的模型清單
```

### 13.3 手動拉取模型

```bash
docker compose exec ollama ollama pull llama3.2
docker compose exec ollama ollama pull mistral
```

### 13.4 在前端選擇本地模型

在「模型設定」面板中選擇：
- `llama3.2-local`
- `mistral-local`

### 13.5 Ollama 不運行時的行為

Worker 中的 `_resolve_model()` 函數會自動偵測本地模型（名稱包含 `llama`、`mistral`、`-local` 等字樣），並降級使用 `claude-haiku`，確保分析不中斷。

---

## 附錄：服務健康檢查 URL

| 服務 | 健康檢查 URL |
|------|------------|
| API | http://localhost:8000/health |
| API 文件 | http://localhost:8000/docs |
| LiteLLM | http://localhost:4000/health |
| LiteLLM UI | http://localhost:4000/ui |
| Ollama | http://localhost:11434/api/tags |

---

*最後更新：2026-02-25*
