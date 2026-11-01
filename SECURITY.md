# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Chapar, please report it responsibly.

- Open a private security advisory via GitHub's "Security Advisories" feature on this repository, or
- Contact the maintainers through the repository's issue tracker with the `security` label (do **not** include exploit details or secret values in public issues).

Please do not disclose vulnerabilities publicly until a fix has been released.

## Scope

Chapar is a local-first desktop API client. Relevant security concerns include:

- Secret handling (OS keychain storage, injection into requests, exclusion from exports/history).
- The Tauri command surface exposed to the frontend (only registered commands are callable).
- Content Security Policy and webview hardening in `src-tauri/tauri.conf.json`.
- Dependency vulnerabilities in the Rust (`src-tauri/Cargo.lock`) and npm (`package-lock.json`) lockfiles.

## Supported Versions

Security fixes are applied to the latest release. Please keep Chapar up to date.
