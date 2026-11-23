from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_revision_graph_is_unique_and_has_one_head() -> None:
    backend_dir = Path(__file__).resolve().parents[3]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    script = ScriptDirectory.from_config(config)

    revisions = list(script.walk_revisions())
    revision_ids = [revision.revision for revision in revisions]

    assert len(revision_ids) == len(set(revision_ids))
    assert script.get_heads() == ["009"]



def test_inventory_payment_migration_preserves_settings_and_added_data() -> None:
    backend_dir = Path(__file__).resolve().parents[3]
    migration_path = (
        backend_dir
        / "alembic"
        / "versions"
        / "006_inventory_payment_setting_columns.py"
    )
    source = migration_path.read_text(encoding="utf-8")

    assert 'drop_column("settings", "is_encrypted")' not in source
    assert "def downgrade() -> None:" in source
    assert "    pass" in source[source.index("def downgrade() -> None:") :]
