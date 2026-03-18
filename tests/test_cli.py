from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_TASK = ROOT / "tasks" / "examples" / "jobs_sample.json"
ENV = dict(**__import__("os").environ)
ENV["PYTHONPATH"] = str(ROOT / "src")


class CliTests(unittest.TestCase):
    def test_validate_command(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "app.interfaces.cli.main", "--base-dir", str(ROOT / "data"), "validate", str(EXAMPLE_TASK)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            env=ENV,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["task"]["domain"], "jobs")

    def test_run_command_creates_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = subprocess.run(
                [sys.executable, "-m", "app.interfaces.cli.main", "--base-dir", temp_dir, "run", str(EXAMPLE_TASK)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
                env=ENV,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            sqlite_path = Path(payload["artifacts"]["sqlite_file"])
            self.assertTrue(sqlite_path.exists())
            connection = sqlite3.connect(sqlite_path)
            try:
                task_id = connection.execute("SELECT task_id FROM task_runs").fetchone()[0]
            finally:
                connection.close()
            self.assertEqual(task_id, "job-sample-001")


if __name__ == "__main__":
    unittest.main()
