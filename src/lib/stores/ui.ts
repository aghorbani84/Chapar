import { writable } from "svelte/store";

export type AppView =
  | "requests"
  | "environments"
  | "secrets"
  | "history"
  | "data";

export const appView = writable<AppView>("requests");
