import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  withCredentials: true,
});

// Types
export interface Email {
  id: string;
  thread_id: string | null;
  subject: string | null;
  sender: string | null;
  sender_name: string | null;
  snippet: string | null;
  has_attachments: boolean;
  labels: string[];
  is_read: boolean;
  is_starred: boolean;
  urgency_score: number | null;
  importance_score: number | null;
  action_required: boolean | null;
  ai_category: string | null;
  sentiment: "positive" | "neutral" | "negative" | null;
  received_at: string | null;
  summary: {
    text: string;
    style: string;
    model_used: string;
    reply_suggestions: string[];
  } | null;
}

export interface EmailListResponse {
  emails: Email[];
  total: number;
  page: number;
  page_size: number;
}

export interface Model {
  id: string;
  name: string;
  provider: string;
  tier: string;
  cost: string;
  best_for: string[];
}

export interface SummaryStyle {
  id: string;
  name: string;
  icon: string;
  description: string;
}

// API functions
export const emailsApi = {
  list: (params?: {
    page?: number;
    search?: string;
    urgency_min?: number;
    category?: string;
    action_required?: boolean;
  }) => api.get<EmailListResponse>("/emails", { params }),

  get: (id: string) => api.get<Email>(`/emails/${id}`),

  summarize: (id: string, style: string, model?: string) =>
    api.post(`/emails/${id}/summarize`, null, {
      params: { style, model },
    }),

  threads: (page?: number) =>
    api.get("/emails/threads", { params: { page } }),
};

export const settingsApi = {
  getModels: () => api.get<{ models: Model[] }>("/settings/models"),
  getStyles: () => api.get<{ styles: SummaryStyle[] }>("/settings/styles"),
  updateLLM: (data: {
    default_model?: string;
    default_summary_style?: string;
    summary_language?: string;
  }) => api.put("/settings/llm", data),
  getDigest: () => api.get("/settings/digest"),
  updateDigest: (data: object) => api.put("/settings/digest", data),
};

export const authApi = {
  getGmailAuthUrl: () => api.get<{ auth_url: string }>("/auth/gmail"),
  getMe: () => api.get("/auth/me"),
  logout: () => api.post("/auth/logout"),
};
