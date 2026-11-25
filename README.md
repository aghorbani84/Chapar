<p align="center">
  <img src="app-icon.png" alt="Chapar icon" width="96" />
</p>

<h1 align="center">Chapar</h1>

<p align="center">
  <b>A local-first, security-focused desktop API client — built with Tauri 2, Rust and SvelteKit.</b>
</p>

<p align="center">
  <a href="https://github.com/aghorbani84/Chapar/actions/workflows/ci.yml"><img src="https://github.com/aghorbani84/Chapar/actions/workflows/ci.yml/badge.svg?branch=master" alt="CI" /></a>
  <a href="https://github.com/aghorbani84/Chapar/releases"><img src="https://img.shields.io/github/v/release/aghorbani84/Chapar" alt="Latest release" /></a>
  <img src="https://img.shields.io/badge/Tauri-2-24C8DB?logo=tauri&logoColor=white" alt="Tauri 2" />
  <img src="https://img.shields.io/badge/Rust-backend-DEA584?logo=rust&logoColor=black" alt="Rust" />
  <img src="https://img.shields.io/badge/Svelte-5-FF3E00?logo=svelte&logoColor=white" alt="Svelte 5" />
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT License" /></a>
</p>

---

## Overview

Chapar (چاپار, Persian for "courier") is a desktop HTTP client in the spirit of Postman or Insomnia, designed to keep everything on your machine. Requests are executed by the Rust backend — not the WebView — so there are no CORS limits, and secrets live in your operating system's keychain instead of in app storage.

## Features

- **Collections & requests** — organize saved requests into named collections
- **All common methods** — `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `HEAD`, `OPTIONS`
- **Request bodies** — none, JSON, text, form URL-encoded, or raw
- **Environments** — reusable `{{variable}}` placeholders with an active environment
- **Secret vault** — values stored in the OS keychain (macOS Keychain, Windows Credential Manager, Linux Secret Service); only metadata is kept in SQLite
- **Secret injection** — reference secrets as `{{secret:id}}` (for example in an `Authorization` header); only secrets attached to the request are allowed, and values are resolved in Rust and never returned to the UI
- **Pre-flight validation** — requests with unresolved or unauthorized variables are blocked before sending
- **Timeouts & redirects** — per-request timeout, follow/no-follow, and a redirect limit (default 10)
- **Response inspector** — JSON, text, or binary (base64) bodies shown in Monaco Editor
- **History** — the most recent 200 requests are kept locally
- **Export / import** — back up and restore your workspace as a bundle; secret values are never exported

## Tech Stack

| Layer | Technology |
| --- | --- |
| Desktop shell | [Tauri 2](https://tauri.app/) |
| Backend | Rust · `reqwest` (HTTP) · `rusqlite` (bundled SQLite) · `keyring` (OS keychain) |
| Frontend | SvelteKit (static SPA) · Svelte 5 · TypeScript |
| Styling | Tailwind CSS 4 |
| Editor | Monaco Editor |
| Icons | Lucide |

## Getting Started

### Prerequisites

- [Rust](https://www.rust-lang.org/tools/install) (stable)
- [Node.js](https://nodejs.org/) (CI uses Node 22) and npm
- The [Tauri 2 system prerequisites](https://v2.tauri.app/start/prerequisites/) for your OS (on Linux: WebKitGTK 4.1 and related dev packages)

### Run in development

```bash
git clone https://github.com/aghorbani84/Chapar.git
cd Chapar
npm install
npm run tauri dev        # starts the Vite dev server on port 1420 and opens the app
```

### Build

```bash
npm run tauri build      # native bundles for your platform
```

Pre-built Linux packages (`.deb`, `.rpm`) are attached to [GitHub Releases](https://github.com/aghorbani84/Chapar/releases).

### Checks

```bash
npm run check                         # svelte-check / TypeScript
cd src-tauri
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test
```

## Using Variables and Secrets

```text
# Environment variable
base_url = http://localhost:8080

# Request URL
{{base_url}}/users        →  http://localhost:8080/users

# Secret reference in a header
Authorization: Bearer {{secret:api-key}}
```

Missing variables block the request instead of sending a half-resolved URL.

## Project Structure

```text
Chapar/
├── src/                     # SvelteKit frontend
│   ├── lib/components/      # Request/response panes, sidebar, env & secret panels
│   ├── lib/stores/          # Svelte stores (collections, history, environments…)
│   ├── lib/services/        # Typed wrappers around Tauri commands
│   └── routes/              # App entry page
├── src-tauri/               # Rust backend
│   └── src/
│       ├── commands/        # Tauri command handlers
│       ├── http.rs          # Request execution (reqwest)
│       ├── env.rs           # Variable & secret resolution
│       ├── vault.rs         # OS keychain access
│       └── db.rs            # SQLite persistence
├── docs/                    # Standalone HTML docs
└── .github/workflows/       # CI and release builds
```

## Security

See [SECURITY.md](SECURITY.md) for the security policy and how to report issues.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Released under the [MIT License](LICENSE).

## Author

Built by [@aghorbani84](https://github.com/aghorbani84).
