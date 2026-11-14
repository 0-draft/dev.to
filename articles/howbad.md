---
title: "howbad: What a Prompt-Injected Coding Agent Could Do With the Credentials on Your Machine"
published: false
description: "Claude Code, Codex and Cursor run as you, so a hijacked agent gets every credential your shell can reach. howbad finds them and asks each provider, read-only, what they can actually do."
tags: ["showdev", "security", "ai", "go"]
series: ShowDev
cover_image: "https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/howbad/cover.png"
---

Claude Code, Codex and Cursor run as me. A prompt injection in a README or an issue comment doesn't need a sandbox escape. It gets whatever my shell gets: the `gh` token, the npm token that publishes packages, the AWS profile from this morning, the Slack token pasted into an MCP config.

I knew roughly what was on my laptop. I didn't know what any of it could do. "There is a GitHub token" and "this token can push to 49 repos and rewrite their CI" are different answers, so I wrote a tool that gives the second one.

- Source: <https://github.com/kanywst/howbad>
- Install: `brew install kanywst/tap/howbad` or `go install github.com/kanywst/howbad@latest`

![howbad prints a ranked list of what a hijacked agent could do with the credentials on a fake machine](./assets/howbad/demo.gif)

## The report

This is the repo's demo harness (`go run ./internal/demo`): a throwaway home directory with fake tokens, and an `httptest` server standing in for GitHub, npm and Slack. Same binary, same report code.

```text
  howbad · if a coding agent on this machine got hijacked right now, it could:

  CRITICAL  push code to 49 GitHub repos and rewrite their CI workflows
            e.g. acme/sdk-js (1830★), you/dotfiles (240★), acme/payments (12★)
            ↳ gh CLI · you on github.com · ~/.config/gh/hosts.yml · #e9e4a9d1
  CRITICAL  publish new versions of 3 npm packages (234k downloads/week) unless npm demands 2FA (inferred)
            e.g. @acme/sdk (184k/week), @acme/cli (41k/week), @acme/ui (9.8k/week)
            ↳ npm · you on npm · ~/.npmrc · #f54f870e
  HIGH      change settings on 2 repos (branch protection, deploy keys, webhooks)
            ↳ gh CLI · you on github.com · ~/.config/gh/hosts.yml · #e9e4a9d1
  HIGH      read message history in Acme: public channels, private channels, DMs
  HIGH      search every message you can see in Acme
  HIGH      post messages as you in Acme (trusted-sender phishing)
            ↳ MCP server "slack" (Cursor) · you in Slack workspace Acme · ~/.cursor/mcp.json · #dadd4c65
  MEDIUM    spend money on your OpenAI API account (not verified)
            ↳ $OPENAI_API_KEY · environment variable $OPENAI_API_KEY · #85bd6af8
  MEDIUM    create secret gists, a ready-made exfiltration channel
            ↳ gh CLI · you on github.com · ~/.config/gh/hosts.yml · #e9e4a9d1

  one login away:
    AWS profile prod: likely do anything (role AdministratorAccess) once logged in again

  agents running as you: Claude Code (bypassPermissions), Cursor, Codex
  pasted straight into agent configs: 1 credential
  5 credentials · 3 verified read-only with the issuer · nothing sent anywhere else
```

Each line is a capability, not a token. The `#e9e4a9d1` is the first 8 hex of the token's SHA-256, so you can tell two tokens apart without the secret ever being printed. The AWS profile is an SSO profile whose session expired, so it lands under "one login away" with the role name instead of being dropped. The footer lists which agents are installed and flags Claude Code because its settings set `defaultMode` to `bypassPermissions`.

## Where it looks and who it asks

It reads env vars, the `gh` CLI (hosts.yml or keychain), `.npmrc`, `~/.aws`, kubeconfig, gcloud and Application Default Credentials, and the MCP configs of Claude Code, Codex, Cursor, Gemini CLI, Antigravity, VS Code, Zed, GitHub Copilot, Cline, Continue, Windsurf, Devin Desktop and Claude Desktop.

Each credential goes only to the provider that issued it, and only to read-only endpoints:

| Credential | Asked with | Comes back as |
| --- | --- | --- |
| GitHub | `GET /user`, `/user/repos`, the `X-OAuth-Scopes` header | repos you can push to, CI workflow access, admin repos, gists |
| npm | `whoami`, token list, package search | packages you maintain and their weekly downloads |
| Slack | `auth.test` scopes | history, search, posting as you |
| AWS | `sts:GetCallerIdentity`, attached policies | identity, account, policy or SSO permission set |
| Kubernetes | `SelfSubjectAccessReview` per context | cluster-admin, Secrets, exec, pod creation |
| GitLab | `GET /personal_access_tokens/self` | push, CI/CD, registries, runners, admin |
| Google Cloud | `testIamPermissions` per project (up to 25) | IAM admin, impersonation, Secret Manager, GKE |

Stripe, OpenAI, Anthropic, Google API keys, Hugging Face tokens and database URLs are recognized by format and never called. That's why the OpenAI line says "not verified".

## Where it can't read permissions

Fine-grained GitHub tokens, GitHub App tokens and npm tokens can't report their own permissions. For those, howbad reports the account's access as an upper bound and marks it `inferred`. The repo's own rule for this is "under-reporting is the dangerous direction", and it shows up in the code: a GitHub token with no `X-OAuth-Scopes` gets every repo the user can push to, prefixed with "up to".

`--offline` shows the same thing without any network calls. Everything becomes an upper bound:

```text
  CRITICAL  likely do anything (role AdministratorAccess) (inferred, not checked)
            ↳ AWS profile prod · ~/.aws/config
  HIGH      use a GitHub token as its owner (inferred, not checked)
            ↳ gh CLI · ~/.config/gh/hosts.yml · #e9e4a9d1
  HIGH      use an npm token as its owner (inferred, not checked)
            ↳ npm · ~/.npmrc · #f54f870e
```

## Being boring with live credentials

A tool that reads every token on the machine is itself a good injection target, so:

- The secret is an unexported field on `cred.Credential`, and the type implements `fmt.Formatter`, so `%v`, `%+v` and `%#v` can't print it either. Tests assert no secret appears in any output.
- `--no-exec` skips everything that runs a helper: `gh auth token`, `gcloud auth print-access-token`, AWS `credential_process`, kubeconfig exec plugins.
- Configs in the current directory are read, but a cloned repo can't steer where a token goes. `${VAR}` in a repo's `.npmrc` isn't expanded, and if both the token and its host come from a repo-local config, nothing is sent:

```go
case c.RepoLocal && h != "" && h != "github.com":
    // A cloned repo names this host; don't let it make howbad dial out.
    f.Status, f.Detail = finding.Unverified, "token and host both come from a repo-local config; not sent"
```

## In CI

`--fail-on high` exits `2` if anything at or above that severity is reachable. It also exits `2` when a credential couldn't be checked, because "couldn't check" isn't "safe":

```text
$ howbad --offline --no-exec --fail-on high
  howbad · if a coding agent on this machine got hijacked right now, it could:

  HIGH      use an npm token as its owner (inferred, not checked)
            ↳ npm · ~/.npmrc, ./.npmrc · #f54f870e

  1 credential · 0 verified read-only with the issuer · nothing sent anywhere else
$ echo $?
2
```

`--json` gives the same findings with severity, `inferred` and `status` per credential. Those fields and the exit code are treated as an API.

## Not covered

Custom AWS policies aren't evaluated, only attached policy names. Remote MCP servers using OAuth keep their tokens in the agent's own store, often the keychain, which howbad doesn't read. Claude Code policies pushed through macOS configuration profiles aren't read either.

Source and issues: <https://github.com/kanywst/howbad>
