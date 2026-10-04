"""Structure of the instruction files Claude follows: templates, presets, core rules."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
LEARN = ROOT / "skills/learn"
HEADINGS = ["What I'm learning", "Learning loop", "Explaining", "Pace", "Questions",
            "Who writes the code", "When I'm stuck", "Terms", "Quizzes"]
STEP = re.compile(r"^(\d+)\. (.+?) \((learner|Claude)\)( \[gate\])?: (.+)$")
CODE_WORK = re.compile(r"\b(write|writes|writing|code|implement\w*|change[sd]?)\b", re.I)
PRESETS = ("Design first", "Practice first", "Read first")


def read(name):
    return (LEARN / name).read_text(encoding="utf-8")


def template(name):
    """The fenced Markdown block under '## <name>' in state-templates.md."""
    match = re.search(rf"^## {re.escape(name)}\n.*?^```markdown\n(.*?)^```$",
                      read("state-templates.md"), re.M | re.S)
    if not match:
        raise AssertionError(f"no template for {name}")
    return match.group(1)


def preset(name):
    """Numbered steps under '### <name>' in state-templates.md."""
    match = re.search(rf"^### {re.escape(name)}\n(.*?)(?=^##|\Z)",
                      read("state-templates.md"), re.M | re.S)
    if not match:
        raise AssertionError(f"no preset {name}")
    steps = []
    for line in match.group(1).splitlines():
        if not re.match(r"\d+\.", line):
            continue
        step = STEP.match(line)
        if not step:
            raise AssertionError(f"{name}: malformed step line: {line}")
        steps.append(step)
    return steps


class TemplateTests(unittest.TestCase):
    def test_teaching_template_has_fixed_headings_in_order(self):
        body = template("teaching.md")
        self.assertTrue(body.startswith("# How to teach me in this project\n"))
        self.assertEqual(re.findall(r"^## (.+)$", body, re.M), HEADINGS)

    def test_presets_follow_the_loop_rules(self):
        for name in PRESETS:
            with self.subTest(preset=name):
                steps = preset(name)
                self.assertTrue(3 <= len(steps) <= 6, len(steps))
                self.assertEqual([int(s.group(1)) for s in steps],
                                 list(range(1, len(steps) + 1)))
                names = [s.group(2) for s in steps]
                self.assertEqual(len(names), len(set(names)))
                gates = [i for i, s in enumerate(steps) if s.group(4)]
                self.assertTrue(gates, "every preset needs a [gate] step")
                for i, s in enumerate(steps):
                    if s.group(3) == "Claude" and CODE_WORK.search(s.group(2) + " " + s.group(5)):
                        self.assertGreater(i, gates[0], f"{s.group(2)} before the gate")

    def test_profile_template_no_longer_holds_preferences(self):
        body = template("profile.md")
        self.assertIn("Learning mode: active\nOnboarding: complete\n", body)
        for gone in ("## Goals", "## Preferences", "Checkpoint frequency"):
            self.assertNotIn(gone, body)

    def test_progress_notes_use_pending_step(self):
        text = read("state-templates.md")
        self.assertIn("## Pending step", text)
        self.assertNotIn("## Pending decision", text)

    def test_design_first_notes_name_the_confirmations(self):
        match = re.search(r"^### Design first\n(.*?)(?=^###|\Z)",
                          read("state-templates.md"), re.M | re.S)
        self.assertTrue(match, "no Design first preset")
        notes = " ".join(match.group(1).split())
        self.assertIn("Confirm and continue", notes)
        self.assertIn("Implement this step", notes)


class CoreTests(unittest.TestCase):
    def test_core_rules_cover_every_loop_invariant(self):
        text = read("core.md")
        for heading in ("Who decides", "Approval gate", "Report", "Pending step",
                        "Evidence", "Learner control", "Notes format", "Safety",
                        "Presentation"):
            with self.subTest(heading=heading):
                self.assertRegex(text, rf"(?m)^## {heading}$")
        self.assertIn("this file wins", text)

    def test_core_keeps_teaching_behaviors(self):
        raw = read("core.md")
        text = " ".join(raw.split())
        for phrase in ("Proposed additions", "Detail / Proposal / Why it matters",
                       "Reports need no question", "a brief answer as being stuck"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        self.assertRegex(raw, r"(?m)^## Explanations$")


QUESTIONS = [
    "What are we doing?",
    "What do you want to learn in this project?",
    "How do you want to learn in this project?",
    "How should I explain new things?",
    "How often should I stop you?",
    "How should I ask you questions?",
    "Who writes the code?",
    "When you're stuck, what helps most?",
    "Which terms should I explain?",
    "When should I quiz you?",
]
ROUNDS = ["Project", "You", "Learning loop", "Style", "Support", "Review"]


class SkillTests(unittest.TestCase):
    def test_setup_has_six_rounds_and_every_question(self):
        text = read("SKILL.md")
        for number, name in enumerate(ROUNDS, 1):
            self.assertIn(f"### Round {number}: {name}", text)
        for question in QUESTIONS:
            with self.subTest(question=question):
                self.assertIn(question, text)

    def test_skill_uses_the_approval_helper(self):
        text = read("SKILL.md")
        self.assertIn("teaching.py' approve --state", text)
        self.assertIn("teaching.py' check --state", text)

    def test_setup_keeps_notes_and_quiz_setting(self):
        skill = " ".join(read("SKILL.md").split())
        self.assertIn("never replace them with a template", skill)
        step = re.search(r"^6\. If the output says.*?(?=\n\n)", read("terms.md"), re.M | re.S)
        self.assertTrue(step, "terms.md step 6 not found")
        step = " ".join(step.group(0).split())
        self.assertIn("quiz_suggested", step)
        self.assertIn("After explainer pages", step)

    def test_relative_links_in_skills_resolve(self):
        for guide in (ROOT / "skills").rglob("*.md"):
            for target in re.findall(r"\]\(([^)#:]+\.md)\)", guide.read_text(encoding="utf-8")):
                with self.subTest(guide=str(guide.relative_to(ROOT)), target=target):
                    self.assertTrue((guide.parent / target).is_file())

    def test_removed_guides_are_gone_and_unreferenced(self):
        for gone in ("behavior.md", "onboarding.md"):
            self.assertFalse((LEARN / gone).exists())
        paths = [*(ROOT / "skills").rglob("*.md"), *(ROOT / "skills").rglob("*.py"),
                 *(ROOT / "hooks").rglob("*.py"), ROOT / "README.md"]
        for path in paths:
            text = path.read_text(encoding="utf-8")
            for gone in ("behavior.md", "onboarding.md"):
                with self.subTest(path=str(path.relative_to(ROOT)), gone=gone):
                    self.assertNotIn(gone, text)
        # Term scope now lives in teaching.md; terms.md must not send Claude elsewhere.
        self.assertNotIn("term-scope.md", read("terms.md"))


if __name__ == "__main__":
    unittest.main()
