## Privacy gate

- [ ] No real bank/card statements, transaction exports, screenshots, databases, logs, or archives are included.
- [ ] No API keys, tokens, service-role keys, credentials, or `.env` files are included.
- [ ] Tests use synthetic data only.
- [ ] Logs and error messages do not expose filenames, paths, descriptions, balances, or transaction rows.
- [ ] `python scripts/privacy_guard.py --all-files` passes.
