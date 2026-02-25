"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { settingsApi } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function ModelStyleSelector() {
  const qc = useQueryClient();

  const { data: modelsData } = useQuery({
    queryKey: ["models"],
    queryFn: () => settingsApi.getModels().then((r) => r.data),
  });

  const { data: stylesData } = useQuery({
    queryKey: ["styles"],
    queryFn: () => settingsApi.getStyles().then((r) => r.data),
  });

  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      const { authApi } = await import("@/lib/api");
      return authApi.getMe().then((r) => r.data);
    },
  });

  const updateMutation = useMutation({
    mutationFn: settingsApi.updateLLM,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me"] }),
  });

  const TIER_BADGE: Record<string, string> = {
    fast:      "bg-green-100 text-green-700",
    balanced:  "bg-blue-100 text-blue-700",
    powerful:  "bg-purple-100 text-purple-700",
    private:   "bg-gray-100 text-gray-700",
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="font-semibold text-gray-900 mb-4">模型與風格設定</h3>

      {/* 模型選擇 */}
      <div className="mb-5">
        <p className="text-sm text-gray-500 mb-2">LLM 模型</p>
        <div className="grid grid-cols-1 gap-2">
          {modelsData?.models.map((m) => (
            <button
              key={m.id}
              onClick={() => updateMutation.mutate({ default_model: m.id })}
              className={cn(
                "flex items-center justify-between p-3 rounded-lg border text-sm transition",
                me?.default_model === m.id
                  ? "border-primary-500 bg-primary-50 text-primary-700"
                  : "border-gray-200 hover:border-gray-300 text-gray-700"
              )}
            >
              <div className="flex items-center gap-2">
                <span className="font-medium">{m.name}</span>
                <span className={cn("text-xs px-1.5 py-0.5 rounded", TIER_BADGE[m.tier])}>
                  {m.tier}
                </span>
              </div>
              <div className="flex items-center gap-2 text-xs text-gray-400">
                <span>費用：{m.cost}</span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* 風格選擇 */}
      <div>
        <p className="text-sm text-gray-500 mb-2">預設摘要風格</p>
        <div className="grid grid-cols-1 gap-1.5">
          {stylesData?.styles.map((s) => (
            <button
              key={s.id}
              onClick={() => updateMutation.mutate({ default_summary_style: s.id })}
              className={cn(
                "flex items-center justify-between p-2.5 rounded-lg border text-sm transition",
                me?.default_summary_style === s.id
                  ? "border-primary-500 bg-primary-50"
                  : "border-gray-200 hover:border-gray-300"
              )}
            >
              <span className="font-medium text-gray-800">{s.name}</span>
              <span className="text-xs text-gray-500">{s.description}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
