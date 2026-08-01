# Security and privacy policy

This public repository contains application code only. Real financial records, generated reports, logs, local paths, credentials, and database exports must remain outside Git.

## Data boundary

Use the ignored `private/` tree for local inputs, outputs, and logs. The API is disabled by default and requires both `KAKEIBO_API_ENABLED=true` and a random `KAKEIBO_API_TOKEN` of at least 32 characters. Requests must send the token in the `X-API-Key` header.

The API accepts one raw file body per request, limits its size and suffix, never receives or stores the original filename, processes it inside a temporary directory, and removes that directory when the request ends.

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
