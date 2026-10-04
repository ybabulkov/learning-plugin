"""Term registry: showing limits, quiz scheduling, CLI, and the session-start quiz note."""

import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/learn/terms.py"
sys.path.insert(0, str(ROOT / "skills/learn"))
import terms  # noqa: E402

D0 = dt.date(2026, 10, 4)


def definitions(*ids):
    return [{"id": i, "term": i.title(), "kind": "Test", "short": f"About {i}.",
             "match": [rf"\b{i}\b"], "prose": False} for i in ids]


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.data = terms.empty()
        terms.define(self.data, definitions("alpha", "beta", "gamma"))

    def test_term_gets_tooltips_on_at_most_three_pages(self):
        for n, page in enumerate(["p1", "p2", "p3"], start=1):
            planned = terms.plan(self.data, page, ["alpha"])
            self.assertEqual(planned["terms"]["alpha"]["nth"], n)
            terms.record_page(self.data, page, ["alpha"], D0)
        planned = terms.plan(self.data, "p4", ["alpha", "beta", "nope"])
        self.assertEqual(planned["retired"], ["alpha"])
        self.assertEqual(list(planned["terms"]), ["beta"])
        self.assertEqual(planned["unknown"], ["nope"])
        out = terms.record_page(self.data, "p4", ["alpha"], D0)
        self.assertEqual(out["retired"], ["alpha"])
        self.assertEqual(len(self.data["terms"]["alpha"]["shown_in"]), 3)

    def test_republishing_a_page_never_counts_twice(self):
        terms.record_page(self.data, "p1", ["alpha"], D0)
        terms.record_page(self.data, "p1", ["alpha", "beta"], D0)
        self.assertEqual(self.data["terms"]["alpha"]["shown_in"], ["p1"])
        self.assertEqual(self.data["pages_since_quiz"], 1)
        terms.record_page(self.data, "p2", ["alpha"], D0)
        terms.record_page(self.data, "p3", ["alpha"], D0)
        # The page that already showed it keeps its tooltip when republished.
        self.assertEqual(terms.plan(self.data, "p1", ["alpha"])["terms"]["alpha"]["nth"], 1)

    def test_redefining_keeps_history(self):
        terms.record_page(self.data, "p1", ["alpha"], D0)
        terms.define(self.data, [{"id": "alpha", "term": "Alpha", "kind": "Test", "short": "New text."}])
        self.assertEqual(self.data["terms"]["alpha"]["shown_in"], ["p1"])
        self.assertEqual(self.data["terms"]["alpha"]["short"], "New text.")

    def test_never_quizzed_on_the_day_first_shown(self):
        terms.record_page(self.data, "p1", ["alpha", "beta"], D0)
        self.assertEqual(terms.due(self.data, D0), [])
        due = terms.due(self.data, D0 + dt.timedelta(days=1))
        self.assertEqual({d["id"] for d in due}, {"alpha", "beta"})
        self.assertNotIn("gamma", {d["id"] for d in due})

    def test_leitner_intervals(self):
        terms.record_page(self.data, "p1", ["alpha"], D0)
        day = D0 + dt.timedelta(days=1)
        expected = [1, 3, 7, 21, 60, 60]
        for gap in expected:
            out = terms.result(self.data, "alpha", "right", day)
            self.assertEqual(dt.date.fromisoformat(out["next_due"]) - day, dt.timedelta(days=gap))
            day = dt.date.fromisoformat(out["next_due"])
        out = terms.result(self.data, "alpha", "wrong", day)
        self.assertEqual(out["box"], 1)
        self.assertEqual(dt.date.fromisoformat(out["next_due"]) - day, dt.timedelta(days=1))
        self.assertEqual(self.data["terms"]["alpha"]["quiz"]["history"][-1]["result"], "wrong")

    def test_quiz_suggested_after_two_pages_only_when_something_is_due(self):
        out = terms.record_page(self.data, "p1", ["alpha"], D0)
        self.assertFalse(out["quiz_suggested"])
        out = terms.record_page(self.data, "p2", ["beta"], D0)
        self.assertFalse(out["quiz_suggested"])  # nothing due on day one
        later = D0 + dt.timedelta(days=2)
        out = terms.record_page(self.data, "p3", ["gamma"], later)
        self.assertTrue(out["quiz_suggested"])
        terms.quiz_done(self.data, later)
        out = terms.record_page(self.data, "p4", ["gamma"], later)
        self.assertFalse(out["quiz_suggested"])

    def test_excluded_terms_are_never_explained_counted_or_quizzed(self):
        terms.record_page(self.data, "p1", ["beta", "alpha"], D0)
        terms.set_excluded(self.data, ["beta"], True, "general programming")
        planned = terms.plan(self.data, "p2", ["beta", "alpha"])
        self.assertEqual(planned["excluded"], ["beta"])
        self.assertEqual(list(planned["terms"]), ["alpha"])
        out = terms.record_page(self.data, "p2", ["beta", "alpha"], D0)
        self.assertEqual(out["excluded"], ["beta"])
        self.assertEqual(self.data["terms"]["beta"]["shown_in"], ["p1"])
        later = D0 + dt.timedelta(days=5)
        self.assertEqual([d["id"] for d in terms.due(self.data, later)], ["alpha"])
        # Redefining keeps the exclusion; include brings the term back.
        terms.define(self.data, definitions("beta"))
        self.assertTrue(self.data["terms"]["beta"]["excluded"])
        terms.set_excluded(self.data, ["beta"], False)
        self.assertIn("beta", [d["id"] for d in terms.due(self.data, later)])
        self.assertEqual(terms.status(self.data, later)["excluded"], 0)
        with self.assertRaises(terms.RegistryError):
            terms.set_excluded(self.data, ["nope"], True)

    def test_bad_definitions_are_rejected(self):
        for bad in ([{"id": "Bad Id", "term": "x", "kind": "k", "short": "s"}],
                    [{"id": "x", "term": "x", "kind": "k", "short": ""}],
                    [{"id": "x", "term": "x", "kind": "k", "short": "s", "match": ["("]}],
                    {"id": "x"}):
            with self.assertRaises(terms.RegistryError):
                terms.define(terms.empty(), bad)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="learning-terms-")
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name) / ".learning"
        self.state.mkdir()

    def cli(self, *args, stdin=None, today="2026-10-04"):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--state", str(self.state), "--today", today, *args],
            input=stdin, text=True, capture_output=True, timeout=10,
        )
        return result.returncode, json.loads(result.stdout)

    def test_end_to_end(self):
        code, out = self.cli("define", "-", stdin=json.dumps(definitions("alpha")))
        self.assertEqual((code, out), (0, {"defined": ["alpha"]}))
        code, out = self.cli("plan", "--page", "p1", "alpha")
        self.assertEqual(out["terms"]["alpha"]["nth"], 1)
        code, out = self.cli("record-page", "--page", "p1", "--title", "Page", "alpha")
        self.assertEqual(out["recorded"], ["alpha"])
        code, out = self.cli("due", today="2026-10-05")
        self.assertEqual([d["id"] for d in out], ["alpha"])
        code, out = self.cli("result", "alpha", "right", today="2026-10-05")
        self.assertEqual(out["next_due"], "2026-10-06")
        code, out = self.cli("quiz-done", today="2026-10-05")
        code, out = self.cli("status", today="2026-10-05")
        self.assertEqual(out["last_quiz"], "2026-10-05")
        self.assertEqual(out["due"], 0)

    def test_errors_are_json_and_nonzero(self):
        code, out = self.cli("result", "missing", "right")
        self.assertEqual(code, 1)
        self.assertIn("unknown term", out["error"])

    def test_symlinked_registry_is_refused(self):
        target = Path(self.temp.name) / "elsewhere.json"
        target.write_text(json.dumps(terms.empty()))
        (self.state / "terms.json").symlink_to(target)
        code, out = self.cli("status")
        self.assertEqual(code, 1)
        self.assertIn("symlink", out["error"])


class SessionStartQuizTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="learning-hook-")
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name).resolve() / "project"
        self.project.mkdir()
        self.state = self.project / ".learning"
        self.state.mkdir()
        (self.state / "profile.md").write_text("# Learner Profile\nLearning mode: active\n")

    def context(self):
        command = json.loads((ROOT / "hooks/hooks.json").read_text())["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        result = subprocess.run(
            command, shell=True, text=True, capture_output=True, timeout=5,
            input=json.dumps({"hook_event_name": "SessionStart", "source": "startup", "cwd": str(self.project)}),
            env={"PATH": os.pathsep.join((str(Path(sys.executable).parent), os.defpath)),
                 "CLAUDE_PLUGIN_ROOT": str(ROOT),
                 "XDG_CONFIG_HOME": str(Path(self.temp.name) / "config")},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]

    def registry(self, last_quiz=None):
        data = terms.empty()
        terms.define(data, definitions("alpha"))
        terms.record_page(data, "p1", ["alpha"], dt.date(2000, 1, 1))
        data["last_quiz"] = last_quiz
        terms.save(self.state / "terms.json", data)

    def test_due_terms_add_a_quiz_note_without_term_content(self):
        self.registry()
        context = self.context()
        self.assertIn("Term quiz: 1 term(s)", context)
        self.assertIn(str(ROOT / "skills/learn/terms.md"), context)
        self.assertIn("Follow the Quizzes section of an approved teaching.md", context)
        self.assertNotIn("About alpha", context)

    def test_no_note_when_already_quizzed_today_or_no_registry(self):
        self.assertNotIn("Term quiz", self.context())
        self.registry(last_quiz=dt.date.today().isoformat())
        self.assertNotIn("Term quiz", self.context())

    def test_damaged_registry_does_not_break_the_hook(self):
        (self.state / "terms.json").write_text("{not json")
        context = self.context()
        self.assertIn("Learning mode is active", context)
        self.assertNotIn("Term quiz", context)


if __name__ == "__main__":
    unittest.main()
