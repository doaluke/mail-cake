"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { emailsApi } from "@/lib/api";
import { timeAgo, urgencyColor, urgencyLabel } from "@/lib/utils";
import {
  Layers,
  MessageCircle,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  Clock,
  Inbox,
} from "lucide-react";

interface Thread {
  thread_id: string;
  message_count: number;
  latest_at: string | null;
  max_urgency: number | null;
  subject: string | null;
  sender: string | null;
  snippet: string | null;
  summary: string | null;
}

interface ThreadsResponse {
  threads: Thread[];
  total: number;
}

function ThreadRow({ thread }: { thread: Thread }) {
  const [expanded, setExpanded] = useState(false);

  const urgency = thread.max_urgency ?? 0;
  const borderColor =
    urgency >= 4
      ? "border-l-red-400"
      : urgency >= 3
      ? "border-l-yellow-400"
      : "border-l-transparent";

  return (
    <div
      className={`border-l-4 ${borderColor} bg-white rounded-lg shadow-sm mb-3 overflow-hidden`}
    >
      {/* Thread header – click to expand */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left px-5 py-4 hover:bg-gray-50 transition flex items-start gap-3"
      >
        <span className="mt-0.5 text-gray-400">
          {expanded ? (
            <ChevronDown className="w-4 h-4" />
          ) : (
            <ChevronRight className="w-4 h-4" />
          )}
        </span>

        <div className="flex-1 min-w-0">
          {/* Subject + meta */}
          <div className="flex items-center justify-between gap-2">
            <h3 className="font-semibold text-gray-900 truncate text-sm">
              {thread.subject || "(無主旨)"}
            </h3>
            <div className="flex items-center gap-2 shrink-0">
              {urgency >= 3 && (
                <span
                  className={`text-xs px-2 py-0.5 rounded-full font-medium ${urgencyColor(
                    urgency
                  )}`}
                >
                  {urgencyLabel(urgency)}
                </span>
              )}
              <span className="text-xs text-gray-400 flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {thread.latest_at ? timeAgo(thread.latest_at) : "—"}
              </span>
            </div>
          </div>

          {/* Sender + message count */}
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs text-gray-500 truncate">
              {thread.sender || "未知寄件人"}
            </span>
            <span className="text-xs text-primary-600 bg-primary-50 px-1.5 py-0.5 rounded-full flex items-center gap-1">
              <MessageCircle className="w-3 h-3" />
              {thread.message_count} 封
            </span>
          </div>

          {/* Snippet (collapsed) */}
          {!expanded && thread.snippet && (
            <p className="text-xs text-gray-400 mt-1.5 line-clamp-1">
              {thread.snippet}
            </p>
          )}
        </div>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="px-5 pb-4 border-t border-gray-100 bg-gray-50">
          {thread.summary ? (
            <div className="mt-3">
              <p className="text-xs font-semibold text-primary-700 mb-1 flex items-center gap-1">
                ✨ AI 摘要
              </p>
              <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
                {thread.summary}
              </p>
            </div>
          ) : (
            <div className="mt-3">
              <p className="text-xs font-semibold text-gray-500 mb-1">
                最新訊息片段
              </p>
              <p className="text-sm text-gray-600">
                {thread.snippet || "（無內容預覽）"}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ThreadsPage() {
  const [page, setPage] = useState(1);

  const { data, isLoading, isError } = useQuery<ThreadsResponse>({
    queryKey: ["threads", page],
    queryFn: async () => {
      const res = await emailsApi.threads(page);
      return res.data as ThreadsResponse;
    },
  });

  const threads = data?.threads ?? [];

  return (
    <div className="h-full flex flex-col">
      {/* Page header */}
      <div className="px-6 py-5 border-b border-gray-200 bg-white flex items-center gap-3">
        <Layers className="w-5 h-5 text-primary-600" />
        <div>
          <h1 className="text-lg font-bold text-gray-900">對話串</h1>
          <p className="text-xs text-gray-500 mt-0.5">
            依對話串分組，快速掌握完整討論脈絡
          </p>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {isLoading && (
          <div className="space-y-3">
            {[...Array(6)].map((_, i) => (
              <div
                key={i}
                className="bg-white rounded-lg shadow-sm p-4 animate-pulse"
              >
                <div className="h-4 bg-gray-200 rounded w-3/4 mb-2" />
                <div className="h-3 bg-gray-100 rounded w-1/2" />
              </div>
            ))}
          </div>
        )}

        {isError && (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <AlertTriangle className="w-10 h-10 text-red-400 mb-3" />
            <p className="text-gray-600 font-medium">載入失敗</p>
            <p className="text-sm text-gray-400 mt-1">請稍後再試</p>
          </div>
        )}

        {!isLoading && !isError && threads.length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <Inbox className="w-12 h-12 text-gray-300 mb-4" />
            <p className="text-gray-500 font-medium">尚無對話串</p>
            <p className="text-sm text-gray-400 mt-1">
              信件同步後，有 thread 的對話會顯示在這裡
            </p>
          </div>
        )}

        {!isLoading && threads.length > 0 && (
          <>
            <p className="text-xs text-gray-400 mb-3">
              共 {data?.total ?? threads.length} 個對話串
            </p>
            {threads.map((thread) => (
              <ThreadRow key={thread.thread_id} thread={thread} />
            ))}

            {/* Pagination */}
            {(data?.total ?? 0) > 20 && (
              <div className="flex justify-center gap-2 mt-4 pb-4">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                  className="px-3 py-1.5 text-sm rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  上一頁
                </button>
                <span className="px-3 py-1.5 text-sm text-gray-600">
                  第 {page} 頁
                </span>
                <button
                  onClick={() => setPage((p) => p + 1)}
                  className="px-3 py-1.5 text-sm rounded-lg border border-gray-200 hover:bg-gray-50"
                >
                  下一頁
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
