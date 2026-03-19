from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_TASK = ROOT / "tasks" / "examples" / "jobs_sample.json"
ENV = dict(**os.environ)
ENV["PYTHONPATH"] = str(ROOT / "src")


class CliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "app.interfaces.cli.main", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            env=ENV,
        )

    def test_validate_command(self) -> None:
        result = self.run_cli("--base-dir", str(ROOT / "data"), "validate", str(EXAMPLE_TASK))
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["task"]["domain"], "jobs")
        self.assertIn("selected_source_details", payload)

    def test_run_command_creates_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = self.run_cli("--base-dir", temp_dir, "run", str(EXAMPLE_TASK))
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            sqlite_path = Path(payload["artifacts"]["sqlite_file"])
            self.assertTrue(sqlite_path.exists())
            self.assertIn("created_at", payload)
            self.assertIn("selected_sources", payload)
            self.assertIn("fetch_stats", payload["quality_report"])
            connection = sqlite3.connect(sqlite_path)
            try:
                task_id = connection.execute("SELECT task_id FROM task_runs").fetchone()[0]
            finally:
                connection.close()
            self.assertEqual(task_id, "job-sample-001")

    def test_sources_command_lists_configured_profiles(self) -> None:
        result = self.run_cli("--base-dir", str(ROOT / "data"), "sources", "--domain", "jobs", "--channel", "rss")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["sources"][0]["source_id"], "python_org_jobs_rss")

    def test_sources_command_can_preview_task_selection(self) -> None:
        result = self.run_cli("--base-dir", str(ROOT / "data"), "sources", "--task-file", str(EXAMPLE_TASK))
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["task"]["task_id"], "job-sample-001")
        self.assertTrue(payload["selected_sources"])

    def test_tasks_command_lists_completed_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.run_cli("--base-dir", temp_dir, "run", str(EXAMPLE_TASK))
            result = self.run_cli("--base-dir", temp_dir, "tasks", "--domain", "jobs")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["total"], 1)
            self.assertEqual(payload["tasks"][0]["task_id"], "job-sample-001")
            self.assertEqual(payload["tasks"][0]["status"], "success")

    def test_status_command_shows_quality_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.run_cli("--base-dir", temp_dir, "run", str(EXAMPLE_TASK))
            result = self.run_cli("--base-dir", temp_dir, "status", "job-sample-001")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["task"]["task_id"], "job-sample-001")
            self.assertEqual(payload["status"], "success")
            self.assertIn("sqlite_file", payload["artifacts"])
            self.assertEqual(payload["quality_report"]["output_count"], 1)
            self.assertIn("fetch_stats", payload["quality_report"])

    def test_report_command_can_show_quality_report_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.run_cli("--base-dir", temp_dir, "run", str(EXAMPLE_TASK))
            result = self.run_cli("--base-dir", temp_dir, "report", "job-sample-001", "--kind", "quality")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["task"]["task_id"], "job-sample-001")
            self.assertNotIn("run_report", payload)
            self.assertEqual(payload["quality_report"]["task_id"], "job-sample-001")


if __name__ == "__main__":
    unittest.main()
