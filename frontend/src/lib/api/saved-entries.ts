import { apiFetch } from "./client";
export const ENTRY_CATEGORIES = [
  "journal",
  "rules",
  "strategies",
  "news_analysis",
  "lessons",
] as const;
export type EntryCategory = (typeof ENTRY_CATEGORIES)[number];
export const ENTRY_LABELS: Record<EntryCategory, string> = {
  journal: "Journal",
  rules: "Rules",
  strategies: "Strategies",
  news_analysis: "News & Analysis",
  lessons: "Lessons",
};
export interface SavedEntry {
  id: string;
  title: string;
  summary: string;
  category: EntryCategory;
  revision: number;
  conversation_id: string;
  source_message_ids: string[];
  source_document_id: string | null;
  trade_id: string | null;
  tags: string[];
  original_text: string;
  created_at: string;
  updated_at: string;
  draft: Record<string, unknown> | null;
  undone: boolean;
}
export const savedEntries = {
  list: (query?: {
    category?: string;
    view?: "journal" | "knowledge";
    q?: string;
    limit?: number;
    offset?: number;
  }) =>
    apiFetch<{ items: SavedEntry[]; total: number }>("/agent/saved", {
      query,
      auth: true,
    }),
  get: (id: string) =>
    apiFetch<SavedEntry>(`/agent/saved/${id}`, { auth: true }),
  update: (
    id: string,
    body: {
      expected_revision: number;
      category?: EntryCategory;
      title?: string;
      summary?: string;
      undo?: boolean;
    },
  ) =>
    apiFetch<SavedEntry>(`/agent/saved/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
      auth: true,
    }),
};
