---
title: A Repo That Makes Claude Correct My English Instead of Writing It
published: true
description: 'claude-english-coach is a template repo: a CLAUDE.md that makes Claude point at your English mistakes without fixing them, plus Markdown files where every mistake and new word gets logged for quizzes.'
tags:
  - showdev
  - claude
  - english
  - learning
series: ShowDev
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/claude-english-coach/cover.png?v=e7ae9036'
id: 5038074
date: '2026-11-14T21:50:25Z'
---

I write issues and PRs in English most days, and Claude is open in the same terminal. Ask it to fix a sentence and it rewrites the whole paragraph. The text gets better. My English doesn't.

So I turned a repository into the opposite: Claude still reads everything I write, but it is told to point at the mistake and wait for me to fix it, then write the mistake down.

- Source: <https://github.com/0-draft/claude-english-coach>
- Use: **Use this template** on GitHub, clone your copy, run `claude` inside

## What's in it

```text
CLAUDE.md                 rules Claude follows in this repo
phrases.md                mistake → correction, with a count
vocab.md                  words you didn't know, with an example
journal/YYYY/MM-DD.md     what you wrote each day
tech/README.md            reusable phrases for issues, PRs, review replies
app/rounds.html           a drill app (below)
docs/research-ja.md       the research the rules are built on
```

The coach itself is just `CLAUDE.md`: nothing to install. `phrases.md` and `vocab.md` start as empty tables, `journal/` as an empty directory, and they fill up as you write.

The first line to edit is the native language, because feedback is given in it:

```markdown
Native language: **Japanese** (change this line to your own language)
```

## The loop

**1. Write something in English.** A chat message, a diary entry, a draft PR description.

**2. Claude answers the content first, then marks errors.** It says where the error is and what kind it is (`article`, `tense`, `preposition`...), and does not give the corrected sentence. You try again. Only if the second attempt is still wrong does it show the answer and the rule. From `CLAUDE.md`:

```markdown
- Prompt before you correct. Mark where each error is and what kind it is (for example `article`, `tense`), and let the user try to fix it. Give the corrected form and the rule only if their second attempt is still wrong. Prompts that make learners self-correct outperform simply recasting the sentence (Lyster & Saito 2010).
- Keep corrections minimal. Fix what is wrong or clearly unnatural; do not rewrite style or rephrase sentences that already work. LLMs tend to over-correct, and that hides which errors actually matter.
- Never write the user's text for them before they have tried. If they ask "how do I say X", ask for their attempt first.
```

If you write in your native language, it asks you to try English first.

**3. Claude logs it.** The exchange goes into `journal/YYYY/MM-DD.md`, split into what you fixed yourself and what needed the answer. Each mistake becomes a row in `phrases.md`:

```markdown
| Mistake | Correction | Category | Note | Count |
| --- | --- | --- | --- | --- |
| I will fix it until tomorrow. | I'll fix it by tomorrow. | preposition | deadline is "by" | 1 |
```

Making the same mistake again bumps `Count` instead of adding a row. New words go to `vocab.md`, always with an example sentence. At the end of the session Claude commits with `docs(journal): YYYY-MM-DD`, so `git log` is the study history.

**4. Pick a focus.** `phrases.md` has a `## Focus` section for one or two categories a week, chosen by the highest counts. Errors in those categories get full feedback. Everything else is mentioned only if it blocks understanding.

**5. Say `quiz`.** Claude asks five questions from `phrases.md` and `vocab.md`, weighted toward high counts and the focus categories, one at a time. They are production questions: a meaning or a sentence with a blank, and you type the English. No multiple choice.

## Why these rules

Each rule in `CLAUDE.md` names the paper it comes from, and `docs/research-ja.md` (Japanese) has the sources. The three that shaped the loop:

- Prompting learners to fix their own errors beat recasting the sentence for them (Lyster & Saito 2010).
- Students who had free access to GPT scored 17% lower than the control group once it was taken away (Bastani et al. 2025, a math RCT).
- ChatGPT tends to rewrite parts that were not wrong (Fang 2023), which hides the errors that matter.

## The drill app

The Markdown loop needs a session of writing. For short daily practice there is `app/rounds.html`: one HTML file, made to run as a Claude artifact. Opened in a plain browser it works too and saves to `localStorage`. The UI is in Japanese.

![English Rounds, opened outside claude.ai: today's minutes against a 45-minute plan, the three blocks Review, Listen and Speak, and a 66-day habit grid](./assets/claude-english-coach/rounds.png?v=69045367)

- **Review**: spaced repetition with [ts-fsrs](https://github.com/open-spaced-repetition/ts-fsrs) 5.4.2. Every card makes you type the English.
- **Listen**: dictation one sentence at a time. Missed words become cards. Playback speed adjusts to keep you at 80-90% of words right.
- **Speak**: role-play a stand-up or an incident report with Claude, or the 4/3/2 drill (same talk in 4, 3, then 2 minutes). It records how many words you spoke.

The cards come from the same files. Paste the `phrases.md` or `vocab.md` table into the import box and each row becomes a card. I pulled the parser out of the page and ran it on a small table I wrote (output trimmed):

```text
$ node run.js app/rounds.html table.md
[
  {
    "kind": "fix",
    "prompt": "I fixed the bug in yesterday.",
    "answer": "I fixed the bug yesterday.",
    "category": "preposition",
    "note": "no \"in\" before yesterday"
  },
  ...
  {
    "kind": "vocab",
    "prompt": "不安定な (テストが)",
    "answer": "flaky",
    "example": "The test is ____ on CI.",
    "note": ""
  }
]
```

A vocab row gets its word blanked out of the example sentence, so the card asks for the word in context.

The habit grid runs for 66 days, the median time to form a habit in Lally et al. (2010). Five minutes keeps the streak, 15 meets the goal, and one missed day a week is forgiven. `docs/apps-research-ja.md` goes through which Duolingo mechanics made it in and which didn't. There are no XP, leagues, gems or hearts.

The artifact viewer sometimes decodes the page in a charset other than UTF-8, and every Japanese string turned into mojibake. `app/build.py` escapes every non-ASCII character in the HTML, CSS and JS so it can't happen:

```text
$ python3 app/build.py app/rounds.html dist/rounds.html
$ LC_ALL=C grep -c $'[^\t -~]' app/rounds.html dist/rounds.html
app/rounds.html:292
dist/rounds.html:0
```

The ASCII copy is the one you publish, with the `db`, `user` and `sample` capabilities. `sample` is what lets the page call Claude. Without it the role-play and the "why?" explanation buttons stay hidden. Artifact frames block the microphone, so speech goes in through OS dictation (fn twice on macOS).

Source: <https://github.com/0-draft/claude-english-coach>
