import { writable } from "svelte/store";

export interface SidebarState {
  open: boolean;
}

function createSidebarStore() {
  const { subscribe, set, update } = writable<SidebarState>({
    open: true
  });

  return {
    subscribe,
    set,
    toggle() {
      update((current) => ({
        ...current,
        open: !current.open
      }));
    }
  };
}

export const sidebarStore = createSidebarStore();
