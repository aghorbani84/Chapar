export type HttpMethod =
  | "GET"
  | "POST"
  | "PUT"
  | "PATCH"
  | "DELETE"
  | "HEAD"
  | "OPTIONS";

export type RequestBodyKind =
  | "none"
  | "json"
  | "text"
  | "formUrlEncoded"
  | "raw";

export type ResponseBodyKind =
  | "json"
  | "text"
  | "binary";

export interface Collection {
  id: string;
  name: string;
  parentId: string | null;
  position: number;
  createdAt: string;
  updatedAt: string;
}

export interface KeyValueEntry {
  id: string;
  key: string;
  value: string;
  enabled: boolean;

  /**
   * If present, Rust must replace the value with the secret stored in OS Keychain.
   * The frontend must never populate this with an actual secret value.
   */
  secretId: string | null;
}

export interface RequestBody {
  kind: RequestBodyKind;
  text: string;
  form: KeyValueEntry[];
}

export interface ApiRequest {
  id: string;
  collectionId: string | null;
  name: string;
  method: HttpMethod;
  url: string;
  params: KeyValueEntry[];
  headers: KeyValueEntry[];
  body: RequestBody;

  /**
   * Explicit allowlist of secret IDs that this request is permitted to use.
   * Rust must refuse to inject secrets not present in this list.
   */
  allowedSecretIds: string[];

  timeoutMs: number | null;
  followRedirects: boolean;
  position: number;
  createdAt: string;
  updatedAt: string;
}

export interface EnvironmentVariable {
  id: string;
  key: string;
  value: string;
  enabled: boolean;
}

export interface Environment {
  id: string;
  name: string;
  variables: EnvironmentVariable[];
  createdAt: string;
  updatedAt: string;
}

/**
 * Secret metadata only.
 * The value must never be persisted in SQLite or returned to normal UI state.
 */
export interface SecretMetadata {
  id: string;
  label: string;
  createdAt: string;
}

export interface RequestPayload {
  request: ApiRequest;
  environmentId: string | null;
  timeoutMs: number | null;
  followRedirects: boolean;
  maxRedirects: number | null;
}

export interface ResponseHeader {
  name: string;
  value: string;
}

export interface ResponseBody {
  kind: ResponseBodyKind;
  text: string | null;
  base64: string | null;
}

export interface ResponsePayload {
  requestId: string;
  status: number;
  statusText: string;
  httpVersion: string;
  latencyMs: number;
  sizeBytes: number;
  headers: ResponseHeader[];
  body: ResponseBody;
  unresolvedVariables: string[];
  error: string | null;
}

export interface CreateCollectionPayload {
  name: string;
  parentId: string | null;
  position?: number;
}

export interface UpdateCollectionPayload {
  id: string;
  name: string;
  position?: number;
}

export interface SaveRequestPayload {
  request: ApiRequest;
}

export interface SaveEnvironmentPayload {
  environment: Environment;
}

export interface StoreSecretPayload {
  id: string;
  value: string;
  label?: string;
}

export interface HistoryEntry {
  id: string;
  requestId: string;
  environmentId: string | null;
  requestSnapshot: ApiRequest;
  status: number | null;
  latencyMs: number | null;
  sizeBytes: number | null;
  response: ResponsePayload | null;
  createdAt: string;
}

export interface ExportBundle {
  exportedAt: string;
  collections: Collection[];
  requests: ApiRequest[];
  environments: Environment[];
  secretMetadata: SecretMetadata[];
}
