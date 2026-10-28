# Local statement normalization SDK

The public facade is `src.kakeibo.sdk.normalize_statement`. It runs entirely against a caller-provided local file and does not start the CLI or API server.

Contract version: `kakeibo-normalization/v1`

The result records the statement type, parser contract version, input SHA-256, declared encoding, canonical record count, rejected count, covered period, structured reason code, and canonical transactions. It never returns the local file path, raw statement rows, account/card identifiers, API tokens, or other secrets.

Supported adapters are discovered from the existing `StatementTypeSpec` registry through `adapter_manifest()`. That registry remains the canonical adapter authority. Current adapters include Sony Bank, e-NAVI, APLUS, transaction-history CSV, and generic CSV.

Example:

```python
from src.kakeibo.sdk import normalize_statement

result = normalize_statement("statement.csv", statement_type="transaction")
if not result.success:
    raise RuntimeError(result.reason_code)
for transaction in result.canonical_transactions:
    consume(transaction)
```

Structured failure states are `UNKNOWN_STATEMENT_TYPE`, `SUFFIX_MISMATCH`, `INPUT_NOT_FOUND`, `PARSE_FAILED`, and `SCHEMA_MISMATCH`. Callers must not reinterpret these as an empty successful statement.

Synthetic integrations should create fixture statements locally, call the SDK, and discard the fixtures after the test. Real statement files must not be committed or sent to analytics.

Optional product analytics may use `docs/sdk-events.schema.json`. Only contract-level metadata is allowed. Raw transaction text, filenames, filesystem paths, account/card data, or tokens are prohibited. The schema distinguishes synthetic/test events from actual observations through `observation_kind`.

For integration or additional adapter work, use the repository issue tracker. External buyer activity, contracts, and sales are not required for SDK correctness.
