"use client";
import { useState } from "react";
import {
  Sparkles,
  Pencil,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  ChevronLeft,
  ChevronRight,
  Loader2,
} from "lucide-react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { topicsApi, type TopicEmail, type TopicSummaryResponse } from "@/lib/api";
import { cn, timeAgo, urgencyColor } from "@/lib/utils";
import TopicEditor from "./TopicEditor";

const URGENCY_BORDER: Record<string, string> = {
  red: "border-l-red-500",
  yellow: "border-l-amber-400",
  green: "border-l-green-400",
  gray: "border-l-gray-200",
};

function CompactEmailCard({ email }: { email: TopicEmail }) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);
  const color = urgencyColor(email.urgency_score);

  const copyReply = async (text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(text);
    setTimeout(() => setCopied(null), 2000);
  };

  return (
    <div
      className={cn(
        "rounded-lg border border-l-4 bg-white transition hover:shadow-sm",
        URGENCY_BORDER[color]
      )}
    >
      <div
        className="flex items-start justify-between gap-3 px-4 py-3 cursor-pointer"
        onClick={() => setExpanded((v) => !v)}
      >
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-gray-900 truncate">
            {email.subject || "(無主旨)"}
          </p>
          <p className="text-xs text-gray-500 mt-0.5 truncate">
            {email.sender_name || email.sender}
            {email.received_at && (
              <span className="ml-2 text-gray-400">{timeAgo(email.received_at)}</span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {email.urgency_score && email.urgency_score >= 4 && (
            <span className="text-xs font-medium text-red-600 bg-red-50 px-1.5 py-0.5 rounded">
              緊急
            </span>
          )}
          {expanded ? (
            <ChevronUp size={16} className="text-gray-400" />
          ) : (
            <ChevronDown size={16} className="text-gray-400" />
          )}
        </div>
      </div>

      {expanded && (
        <div className="px-4 pb-4 border-t border-gray-100 space-y-3 pt-3">
          {email.summary ? (
            <>
              <p className="text-sm text-gray-700 whitespace-pre-line leading-relaxed">
                {email.summary.text}
              </p>
              {email.summary.reply_suggestions.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-gray-500 mb-1.5">建議回覆</p>
                  <div className="space-y-1.5">
                    {email.summary.reply_suggestions.map((s, i) => (
                      <div
                        key={i}
                        className="flex items-start justify-between gap-2 bg-gray-50 rounded-md px-3 py-2"
                      >
                        <p className="text-sm text-gray-700 flex-1">{s}</p>
                        <button
                          onClick={() => copyReply(s)}
                          className="shrink-0 text-gray-400 hover:text-gray-600"
                        >
                          {copied === s ? <Check size={14} /> : <Copy size={14} />}
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <p className="text-sm text-gray-400 italic">尚無 AI 摘要</p>
          )}
        </div>
      )}
    </div>
  );
}

interface Props {
  topicId: string;
}

export default function TopicPanel({ topicId }: Props) {
  const [page, setPage] = useState(1);
  const [editOpen, setEditOpen] = useState(false);
  const [aggregateSummary, setAggregateSummary] = useState<TopicSummaryResponse | null>(null);

  const PAGE_SIZE = 20;

  const { data, isLoading, isError } = useQuery({
    queryKey: ["topic", topicId, page],
    queryFn: () => topicsApi.get(topicId, page, PAGE_SIZE).then((r) => r.data),
  });

  const summarizeMutation = useMutation({
    mutationFn: () => topicsApi.summarize(topicId, 10).then((r) => r.data),
    onSuccess: (result) => setAggregateSummary(result),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-400">
        <Loader2 className="animate-spin mr-2" size={20} />
        <span>載入中…</span>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-400">
        載入失敗，請重新整理
      </div>
    );
  }

  const totalPages = Math.ceil(data.total / PAGE_SIZE);

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div
            className="w-4 h-4 rounded-full shrink-0"
            style={{ backgroundColor: data.color }}
          />
          <div>
            <h1 className="text-xl font-semibold text-gray-900">{data.name}</h1>
            <p className="text-sm text-gray-500">
              {data.total} 封信件
              {data.description && ` · ${data.description}`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => setEditOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            <Pencil size={14} />
            編輯
          </button>
          <button
            onClick={() => summarizeMutation.mutate()}
            disabled={summarizeMutation.isPending}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-60"
          >
            {summarizeMutation.isPending ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Sparkles size={14} />
            )}
            整理此集合
          </button>
        </div>
      </div>

      {/* Skill prompt display */}
      {data.skill_prompt && (
        <div className="bg-indigo-50 border border-indigo-100 rounded-lg px-4 py-3">
          <p className="text-xs font-medium text-indigo-700 mb-1">整理描述 Skill</p>
          <p className="text-sm text-indigo-600">{data.skill_prompt}</p>
        </div>
      )}

      {/* Aggregate summary */}
      {aggregateSummary && (
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-5 space-y-4">
          <h2 className="font-semibold text-gray-900 flex items-center gap-2">
            <Sparkles size={16} className="text-indigo-500" />
            聚合摘要
          </h2>
          <p className="text-sm text-gray-700 leading-relaxed">
            {aggregateSummary.aggregate_summary}
          </p>

          {aggregateSummary.key_themes.length > 0 && (
            <div>
              <p className="text-xs font-medium text-gray-500 mb-2">主要主題</p>
              <div className="flex flex-wrap gap-2">
                {aggregateSummary.key_themes.map((t, i) => (
                  <span
                    key={i}
                    className="text-xs bg-indigo-50 text-indigo-700 px-2.5 py-1 rounded-full"
                  >
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}

          {aggregateSummary.action_items.length > 0 && (
            <div>
              <p className="text-xs font-medium text-gray-500 mb-2">待辦事項</p>
              <ul className="space-y-1">
                {aggregateSummary.action_items.map((item, i) => (
                  <li key={i} className="text-sm text-gray-700 flex items-start gap-2">
                    <span className="mt-1 w-1.5 h-1.5 rounded-full bg-amber-400 shrink-0" />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <p className="text-xs text-gray-400">
            分析 {aggregateSummary.email_count} 封信件 · {aggregateSummary.model_used}
          </p>
        </div>
      )}

      {/* Email list */}
      {data.emails.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <p>此集合目前沒有信件</p>
          <p className="text-sm mt-1">設定自動規則後，符合的信件將自動歸入</p>
        </div>
      ) : (
        <div className="space-y-2">
          {data.emails.map((email) => (
            <CompactEmailCard key={email.id} email={email} />
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-4 pt-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-800 disabled:opacity-40"
          >
            <ChevronLeft size={16} />
            上一頁
          </button>
          <span className="text-sm text-gray-500">
            {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-800 disabled:opacity-40"
          >
            下一頁
            <ChevronRight size={16} />
          </button>
        </div>
      )}

      {/* Edit modal */}
      {editOpen && (
        <TopicEditor topic={data} onClose={() => setEditOpen(false)} />
      )}
    </div>
  );
}
