# Local state templates

Create these files in the state directory chosen by SKILL.md: `.learning/`, or an
existing legacy `.vibe-wise/` or `.sensible-vibes/` when resuming. Replace bracketed
values with actual evidence or "Not specified". Keep the two status lines
unformatted and near the top of `profile.md`; the session-start hook reads them.
Never replace existing notes with a fresh template.

`terms.json` is created and changed only by `terms.py` (see terms.md); never write
it from a template or by hand. `teaching.md` is written at the end of setup and
approved with `teaching.py approve`.

## profile.md

```markdown
# Learner Profile

Learning mode: active
Onboarding: complete

## Project
Situation: [New / Existing / Known]
Building: [project purpose]
Codebase familiarity: [New / A little / Know it well, or Not specified]
Learning scope: [Whole system / Parts we touch / A mix, or Not specified]

## Experience
Overall programming: [Beginner / Intermediate / Advanced, or Not specified]
Stack familiarity: [per-technology levels if given; otherwise Not specified]

## Strong Concepts
No demonstrated understanding recorded yet.

## Developing Concepts
None recorded yet.

## Revisit
None recorded yet.
```

While setup is unfinished, use `Onboarding: incomplete` and keep a
`## Setup answers` section with one line per answered question (a custom loop may
take several lines), plus a `Remaining setup:` line naming the unanswered rounds.
Remove both when setup is saved.

## progress.md

```markdown
# Learning Progress

No learning events recorded yet.
```

As learning occurs, add a `## Topic` with concise bullets under Introduced,
Demonstrated understanding, and Needs reinforcement. Record reasoning evidence,
not quotations of a whole exchange. Product preferences establish requirements;
they aren't evidence of engineering understanding. Keep learner-proposed reasoning
distinct from concepts Claude explained. Consolidate repeated entries. Keep each
topic independently readable so it can be loaded without the whole file.
While waiting on the learner, keep a short `## Pending step` section with the step
name from the loop, the proposal, and what reply is awaited. Remove it once
resolved. Record confirmed choices in the map without claiming they are
implemented. Keep any proposed coding scope explicit. Confirmation covers only the
proposal presented. Don't append unmentioned fields, behaviors, rejected
alternatives, or reasons to the chosen design. Mark unresolved details unknown and
Claude's suggestions proposed; never attribute them to the learner.

## project-map.md

```markdown
# Project Map

## Purpose
[What this software does.]

## Requirements
[User needs and constraints. These do not automatically settle technical choices.]

## Components
[Components, responsibilities, and supporting file paths.]

## Main Flow
[Compact text diagram with labeled arrows. Mark unknowns and distinguish proposed,
chosen, and implemented components. Reflect the learner's model refined together,
or verified existing code; don't fill missing relationships with assumed designs.]

## Data and Trust Boundaries
[Storage, ownership, auth, external services; unknown when unverified.]

## Build and Deployment
[Commands and configuration paths verified in the repository.]

## Unknowns
[Unresolved technical choices and what needs inspection, including relevant stack,
storage location/model, data structures, interfaces, and deployment choices.]
```

## teaching.md

```markdown
# How to teach me in this project
Written at setup on [YYYY-MM-DD] from your answers. Edit freely; you'll be asked
to approve changes before they're followed.

## What I'm learning
[The subject, the project used to learn it, and relevant background, in the
learner's words.]

## Learning loop
[Preset name, or Custom]
[Numbered steps and the notes under them, copied from the chosen preset below, or the custom loop]

## Explaining
[Example first / Concept first / Diagram first / Mix, plus any detail given]

## Pace
[Light: stop only at major decisions / Normal: stop at meaningful decisions /
Frequent: also stop at smaller steps]

## Questions
[Open-ended / Multiple choice / Mixed]

## Who writes the code
[Claude / A mix, with the split described / Mostly me]

## When I'm stuck
[A hint / A smaller question / Explain the concept / Show options]

## Terms
Explain: [kinds of terms, with examples]
Skip: [kinds of terms, with examples]

## Quizzes
[Start of each session / After explainer pages / Only when I ask / Never]
```

Values filled in because the learner skipped setup end with
`(default, not chosen)`.

## Learning loops

Each step is written `N. <Step name> (<learner|Claude>)[ [gate]]: <what happens>`.
A loop has 3 to 6 steps with unique names. If any step has Claude write project
code, a `[gate]` step must come before it. Step names appear in callout headings
and in `## Pending step`.

### Design first
For architecture and system design.

1. Build checkpoint (learner): explain how you'd approach the problem. Claude asks follow-ups only to resolve meaningful gaps.
2. Design checkpoint (learner): confirm the design and its tradeoffs. This records the design; no code yet.
3. Implementation checkpoint (learner) [gate]: approve the specific code changes Claude describes.
4. Write code (Claude): make only the approved changes.
5. Implementation report (Claude): what changed, how it works and what was verified.

Repeat for each piece. Several Build checkpoints may lead to one confirmation. When
ready to code, the Implementation checkpoint also confirms the design; skip a
separate Design checkpoint. The Design checkpoint offers **Confirm and continue**
("This approach makes sense to me; move to the next piece.") next to **Discuss**
("Ask questions or clarify anything that doesn't make sense before deciding."). The
Implementation checkpoint offers **Implement this step** ("This approach makes
sense to me; write the code for this step.") next to **Discuss**.

### Practice first
For a new language or library.

1. Concept (Claude): explain the idea with a tiny example outside the project.
2. Exercise (learner): write a small snippet that uses it.
3. Review (Claude): say what works, what to fix and why.
4. Apply (learner) [gate]: write it into the project, or approve Claude writing a stated scope.

Repeat for each concept.

### Read first
For joining an existing codebase.

1. Point (Claude): show a real piece of the repository relevant to the task.
2. Explain (learner): say what it does in your own words.
3. Correct (Claude): confirm what's right and fill the gaps.
4. Change (learner) [gate]: plan a change and approve the code scope.

Repeat for each area.
