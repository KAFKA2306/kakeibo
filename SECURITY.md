# Security and privacy policy

This public repository contains application code only. Real financial records, generated reports, logs, local paths, credentials, and database exports must remain outside Git.

## Data boundary

Use the ignored `private/` tree for local inputs, outputs, and logs. The API is disabled by default and requires both `KAKEIBO_API_ENABLED=true` and a random `KAKEIBO_API_TOKEN` of at least 32 characters. Requests must send the token in the `X-API-Key` header.

The API accepts one raw file body per request, limits its size, never receives or stores the original filename, processes it inside a temporary directory, and removes that directory when the request ends.

## Statement type boundary

API callers must send both:

```text
X-Statement-Type: sony | enavi | aplus | transaction | generic
X-File-Suffix: .txt | .csv
```

The server validates the pair against the canonical registry before reading the body as a statement. The original filename is not an identification channel. Unknown types, incompatible suffixes, and types without a registered Parser are rejected; they do not fall back to a generic Parser.

The accepted type is safe operational metadata, not a private filename. Logs may include the normalized type and an opaque file ID, but must not include the request body, transaction rows, source path, original filename, account number, balance, or description.

## Before every push

Run:

```bash
python scripts/privacy_guard.py --all-files
```

The same guard runs in GitHub Actions. The local pre-commit hook can be enabled with:

```bash
uvx pre-commit install
```

## Incident response

If sensitive data or a credential is committed, do not only delete the latest file. Revoke or rotate the credential immediately, remove the object from Git history, force-update affected refs, invalidate caches and published artifacts, then verify GitHub secret-scanning alerts.
