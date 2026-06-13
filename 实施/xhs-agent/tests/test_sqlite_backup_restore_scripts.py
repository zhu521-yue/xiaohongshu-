import sqlite3
from pathlib import Path

from scripts import backup_sqlite_db, restore_sqlite_db


def _make_db(path: Path, value: str) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS sample (value TEXT)")
        connection.execute("DELETE FROM sample")
        connection.execute("INSERT INTO sample (value) VALUES (?)", (value,))


def _read_value(path: Path) -> str:
    with sqlite3.connect(path) as connection:
        return connection.execute("SELECT value FROM sample").fetchone()[0]


def test_backup_creates_timestamped_copy(tmp_path: Path) -> None:
    db_path = tmp_path / "xhs.sqlite3"
    backup_dir = tmp_path / "backups"
    _make_db(db_path, "original")

    result = backup_sqlite_db.backup_database(
        db_path=db_path,
        backup_dir=backup_dir,
        timestamp="20260613_200000",
    )

    assert result["ok"] is True
    backup_path = Path(result["backup_path"])
    assert backup_path.exists()
    assert backup_path.name == "xhs_20260613_200000.sqlite3"
    assert _read_value(backup_path) == "original"


def test_restore_dry_run_does_not_modify_target(tmp_path: Path) -> None:
    target = tmp_path / "xhs.sqlite3"
    backup = tmp_path / "backup.sqlite3"
    _make_db(target, "target")
    _make_db(backup, "backup")

    result = restore_sqlite_db.restore_database(
        target_db_path=target,
        backup_path=backup,
        apply=False,
    )

    assert result["ok"] is True
    assert result["applied"] is False
    assert _read_value(target) == "target"


def test_restore_apply_creates_pre_restore_backup_and_replaces_db(tmp_path: Path) -> None:
    target = tmp_path / "xhs.sqlite3"
    backup = tmp_path / "backup.sqlite3"
    pre_restore_dir = tmp_path / "pre_restore"
    _make_db(target, "target")
    _make_db(backup, "backup")

    result = restore_sqlite_db.restore_database(
        target_db_path=target,
        backup_path=backup,
        pre_restore_dir=pre_restore_dir,
        timestamp="20260613_200001",
        apply=True,
    )

    assert result["ok"] is True
    assert result["applied"] is True
    assert Path(result["pre_restore_backup_path"]).exists()
    assert _read_value(target) == "backup"
