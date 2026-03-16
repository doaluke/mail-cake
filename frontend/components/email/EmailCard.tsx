"use client";
import { useState, useEffect, useRef } from "react";
import { Paperclip, Zap, Star, ChevronDown, ChevronUp, Copy, Check, RefreshCw } from "lucide-react";
import { cn, timeAgo, urgencyColor, urgencyLabel, sentimentEmoji } from "@/lib/utils";
import type { Email } from "@/lib/api";

interface Props {
  email: Email;
  onResummarize?: (id: string, style: string, model: string, newText: string) => void;
}

const URGENCY_STYLES: Record<string, string> = {
  red:    "bg-red-50 border-red-200 border-l-red-500",
  yellow: "bg-amber-50 border-amber-200 border-l-amber-500",
  green:  "bg-green-50 border-green-200 border-l-green-500",
  gray:   "bg-white border-gray-200 border-l-gray-200",
};

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function EmailCard({ email, onResummarize }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [copiedReply, setCopiedReply] = useState<string | null>(null);
  const [streamingText, setStreamingText] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  // 清理 EventSource（元件卸載或 email 切換時）
  useEffect(() => {
    return () => {
      esRef.current?.close();
    };
  }, [email.id]);

  const color = urgencyColor(email.urgency_score);

  // 展開時，如果沒有摘要也沒在 streaming，自動觸發生成
  const autoTriggered = useRef(false);
  useEffect(() => {
    if (expanded && !email.summary && !isStreaming && !streamingText && !autoTriggered.current) {
      autoTriggered.current = true;
      handleResummarize();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expanded]);

  const handleResummarize = () => {
    if (isStreaming) return;

    const style = email.summary?.style || "bullet_points";
    const model = email.summary?.model_used || "";
    const params = new URLSearchParams({ style });
    if (model) params.set("model", model);

    setIsStreaming(true);
    setStreamingText("");

    const es = new EventSource(
      `${API_URL}/api/v1/emails/${email.id}/summarize/stream?${params}`,
      { withCredentials: true }
    );
    esRef.current = es;

    let accumulated = "";

    es.onmessage = (e) => {
      if (e.data === "[DONE]") {
        es.close();
        setIsStreaming(false);
        setStreamingText(null); // 切回由 parent cache 提供資料
        onResummarize?.(email.id, style, model, accumulated);
      } else {
        accumulated += e.data;
        setStreamingText(accumulated);
      }
    };

    es.onerror = () => {
      es.close();
      setIsStreaming(false);
      setStreamingText(null);
    };
  };

  const copyReply = async (text: string) => {
    await navigator.clipboard.writeText(text);
    setCopiedReply(text);
    setTimeout(() => setCopiedReply(null), 2000);
  };

  // streaming 中顯示串流文字，完成後顯示 DB 資料（由 parent 刷新）
  const displayText = streamingText !== null ? streamingText : email.summary?.text;

  return (
    <div
      className={cn(
        "rounded-lg border border-l-4 transition hover:shadow-sm",
        URGENCY_STYLES[color]
      )}
    >
      {/* Header */}
      <div
        className="p-4 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            {/* 主旨 + 標籤 */}
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              {!email.is_read && (
                <span className="w-2 h-2 rounded-full bg-primary-500 shrink-0" />
              )}
              <span className={cn("text-sm font-semibold truncate", !email.is_read && "text-gray-900")}>
                {email.subject || "(無主旨)"}
              </span>
              {email.action_required && (
                <span className="text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded font-medium shrink-0">
                  需行動
                </span>
              )}
              {email.ai_category && (
                <span className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded shrink-0">
                  {email.ai_category}
                </span>
              )}
            </div>

            {/* 寄件者 + 時間 */}
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <span className="truncate">{email.sender}</span>
              <span>·</span>
              <span className="shrink-0">{timeAgo(email.received_at)}</span>
              {email.has_attachments && <Paperclip className="w-3 h-3 shrink-0" />}
              {email.is_starred && <Star className="w-3 h-3 text-amber-500 shrink-0" />}
            </div>
          </div>

          {/* 右側：評分 + 展開 */}
          <div className="flex items-center gap-2 shrink-0">
            {email.urgency_score && email.urgency_score >= 3 && (
              <span className={cn(
                "flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full",
                color === "red" ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-700"
              )}>
                <Zap className="w-3 h-3" />
                {urgencyLabel(email.urgency_score)}
              </span>
            )}
            {email.sentiment && (
              <span className="text-base">{sentimentEmoji(email.sentiment)}</span>
            )}
            {expanded ? (
              <ChevronUp className="w-4 h-4 text-gray-400" />
            ) : (
              <ChevronDown className="w-4 h-4 text-gray-400" />
            )}
          </div>
        </div>

        {/* Snippet（收合時顯示） */}
        {!expanded && displayText && (
          <p className="mt-2 text-xs text-gray-600 line-clamp-2">
            {displayText}
          </p>
        )}
      </div>

      {/* 展開內容 */}
      {expanded && (
        <div className="px-4 pb-4 border-t border-gray-100 pt-3">
          {displayText !== undefined ? (
            <>
              {/* 摘要 */}
              <div className="mb-3">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-medium text-gray-500">
                    AI 摘要 · {email.summary?.model_used} · {email.summary?.style}
                  </span>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleResummarize(); }}
                    disabled={isStreaming}
                    className="flex items-center gap-1 text-xs text-primary-600 hover:text-primary-700 disabled:opacity-40"
                  >
                    <RefreshCw className={cn("w-3 h-3", isStreaming && "animate-spin")} />
                    {isStreaming ? "生成中..." : "重新生成"}
                  </button>
                </div>
                <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
                  {displayText}
                  {isStreaming && (
                    <span className="inline-block w-0.5 h-4 bg-primary-500 ml-0.5 animate-pulse align-text-bottom" />
                  )}
                </div>
              </div>

              {/* Smart Reply（streaming 中隱藏，完成後顯示） */}
              {!isStreaming && email.summary?.reply_suggestions && email.summary.reply_suggestions.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-gray-500 mb-2">💬 回覆建議</p>
                  <div className="flex gap-2 flex-wrap">
                    {email.summary.reply_suggestions.map((reply, i) => (
                      <button
                        key={i}
                        onClick={() => copyReply(reply)}
                        className="flex items-center gap-1.5 text-xs bg-white border border-gray-200 hover:border-primary-300 text-gray-700 px-3 py-1.5 rounded-full transition"
                      >
                        {copiedReply === reply ? (
                          <><Check className="w-3 h-3 text-green-500" /> 已複製</>
                        ) : (
                          <><Copy className="w-3 h-3" /> {reply}</>
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="flex items-center gap-2 text-sm text-gray-400 italic">
              <RefreshCw className="w-3 h-3 animate-spin" />
              摘要生成中...
            </div>
          )}
        </div>
      )}
    </div>
  );
}
