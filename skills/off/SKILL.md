---
name: off
description: Completely turn off learning in this project and continue normal work. Keeps saved learning notes for later.
disable-model-invocation: true
---

# Turn learning off

Run only when explicitly invoked. Use the current project's absolute working
directory, safely quoted:

```sh
python3 "${CLAUDE_PLUGIN_ROOT}/skills/learn/mode.py" off --cwd "<absolute project directory>"
```

On an error, report it and stop; don't claim the switch succeeded.
On success, say "Learning is off for this project" and continue the user's task
as normal development. The switch takes effect immediately in this conversation
and persists through restarts, compaction, resume and fork.

Stop applying all previously loaded learning instructions, including core.md,
teaching.md, learning checkpoints, implementation approval gates, teaching style,
learner reasoning questions, quizzes, term tooltips and progress tracking.
Don't read or update learning notes, restore pending learning steps, record term
showings, or add teaching callouts. Explain things normally when asked. Follow the
user's task, ordinary project instructions and tool permissions.

Keep saved learning notes intact. Only an explicit `/learning:learn`,
`/learning:learn on`, or request to turn learning on reactivates it. Ordinary build
requests, explanations and quizzes don't reactivate it. Don't read the Learn
guide or other teaching files to turn learning off.
