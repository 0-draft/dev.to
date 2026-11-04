---
title: Secret Scanners Look for Credentials. I Wanted One That Looks for Me.
published: true
description: 'Coding agents commit what they see on your machine: home paths, hostnames, session links. None of it is a secret, so gitleaks stays quiet. kwangmyong looks for you, shows it in a terminal UI, and blocks the agent before it pushes.'
tags:
  - showdev
  - git
  - privacy
  - security
series: ShowDev
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/kwangmyong/cover.png?v=6ec95fc7'
id: 4973059
date: '2026-11-04T04:39:45Z'
---

I let coding agents write a lot of my commits now. They write what they see, and what they see is my machine: `/Users/<me>/...` in a README, `me@my-laptop ~ %` in a pasted test log, a `claude.ai/code/session_...` link at the bottom of a PR body.

None of that is a credential, so secret scanners don't flag it. I wanted one that knows who I am.

- Source: <https://github.com/kanywst/kwangmyong>
- Install: `brew install --cask kanywst/tap/kwangmyong` or `go install github.com/kanywst/kwangmyong/cmd/kwangmyong@latest`

![gitleaks finds nothing; kwangmyong's terminal UI walks the made-up developer's home path, hostname, name and session link, its Claude Code hook blocks gh pr create, and a clean repo comes back TARGET DARK](./assets/kwangmyong/demo.gif?v=839e39cb)

## Same repository, two scanners

The demo is a four-commit repository for a made-up developer, Taro Yamada (login `tyamada`, laptop `Taros-MacBook-Pro`):

- `README.md` mentions `/Users/tyamada/src/app/log`
- `NOTES.md` mentions `~/.claude/projects/-Users-tyamada-src-app/memory`
- `test.log` has `tyamada@Taros-MacBook-Pro app % make test`
- one commit message ends with a Claude Code session URL
- `AUTHORS` with `山田 太郎` was added in one commit and deleted in the next

gitleaks 8.30.1:

```text
$ gitleaks git . --no-banner
INF 3 commits scanned.
INF scanned ~204 bytes (204 bytes) in 36.2ms
INF no leaks found
```

Correct. There are no secrets in it.

## What kwangmyong shows

On a terminal, `kwangmyong scan --history .` sweeps the repository with a live count, then opens this:

![The kwangmyong terminal UI: places on the left, the masked line, what leaks, why it matters, where else the same value is, and the fix on the right](./assets/kwangmyong/tui.png?v=07b722ec)

Every value is masked as a prefix and a fingerprint (`ty…[b35fc2ee]`), so a screenshot or a CI log is not a new leak. `r` reveals values on that screen only. Search only sees masked text, so typing your own name into it finds nothing.

`ALSO` lists the other places the same value turns up. `FIX` depends on where it is: a file needs an edit, a deleted file or a commit message needs a history rewrite, and `p` drafts that rewrite (git filter-repo inputs plus a checklist of what a rewrite cannot reach) without leaving the screen.

Quit, and the verdict stays in the scrollback:

```text

╭────────────────────────────────────────────────────────────────────────────╮
│ ✗ TARGET EXPOSED  6 pieces of intel on you, from 5 places                  │
│   4 to fix in files · 2 baked into history                                 │
│   threat level ■■■■□ HIGH                                                  │
│   swept 3 files · 4 commits · 1 deleted blob                               │
│   looked for 2 names · 1 login · 1 host · home paths · agent session links │
│   values are masked · --reveal shows them                                  │
│   next ▸ kwangmyong plan .  drafts the history rewrite for you to review   │
╰────────────────────────────────────────────────────────────────────────────╯
```

A clean repository gets `✓ TARGET DARK` with what was swept and what was looked for, so "nothing found" also says how hard it looked. Piped, in CI, or with `--format json|sarif`, the same report prints without the UI.

## It starts from who you are

The profile lives in `~/.config/kwangmyong/config.toml`, never in the repository, and `kwangmyong init` fills it in from the machine: login, home directory, full name, hostname, global git identity.

```toml
[identity]
names  = ["Taro Yamada", "山田 太郎"]
logins = ["tyamada"]
hosts  = ["Taros-MacBook-Pro"]
```

Each value is expanded into the forms it actually shows up in: `tyamada`, `t.yamada`, `Yamada Taro`, `-Users-tyamada-`, `Taro's MacBook Pro`. Session links from Claude Code and Codex are flagged without any config.

## Stop the agent, not just the commit

The part I use most is the hooks. `kwangmyong hook install` sets up pre-commit, commit-msg and pre-push for a repository. For agents, the pre-tool hook gets the tool call before it runs:

| Agent | Hook |
| --- | --- |
| Claude Code | `kwangmyong hook claude` |
| Codex CLI | `kwangmyong hook codex` |
| Gemini CLI | `kwangmyong hook gemini` |
| Cursor | `kwangmyong hook cursor` |
| GitHub Copilot | `kwangmyong hook copilot` |
| Windsurf, Kiro, Devin | `kwangmyong hook windsurf`, `kiro`, `devin` |

It checks `git commit`, `git push`, `gh` bodies and body files, file writes into the repository and GitHub MCP writes, and exits `2` to block. The agent gets the reason back, masked:

```text
✗ TRANSMISSION BLOCKED. kwangmyong stopped this command: it would hand out intel on you.

[HIGH] command gh:3
  3 │ ht…[bf572e0c]'
    │ ^^^^^^^^^^^^^ your agent's session link

fix ▸ use ~/ or repo-relative paths, your public handle instead of a real name,
      the GitHub noreply address as the commit email, and no agent session links.
```

## CI

```yaml
- uses: kanywst/kwangmyong@v0
  with:
    identity: ${{ secrets.KWANGMYONG_IDENTITY }}
    sarif: kwangmyong.sarif
```

The identity comes from a secret as TOML. The Action checks the release binary against its signed checksums, and the SARIF is masked no matter what.

## Not covered yet

Wikis, Actions logs, Discussions.

Source and issues: <https://github.com/kanywst/kwangmyong>
