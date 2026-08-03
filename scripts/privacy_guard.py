#!/usr/bin/env python3
"""Reject secrets, personal finance artifacts, and identifying local paths."""

from __future__ import annotations

import argparse
import math
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_TEXT_BYTES = 1_000_000

BLOCKED_SUFFIXES = {
    ".csv",
    ".tsv",
    ".xls",
    ".xlsx",
    ".ods",
    ".ofx",
    ".qfx",
    ".qif",
    ".mt940",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".jks",
    ".log",
    ".zip",
    ".7z",
    ".rar",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".pdf",
}

BLOCKED_PARTS = {
    "private",
    "input",
    "output",
    "raw",
    "exports",
    "statements",
    "transactions",
    "credentials",
    "secrets",
    "backups",
    "logs",
}

ALLOWED_PATHS = {
    ".env.example",
    "scripts/privacy_guard.py",
}
# Generated dependency locks contain checksums and registry metadata that can
# coincidentally pass the Luhn test. The lock remains path-scanned and size-
# scanned, but its generated content is not treated as a financial statement.
CONTENT_SCAN_EXEMPT = {"scripts/privacy_guard.py", "uv.lock"}

SECRET_PATTERNS = (
    (
        "private key",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    ),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,255}\b")),
    ("AWS access key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{20,}\b")),
    ("Stripe secret", re.compile(r"\bsk_(?:live|test)_[0-9A-Za-z]{20,}\b")),
    (
        "JWT",
        re.compile(
            r"\beyJ[A-Za-z0-9_-]{15,}\."
            r"[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\b"
        ),
    ),
)

ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|"
    r"service[_-]?role[_-]?key|password|passwd|secret)\b\s*[:=]\s*[\"']?"
    r"([A-Za-z0-9_./+=-]{12,})"
)

LOCAL_PATH_PATTERNS = (
    re.compile(r"(?i)\b[A-Z]:\\Users\\[^\\\s]+\\"),
    re.compile(r"/Users/[^/\s]+/"),
    re.compile(r"/home/[^/\s]+/"),
    re.compile(r"(?i)\b[A-Z]:\\(?:DB|Documents|Downloads|Desktop)\\"),
)

LABELED_FINANCIAL_NUMBER = re.compile(
    r"(?i)(?:口座番号|account\s*(?:number|no\.?))\D{0,12}([0-9 -]{6,20})"
)
CARD_CANDIDATE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
PLACEHOLDER_MARKERS = {
    "example",
    "placeholder",
    "replace",
    "dummy",
    "sample",
    "changeme",
    "your_",
    "xxxx",
    "...",
}


def _run_git(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [item for item in result.stdout.split("\0") if item]


def candidate_paths(all_files: bool, explicit: list[str]) -> list[Path]:
    if explicit:
        names = explicit
    elif all_files:
        names = _run_git("ls-files", "-z")
    else:
        names = _run_git(
            "diff",
            "--cached",
            "--name-only",
            "--diff-filter=ACMR",
            "-z",
        )
    return [ROOT / name for name in names if (ROOT / name).is_file()]


def luhn_valid(value: str) -> bool:
    digits = [int(char) for char in value if char.isdigit()]
    if not 13 <= len(digits) <= 19 or len(set(digits)) == 1:
        return False
    checksum = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def high_entropy_secret(value: str) -> bool:
    lowered = value.lower()
    if any(marker in lowered for marker in PLACEHOLDER_MARKERS):
        return False
    probabilities = [value.count(char) / len(value) for char in set(value)]
    entropy = -sum(
        probability * math.log2(probability) for probability in probabilities
    )
    return entropy >= 3.5


def blocked_path_reason(relative: Path) -> str | None:
    normalized = relative.as_posix()
    if normalized in ALLOWED_PATHS:
        return None
    if relative.name == ".env" or relative.name.startswith(".env."):
        return "environment file"
    if relative.suffix.lower() in BLOCKED_SUFFIXES:
        return f"blocked data or credential suffix {relative.suffix.lower()}"
    if any(part.lower() in BLOCKED_PARTS for part in relative.parts[:-1]):
        return "blocked private-data directory"
    return None


def content_findings(text: str) -> list[str]:
    findings: list[str] = []
    for label, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            findings.append(label)

    for match in ASSIGNMENT_PATTERN.finditer(text):
        if high_entropy_secret(match.group(1)):
            findings.append("high-entropy credential assignment")
            break

    if any(pattern.search(text) for pattern in LOCAL_PATH_PATTERNS):
        findings.append("identifying absolute local path")

    if LABELED_FINANCIAL_NUMBER.search(text):
        findings.append("labeled bank account number")

    if any(luhn_valid(match.group(0)) for match in CARD_CANDIDATE.finditer(text)):
        findings.append("payment-card-like number")

    return sorted(set(findings))


def scan(path: Path) -> list[str]:
    relative = path.relative_to(ROOT)
    reason = blocked_path_reason(relative)
    findings = [reason] if reason else []

    size = path.stat().st_size
    if size > MAX_TEXT_BYTES:
        findings.append(f"file exceeds {MAX_TEXT_BYTES} bytes")
        return findings

    data = path.read_bytes()
    if b"\x00" in data:
        findings.append("binary file")
        return findings

    text = data.decode("utf-8", errors="replace")
    if relative.as_posix() not in CONTENT_SCAN_EXEMPT:
        findings.extend(content_findings(text))
    return sorted(set(findings))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--all-files", action="store_true")
    args = parser.parse_args()

    failures: list[tuple[str, list[str]]] = []
    for path in candidate_paths(args.all_files, args.paths):
        findings = scan(path)
        if findings:
            failures.append((path.relative_to(ROOT).as_posix(), findings))

    if failures:
        print("Privacy guard blocked the change:", file=sys.stderr)
        for path, findings in failures:
            print(f"- {path}: {', '.join(findings)}", file=sys.stderr)
        return 1

    print("Privacy guard passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
