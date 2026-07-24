import { writable } from "svelte/store";
import type { ResponsePayload } from "$lib/types/api";

export interface ResponseState {
  busy: boolean;
  statusText: string;
  response: ResponsePayload | null;
}

function createResponseStore() {
  const { subscribe, set, update } = writable<ResponseState>({
    busy: false,
    statusText: "Idle",
    response: null
  });

  return {
    subscribe,
    set,
    update,
    start() {
      update((current) => ({
        ...current,
        busy: true,
        statusText: "Executing request..."
      }));
    },
    success(response: ResponsePayload) {
      update((current) => ({
        ...current,
        busy: false,
        response,
        statusText: response.error
          ? `Completed with error: ${response.error}`
          : `Completed: ${response.status} ${response.statusText}`
      }));
    },
    failure(error: unknown) {
      update((current) => ({
        ...current,
        busy: false,
        response: null,
        statusText: `Execution failed: ${String(error)}`
      }));
    },
    reset() {
      set({
        busy: false,
        statusText: "Idle",
        response: null
      });
    }
  };
}

export const responseStore = createResponseStore();
