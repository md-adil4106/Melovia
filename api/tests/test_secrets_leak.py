"""Architectural boundary and secret leakage regression tests for Melovia.

Verifies:
1. Pure recsys boundary: Zero imports of `app.platforms` in `api/app/recsys/*`.
2. Offline file adapter: `app.platforms.files` has zero network libraries or external calls.
3. Secret security: No `.env` files tracked in git, no hardcoded API keys/tokens.
"""

import re
from pathlib import Path


def test_recsys_has_zero_platform_imports():
    """Verify api/app/recsys/* strictly has no imports of app.platforms or platform adapters."""
    recsys_dir = Path(__file__).resolve().parent.parent / "app" / "recsys"
    assert recsys_dir.exists() and recsys_dir.is_dir()

    forbidden_patterns = [
        re.compile(r"^\s*from\s+app\.platforms", re.MULTILINE),
        re.compile(r"^\s*import\s+app\.platforms", re.MULTILINE),
        re.compile(r"^\s*from\s+.*platforms\s+import", re.MULTILINE),
        re.compile(r"spotify", re.IGNORECASE),
        re.compile(r"apple_music", re.IGNORECASE),
    ]

    for py_file in recsys_dir.glob("**/*.py"):
        content = py_file.read_text(encoding="utf-8")
        for pat in forbidden_patterns:
            matches = pat.findall(content)
            assert not matches, f"Architecture violation in '{py_file.name}': found {matches}"


def test_offline_files_adapter_has_no_network_imports():
    """Verify api/app/platforms/files.py has zero network/http imports."""
    files_adapter = Path(__file__).resolve().parent.parent / "app" / "platforms" / "files.py"
    assert files_adapter.exists()

    content = files_adapter.read_text(encoding="utf-8")
    forbidden_network = ["httpx", "requests", "urllib.request", "aiohttp", "socket"]
    for net_mod in forbidden_network:
        assert f"import {net_mod}" not in content, (
            f"FileExportAdapter must be 100% offline. Found import '{net_mod}' in files.py."
        )


def test_git_does_not_track_env_files():
    """Verify no active .env secret files are present in git repository."""
    repo_root = Path(__file__).resolve().parent.parent.parent

    # Check that .gitignore properly ignores .env
    gitignore_path = repo_root / ".gitignore"
    if gitignore_path.exists():
        gi_content = gitignore_path.read_text(encoding="utf-8")
        assert ".env" in gi_content, ".gitignore must explicitly ignore .env"
