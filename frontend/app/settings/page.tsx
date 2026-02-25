"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { settingsApi, authApi } from "@/lib/api";
import Sidebar from "@/components/layout/Sidebar";
import ModelStyleSelector from "@/components/email/ModelStyleSelector";
import { useState } from "react";

export default function SettingsPage() {
  const qc = useQueryClient();
  const { data: digestData } = useQuery({
    queryKey: ["digest"],
    queryFn: () => settingsApi.getDigest().then((r) => r.data),
  });

  const updateDigestMutation = useMutation({
    mutationFn: settingsApi.updateDigest,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["digest"] }),
  });

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 p-8 max-w-2xl">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">設定</h1>

        {/* LLM 設定 */}
        <section className="mb-6">
          <h2 className="text-lg font-semibold text-gray-700 mb-3">AI 模型設定</h2>
          <ModelStyleSelector />
        </section>

        {/* Digest 設定 */}
        <section className="mb-6">
          <h2 className="text-lg font-semibold text-gray-700 mb-3">每日 Digest 摘要信</h2>
          <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
            <label className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-700">啟用每日摘要信</span>
              <input
                type="checkbox"
                checked={digestData?.is_enabled ?? false}
                onChange={(e) =>
                  updateDigestMutation.mutate({ is_enabled: e.target.checked })
                }
                className="w-4 h-4 text-primary-600 rounded"
              />
            </label>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                發送時間
              </label>
              <select
                value={digestData?.send_at_hour ?? 8}
                onChange={(e) =>
                  updateDigestMutation.mutate({ send_at_hour: parseInt(e.target.value) })
                }
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              >
                {Array.from({ length: 24 }, (_, i) => (
                  <option key={i} value={i}>
                    {String(i).padStart(2, "0")}:00
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                寄送頻率
              </label>
              <select
                value={digestData?.frequency ?? "daily"}
                onChange={(e) =>
                  updateDigestMutation.mutate({ frequency: e.target.value })
                }
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              >
                <option value="daily">每天</option>
                <option value="weekly">每週</option>
              </select>
            </div>
          </div>
        </section>

        {/* 語言設定 */}
        <section>
          <h2 className="text-lg font-semibold text-gray-700 mb-3">語言設定</h2>
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <label className="block text-sm font-medium text-gray-700 mb-1">摘要語言</label>
            <select
              defaultValue="zh-TW"
              onChange={(e) =>
                settingsApi.updateLLM({ summary_language: e.target.value })
              }
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
            >
              <option value="zh-TW">繁體中文</option>
              <option value="zh-CN">簡體中文</option>
              <option value="en">English</option>
              <option value="ja">日本語</option>
            </select>
          </div>
        </section>
      </main>
    </div>
  );
}
