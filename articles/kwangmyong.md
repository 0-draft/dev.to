---
title: Secret Scanners Look for Credentials. I Wanted One That Looks for Me.
published: true
description: 'Coding agents commit what they see. Home paths, the project slug Claude Code derives from your home directory, a hostname in pasted terminal output, a session link in the PR body. None of it is a secret, so gitleaks stays quiet. kwangmyong scans repositories and GitHub for your own identity instead.'
tags:
  - showdev
  - git
  - privacy
  - security
series: ShowDev
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/kwangmyong/cover.png?v=cd8716a6'
id: 4973059
date: '2026-11-04T04:39:45Z'
---

I let coding agents write a lot of my commits now. They write what they see, and what they see is my machine: `/Users/<me>/src/...` in a README, the `-Users-<me>-<repo>` slug Claude Code uses for its project directory in a note about memory, `me@my-laptop ~ %` in a pasted test log, a `claude.ai/code/session_...` link at the bottom of a PR body.

None of that is a credential, so secret scanners have no reason to flag it. I wanted a scanner that knows who I am and looks for that.

- Source: <https://github.com/0-draft/kwangmyong>
- Install: `go install github.com/0-draft/kwangmyong/cmd/kwangmyong@latest`, or a binary from the releases page (SBOM and cosign signature attached from v0.2.0)

## Same repository, two scanners

I built a four-commit repository for a made-up developer, Taro Yamada (login `tyamada`, laptop `Taros-MacBook-Pro`):

- `README.md` mentions `/Users/tyamada/src/app/log`
- `NOTES.md` mentions `~/.claude/projects/-Users-tyamada-src-app/memory`
- `test.log` has a shell prompt, `tyamada@Taros-MacBook-Pro app % make test`
- one commit message ends with a Claude Code session URL
- `AUTHORS` with `山田 太郎` was added in one commit and deleted in the next

gitleaks 8.30.1:

```text
$ gitleaks git . --no-banner
INF 3 commits scanned.
INF scanned ~204 bytes (204 bytes) in 36.2ms
INF no leaks found
```

That is correct. There are no secrets in it.

kwangmyong, given the name, login and hostname:

```text
$ kwangmyong scan --history .
HIGH  identity.name              file NOTES.md:1            ty…[b35fc2ee]
HIGH  identity.name              file README.md:3           ty…[b35fc2ee]
HIGH  identity.name              file test.log:1            ty…[b35fc2ee]
HIGH  identity.host              file test.log:1            Ta…[a84654fa]
HIGH  generic.agent-session-url  commit 871e593 message     ht…[509ace00]
HIGH  identity.name              history AUTHORS@686ce61:1  山…[ed6d53c9]

6 findings (6 high, 0 warn)
```

`tyamada` shows up as `identity.name` rather than `identity.login` because `Taro Yamada` already expands to `tyamada`, and name rules run first. The deleted `AUTHORS` file is only found because `--history` reads every blob reachable from any ref, not just the current tree.

## What it searches for

The identity lives in `~/.config/kwangmyong/config.toml`, never in the repository:

```toml
[identity]
names  = ["Taro Yamada", "山田 太郎"]
logins = ["tyamada"]
emails = ["taro@example.com"]
hosts  = ["Taros-MacBook-Pro"]
```

On top of that it adds what it can read from the current machine: login, home directory, full name, hostname and the global git identity (`--no-auto` turns that off). Each entry is expanded into the forms it actually appears in:

| Kind | Also matches |
| --- | --- |
| Latin name | swapped order, `.` `_` `-` or no separator, any case, `tyamada`, `t.yamada` |
| CJK name | swapped order, with or without half-width, full-width or `・` separators |
| Login | `/Users/x`, `/home/x`, `C:\Users\x`, `-Users-x-`, `x@host` |
| Email | URL-encoded |
| Host | spaced and possessive (`Taro's MacBook Pro`) |

GitHub noreply addresses are never reported.

A few rules need no configuration. `generic.agent-session-url` flags Claude Code (`claude.ai/code/session_...`) and Codex (`chatgpt.com/codex/tasks/task_...`) session links as high: in your own repository, that link is your account. `generic.home-path` flags anyone's home path as a warning, which `--strict` turns into a failure.

## The output does not repeat the leak

Every match is printed as two characters and a fingerprint (`ty…[b35fc2ee]`). The fingerprint is a SHA-256 of the lowercased value, so the same leak has the same fingerprint everywhere, and a CI log of the scan is not itself a new leak. `--reveal` prints raw values for a local terminal.

## Beyond the working tree

`kwangmyong github <owner>` reads issues, pull requests, comments, review bodies, releases, gists and repository metadata through the GitHub API. Those are places a `git filter-repo` never reaches.

`kwangmyong plan .` writes `replacements.txt`, a `mailmap` and a `PLAN.md` to a private temp directory outside the repository. For the demo repository:

```text
$ kwangmyong plan .
4 commit(s) from fee9bcc2ac41 would be rewritten, 0 tag(s) move
```

`PLAN.md` starts with what a rewrite cannot fix: forks, clones and caches keep the old history, signed commits lose their signatures, and closed pull requests lose their diffs. Sometimes switching to a noreply address and moving on is the better trade.

## Stopping it before it lands

The part I use most is the hooks:

| Hook | Command |
| --- | --- |
| git pre-commit | `kwangmyong hook pre-commit` |
| git pre-push | `kwangmyong hook pre-push` |
| Claude Code `PreToolUse` | `kwangmyong hook claude` |

The Claude Code hook checks file writes into a repository, `git commit`, `git push`, `gh` bodies and GitHub MCP writes, and exits `2` to block the tool call. Exit `2` is the code Claude Code treats as a block, and the reason goes back to the agent, so it gets a chance to fix the text instead of just failing. Here is the hook fed the tool call an agent would make to open a PR with its session link in the body:

```text
$ kwangmyong hook claude < tool-call.json
kwangmyong: this command would publish your identity (1 finding(s)):
  generic.agent-session-url  command gh:3  ht…[509ace00]
Use ~/ or repo-relative paths, your public handle instead of a real name, the GitHub noreply address as the commit email, and drop agent session links.
$ echo $?
2
```

Hooks block on high findings only, so a home path written by someone else's tool does not stop your commit.

## Not covered yet

Wikis (scan the wiki repository directly), Actions logs and artifacts, and Discussions.

Source and issues: <https://github.com/0-draft/kwangmyong>
