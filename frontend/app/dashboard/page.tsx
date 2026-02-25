"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Search, Filter, Zap, RefreshCw } from "lucide-react";
import { emailsApi } from "@/lib/api";
import EmailCard from "@/components/email/EmailCard";
import ModelStyleSelector from "@/components/email/ModelStyleSelector";
import { cn } from "@/lib/utils";

const FILTER_TABS = [
  { label: "全部",     filter: {} },
  { label: "需行動",   filter: { action_required: true } },
  { label: "緊急",     filter: { urgency_min: 4 } },
  { label: "工作信",   filter: { category: "工作信件" } },
  { label: "電子報",   filter: { category: "電子報" } },
];

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState(0);
  const [search, setSearch] = useState("");
  const [showSettings, setShowSettings] = useState(false);
  const qc = useQueryClient();

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["emails", activeTab, search],
    queryFn: () =>
      emailsApi
        .list({ page: 1, search: search || undefined, ...FILTER_TABS[activeTab].filter })
        .then((r) => r.data),
    refetchInterval: 30_000,           // 每 30 秒自動刷新
    refetchIntervalInBackground: false, // 切到其他分頁時暫停，省資源
  });

  const resummarizeMutation = useMutation({
    mutationFn: ({ id, style, model }: { id: string; style: string; model: string }) =>
      emailsApi.summarize(id, style, model),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["emails"] }),
  });

  return (
    <div className="flex h-screen">
      {/* Main */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="bg-white border-b border-gray-200 px-6 py-4">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-xl font-bold text-gray-900">收件匣</h1>
            <div className="flex items-center gap-2">
              <button
                onClick={() => refetch()}
                className="p-2 rounded-lg hover:bg-gray-100 transition"
                title={isFetching ? "更新中..." : "立即重新整理"}
                disabled={isFetching}
              >
                <RefreshCw className={cn(
                  "w-4 h-4 text-gray-500",
                  isFetching && "animate-spin text-primary-500"
                )} />
              </button>
              <button
                onClick={() => setShowSettings(!showSettings)}
                className={cn(
                  "flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition",
                  showSettings
                    ? "bg-primary-100 text-primary-700"
                    : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                )}
              >
                <Filter className="w-4 h-4" />
                模型設定
              </button>
            </div>
          </div>

          {/* Search */}
          <div className="relative mb-3">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="搜尋信件..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>

          {/* Filter Tabs */}
          <div className="flex gap-1">
            {FILTER_TABS.map((tab, i) => (
              <button
                key={i}
                onClick={() => setActiveTab(i)}
                className={cn(
                  "px-3 py-1.5 rounded-lg text-sm font-medium transition",
                  activeTab === i
                    ? "bg-primary-600 text-white"
                    : "text-gray-500 hover:bg-gray-100"
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Email List */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-2">
          {isLoading ? (
            <div className="text-center py-12 text-gray-400">載入中...</div>
          ) : data?.emails.length === 0 ? (
            <div className="text-center py-12">
              <div className="text-4xl mb-3">📭</div>
              <p className="text-gray-500">沒有符合的信件</p>
            </div>
          ) : (
            data?.emails.map((email) => (
              <EmailCard
                key={email.id}
                email={email}
                onResummarize={(id, style, model) =>
                  resummarizeMutation.mutate({ id, style, model })
                }
              />
            ))
          )}

          {data && (
            <p className="text-center text-xs text-gray-400 py-4">
              共 {data.total} 封信件
            </p>
          )}
        </div>
      </div>

      {/* Settings Panel */}
      {showSettings && (
        <div className="w-72 border-l border-gray-200 bg-gray-50 p-4 overflow-y-auto">
          <ModelStyleSelector />
        </div>
      )}
    </div>
  );
}
