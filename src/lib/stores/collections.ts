import { writable, get } from "svelte/store";
import { api } from "$lib/services/api";
import type { Collection } from "$lib/types/api";

export const collections = writable<Collection[]>([]);
export const selectedCollectionId = writable<string | null>(null);
export const collectionsError = writable<string | null>(null);

export async function loadCollections(): Promise<void> {
  try {
    const list = await api.listCollections();
    collections.set(list);
    collectionsError.set(null);
  } catch (error) {
    collectionsError.set(String(error));
  }
}

export async function createCollection(name: string): Promise<void> {
  const trimmed = name.trim();

  if (!trimmed) {
    return;
  }

  const saved = await api.createCollection({
    name: trimmed,
    parentId: null,
    position: 0
  });

  collections.update((list) => [...list, saved]);
  selectedCollectionId.set(saved.id);
}

export async function deleteCollectionById(id: string): Promise<void> {
  await api.deleteCollection(id);

  if (get(selectedCollectionId) === id) {
    selectedCollectionId.set(null);
  }

  await loadCollections();
}
