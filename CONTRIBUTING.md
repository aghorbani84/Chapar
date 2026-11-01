# Contributing to Chapar

Thank you for your interest in contributing!

## Development Setup

1. Install [Rust](https://www.rust-lang.org/tools/install) (1.85+) and [Node.js](https://nodejs.org/) 20+.
2. Install dependencies: `npm ci`
3. Run the frontend dev server: `npm run dev`
4. In another terminal, run the desktop app: `npm run tauri dev`

## Checks

Before opening a pull request, please run:

```bash
# Frontend
npm ci
npm run check
npm run build

# Backend (from src-tauri/)
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test
```

These checks also run automatically in CI on every pull request.

## Pull Requests

- Keep changes focused and incremental.
- Do not commit secrets, tokens, or credentials.
- Update documentation (README.md) when behavior changes.
