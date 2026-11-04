---
title: Secret Scanners Look for Credentials. I Wanted One That Looks for Me.
published: true
description: 'Coding agents commit what they see on your machine. None of it is a secret, so gitleaks stays quiet. kwangmyong looks for you instead.'
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

I let coding agents write a lot of my commits now. They write what they see, and what they see is my machine: `/Users/<me>/...` in a README, `me@my-laptop ~ %` in a pasted test log, a `claude.ai/code/session_...` link at the bottom of a PR body.

None of that is a credential, so secret scanners don't flag it. I wanted one that knows who I am.

- Source: <https://github.com/0-draft/kwangmyong>
- Install: `go install github.com/0-draft/kwangmyong/cmd/kwangmyong@latest`, or a binary from the releases page

![gitleaks finds nothing; kwangmyong finds the made-up developer's home path, hostname, name and session link, and its Claude Code hook blocks gh pr create](./assets/kwangmyong/demo.gif?v=d3d875b1)

## Same repository, two scanners

A four-commit repository for a made-up developer, Taro Yamada (login `tyamada`, laptop `Taros-MacBook-Pro`):

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

Values are printed as a prefix and a fingerprint, so the scan log doesn't leak them again. `--reveal` prints them.

## What it searches for

```toml
# ~/.config/kwangmyong/config.toml
[identity]
names  = ["Taro Yamada", "山田 太郎"]
logins = ["tyamada"]
hosts  = ["Taros-MacBook-Pro"]
```

It also adds this machine's login, home directory, hostname and git identity. Each value is expanded into the forms it shows up in: `tyamada`, `t.yamada`, `Yamada Taro`, `-Users-tyamada-`, `Taro's MacBook Pro`.

Session links from Claude Code and Codex are flagged without any config.

## Beyond the working tree

`kwangmyong github <owner>` reads issues, PRs, comments, reviews, releases and gists through the API. `git filter-repo` doesn't reach those.

`kwangmyong plan .` writes the `filter-repo` inputs and a checklist to a temp directory outside the repository:

```text
$ kwangmyong plan .
4 commit(s) from fee9bcc2ac41 would be rewritten, 0 tag(s) move
```

## Hooks

```text
kwangmyong hook pre-commit
kwangmyong hook pre-push
kwangmyong hook claude      # Claude Code PreToolUse
```

The Claude Code hook exits `2`, so the agent gets the reason back instead of the command running. Here it is on the tool call for a `gh pr create` with a session link in the body:

```text
$ kwangmyong hook claude < tool-call.json
kwangmyong: this command would publish your identity (1 finding(s)):
  generic.agent-session-url  command gh:3  ht…[509ace00]
Use ~/ or repo-relative paths, your public handle instead of a real name, the GitHub noreply address as the commit email, and drop agent session links.
$ echo $?
2
```

Not covered yet: wikis, Actions logs, Discussions.
