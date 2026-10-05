"""Persistent project switches, note preservation, and Off-mode isolation."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/learn"))
import mode
sys.path.insert(0, str(ROOT / "hooks"))
import session_start


class ModeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="learning-mode-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / "project with spaces"
        self.project.mkdir()
        (self.project / ".git").mkdir()

    def notes(self, name=".learning"):
        state = self.project / name
        state.mkdir()
        (state / "profile.md").write_bytes(
            b"# Profile\r\nLearning mode: active\r\nOnboarding: complete\r\nExperience: Intermediate\r\n")
        for name in ("teaching.md", "progress.md", "project-map.md", "terms.json"):
            (state / name).write_text("Saved " + name)
        return state

    def snapshot(self, state):
        return {p.name: p.read_bytes() for p in state.iterdir()}

    def test_status_is_read_only_and_fresh_project_is_off(self):
        before = list(self.project.iterdir())
        self.assertEqual(mode.switch(self.project, "status"), {"mode": "off", "state": None})
        self.assertEqual(before, list(self.project.iterdir()))

    def test_switch_preserves_notes_and_profile_bytes_except_mode(self):
        state = self.notes()
        before = self.snapshot(state)
        self.assertEqual(mode.switch(self.project, "off")["mode"], "off")
        after = self.snapshot(state)
        expected = dict(before)
        expected["profile.md"] = before["profile.md"].replace(b"active", b"off")
        self.assertEqual(after, expected)
        self.assertEqual(mode.switch(self.project, "status")["mode"], "off")
        mode.switch(self.project, "on")
        self.assertEqual(self.snapshot(state), before)
        self.assertEqual(mode.switch(self.project, "status")["mode"], "on")

    def test_fresh_off_creates_only_a_disabled_profile_at_git_root(self):
        nested = self.project / "src" / "services"
        nested.mkdir(parents=True)
        result = mode.switch(nested, "off")
        state = self.project / ".learning"
        self.assertEqual(result["state"], str(state))
        self.assertEqual([p.name for p in state.iterdir()], ["profile.md"])
        self.assertFalse(mode.profile_is_active(state / "profile.md"))
        self.assertIn("Onboarding: incomplete", (state / "profile.md").read_text())
        mode.switch(nested, "on")
        self.assertTrue(mode.profile_is_active(state / "profile.md"))

    def test_both_legacy_names_switch_in_place(self):
        for name in (".vibe-wise", ".sensible-vibes"):
            with self.subTest(name=name):
                state = self.notes(name)
                nested = self.project / "src"
                nested.mkdir(exist_ok=True)
                self.assertEqual(mode.switch(nested, "off")["state"], str(state))
                self.assertFalse((self.project / ".learning").exists())
                mode.switch(nested, "on")
                for p in state.iterdir():
                    p.unlink()
                state.rmdir()

    def test_nested_repository_and_worktree_do_not_change_parent_mode(self):
        state = self.notes()
        before = self.snapshot(state)
        for name, git_file in (("nested", False), ("worktree", True)):
            child = self.project / name
            child.mkdir()
            if git_file:
                (child / ".git").write_text("gitdir: /other/repo/.git/worktrees/test")
            else:
                (child / ".git").mkdir()
            mode.switch(child, "off")
            self.assertEqual(self.snapshot(state), before)
            self.assertEqual(mode.switch(child, "status")["mode"], "off")

    def test_legacy_paused_and_duplicate_off_markers_are_off(self):
        state = self.notes()
        profile = state / "profile.md"
        for marker in ("paused", "off", "OFF", "disabled", "unknown"):
            with self.subTest(marker=marker):
                profile.write_text("Learning mode: active\n" + "History\n" * 1000 +
                                   "Learning mode: " + marker + "\n")
                self.assertEqual(mode.switch(self.project, "status")["mode"], "off")
                mode.switch(self.project, "on")
                self.assertTrue(mode.profile_is_active(profile))

    def test_symlinked_notes_and_profile_are_refused_without_fallback(self):
        state = self.notes(".vibe-wise")
        linked = self.project / ".learning"
        linked.symlink_to(self.root / "missing", target_is_directory=True)
        with self.assertRaises(ValueError):
            mode.switch(self.project, "off")
        self.assertTrue(mode.profile_is_active(state / "profile.md"))
        linked.unlink()
        profile = state / "profile.md"
        outside = self.root / "outside.md"
        outside.write_bytes(profile.read_bytes())
        profile.unlink()
        profile.symlink_to(outside)
        before = outside.read_bytes()
        with self.assertRaises(ValueError):
            mode.switch(self.project, "on")
        self.assertEqual(outside.read_bytes(), before)

    def test_failed_replace_keeps_profile_and_removes_temp_file(self):
        state = self.notes()
        before = self.snapshot(state)
        with patch.object(mode.os, "replace", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                mode.switch(self.project, "off")
        self.assertEqual(self.snapshot(state), before)

    def test_off_hook_never_checks_teaching_quizzes_or_emits_context(self):
        state = self.notes()
        mode.switch(self.project, "off")
        before = self.snapshot(state)
        with patch.object(session_start, "teaching_status", side_effect=AssertionError("read teaching")), \
                patch.object(session_start, "quiz_due", side_effect=AssertionError("read terms")):
            for source in ("startup", "resume", "clear", "compact", "fork"):
                self.assertIsNone(session_start.restore({
                    "hook_event_name": "SessionStart", "cwd": str(self.project), "source": source}))
        self.assertEqual(self.snapshot(state), before)

    def test_cli_handles_paths_as_data_and_errors_as_json(self):
        env = {"PATH": os.defpath}
        script = ROOT / "skills/learn/mode.py"
        for command in ("off", "on", "status"):
            result = subprocess.run([sys.executable, "-B", str(script), command,
                                     "--cwd", str(self.project)], capture_output=True, text=True, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(json.loads(result.stdout)["mode"], ("on", "off"))
        result = subprocess.run([sys.executable, "-B", str(script), "off", "--cwd", "relative"],
                                capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 1)
        self.assertIn("error", json.loads(result.stdout))
        self.assertEqual(result.stderr, "")

    def test_terms_commands_are_blocked_before_loading_or_mutating_registry(self):
        state = self.notes()
        mode.switch(self.project, "off")
        before = self.snapshot(state)
        script = ROOT / "skills/learn/terms.py"
        commands = (("status",), ("due",), ("plan", "--page", "p", "alpha"),
                    ("record-page", "--page", "p", "alpha"), ("define", "missing.json"),
                    ("result", "alpha", "right"), ("quiz-done",),
                    ("include", "alpha"), ("exclude", "alpha"))
        for command in commands:
            with self.subTest(command=command):
                result = subprocess.run([sys.executable, "-B", str(script), "--state", str(state),
                                         *command], capture_output=True, text=True, env={"PATH": os.defpath})
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("Learning is off", json.loads(result.stdout)["error"])
                self.assertEqual(result.stderr, "")
                self.assertEqual(self.snapshot(state), before)


if __name__ == "__main__":
    unittest.main()
