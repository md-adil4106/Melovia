#!/usr/bin/env python3
"""Scan Git commit history for accidentally committed secrets, tokens, and keys.

Usage:
    python scripts/scan_secrets_history.py
"""

import re
import subprocess
import sys

# High-confidence secret patterns
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("OpenAI / Provider API Key", re.compile(r"""(?i)(?:api[_-]?key|secret|token)\s*[:=]\s*["'](sk-[A-Za-z0-9_-]{20,})["']""")),
    ("Private Key Header", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("AWS Access Key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub Personal Access Token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{36,}\b")),
    ("Generic Hardcoded Token Assignment", re.compile(r"""(?i)(?:client_secret|oauth_token|jwt_secret)\s*[:=]\s*["']([A-Za-z0-9_\-]{24,})["']""")),
]

# Whitelist safe placeholders used in tests, examples, and fixtures
SAFE_PLACEHOLDERS = {
    "your-llm-api-key-here",
    "your-spotify-client-id",
    "your-spotify-client-secret",
    "melovia_password",
    "melovia_secret",
    "mock_spotify_secret",
    "dummy_secret_key",
    "test-secret-value",
}


def scan_git_history() -> int:
    """Run git log -p and scan all added/modified lines for secrets."""
    print("=== Scanning Full Git Commit History for Secrets ===")
    try:
        proc = subprocess.run(
            ["git", "log", "-p", "--full-history", "--no-merges"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=True,
        )
    except subprocess.CalledProcessError as err:
        print(f"Failed to execute git log: {err}")
        return 1

    lines = proc.stdout.splitlines()
    violations: list[tuple[str, str, str]] = []
    current_commit = "HEAD"
    current_file = "unknown"

    for line in lines:
        if line.startswith("commit "):
            current_commit = line.split()[1][:8]
        elif line.startswith("+++ b/"):
            current_file = line[6:].strip()
        elif line.startswith("+") and not line.startswith("+++"):
            content = line[1:].strip()
            # Ignore comments, markdown docs, examples, and tests with known placeholders
            if (
                current_file.endswith((".example", ".md", ".json.example"))
                or "test_" in current_file
                or "conftest.py" in current_file
            ):
                continue

            for pattern_name, pattern in SECRET_PATTERNS:
                match = pattern.search(content)
                if match:
                    candidate = match.group(0)
                    # Check if candidate contains known safe placeholder
                    if any(safe in candidate for safe in SAFE_PLACEHOLDERS):
                        continue
                    violations.append((current_commit, current_file, f"{pattern_name}: {candidate[:35]}..."))

    if violations:
        print(f"\n[ALERT] Found {len(violations)} potential secret(s) in git history:")
        for commit, filepath, reason in violations:
            print(f"  - [{commit}] {filepath}: {reason}")
        return 1

    print("[PASS] Clean! No unwhitelisted secrets, tokens, or private keys found in Git history.")
    return 0


if __name__ == "__main__":
    sys.exit(scan_git_history())
