import { writable } from "svelte/store";
import { newId } from "$lib/utils/id";
import type {
  ApiRequest,
  HttpMethod,
  KeyValueEntry,
  RequestBodyKind
} from "$lib/types/api";

export interface RequestEditorState {
  id: string;
  name: string;
  collectionId: string | null;
  method: HttpMethod;
  url: string;
  environmentId: string;
  bodyKind: RequestBodyKind;
  bodyText: string;
  timeoutMs: string;
  followRedirects: boolean;
  headers: KeyValueEntry[];
  allowedSecretIds: string[];
  position: number;
  createdAt: string;
  updatedAt: string;
}

export function newRequestDraft(collectionId: string | null): RequestEditorState {
  const now = new Date().toISOString();

  return {
    id: newId(),
    name: "New Request",
    collectionId,
    method: "GET",
    url: "http://localhost:8080",
    environmentId: "",
    bodyKind: "none",
    bodyText: "",
    timeoutMs: "",
    followRedirects: true,
    headers: [],
    allowedSecretIds: [],
    position: 0,
    createdAt: now,
    updatedAt: now
  };
}

export function requestToEditor(request: ApiRequest): RequestEditorState {
  return {
    id: request.id,
    name: request.name,
    collectionId: request.collectionId,
    method: request.method,
    url: request.url,
    environmentId: "",
    bodyKind: request.body.kind,
    bodyText: request.body.text,
    timeoutMs:
      request.timeoutMs === null || request.timeoutMs === undefined
        ? ""
        : String(request.timeoutMs),
    followRedirects: request.followRedirects,
    headers: request.headers,
    allowedSecretIds: request.allowedSecretIds,
    position: request.position,
    createdAt: request.createdAt,
    updatedAt: request.updatedAt
  };
}

function extractSecretIds(input: string): string[] {
  const ids: string[] = [];

  const regex = /{{\s*secret:\s*([A-Za-z0-9_:.-]+)\s*}}/g;

  let match: RegExpExecArray | null;

  while ((match = regex.exec(input)) !== null) {
    const id = match[1];

    if (id) {
      ids.push(id.trim());
    }
  }

  return ids;
}

function computeAllowedSecretIds(state: RequestEditorState): string[] {
  const allowed = new Set<string>(state.allowedSecretIds);

  for (const header of state.headers) {
    if (header.secretId) {
      allowed.add(header.secretId);
    }

    for (const id of extractSecretIds(header.key)) {
      allowed.add(id);
    }

    for (const id of extractSecretIds(header.value)) {
      allowed.add(id);
    }
  }

  for (const id of extractSecretIds(state.url)) {
    allowed.add(id);
  }

  for (const id of extractSecretIds(state.bodyText)) {
    allowed.add(id);
  }

  return Array.from(allowed);
}

export function editorToRequest(state: RequestEditorState): ApiRequest {
  const timeoutValue = state.timeoutMs.trim() === "" ? null : Number(state.timeoutMs);

  return {
    id: state.id,
    collectionId: state.collectionId,
    name: state.name.trim() === "" ? "Untitled" : state.name.trim(),
    method: state.method,
    url: state.url,
    params: [],
    headers: state.headers,
    body: {
      kind: state.bodyKind,
      text: state.bodyText,
      form: []
    },
    allowedSecretIds: computeAllowedSecretIds(state),
    timeoutMs:
      timeoutValue !== null && Number.isFinite(timeoutValue) ? timeoutValue : null,
    followRedirects: state.followRedirects,
    position: state.position,
    createdAt: state.createdAt,
    updatedAt: new Date().toISOString()
  };
}

function createRequestEditorStore() {
  const { subscribe, set, update } = writable<RequestEditorState>(
    newRequestDraft(null)
  );

  return {
    subscribe,
    set,
    update
  };
}

export const requestEditor = createRequestEditorStore();
