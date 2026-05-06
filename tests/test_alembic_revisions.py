import ast
from dataclasses import dataclass
from pathlib import Path
import unittest


VERSIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"


@dataclass(frozen=True)
class RevisionMeta:
    revision: str
    down_revision: str | None
    path: Path


def load_revision_meta(path: Path) -> RevisionMeta:
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values: dict[str, str | None] = {}

    for node in module.body:
        if not isinstance(node, ast.AnnAssign):
            continue
        if not isinstance(node.target, ast.Name):
            continue
        if node.target.id not in {"revision", "down_revision"}:
            continue

        value = node.value
        if isinstance(value, ast.Constant):
            values[node.target.id] = value.value

    revision = values.get("revision")
    if not isinstance(revision, str):
        raise AssertionError(f"Missing revision id in {path.name}")

    down_revision = values.get("down_revision")
    if down_revision is not None and not isinstance(down_revision, str):
        raise AssertionError(f"Unexpected down_revision in {path.name}")

    return RevisionMeta(
        revision=revision,
        down_revision=down_revision,
        path=path,
    )


class AlembicRevisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.revisions = {
            meta.revision: meta
            for meta in (load_revision_meta(path) for path in sorted(VERSIONS_DIR.glob("*.py")))
        }

    def test_test_session_quiz_type_migration_exists(self) -> None:
        revision = self.revisions.get("b7c9d1e2f3a4")
        self.assertIsNotNone(revision, "Missing migration for test_sessions.quiz_type")
        self.assertEqual(revision.down_revision, "a1b2c3d4e5f6")

    def test_performance_indexes_follow_quiz_type_migration(self) -> None:
        revision = self.revisions["c7f8a9b0d1e2"]
        self.assertEqual(revision.down_revision, "b7c9d1e2f3a4")


if __name__ == "__main__":
    unittest.main()
