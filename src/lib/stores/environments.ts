import { writable, get } from "svelte/store";
import { api } from "$lib/services/api";
import { newId } from "$lib/utils/id";
import type { Environment } from "$lib/types/api";

export const environments = writable<Environment[]>([]);
export const activeEnvironmentId = writable<string | null>(null);
export const environmentsError = writable<string | null>(null);

export async function loadEnvironments(): Promise<void> {
  try {
    const list = await api.listEnvironments();
    const activeId = await api.getActiveEnvironmentId();

    environments.set(list);
    activeEnvironmentId.set(activeId);
    environmentsError.set(null);
  } catch (error) {
    environmentsError.set(String(error));
  }
}

export function createEmptyEnvironment(name: string): Environment {
  const now = new Date().toISOString();

  return {
    id: newId(),
    name,
    variables: [],
    createdAt: now,
    updatedAt: now
  };
}

export async function saveEnvironment(environment: Environment): Promise<Environment> {
  const saved = await api.saveEnvironment({ environment });

  environments.update((list) => {
    const index = list.findIndex((item) => item.id === saved.id);

    if (index >= 0) {
      const next = [...list];
      next[index] = saved;
      return next;
    }

    return [...list, saved];
  });

  return saved;
}

export async function deleteEnvironment(id: string): Promise<void> {
  await api.deleteEnvironment(id);

  environments.update((list) => list.filter((item) => item.id !== id));

  if (get(activeEnvironmentId) === id) {
    activeEnvironmentId.set(null);
  }
}

export async function setActiveEnvironment(id: string | null): Promise<void> {
  await api.setActiveEnvironment(id);
  activeEnvironmentId.set(id);
}
