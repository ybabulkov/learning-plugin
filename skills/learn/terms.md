# Terms, tooltips and quizzes

Applies whenever learning mode is active.

Every term or piece of syntax the learner meets in an HTML explanation is tracked in
`<state>/terms.json`. A term is explained in a tooltip on at most 3 pages; after that
the learner is expected to know it, and it moves into spaced-repetition quizzes.
Never edit `terms.json` by hand: run `terms.py` (next to this file) so counts and
dates stay exact. `<state>` is the project's `.learning/` directory (or a legacy `.vibe-wise/` or `.sensible-vibes/`).

```
python3 <this directory>/terms.py --state <state> <command> ...
```

## What counts as a term

The project decides, in the Terms section of its approved `teaching.md`: explain
what its Explain list covers and nothing its Skip list covers. Never explain names
that only exist in the project's own sketch code.

**Default**, when there is no approved `teaching.md`: explain what is specific to
the project's language, platform and libraries, things a programmer at the
learner's level (see profile.md) wouldn't already know from elsewhere. Don't
explain general programming basics the learner already knows (keywords for
functions, variables, classes and loops; visibility modifiers; number literals) or
general knowledge from other fields (SQL, HTTP).

When the learner states a rule about which kinds of terms to explain or skip,
update the Terms section of `teaching.md` as SKILL.md describes for mid-project
changes. For single terms, run `exclude <ids...> --reason "<why>"` or
`include <ids...>`. `plan` never returns excluded terms and `due` never quizzes
them; `define` keeps a term excluded.

## When building any HTML explanation

1. **List the terms the page shows.** Include concepts, framework and library APIs,
   and syntax specific to the project's language, following "What counts as a term"
   above.
2. **Define new terms** with `define FILE` (or `-` for stdin), a JSON list of:
   - `id`: lowercase, digits and dashes; stable forever.
   - `term`: the real name as written in code or docs.
   - `kind`: short category, such as "Language syntax", "Framework class", "Library annotation".
   - `short`: one or two plain sentences: what it is, then what it does here if that helps.
     Use the real term; define any other term it relies on.
   - `match`: JavaScript regex sources, case-sensitive, matched in page text. Use
     `\\b` word boundaries for words; the longest match at a position wins, so
     `data class` beats `class`.
   - `prose`: `true` only for distinctive names that are safe to match in captions
     (class, library and concept names nobody uses as ordinary words). Keep it `false`
     for words that are also English (`is`, `in`, `with`, `when`).
   Updating a definition keeps its showing and quiz history.
3. **Plan the page**: `plan --page <page-id> <ids...>`. Use one stable `page-id` per
   explainer (the file's base name). The output's `terms` are the only ones that may
   get tooltips; `retired` terms (already shown on 3 pages) and `excluded` terms
   appear as plain text with no explanation anywhere on the page, including captions
   and glossaries.
4. **Embed** in the page, in this order, before `</body>` or at the end of the file:
   - `<script type="application/json" id="learn-terms">` with `{"page", "max_showings", "terms"}`
     from the plan output;
   - a `<script>` containing the full contents of `assets/term-tooltips.js`.
   Mark containers: `data-learn="code"` on code panels and code chips, `data-learn="prose"`
   on captions. Keep comments in `.cm` spans and strings in `.str` spans when the page
   highlights code, so the kit leaves them alone. Pages that swap content per step are
   re-scanned automatically.
5. **After publishing**, run `record-page --page <page-id> --title "<title>" --url <url> <ids...>`
   with the planned ids. Re-recording the same page never counts twice.
6. If the output says `"quiz_suggested": true` and the Quizzes section of the
   approved `teaching.md` says After explainer pages (or there is no approved
   `teaching.md`), run a quiz after presenting the page (see Quizzes below). Terms
   first shown today are never due, so this can't quiz what the page just explained.

## Quizzes

**When:** as the Quizzes section of the approved `teaching.md` says.
- Start of each session: when the session-start context reports due terms, run the
  quiz in the first reply, before starting new work, unless the learner asks to skip.
- After explainer pages: when `record-page` reports `"quiz_suggested": true`.
- Only when I ask, or Never: don't start quizzes yourself.
- Without an approved `teaching.md`: both Start of each session and After explainer pages.
- Whatever the setting, quiz whenever the learner asks ("quiz me").

Don't interrupt a step that is waiting for the learner's reasoning; finish that
exchange first. If the learner skips, don't ask again in the same session.

**How:** the question format follows the Questions section of `teaching.md` (Mixed
when there is none).
1. `due --limit 4` (`--limit 2` for Open-ended). If nothing is due, say so in one
   line and move on.
2. Multiple-choice questions go in one AskUserQuestion call, one per term: all due
   terms for Multiple choice, up to 3 for Mixed, none for Open-ended. Ask "What does
   `<term>` do?" with 3–4 options. Write the correct option fresh from the
   definition; take wrong options from other terms' meanings or common
   misconceptions, of similar length and tone. Put the correct option in a varied
   position. Never mark any option "(Recommended)".
3. Open-ended questions go in chat, one at a time: "In your own words, …". Ask about
   every due term for Open-ended, and about the remaining due term (or the one most
   missed) for Mixed. Wait for each answer.
4. Feedback: for each question, right or wrong, plus the correct answer in one
   sentence. For the open-ended one, say what was right and what was missing.
   Count it right only if the core idea is correct.
5. Record each answer with `result <id> right|wrong`, then `quiz-done`.
6. Add a short line to the `## Term quiz` topic in progress.md: date, terms right,
   terms missed (missed ones also go under Needs reinforcement).

**Schedule** (handled by `terms.py`): a term becomes due the day after it was first
shown. A right answer moves it up a box: next quiz in 1, 3, 7, 21, then 60 days.
A wrong answer sends it back to 1 day.
