---
title: 'ccretro: A Monthly Claude Code Retro That Checks Last Month''s Suggestions'
published: false
description: 'ccretro reads your local Claude Code transcripts, compares the period with the one before, and on the next run checks whether last month''s suggestions happened. A /ccretro skill turns them into skills, hooks and CLAUDE.md lines.'
tags:
  - showdev
  - ai
  - claude
  - productivity
series: ShowDev
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/ccretro/cover.png?v=05078138'
id: 5038051
---

`/insights` gives me a list of things to change. A month later it gives me another list. Nothing tells me whether I did anything about the first one, and Claude Code deletes transcripts older than `cleanupPeriodDays` (30 by default), so a quarter is out of reach anyway.

ccretro is a local web page that compares a period with the one before it, remembers what it suggested last time and checks it, plus a skill that turns the suggestions into real config.

- Source: <https://github.com/0-draft/ccretro>
- Run: `npx --allow-git=root github:0-draft/ccretro` (Node 20+, no runtime dependencies; npm 12 needs `--allow-git=root`)

![The top of a ccretro report: headline, KPI row with change against the previous 30 days, and a daily prompts chart](./assets/ccretro/report.png?v=3e9f7726)

That page, and every number below, comes from a synthetic `~/.claude`: 91 generated transcripts for a made-up developer with three projects. Not my history.

## What it counts

It reads `~/.claude/projects/**/*.jsonl` and reduces each transcript to a summary (counts, plus the first 400 characters of each prompt). Summaries go into `~/.local/share/ccretro/archive.json`. When Claude Code deletes the transcript, the summary stays, so `-d 90` or `-d 0` still covers it on later runs.

How things are counted:

- A prompt is something you typed. Tool results, system reminders, interrupts and headless `claude -p` / SDK sessions are not prompts. A resumed session that copies old messages is de-duplicated by UUID.
- Active hours are merged across sessions. Three parallel sessions for an hour count as one hour.
- Cost is what the tokens would cost at API list prices, per model, de-duplicated by message id. A subscription doesn't bill it.
- Pull requests come from the `pr-link` entries Claude Code writes, counted once in the period that first linked them.

The period switch (7 days, 1 month, 3 months, all time) recomputes everything, and each KPI shows the change against the previous period of the same length. If that previous period reaches back past the oldest data, the comparison is left out instead of comparing against zero.

## What gets sent to Claude

The written parts (headline, themes, four AI Fluency cards, next actions) come from your own `claude -p`, run with no tools, no MCP servers and `--no-session-persistence`, so the retro doesn't land in the next retro. `--dry-run` prints the exact digest. On the fixture, the top of it:

```text
$ ccretro --dry-run -d 30
PERIOD: last 30 days
TOTALS: sessions=36 prompts=222 activeDays=20 bestStreak=11 activeHours(wall-clock, parallel sessions merged)=11.7 claudeTurnHours(summed across parallel sessions)=0 toolCalls=501 projects=3
RHYTHM: peakWeekday=Sat peakHour=12:00 lateNight(0-5h)share=16%
VS PREVIOUS 30 DAYS: prompts 300→222, sessions 49→36, activeHours 14.9→11.7, activeDays 25→20, projects 3→3, costUsd 14.99→10.83, prs 8→2, interruptsPer100 4.7→2.3, errorRate 4.7→5, agentCalls 0→46, skillCalls 0→62
CACHE: hitRate=89% of input tokens served from prompt cache
...
REPEATED PROMPTS (normalised, count, #projects):
- "run the tests and fix whatever fails" ×26 in 3 projects
- "commit this with a conventional commit message" ×14 in 3 projects

EXISTING SETUP (do not suggest what already exists):
global CLAUDE.md=false outputStyle=null allowRules=0 hookEvents=none
user skills: run-tests
user subagents: none
user commands: none
per-project: src/blog(CLAUDE.md=n,skills=0), src/api-server(CLAUDE.md=y,skills=0), dotfiles(CLAUDE.md=n,skills=0)
```

After that come up to 140 sampled prompts, each cut to 220 characters. `-x <project>` removes a project from all of it, the stats and the page included.

## Following up on last month

Each run saves its suggestions to `~/.cache/ccretro/last-insight.json`. The next digest gets a `PREVIOUS SUGGESTIONS` block next to `EXISTING SETUP` and the repeated-prompt counts, and the model marks each one done, partial, not yet or unclear. A skill that now exists is done. A prompt that is still typed all the time is not.

I seeded the fixture with three old suggestions: make a skill for "run the tests and fix whatever fails", add a Stop hook for em dashes, add CLAUDE.md to `src/blog`. The digest above shows why the first one is interesting: `run-tests` exists and gets called, and the prompt was still typed 26 times. The skill was made and the habit didn't change. That's the case a single `/insights` run can't see.

Without a logged-in `claude`, or with `--no-ai`, you still get every number and rule-based suggestions, but no follow-up section. The rules are blunter. On the fixture they proposed turning "run the tests and fix wh" into a skill, because they look at repeated prompts and not at which skills already exist.

## Share mode

`--redact` aliases names in the data itself, before the digest, the fallback text or the page is built from it. Session titles, repeated prompts and previous suggestions are dropped, and the model gets a separate prompt that forbids quoting. The same fixture:

```text
$ ccretro --dry-run --redact -d 30
PROJECTS (prompts / sessions / active hours / session titles):
- project 2: 100 / 15 / 5.2h
- project 1: 74 / 12 / 4h
- project 3: 48 / 9 / 2.5h

REPEATED PROMPTS (normalised, count, #projects):
```

(I trimmed a trailing separator from the project lines.) Sampled prompt text is still sent in this mode, since the model needs it to find themes, but it never reaches the page.

## The `/ccretro` skill

The repo is also a Claude Code plugin:

```text
/plugin marketplace add 0-draft/ccretro
/plugin install ccretro@ccretro
```

`/ccretro` runs the CLI, reads the JSON written next to the HTML, and checks each suggestion against the real files before proposing anything. It lists `~/.claude/skills` and the project's skills, follows symlinks into a dotfiles repo, and if an existing skill already covers most of a suggestion, it proposes editing that skill instead of adding one. Same for CLAUDE.md: tighten the rule that's there rather than add a line restating it. Then one multi-select, and only the picked items get written. Nothing is committed or pushed unless you ask.

The SKILL.md opens with the line that sums up why it exists: "The report alone changes nothing."

Source and issues: <https://github.com/0-draft/ccretro>
