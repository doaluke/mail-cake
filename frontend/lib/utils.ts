import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { formatDistanceToNow, parseISO } from "date-fns";
import { zhTW } from "date-fns/locale";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function timeAgo(dateStr: string | null): string {
  if (!dateStr) return "";
  try {
    return formatDistanceToNow(parseISO(dateStr), {
      addSuffix: true,
      locale: zhTW,
    });
  } catch {
    return dateStr;
  }
}

export function urgencyColor(score: number | null): string {
  if (!score) return "gray";
  if (score >= 4) return "red";
  if (score >= 3) return "yellow";
  return "green";
}

export function urgencyLabel(score: number | null): string {
  if (!score) return "未評分";
  if (score >= 4) return "緊急";
  if (score >= 3) return "重要";
  if (score >= 2) return "一般";
  return "低";
}

export function sentimentEmoji(sentiment: string | null): string {
  if (sentiment === "positive") return "😊";
  if (sentiment === "negative") return "😟";
  return "😐";
}
