import { writable } from "svelte/store";
import { api } from "$lib/services/api";
import type { SecretMetadata } from "$lib/types/api";

export const secretMetadata = writable<SecretMetadata[]>([]);
export const secretsError = writable<string | null>(null);

export async function loadSecrets(): Promise<void> {
  try {
    const list = await api.listSecretMetadata();
    secretMetadata.set(list);
    secretsError.set(null);
  } catch (error) {
    secretsError.set(String(error));
  }
}

export async function saveSecret(
  id: string,
  label: string,
  value: string
): Promise<SecretMetadata> {
  const saved = await api.saveSecret({
    id,
    value,
    label: label.trim() === "" ? undefined : label.trim()
  });

  secretMetadata.update((list) => {
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

export async function deleteSecretById(id: string): Promise<void> {
  await api.deleteSecret(id);
  secretMetadata.update((list) => list.filter((item) => item.id !== id));
}
