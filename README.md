# Chapar

Chapar is a local-first, security-focused desktop API client.

It is built with Tauri v2, Rust, SvelteKit, TypeScript, Tailwind CSS, Monaco Editor, SQLite, and the OS keychain via <code>keyring</code>.

## Security Model

- HTTP requests are executed only from the Rust backend.
- Secrets are stored in the OS keychain.
- Secret values are not stored in SQLite.
- Secret values are not exported.
- Secret values are not returned to the normal frontend UI.
- Requests using unresolved or unauthorized variables are blocked before sending.
- Diagnostic secret retrieval commands are not exposed in production mode.

## Tech Stack

- Desktop shell: Tauri v2
- Backend: Rust
- HTTP client: reqwest
- Database: SQLite via rusqlite
- Secret storage: OS keychain via keyring
- Frontend: SvelteKit in SPA mode
- UI styling: Tailwind CSS
- Editor: Monaco Editor
- Icons: Lucide

## Features

- Collections and saved requests
- SQLite persistence for non-sensitive data
- Environment variables
- Secret vault backed by OS keychain
- Secret injection into headers
- Request execution from Rust
- Response inspector with Monaco Editor
- Request history
- Export and import for collections, requests, environments, and secret metadata
- Production hardening scripts

## Project Scripts

Phase and maintenance scripts:

<pre>
./scripts/phase0.sh
./scripts/phase1.sh
./scripts/phase2.sh
./scripts/phase3.sh
./scripts/phase4.sh
./scripts/phase5.sh
./scripts/phase6.sh
./scripts/phase7.sh
./scripts/phase8.sh
./scripts/phase9.sh
</pre>

Final production script:

<pre>
python3 scripts/phase9_final.py
</pre>

Final verification:

<pre>
python3 scripts/final_check.py
</pre>

## Development

Install dependencies if needed:

<pre>
npm install
</pre>

Start the app in development mode:

<pre>
npm run tauri dev
</pre>

## Environment Variables

Environment variables use this syntax:

<pre>
{{base_url}}
</pre>

Example environment variable:

<pre>
base_url = http://localhost:8080
</pre>

Then request:

<pre>
{{base_url}}/users
</pre>

Chapar resolves it to:

<pre>
http://localhost:8080/users
</pre>

Missing variables are blocked before the request is sent.

## Secrets

Secrets use this syntax:

<pre>
{{secret:prod-api-key}}
</pre>

Secrets can also be attached directly to a header using the header secret selector.

Secret values are stored in the OS keychain.

Only secret metadata is stored in SQLite:

- secret ID
- secret label
- created date

Secret values are not exported.

## Request History

Executed requests are automatically saved to history.

History entries can be:

- viewed
- inspected
- loaded back into the request editor
- cleared

History is pruned automatically to the most recent 200 entries.

## Export and Import

Chapar can export:

- collections
- requests
- environments
- secret metadata

Chapar does not export secret values.

Exported data can be imported again from the Data panel.

## Production Build

Run final checks:

<pre>
python3 scripts/final_check.py
</pre>

Create a production bundle:

<pre>
./scripts/release.sh
</pre>

Create a faster debug bundle:

<pre>
./scripts/release.sh -- --debug
</pre>

## Production Secret Commands

The following diagnostic commands are not exposed to the frontend in production mode:

<pre>
get_secret
store_secret
</pre>

Secrets are managed through:

<pre>
save_secret
delete_secret
secret_exists
list_secret_metadata
</pre>

Secret values are injected only inside Rust during request execution.

## Local Documentation

A local HTML documentation file is generated at:

<pre>
docs/chapar.html
</pre>

This README generator is located at:

<pre>
docs/readme_generator.html
</pre>

## Phase Status

<pre>
Phase 0: Architectural skeleton              Complete
Phase 1: Scaffolding and SQLite setup         Complete
Phase 2: Keyring secret storage               Complete
Phase 3: Rust HTTP engine                     Complete
Phase 4: Frontend UI and Monaco               Complete
Phase 5: Environment variables                Complete
Phase 6: Collections and request persistence  Complete
Phase 7: Secure vault UI and secret injection Complete
Phase 8: History, export, import              Complete
Phase 9: Production hardening                 Complete
</pre>

## Recommended Final Verification

Run:

<pre>
python3 scripts/final_check.py
</pre>

Then start the app:

<pre>
npm run tauri dev
</pre>

Verify:

1. Collections can be created.
2. Requests can be saved.
3. Requests persist after restart.
4. Environment variables resolve correctly.
5. Secrets can be stored.
6. Secrets are injected into headers.
7. Missing variables are blocked.
8. History appears after sending requests.
9. Export produces JSON.
10. Import restores data.