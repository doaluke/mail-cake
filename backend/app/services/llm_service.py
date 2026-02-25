"""
LLM Service - 透過 LiteLLM Proxy 統一呼叫所有模型

一次 LLM call 同時取得：
  - 信件摘要
  - 分流評分（urgency/importance）
  - Smart Reply 草稿建議
  - 主題分類
"""
import json
import time
from typing import AsyncGenerator
from openai import AsyncOpenAI
from app.core.config import get_settings

settings = get_settings()

# ─── 摘要風格 Prompts ────────────────────────────────────────────
STYLE_PROMPTS = {
    "bullet_points": """
你是專業的信件分析師。請將信件整理成 5-7 個重點條列。
- 保留重要的人名、日期、數字
- 每點不超過 30 字
- 按重要性由高到低排列
""",
    "executive": """
你是高階主管助理。請寫一份 100-150 字的主管摘要。
格式：【核心訊息】→【需要決策的事項】→【建議行動】
語氣：專業、簡潔
""",
    "action_items": """
你的任務是從信件中提取待辦事項。
格式：[截止日期或ASAP] 任務描述（負責人/確認對象）
只列出明確的行動項目，忽略純資訊性內容。
""",
    "detailed": """
你是詳細記錄的助理。請整理完整筆記，包含：
## 主要內容
## 重要決定或共識
## 後續行動
## 相關人員
保留所有重要的細節。
""",
    "one_liner": "用一句話（不超過 30 字）說明這封信的核心內容。",
}

# ─── 主系統 Prompt（包含所有功能） ──────────────────────────────
MASTER_SYSTEM_PROMPT = """
你是一個專業的信件分析助理。請分析以下信件並以 JSON 格式回應，包含以下欄位：

{{
  "summary": "依照指定風格整理的摘要",
  "urgency_score": 1-5（1=不急，5=非常緊急），
  "importance_score": 1-5（1=不重要，5=非常重要），
  "action_required": true/false（是否需要採取行動），
  "category": "工作信件|電子報|帳單財務|會議邀請|促銷廣告|個人通知|其他",
  "sentiment": "positive|neutral|negative",
  "reply_suggestions": ["建議回覆1", "建議回覆2", "建議回覆3"]
}}

摘要風格：{style}
語言：請用{language}語言回應

注意：
- reply_suggestions 請根據信件內容提供 3 個自然、實用的回覆選項
- urgency_score 和 importance_score 要基於內容客觀評分
- 若信件是電子報或廣告，reply_suggestions 可為空陣列
"""


class LLMService:
    """透過 LiteLLM Proxy 統一呼叫所有模型"""

    def __init__(self):
        # 後端只需要知道 Proxy URL，不需要各個 API Key
        self.client = AsyncOpenAI(
            base_url=f"{settings.litellm_proxy_url}/v1",
            api_key=settings.litellm_master_key,
        )

    async def analyze_email(
        self,
        email_content: str,
        style: str = "bullet_points",
        model: str | None = None,
        language: str = "zh-TW",
    ) -> dict:
        """
        一次 LLM call 完成摘要 + 評分 + 回覆建議

        Returns:
            {
                summary, urgency_score, importance_score,
                action_required, category, sentiment,
                reply_suggestions, model_used, tokens_used, generation_ms
            }
        """
        model = model or settings.default_model
        start_time = time.time()

        system_prompt = MASTER_SYSTEM_PROMPT.format(
            style=STYLE_PROMPTS.get(style, STYLE_PROMPTS["bullet_points"]),
            language=language,
        )

        # 截斷過長的信件（省 token）
        max_chars = settings.max_tokens_per_email * 3  # 約 3 char/token
        content = email_content[:max_chars] if len(email_content) > max_chars else email_content

        response = await self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"<email>\n{content}\n</email>"},
            ],
            temperature=0.3,
            max_tokens=800,
            response_format={"type": "json_object"},
        )

        generation_ms = int((time.time() - start_time) * 1000)
        raw = response.choices[0].message.content
        result = json.loads(raw)

        # ── 正規化 summary 欄位 ──────────────────────────────────────
        # Claude 有時把 bullet_points 回傳成 JSON array，
        # 但 summary_text 欄位是 VARCHAR，必須是字串。
        summary = result.get("summary", "")
        if isinstance(summary, list):
            result["summary"] = "\n".join(f"• {item}" for item in summary if item)
        elif not isinstance(summary, str):
            result["summary"] = str(summary)

        # ── 正規化 reply_suggestions 欄位 ────────────────────────────
        # 確保一定是 list[str]，避免 JSON 欄位存入非預期型別
        suggestions = result.get("reply_suggestions", [])
        if isinstance(suggestions, str):
            try:
                suggestions = json.loads(suggestions)
            except Exception:
                suggestions = [suggestions]
        if not isinstance(suggestions, list):
            suggestions = []
        result["reply_suggestions"] = [str(s) for s in suggestions]

        return {
            **result,
            "model_used": model,
            "tokens_used": response.usage.total_tokens if response.usage else None,
            "generation_ms": generation_ms,
        }

    async def analyze_email_stream(
        self,
        email_content: str,
        style: str = "bullet_points",
        model: str | None = None,
        language: str = "zh-TW",
    ) -> AsyncGenerator[str, None]:
        """Streaming 版本 - 即時顯示摘要生成"""
        model = model or settings.default_model

        response = await self.client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": STYLE_PROMPTS.get(style, STYLE_PROMPTS["bullet_points"])
                    + f"\n請用{language}語言回應。",
                },
                {"role": "user", "content": f"<email>\n{email_content}\n</email>"},
            ],
            temperature=0.3,
            max_tokens=600,
            stream=True,
        )

        async for chunk in response:
            content = chunk.choices[0].delta.content
            if content:
                yield content

    async def analyze_thread(
        self,
        thread_emails: list[dict],
        style: str = "executive",
        model: str | None = None,
        language: str = "zh-TW",
    ) -> dict:
        """分析整個 Thread（多封信的對話）"""
        model = model or settings.default_model

        # 組合 Thread 內容
        thread_content = "\n\n---\n\n".join(
            [
                f"[{i+1}/{len(thread_emails)}] 寄件人: {e.get('sender', '?')}\n"
                f"時間: {e.get('received_at', '?')}\n"
                f"內容: {e.get('body_plain', '')[:500]}"
                for i, e in enumerate(thread_emails)
            ]
        )

        system_prompt = f"""
你是專業的對話分析師。以下是一段電子郵件對話（共 {len(thread_emails)} 封）。
請分析整個對話並以 JSON 格式回應：
{{
  "summary": "整個對話的{style}風格摘要",
  "urgency_score": 1-5,
  "importance_score": 1-5,
  "action_required": true/false,
  "category": "類別",
  "sentiment": "整體情緒",
  "reply_suggestions": ["建議回覆1", "建議回覆2", "建議回覆3"],
  "thread_summary": "對話進展摘要（誰說了什麼，達成什麼共識）"
}}
請用{language}語言回應。
"""

        response = await self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"<thread>\n{thread_content}\n</thread>"},
            ],
            temperature=0.3,
            max_tokens=1000,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)
        return {
            **result,
            "model_used": model,
            "tokens_used": response.usage.total_tokens if response.usage else None,
        }

    async def get_available_models(self) -> list[dict]:
        """從 LiteLLM Proxy 取得可用模型清單"""
        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.litellm_proxy_url}/v1/models",
                headers={"Authorization": f"Bearer {settings.litellm_master_key}"},
                timeout=5.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                return [m["id"] for m in data.get("data", [])]
        return []
