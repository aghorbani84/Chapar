import { writable } from "svelte/store";
import { api } from "$lib/services/api";
import type { HistoryEntry } from "$lib/types/api";

export const historyEntries = writable<HistoryEntry[]>([]);
export const selectedHistory = writable<HistoryEntry | null>(null);
export const historyError = writable<string | null>(null);

export async function loadHistory(limit = 100): Promise<void> {
  try {
    const entries = await api.listHistory(limit);
    historyEntries.set(entries);
    historyError.set(null);
  } catch (error) {
    historyError.set(String(error));
  }
}

export async function clearAllHistory(): Promise<void> {
  await api.clearHistory();
  historyEntries.set([]);
  selectedHistory.set(null);
}
