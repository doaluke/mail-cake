"use client";
import { useState, useEffect } from "react";
import { X, Folder } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { topicsApi, type Topic } from "@/lib/api";

const PRESET_COLORS = [
  "#6366f1", // indigo
  "#8b5cf6", // violet
  "#ec4899", // pink
  "#ef4444", // red
  "#f97316", // orange
  "#eab308", // yellow
  "#22c55e", // green
  "#14b8a6", // teal
  "#3b82f6", // blue
  "#64748b", // slate
];

interface AutoRules {
  senders: string[];
  subject_contains: string[];
  labels: string[];
}

interface Props {
  topic?: Topic | null;
  onClose: () => void;
}

export default function TopicEditor({ topic, onClose }: Props) {
  const qc = useQueryClient();
  const isEdit = !!topic;

  const [name, setName] = useState(topic?.name ?? "");
  const [description, setDescription] = useState(topic?.description ?? "");
  const [color, setColor] = useState(topic?.color ?? PRESET_COLORS[0]);
  const [skillPrompt, setSkillPrompt] = useState(topic?.skill_prompt ?? "");
  const [senders, setSenders] = useState("");
  const [keywords, setKeywords] = useState("");

  // Parse existing auto_rules on edit
  useEffect(() => {
    if (topic?.auto_rules) {
      try {
        const rules: AutoRules = JSON.parse(topic.auto_rules);
        setSenders((rules.senders ?? []).join(", "));
        setKeywords((rules.subject_contains ?? []).join(", "));
      } catch {}
    }
  }, [topic]);

  const buildAutoRules = (): string | null => {
    const senderList = senders
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const keywordList = keywords
      .split(",")
      .map((k) => k.trim())
      .filter(Boolean);
    if (!senderList.length && !keywordList.length) return null;
    return JSON.stringify({ senders: senderList, subject_contains: keywordList, labels: [] });
  };

  const createMutation = useMutation({
    mutationFn: () =>
      topicsApi.create({
        name,
        description: description || undefined,
        color,
        skill_prompt: skillPrompt || undefined,
        auto_rules: buildAutoRules() ?? undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["topics"] });
      onClose();
    },
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      topicsApi.update(topic!.id, {
        name,
        description: description || undefined,
        color,
        skill_prompt: skillPrompt || undefined,
        auto_rules: buildAutoRules() ?? undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["topics"] });
      onClose();
    },
  });

  const isPending = createMutation.isPending || updateMutation.isPending;
  const error = createMutation.error || updateMutation.error;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    isEdit ? updateMutation.mutate() : createMutation.mutate();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="font-semibold text-gray-900">
            {isEdit ? "編輯信件集" : "新增信件集"}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-5">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              名稱 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例如：工作信件、電子報"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              required
            />
          </div>

          {/* Color */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">顏色</label>
            <div className="flex gap-2 flex-wrap">
              {PRESET_COLORS.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setColor(c)}
                  className="w-7 h-7 rounded-full border-2 transition"
                  style={{
                    backgroundColor: c,
                    borderColor: color === c ? "#1e1e1e" : "transparent",
                  }}
                />
              ))}
              <div className="flex items-center gap-1 ml-1">
                <Folder size={16} style={{ color }} />
                <span className="text-xs text-gray-500">預覽</span>
              </div>
            </div>
          </div>

          {/* Skill Prompt */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              整理描述 Skill
            </label>
            <textarea
              value={skillPrompt}
              onChange={(e) => setSkillPrompt(e.target.value)}
              rows={3}
              placeholder="告訴 AI 如何整理這類信件，例如：請重點列出合約金額、交貨日期、需要簽署的事項，並標示是否有法律風險。"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
            />
            <p className="text-xs text-gray-400 mt-1">
              留空則使用預設摘要風格
            </p>
          </div>

          {/* Auto Rules */}
          <div className="space-y-3">
            <label className="block text-sm font-medium text-gray-700">
              自動歸類規則
              <span className="ml-1 text-xs font-normal text-gray-400">（選填）</span>
            </label>
            <div>
              <p className="text-xs text-gray-500 mb-1">寄件人包含（逗號分隔）</p>
              <input
                type="text"
                value={senders}
                onChange={(e) => setSenders(e.target.value)}
                placeholder="@amazon.com, noreply@github.com"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">主旨關鍵字（逗號分隔）</p>
              <input
                type="text"
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
                placeholder="invoice, 合約, 發票"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>

          {error && (
            <p className="text-sm text-red-600">
              儲存失敗，請稍後再試。
            </p>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={isPending || !name.trim()}
              className="px-4 py-2 text-sm text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50"
            >
              {isPending ? "儲存中…" : isEdit ? "更新" : "建立"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
