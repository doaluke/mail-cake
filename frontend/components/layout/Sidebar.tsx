"use client";
import Link from "next/link";
import { usePathname, useSearchParams, useRouter } from "next/navigation";
import { Mail, Layers, Settings, LogOut, Plus, Folder } from "lucide-react";
import { cn } from "@/lib/utils";
import { authApi, topicsApi } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import TopicEditor from "@/components/topic/TopicEditor";

const STATIC_NAV = [
  { href: "/dashboard",         icon: Mail,   label: "收件匣" },
  { href: "/dashboard/threads", icon: Layers, label: "對話串" },
  { href: "/settings",          icon: Settings, label: "設定" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();
  const activeTopic = searchParams.get("topic");
  const [createOpen, setCreateOpen] = useState(false);

  const { data: topicsData } = useQuery({
    queryKey: ["topics"],
    queryFn: () => topicsApi.list().then((r) => r.data),
  });

  const handleLogout = async () => {
    await authApi.logout();
    router.push("/login");
  };

  return (
    <aside className="w-56 min-h-screen bg-white border-r border-gray-200 flex flex-col">
      {/* Logo */}
      <div className="px-6 py-5 border-b border-gray-100">
        <span className="text-xl font-bold text-primary-600">📬 MailCake</span>
      </div>

      {/* Static Navigation */}
      <nav className="px-3 py-4 space-y-1">
        {STATIC_NAV.map(({ href, icon: Icon, label }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition",
              pathname === href && !activeTopic
                ? "bg-primary-50 text-primary-700"
                : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
            )}
          >
            <Icon className="w-4 h-4" />
            {label}
          </Link>
        ))}
      </nav>

      {/* Topics section */}
      <div className="px-3 flex-1 overflow-y-auto">
        <div className="flex items-center justify-between px-3 mb-2">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
            信件集
          </span>
          <button
            onClick={() => setCreateOpen(true)}
            className="text-gray-400 hover:text-gray-600 transition"
            title="新增信件集"
          >
            <Plus size={15} />
          </button>
        </div>

        <div className="space-y-0.5">
          {topicsData?.topics.map((topic) => (
            <Link
              key={topic.id}
              href={`/dashboard?topic=${topic.id}`}
              className={cn(
                "flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition",
                activeTopic === topic.id
                  ? "bg-primary-50 text-primary-700 font-medium"
                  : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
              )}
            >
              <Folder
                className="w-3.5 h-3.5 shrink-0"
                style={{ color: topic.color }}
              />
              <span className="flex-1 truncate">{topic.name}</span>
              {topic.email_count > 0 && (
                <span className="text-xs text-gray-400 shrink-0">
                  {topic.email_count}
                </span>
              )}
            </Link>
          ))}

          {topicsData?.topics.length === 0 && (
            <p className="px-3 py-2 text-xs text-gray-400">
              點擊 + 新增信件集
            </p>
          )}
        </div>
      </div>

      {/* Logout */}
      <div className="px-3 py-4 border-t border-gray-100">
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-gray-500 hover:bg-gray-50 hover:text-gray-700 transition w-full"
        >
          <LogOut className="w-4 h-4" />
          登出
        </button>
      </div>

      {createOpen && (
        <TopicEditor onClose={() => setCreateOpen(false)} />
      )}
    </aside>
  );
}
