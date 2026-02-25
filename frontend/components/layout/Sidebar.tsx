"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Mail, Layers, Settings, LogOut } from "lucide-react";
import { cn } from "@/lib/utils";
import { authApi } from "@/lib/api";
import { useRouter } from "next/navigation";

const NAV = [
  { href: "/dashboard",          icon: Mail,   label: "收件匣" },
  { href: "/dashboard/threads",  icon: Layers, label: "對話串" },
  { href: "/settings",           icon: Settings, label: "設定" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();

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

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV.map(({ href, icon: Icon, label }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition",
              pathname === href
                ? "bg-primary-50 text-primary-700"
                : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
            )}
          >
            <Icon className="w-4 h-4" />
            {label}
          </Link>
        ))}
      </nav>

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
    </aside>
  );
}
