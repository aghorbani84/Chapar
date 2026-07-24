import { writable, get } from "svelte/store";
import { api } from "$lib/services/api";
import type { ApiRequest } from "$lib/types/api";
import { selectedCollectionId } from "$lib/stores/collections";
import {
  newRequestDraft,
  requestEditor,
  requestToEditor
} from "$lib/stores/requestEditor";

export const requests = writable<ApiRequest[]>([]);
export const selectedRequestId = writable<string | null>(null);
export const requestsError = writable<string | null>(null);

export async function loadRequests(collectionId: string | null): Promise<void> {
  try {
    const list = await api.listRequests(collectionId);
    requests.set(list);
    requestsError.set(null);
  } catch (error) {
    requestsError.set(String(error));
  }
}

export function selectRequest(request: ApiRequest): void {
  selectedRequestId.set(request.id);
  requestEditor.set(requestToEditor(request));
}

export function selectRequestById(id: string): void {
  const found = get(requests).find((request) => request.id === id);

  if (found) {
    selectRequest(found);
  }
}

export function newRequest(): void {
  requestEditor.set(newRequestDraft(get(selectedCollectionId)));
  selectedRequestId.set(null);
}

export async function deleteRequestById(id: string): Promise<void> {
  await api.deleteRequest(id);

  if (get(selectedRequestId) === id) {
    selectedRequestId.set(null);
    requestEditor.set(newRequestDraft(get(selectedCollectionId)));
  }

  await loadRequests(get(selectedCollectionId));
}
