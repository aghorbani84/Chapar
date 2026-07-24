import { invoke } from "@tauri-apps/api/core";
import type {
  ApiRequest,
  Collection,
  CreateCollectionPayload,
  Environment,
  ExportBundle,
  HistoryEntry,
  RequestPayload,
  ResponsePayload,
  SaveEnvironmentPayload,
  SaveRequestPayload,
  SecretMetadata,
  StoreSecretPayload
} from "$lib/types/api";

export const api = {
  listEnvironments() {
    return invoke<Environment[]>("list_environments");
  },

  saveEnvironment(payload: SaveEnvironmentPayload) {
    return invoke<Environment>("save_environment", { payload });
  },

  deleteEnvironment(id: string) {
    return invoke<void>("delete_environment", { id });
  },

  setActiveEnvironment(id: string | null) {
    return invoke<void>("set_active_environment", { id });
  },

  getActiveEnvironmentId() {
    return invoke<string | null>("get_active_environment_id");
  },

  executeRequest(payload: RequestPayload) {
    return invoke<ResponsePayload>("execute_request", { payload });
  },

  listCollections() {
    return invoke<Collection[]>("list_collections");
  },

  createCollection(payload: CreateCollectionPayload) {
    return invoke<Collection>("create_collection", { payload });
  },

  deleteCollection(id: string) {
    return invoke<void>("delete_collection", { id });
  },

  listRequests(collectionId: string | null) {
    return invoke<ApiRequest[]>("list_requests", { collectionId });
  },

  saveRequest(payload: SaveRequestPayload) {
    return invoke<ApiRequest>("save_request", { payload });
  },

  deleteRequest(id: string) {
    return invoke<void>("delete_request", { id });
  },

  listSecretMetadata() {
    return invoke<SecretMetadata[]>("list_secret_metadata");
  },

  saveSecret(payload: StoreSecretPayload) {
    return invoke<SecretMetadata>("save_secret", { payload });
  },

  deleteSecret(id: string) {
    return invoke<void>("delete_secret", { id });
  },

  secretExists(id: string) {
    return invoke<boolean>("secret_exists", { id });
  },

  listHistory(limit?: number) {
    return invoke<HistoryEntry[]>("list_history", {
      limit: limit ?? null
    });
  },

  clearHistory() {
    return invoke<void>("clear_history");
  },

  exportData() {
    return invoke<ExportBundle>("export_data");
  },

  importData(bundle: ExportBundle) {
    return invoke<string>("import_data", { bundle });
  }
};
