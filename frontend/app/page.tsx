"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { authApi } from "@/lib/api";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    authApi.getMe()
      .then(() => router.push("/dashboard"))
      .catch(() => router.push("/login"));
  }, [router]);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <div className="text-4xl mb-4">📬</div>
        <p className="text-gray-500">載入中...</p>
      </div>
    </div>
  );
}
