# Chapar

A local-first, security-focused desktop API client built with Tauri v2, Rust, SvelteKit, TypeScript, Tailwind CSS, Monaco Editor, SQLite, and the OS keychain.

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Tauri](https://img.shields.io/badge/Tauri-2.x-cyan.svg)](https://tauri.app/)
[![Rust](https://img.shields.io/badge/Rust-1.85%2B-orange.svg)](https://www.rust-lang.org/)

---

## Security Model

Chapar is designed with security as a first-class concern:

- **Backend Execution**: HTTP requests are executed only from the Rust backend, preventing CORS restrictions and enabling secure secret handling.
- **Keychain Secrets**: Secrets are stored in the OS keychain (macOS Keychain, Windows Credential Manager, Linux Secret Service).
- **No Secret Leakage**: Secret values are never stored in SQLite, never exported, and never returned to the frontend UI.
- **Injection Validation**: Requests using unresolved or unauthorized variables are blocked before sending.
- **Production Hardening**: Diagnostic secret retrieval commands (`get_secret`, `store_secret`) are disabled in production builds.

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Desktop Shell | [Tauri v2](https://tauri.app/) | Cross-platform native desktop app |
| Backend | Rust | Secure request execution & secret management |
| HTTP Client | reqwest | Async HTTP client with TLS support |
| Database | SQLite (rusqlite) | Local persistence for collections, requests, environments |
| Secret Storage | keyring | OS keychain integration |
| Frontend | SvelteKit (SPA mode) | Reactive UI framework |
| Styling | Tailwind CSS v4 | Utility-first CSS framework |
| Editor | Monaco Editor | Rich text/code editing |
| Icons | Lucide | Open-source icon library |

---

## Features

- **Collections & Requests**: Organize API calls into named collections with full request management.
- **SQLite Persistence**: Non-sensitive data persists locally across sessions.
- **Environment Variables**: Define reusable variables with `{{variable_name}}` syntax.
- **Secret Vault**: Secure OS keychain integration for sensitive credentials.
- **Secret Injection**: Inject secrets directly into headers with UI support.
- **Response Inspector**: View formatted JSON, text, or base64 responses in Monaco.
- **Request History**: Automatic history tracking (last 200 entries).
- **Export/Import**: Backup and restore complete workspaces (no secrets exported).
- **Production Builds**: Hardened builds with secrets isolated from frontend.

---

## Quick Start

### Prerequisites

- [Rust 1.85+](https://www.rust-lang.org/tools/install)
- [Node.js 20+](https://nodejs.org/)
- [Tauri CLI](https://tauri.app/v1/guides/getting-started/prerequisites)

### Development

```bash
# Install dependencies
npm install

# Start in development mode (Tauri + dev server on port 1420)
npm run tauri dev
```

### Build

```bash
# Production build
npm run build

# Preview build locally
npm run preview
```

---

## Configuration

### Environment Variables

Define environment variables using the `{{name}}` syntax:

```
# Environment definition
base_url = http://localhost:8080

# In request URL field
{{base_url}}/users
```

Result: `http://localhost:8080/users`

Missing variables are blocked before request execution.

### Secrets

Secrets use the `{{secret:id}}` syntax or can be attached to headers via the UI:

```
# Secret references in request
Authorization: Bearer {{secret:api-key}}

# Header secret selector
X-API-Key: {{secret:prod-secret}}
```

**Secret Storage**:

- Secrets are stored exclusively in the OS keychain
- Only metadata (ID, label, timestamp) is stored in SQLite
- Secret values are never exported or exposed to frontend

---

## Project Structure

```
├── src/                    # Frontend (SvelteKit)
│   ├── lib/               # Shared components & stores
│   │   ├── components/    # UI components
│   │   ├── services/      # API service layer
│   │   ├── stores/        # Svelte stores
│   │   └── types/         # TypeScript interfaces
│   └── routes/            # SvelteKit pages
├── src-tauri/             # Backend (Rust)
│   ├── src/
│   │   ├── commands/      # Tauri command handlers
│   │   ├── db.rs         # SQLite operations
│   │   ├── env.rs        # Variable resolution
│   │   ├── http.rs       # HTTP execution engine
│   │   ├── vault.rs      # Keychain operations
│   │   └── models.rs     # Data structures
│   └── Cargo.toml
├── build/                 # Build output directory
├── docs/                  # Documentation
└── scripts/               # Build & production scripts
```

---

## API Reference

### Backend Commands

| Command | Description |
|---------|-------------|
| `list_environments` | Get all environments |
| `save_environment` | Create/update environment |
| `delete_environment` | Remove environment |
| `set_active_environment` | Set active environment |
| `list_collections` | Get all collections |
| `create_collection` | Create new collection |
| `list_requests` | Get requests in collection |
| `save_request` | Save/update request |
| `execute_request` | Execute HTTP request |
| `list_history` | Get request history |
| `list_secret_metadata` | Get secret metadata only |
| `save_secret` | Store secret in keychain |
| `delete_secret` | Remove secret from keychain |

### Frontend API Service

```typescript
import { api } from '$lib/services/api';

// Execute request
const response = await api.executeRequest({
  request: myRequest,
  environmentId: 'env-id',
  timeoutMs: 5000,
  followRedirects: true,
  maxRedirects: 10
});
```

---

## Production Build

### Final Verification

```bash
# Run comprehensive checks
python3 scripts/final_check.py
```

### Release Script

```bash
# Create full production bundle
./scripts/release.sh

# Create debug bundle for testing
./scripts/release.sh -- --debug
```

### Production Commands

The following diagnostic commands are only available in development:

- `get_secret` - Retrieve secret value
- `store_secret` - Store secret directly

In production, manage secrets via:

- `save_secret`
- `delete_secret`
- `secret_exists`
- `list_secret_metadata`

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (SvelteKit)                    │
│                                                             │
│  Request Editor → Request Payload → Tauri API → Rust     │
│                             ↓                               │
│                   ┌─────────────────┐                      │
│                   │   Rust Backend  │                      │
│                   │                 │                      │
│                   │ - Validate vars │                      │
│                   │ - Inject secrets│                      │
│                   │ - Execute HTTP  │                      │
│                   │ - Store history │                      │
│                   └────────┬────────┘                      │
│                            ↓                               │
│                  Tauri IPC Transport                      │
│                            ↓                               │
│                   ┌─────────────────┐                      │
│                   │  reqwest Engine │                      │
│                   └────────┬────────┘                      │
│                            ↓                               │
│                    Remote API Server                        │
│                                                             │
│  Response ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
│                                                             │
│        Response Inspector (Monaco Editor)                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Development Scripts

| Script | Description |
|--------|-------------|
| `npm run dev` | Start SvelteKit dev server (port 1420) |
| `npm run build` | Build for production |
| `npm run tauri dev` | Full Tauri development mode |
| `npm run tauri build` | Create production bundle |

---

## Local Documentation

Complete HTML documentation is generated at:

- [docs/chapar.html](docs/chapar.html) - Main documentation
- [docs/readme_generator.html](docs/readme_generator.html) - README generator tool

---

## License

MIT License - See [LICENSE](LICENSE) for details.

---

## Contributing

This is an internal project. For questions or issues, refer to the documentation or contact the development team.

---

**Note**: This README will also be generated automatically by the built-in README generator in `docs/readme_generator.html`.