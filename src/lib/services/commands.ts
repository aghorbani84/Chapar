export const TAURI_COMMANDS = {
  initDb: "init_db",

  listCollections: "list_collections",
  createCollection: "create_collection",
  updateCollection: "update_collection",
  deleteCollection: "delete_collection",

  listRequests: "list_requests",
  saveRequest: "save_request",
  deleteRequest: "delete_request",

  listEnvironments: "list_environments",
  saveEnvironment: "save_environment",
  deleteEnvironment: "delete_environment",
  setActiveEnvironment: "set_active_environment",

  listSecretMetadata: "list_secret_metadata",
  saveSecretMetadata: "save_secret_metadata",
  deleteSecret: "delete_secret",

  /**
   * Diagnostic/testing only.
   * Normal UI must not use this command.
   */
  getSecret: "get_secret",

  /**
   * Diagnostic/testing only.
   */
  storeSecret: "store_secret",

  executeRequest: "execute_request"
} as const;
