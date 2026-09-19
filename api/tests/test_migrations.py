"""Tests for Alembic database migrations."""

from pathlib import Path

from alembic.config import Config

from alembic import command


def test_alembic_migrations_lifecycle(tmp_path: Path) -> None:
    """Test full migration lifecycle: upgrade head -> downgrade base -> upgrade head."""
    db_file = tmp_path / "migration_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    api_dir = Path(__file__).resolve().parent.parent
    alembic_ini = api_dir / "alembic.ini"

    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(api_dir / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)

    # 1. Upgrade to head
    command.upgrade(cfg, "head")

    # 2. Downgrade to base
    command.downgrade(cfg, "base")

    # 3. Upgrade to head again
    command.upgrade(cfg, "head")
