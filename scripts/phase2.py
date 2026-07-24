#!/usr/bin/env python3
"""
Chapar Phase 2: Security and keyring integration.

This script:
- verifies Phase 1 files exist
- adds the keyring crate
- writes the secure vault module
- writes secret Tauri commands
- updates the frontend with a diagnostic secret test panel
- runs frontend and Rust verification checks

This script uses only the Python standard library.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


PHASE2_FILES: dict[str, str] = {
"src-tauri/src/vault.rs": """use keyring::Entry;

const SERVICE: &str = "app.chapar.desktop";
const MAX_SECRET_ID_LEN: usize = 255;
const MAX_SECRET_VALUE_LEN: usize = 4096;

fn normalize_id(id: &str) -> Result<String, String> {
    let id = id.trim();

    if id.is_empty() {
        return Err("secret id must not be empty".to_string());
    }

    if id.len() > MAX_SECRET_ID_LEN {
        return Err(format!(
            "secret id must be {} characters or fewer",
            MAX_SECRET_ID_LEN
        ));
    }

    let allowed = id
        .chars()
        .all(|character| character.is_ascii_alphanumeric() || matches!(character, '-' | '_' | '.' | ':'));

    if !allowed {
        return Err(
            "secret id may only contain letters, numbers, '-', '_', '.', or ':'".to_string(),
        );
    }

    Ok(id.to_string())
}

fn validate_value(value: &str) -> Result<(), String> {
    if value.is_empty() {
        return Err("secret value must not be empty".to_string());
    }

    if value.len() > MAX_SECRET_VALUE_LEN {
        return Err(format!(
            "secret value must be {} characters or fewer",
            MAX_SECRET_VALUE_LEN
        ));
    }

    if value.chars().any(char::is_control) {
        return Err("secret value must not contain control characters".to_string());
    }

    Ok(())
}

fn entry_for(id: &str) -> Result<Entry, String> {
    let id = normalize_id(id)?;

    Entry::new(SERVICE, &id).map_err(|_| "secret store is unavailable".to_string())
}

pub fn store_secret(id: &str, value: &str) -> Result<(), String> {
    validate_value(value)?;

    let entry = entry_for(id)?;

    entry
        .set_password(value)
        .map_err(|_| "failed to store secret".to_string())
}

pub fn get_secret(id: &str) -> Result<String, String> {
    let entry = entry_for(id)?;

    entry.get_password().map_err(|error| match error {
        keyring::Error::NoEntry => "secret not found".to_string(),
        _ => "failed to retrieve secret".to_string(),
    })
}

pub fn secret_exists(id: &str) -> Result<bool, String> {
    let entry = entry_for(id)?;

    match entry.get_password() {
        Ok(_) => Ok(true),
        Err(keyring::Error::NoEntry) => Ok(false),
        Err(_) => Err("failed to check secret".to_string()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn normalize_id_accepts_valid_ids() {
        assert!(normalize_id("prod-api-key").is_ok());
        assert!(normalize_id("prod_api_key").is_ok());
        assert!(normalize_id("prod.api.key").is_ok());
        assert!(normalize_id("prod:api:key").is_ok());
        assert!(normalize_id("  prod-api-key  ").is_ok());
    }

    #[test]
    fn normalize_id_rejects_invalid_ids() {
        assert!(normalize_id("").is_err());
        assert!(normalize_id("   ").is_err());
        assert!(normalize_id("bad id").is_err());
        assert!(normalize_id("bad/id").is_err());
        assert!(normalize_id("bad\\nid").is_err());
        assert!(normalize_id(&"a".repeat(300)).is_err());
    }

    #[test]
    fn validate_value_accepts_normal_values() {
        assert!(validate_value("super-secret-token").is_ok());
        assert!(validate_value("Bearer abc123").is_ok());
        assert!(validate_value("value with spaces").is_ok());
    }

    #[test]
    fn validate_value_rejects_invalid_values() {
        assert!(validate_value("").is_err());
        assert!(validate_value("bad\\nvalue").is_err());
        assert!(validate_value("bad\\u{0000}value").is_err());
        assert!(validate_value(&"a".repeat(5000)).is_err());
    }
}
""",

"src-tauri/src/commands/mod.rs": """pub mod db;
pub mod secrets;
""",

"src-tauri/src/commands/secrets.rs": """#[tauri::command]
pub fn store_secret(id: String, value: String) -> Result<(), String> {
    crate::vault::store_secret(&id, &value)
}

#[tauri::command]
pub fn get_secret(id: String) -> Result<String, String> {
    crate::vault::get_secret(&id)
}

#[tauri::command]
pub fn secret_exists(id: String) -> Result<bool, String> {
    crate::vault::secret_exists(&id)
}
""",

"src-tauri/src/main.rs": """#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod db;
mod error;
mod models;
mod vault;

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            let handle = app.handle().clone();

            db::init_db_for_app(&handle)
                .map(|_| ())
                .map_err(|error| -> Box<dyn std::error::Error> { error.into() })
        })
        .invoke_handler(tauri::generate_handler![
            commands::db::init_db,
            commands::secrets::store_secret,
            commands::secrets::get_secret,
            commands::secrets::secret_exists
        ])
        .run(tauri::generate_context!())
        .expect("error while running Chapar");
}
""",

"src/routes/+page.svelte": """<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";

  let dbStatus = $state("Idle");
  let dbPath = $state<string | null>(null);
  let dbBusy = $state(false);

  let secretId = $state("");
  let secretValue = $state("");
  let secretStatus = $state("Idle");
  let retrievedSecret = $state<string | null>(null);
  let secretExists = $state<boolean | null>(null);
  let secretBusy = $state(false);

  async function initDb() {
    dbBusy = true;
    dbStatus = "Initializing database...";
    dbPath = null;

    try {
      const path = await invoke<string>("init_db");
      dbPath = path;
      dbStatus = "Database initialized.";
    } catch (error) {
      dbStatus = `Database initialization failed: ${String(error)}`;
    } finally {
      dbBusy = false;
    }
  }

  async function storeSecret() {
    secretBusy = true;
    secretStatus = "Storing secret...";
    retrievedSecret = null;
    secretExists = null;

    try {
      await invoke("store_secret", {
        id: secretId.trim(),
        value: secretValue
      });

      secretStatus = `Secret stored: ${secretId.trim()}`;
      secretValue = "";
    } catch (error) {
      secretStatus = `Store failed: ${String(error)}`;
    } finally {
      secretBusy = false;
    }
  }

  async function getSecret() {
    secretBusy = true;
    secretStatus = "Retrieving secret...";
    retrievedSecret = null;
    secretExists = null;

    try {
      const value = await invoke<string>("get_secret", {
        id: secretId.trim()
      });

      retrievedSecret = value;
      secretStatus = "Secret retrieved. Diagnostic use only.";
    } catch (error) {
      secretStatus = `Retrieve failed: ${String(error)}`;
    } finally {
      secretBusy = false;
    }
  }

  async function checkSecretExists() {
    secretBusy = true;
    secretStatus = "Checking secret...";
    retrievedSecret = null;
    secretExists = null;

    try {
      const exists = await invoke<boolean>("secret_exists", {
        id: secretId.trim()
      });

      secretExists = exists;
      secretStatus = "Secret existence checked.";
    } catch (error) {
      secretStatus = `Exists check failed: ${String(error)}`;
    } finally {
      secretBusy = false;
    }
  }

  function clearSecretTest() {
    secretId = "";
    secretValue = "";
    secretStatus = "Idle";
    retrievedSecret = null;
    secretExists = null;
  }
</script>

<main class="p-6">
  <h1 class="text-xl font-semibold">Chapar</h1>

  <section class="mt-6 rounded border border-neutral-800 p-4">
    <h2 class="text-sm font-semibold uppercase tracking-wide text-neutral-400">
      Phase 1: Database
    </h2>

    <button
      class="mt-3 rounded bg-emerald-600 px-4 py-2 text-white disabled:cursor-not-allowed disabled:opacity-50"
      onclick={initDb}
      disabled={dbBusy}
    >
      Initialize DB
    </button>

    <p class="mt-3 text-sm" data-testid="db-status">
      {dbStatus}
    </p>

    {#if dbPath}
      <p class="mt-2 break-all text-xs text-neutral-400" data-testid="db-path">
        {dbPath}
      </p>
    {/if}
  </section>

  <section class="mt-6 rounded border border-neutral-800 p-4">
    <h2 class="text-sm font-semibold uppercase tracking-wide text-neutral-400">
      Phase 2: Secret Vault Diagnostic
    </h2>

    <p class="mt-2 text-xs text-amber-400">
      Warning: Get Secret returns the raw secret to the frontend. This is for testing only.
    </p>

    <div class="mt-4 grid gap-3">
      <input
        class="rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
        placeholder="Secret ID, for example: prod-api-key"
        bind:value={secretId}
        data-testid="secret-id"
      />

      <input
        class="rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
        type="password"
        placeholder="Secret value"
        bind:value={secretValue}
        data-testid="secret-value"
      />
    </div>

    <div class="mt-4 flex flex-wrap gap-2">
      <button
        class="rounded bg-emerald-600 px-4 py-2 text-white disabled:cursor-not-allowed disabled:opacity-50"
        onclick={storeSecret}
        disabled={secretBusy || secretId.trim() === "" || secretValue === ""}
        data-testid="store-secret"
      >
        Store Secret
      </button>

      <button
        class="rounded bg-neutral-700 px-4 py-2 text-white disabled:cursor-not-allowed disabled:opacity-50"
        onclick={getSecret}
        disabled={secretBusy || secretId.trim() === ""}
        data-testid="get-secret"
      >
        Get Secret
      </button>

      <button
        class="rounded bg-neutral-700 px-4 py-2 text-white disabled:cursor-not-allowed disabled:opacity-50"
        onclick={checkSecretExists}
        disabled={secretBusy || secretId.trim() === ""}
        data-testid="secret-exists"
      >
        Exists
      </button>

      <button
        class="rounded bg-neutral-800 px-4 py-2 text-white disabled:cursor-not-allowed disabled:opacity-50"
        onclick={clearSecretTest}
        disabled={secretBusy}
        data-testid="clear-secret"
      >
        Clear
      </button>
    </div>

    <p class="mt-3 text-sm" data-testid="secret-status">
      {secretStatus}
    </p>

    {#if secretExists !== null}
      <p class="mt-2 text-xs text-neutral-400" data-testid="secret-exists-result">
        Secret exists: {secretExists ? "yes" : "no"}
      </p>
    {/if}

    {#if retrievedSecret !== null}
      <p class="mt-2 break-all text-xs text-red-400" data-testid="retrieved-secret">
        {retrievedSecret}
      </p>
    {/if}
  </section>
</main>
""",
}


REQUIRED_PHASE1_FILES = [
    "package.json",
    "src/routes/+page.svelte",
    "src-tauri/Cargo.toml",
    "src-tauri/src/main.rs",
    "src-tauri/src/db.rs",
    "src-tauri/src/commands/mod.rs",
    "src-tauri/src/commands/db.rs",
    "src-tauri/migrations/001_initial.sql",
]


def run(command: list[str], cwd: Path | None = None) -> None:
    printable = " ".join(str(part) for part in command)
    print(f"RUN  {printable}")

    subprocess.run(
        command,
        cwd=str(cwd) if cwd is not None else None,
        check=True,
    )


def verify_phase1() -> None:
    missing = []

    for relative_path in REQUIRED_PHASE1_FILES:
        if not (ROOT / relative_path).exists():
            missing.append(relative_path)

    if missing:
        print("Phase 1 is incomplete. Missing files:", file=sys.stderr)
        for relative_path in missing:
            print(f"  - {relative_path}", file=sys.stderr)

        raise SystemExit(1)

    print("OK    Phase 1 skeleton detected")


def write_phase2_files() -> None:
    for relative_path, content in PHASE2_FILES.items():
        target = ROOT / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print(f"WRITE {relative_path}")


def add_rust_dependencies() -> None:
    run(
        ["cargo", "add", "keyring"],
        cwd=ROOT / "src-tauri",
    )


def main() -> int:
    print(f"Project root: {ROOT}")

    verify_phase1()
    add_rust_dependencies()
    write_phase2_files()

    run(["npm", "run", "check"], cwd=ROOT)
    run(["npm", "run", "build"], cwd=ROOT)

    run(["cargo", "test"], cwd=ROOT / "src-tauri")
    run(["cargo", "check"], cwd=ROOT / "src-tauri")

    print("\nPHASE 2 automated checks passed.")
    print("\nNext manual test:")
    print("  npm run tauri dev")
    print("\nTest sequence:")
    print("  1. Enter Secret ID: test-api-key")
    print("  2. Enter Secret value: super-secret-123")
    print("  3. Click Store Secret")
    print("  4. Click Exists")
    print("  5. Click Get Secret")
    print("\nExpected result:")
    print("  Secret exists: yes")
    print("  Retrieved secret: super-secret-123")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())