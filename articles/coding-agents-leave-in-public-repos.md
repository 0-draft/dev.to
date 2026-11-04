---
title: What Coding Agents Leave in Public Git Repos
published: true
description: 'Tens of thousands of public files carry a developer''s real login in a path an agent wrote, and millions of commits carry a session link. I counted them and wrote a hook that blocks it.'
tags:
  - ai
  - git
  - privacy
  - security
series: ShowDev
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/coding-agents-leave-in-public-repos/cover.png?v=43feca34'
id: 4975796
date: '2026-11-04T13:38:24Z'
---

I let coding agents write a lot of my commits now. They write what they see, and what they see is my machine: `/Users/<me>/src/...` in a README, a project path in a notes file, a session link at the bottom of a commit. None of it is a secret, so no secret scanner flags it. It is still my account name, in public.

I wanted to know how common that is, so I counted with GitHub search and checked samples by hand.

## The numbers

| What | GitHub's count | Real in my sample | Rough estimate |
| --- | --- | --- | --- |
| `CLAUDE.md` with `/Users/<name>/` | 27,424 files | 105 of 300 | ~9,600 files |
| `AGENTS.md` with `/Users/<name>/` | 26,208 files | 140 of 300 | ~12,200 files |
| Claude Code project path `~/.claude/projects/-Users-<name>-…` | 47,104 files | 122 of 300 | ~19,000 files |
| Commits with a Codex task link | ~50,800 | 431 of 500 | ~44,000 commits |
| Commits with a Claude Code session link | 1.8M to 10.8M | 500 of 500 | millions |

"Real" means the path holds an actual account name. I threw out placeholders like `/Users/you/`, `/Users/username/` and `/Users/<user>/`; a third to a half of the hits survived that.

Caveats:

- Code search only sees default branches of indexed repositories, so the file counts are a floor, not a census.
- GitHub's commit count for the session link moved between 1.8 million and 10.8 million in one afternoon. All 500 of the newest results did contain one.
- My samples are the first pages of results, not a random draw.
- No repository or person is named here. Every number is an aggregate.

## Why each one ends up there

**Agent memory files.** `CLAUDE.md` and `AGENTS.md` are where agents keep notes about a project, and agents write what they know: absolute paths to the repo, to a sibling checkout, to a log directory. Those paths start with your home directory, which is your login. The file then gets committed because it is supposed to be shared with the next session.

**The project slug.** Claude Code keeps per-project state under `~/.claude/projects/` in a directory named after the absolute path, so `/Users/taro/src/app` becomes `-Users-taro-src-app`. That slug shows up in notes, logs and debugging output that agents paste into the repository.

**Session links.** Some agent setups add a trailer like `Claude-Session: https://claude.ai/code/session_…` to each commit, or a task link to the PR body. What the link does publicly is tie a commit to an agent session and, across repositories, tie commits to each other.

## Check your own

Your commits with a session link:

```sh
gh search commits "claude.ai/code/session_" --author <your-github-login>
```

Your public files with your home path:

```sh
gh search code "/Users/<your-login>/" --owner <your-github-login>
```

In a local clone, including deleted files and commit metadata:

```sh
brew install --cask kanywst/tap/kwangmyong
kwangmyong init
kwangmyong scan --history .
```

![kwangmyong's terminal UI walking a made-up developer's home path, hostname, name and session link, then blocking an agent's gh pr create](https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/kwangmyong/demo.gif)

## Stop it at the source

Scanning finds what is already out. `kwangmyong hook claude` stops it before the write: as a Claude Code `PreToolUse` hook it blocks `git commit`, `git push`, `gh` bodies, file writes and GitHub MCP calls that carry your name, login, email, hostname or home path, and tells the agent why with the value masked. Codex, Gemini CLI, Cursor, Copilot, Windsurf, Kiro and Devin have adapters too.

```json
{
  "hooks": {
    "PreToolUse": [
      { "matcher": "Bash|Write|Edit|MultiEdit|NotebookEdit|mcp__github__.*", "hooks": [{ "type": "command", "command": "kwangmyong hook claude" }] }
    ]
  }
}
```

## Method

Run with `gh api` on 2026-11-04:

- code: `"/Users/" filename:CLAUDE.md`, `"/Users/" filename:AGENTS.md`, `"-Users-" ".claude/projects"`, first 300 results each, text-match fragments checked with a regex, placeholders excluded
- commits: `"claude.ai/code/session_"` and `"chatgpt.com/codex/tasks"`, newest first, 500 results each, messages checked with a regex

Source for the tool: <https://github.com/kanywst/kwangmyong>
