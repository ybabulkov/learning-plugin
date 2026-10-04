"""teaching.md approvals: a cloned repository can bring a teaching.md, never your approval."""

import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/learn/teaching.py"
sys.path.insert(0, str(ROOT / "skills/learn"))
import teaching  # noqa: E402

TEXT = "# How to teach me in this project\n## Learning loop\nPractice first\n"


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="learning-teaching-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / "project"
        self.state = self.project / ".learning"
        self.state.mkdir(parents=True)
        self.config = self.root / "config"
        self.approvals = self.config / "learning" / "approved.json"
        env = patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.config)})
        env.start()
        self.addCleanup(env.stop)

    def write(self, text=TEXT):
        (self.state / "teaching.md").write_text(text, encoding="utf-8")

    def test_missing_without_teaching_file(self):
        self.assertEqual(teaching.check(self.state), "missing")

    def test_unapproved_until_approved(self):
        self.write()
        self.assertEqual(teaching.check(self.state), "unapproved")
        result = teaching.approve(self.state)
        self.assertEqual(result["approved"], str(self.state / "teaching.md"))
        self.assertEqual(teaching.check(self.state), "approved")

    def test_any_byte_change_needs_a_new_approval(self):
        self.write()
        teaching.approve(self.state)
        self.write(TEXT + "\n")
        self.assertEqual(teaching.check(self.state), "unapproved")

    def test_approve_keeps_other_projects_and_leaves_no_temp_files(self):
        self.approvals.parent.mkdir(parents=True)
        self.approvals.write_text(json.dumps({"/elsewhere/.learning/teaching.md": "abc"}))
        self.write()
        teaching.approve(self.state)
        data = json.loads(self.approvals.read_text())
        self.assertEqual(data["/elsewhere/.learning/teaching.md"], "abc")
        self.assertEqual(data[str(self.state / "teaching.md")],
                         teaching.fingerprint(self.state / "teaching.md"))
        self.assertEqual([p.name for p in self.approvals.parent.iterdir()], ["approved.json"])

    def test_default_location_is_the_config_folder(self):
        with patch.dict(os.environ, {}, clear=True), \
                patch.object(Path, "home", return_value=self.root):
            self.assertEqual(teaching.approvals_path(),
                             self.root / ".config" / "learning" / "approved.json")

    def test_relative_xdg_config_home_is_ignored(self):
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "relative"}), \
                patch.object(Path, "home", return_value=self.root):
            self.assertEqual(teaching.approvals_path(),
                             self.root / ".config" / "learning" / "approved.json")

    def test_symlinked_teaching_is_untrusted_and_refused(self):
        self.write()
        teaching.approve(self.state)
        real = self.root / "real-teaching.md"
        real.write_text(TEXT)
        (self.state / "teaching.md").unlink()
        (self.state / "teaching.md").symlink_to(real)
        self.assertEqual(teaching.check(self.state), "unapproved")
        with self.assertRaises(teaching.ApprovalError):
            teaching.approve(self.state)

    def test_symlinked_state_directory_is_refused(self):
        self.write()
        linked = self.root / "linked-state"
        linked.symlink_to(self.state, target_is_directory=True)
        with self.assertRaises(teaching.ApprovalError):
            teaching.approve(linked)

    def test_symlinked_approvals_file_is_refused_and_untouched(self):
        self.write()
        outside = self.root / "outside.json"
        outside.write_text("{}")
        self.approvals.parent.mkdir(parents=True)
        self.approvals.symlink_to(outside)
        with self.assertRaises(teaching.ApprovalError):
            teaching.approve(self.state)
        self.assertEqual(outside.read_text(), "{}")
        self.assertEqual(teaching.check(self.state), "unapproved")

    def test_unreadable_approvals_mean_unapproved_and_approve_rewrites_them(self):
        self.write()
        self.approvals.parent.mkdir(parents=True)
        for broken in ("{not json", "[]", ""):
            with self.subTest(broken=broken):
                self.approvals.write_text(broken)
                self.assertEqual(teaching.check(self.state), "unapproved")
        teaching.approve(self.state)
        self.assertEqual(list(json.loads(self.approvals.read_text())),
                         [str(self.state / "teaching.md")])

    def test_approvals_path_that_is_a_folder(self):
        self.write()
        self.approvals.mkdir(parents=True)
        self.assertEqual(teaching.check(self.state), "unapproved")
        with self.assertRaises(teaching.ApprovalError):
            teaching.approve(self.state)

    def test_no_home_folder_means_unapproved(self):
        self.write()
        with patch.dict(os.environ, {}, clear=True), \
                patch.object(Path, "home", side_effect=RuntimeError("no home")), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(teaching.check(self.state), "unapproved")
            self.assertEqual(teaching.main(["approve", "--state", str(self.state)]), 1)
        self.assertIn("error", json.loads(out.getvalue()))

    def test_same_project_through_a_symlinked_parent(self):
        self.write()
        alias = self.root / "alias"
        alias.symlink_to(self.project, target_is_directory=True)
        teaching.approve(alias / ".learning")
        self.assertEqual(teaching.check(self.state), "approved")

    def test_moved_project_asks_again(self):
        self.write()
        teaching.approve(self.state)
        moved = self.root / "moved"
        self.project.rename(moved)
        self.assertEqual(teaching.check(moved / ".learning"), "unapproved")


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="learning-teaching-cli-")
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name).resolve()
        self.state = root / "project" / ".learning"
        self.state.mkdir(parents=True)
        self.config = root / "config"

    def cli(self, *args):
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), *args, "--state", str(self.state)],
            capture_output=True, text=True,
            env={"PATH": os.defpath, "XDG_CONFIG_HOME": str(self.config)},
        )
        return result.returncode, json.loads(result.stdout)

    def test_check_and_approve_print_json(self):
        self.assertEqual(self.cli("check"), (0, {"status": "missing"}))
        (self.state / "teaching.md").write_text(TEXT)
        self.assertEqual(self.cli("check"), (0, {"status": "unapproved"}))
        code, out = self.cli("approve")
        self.assertEqual(code, 0)
        self.assertEqual(out["approved"], str(self.state / "teaching.md"))
        self.assertEqual(self.cli("check"), (0, {"status": "approved"}))

    def test_errors_are_json_not_tracebacks(self):
        code, out = self.cli("approve")
        self.assertEqual(code, 1)
        self.assertIn("teaching.md", out["error"])


if __name__ == "__main__":
    unittest.main()
