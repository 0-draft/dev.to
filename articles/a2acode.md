---
title: "a2claude Is Now a2acode: Any ACP Coding Agent Behind A2A"
published: false
description: "I renamed my Claude Code A2A server two weeks after shipping it, because Claude Code had become a launch command. a2acode now fronts Claude Code, Codex or Gemini CLI over ACP and keeps tool calls, diffs and permission prompts on the A2A side."
tags: ["showdev", "ai", "agents", "python"]
series: ShowDev
cover_image: "https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/a2acode/cover.png"
---

In June I shipped [a2claude](https://dev.to/kanywst/a2claude-turn-claude-code-into-a-server-other-ai-agents-can-call-1mf6), which put Claude Code behind A2A so another agent could hand it coding work. It drove Claude through the Claude Agent SDK.

Two weeks later I added a second backend that speaks Zed's Agent Client Protocol instead. ACP agents already report their work as structured `session/update` messages: tool calls, diffs, plans, permission requests. Those map almost one to one onto what a2claude was already sending over A2A. Once that worked, Claude Code was one launch command among several, and the name was wrong. It's a2acode now.

- Source: <https://github.com/kanywst/a2acode>
- Install: `uvx a2acode serve` (PyPI), or `ghcr.io/kanywst/a2acode`

If ACP and A2A are new to you, I mapped them out in [Mapping MCP, A2A, and ACP](https://dev.to/kanywst/mapping-mcp-a2a-and-acp-telling-ai-agent-protocols-apart-in-2026-1hha). This post skips that.

## Picking the agent

```bash
uvx a2acode serve --cwd ./project                   # Claude Code, the default
uvx a2acode serve --agent codex --cwd ./project
uvx a2acode serve --agent gemini --cwd ./project
uvx a2acode serve --agent-command "npx -y some-other-acp-agent"
```

The presets are three lines in `backends/acp.py`, all launched through `npx`: `@zed-industries/claude-agent-acp`, `@zed-industries/codex-acp`, `@google/gemini-cli --acp`. Each agent picks up its own credential from the server's environment. The callers on the A2A side never see which one is running.

The `gemini` preset only works on organization Code Assist plans. Google stopped serving the Gemini CLI to consumer accounts in June 2026, so on a personal account it fails before ACP or a2acode get involved.

## A run, over ACP

I don't have keys for all three, so the output below comes from the repo's test agent (`tests/fake_agent.py`). It's a real ACP agent over stdio, the same handshake and session lifecycle, and each keyword in the prompt makes it exercise one part of the protocol. The server doesn't know it's a test.

```bash
uv run a2acode serve --agent-command "python tests/fake_agent.py" --cwd ./ws --port 9177
uv run a2acode call "plan then edit then boom" --url http://localhost:9177/
```

```text
task 229322b0-0e78-42a1-802d-3a117c59fd92
context 3c0fd964-fd51-4fe1-a694-bcc1044b9ce6

  [thinking]
  considering
  [plan]
  - [x] look
  - [>] fix
  · Write calc.py
  [calc.py]
  --- a/calc.py
  +++ b/calc.py
  @@ -1 +1 @@
  -a
  +b
  · ✓ Write calc.py
  · Run tests
  · ✗ Run tests: 2 tests failed
turn 1: done
[completed]
```

On the A2A side, the reasoning is a `thinking` artifact, separate from the answer. The plan is a `plan` artifact that gets replaced as steps move. The diff is its own named artifact, and each tool call and its outcome arrive as `working` status updates. A caller can tell "the tests failed" apart from "the agent said the tests failed".

All of that mapping lives in `executor.py`. Backends emit a fixed set of events and never import the A2A SDK, and the executor never imports an agent SDK. The ACP backend, the Claude SDK backend and an offline `echo` backend all go through the same mapping.

## Permission prompts go to the caller

When the agent asks for permission, the task pauses in `input-required` and waits for the caller:

```text
$ a2acode call "ask" --url http://localhost:9177/
task a55854f6-f1df-4afc-9a2f-88fc702c03bf
context a53af302-25f7-48c9-92ad-7866536dd94b

  [thinking]
  considering
turn 1: 
[input-required] Permission requested for rm -rf /: rm -rf /
options, answered as "option:<id>":
  'ok' ['allow_once'] 'Allow'
  'no' ['reject_once'] 'Deny'
  reply: a2acode call "allow" --task a55854f6-f1df-4afc-9a2f-88fc702c03bf --context a53af302-25f7-48c9-92ad-7866536dd94b --request 4a2afbaabfb64856901489a94d258644 --url http://localhost:9177/
  (or "deny" to refuse)
```

The agent process stays parked inside `session/request_permission` until an answer arrives on the same task:

```text
$ a2acode call "no, not on my machine" --task a55854f6-... --context a53af302-... --request 4a2afbaa...
permission=no done
[completed]
```

Only a whole-message `allow`, `yes`, `y`, `ok`, `approve`, `accept` or `grant` approves (`_ALLOW_WORDS` in `executor.py`). Anything else denies, so the caller can answer in plain prose without accidentally approving something. The prose itself doesn't reach an ACP agent, though. ACP's permission response only has room for the chosen option, which is why the agent above only saw `no`. The Claude SDK backend does pass the words along, so `no, run pytest -x instead` redirects the turn there.

The `--request` id ties an answer to one prompt. A run often pauses again right after you answer, and a retried request shouldn't approve a tool call the caller never saw.

## Terminals go through the same gate

a2acode implements ACP's terminal capability, so the agent can ask the server to run a build or a test. ACP doesn't require an agent to ask permission before `terminal/create`, so if I had just advertised the capability, agents would have had a way to run commands without going through the gate. Instead every `terminal/create` gets the same pause, with the full command line:

```text
$ a2acode call "shell" --url http://localhost:9177/
...
[input-required] Permission requested for Terminal: …/.venv/bin/python -c 'print('"'"'from the terminal'"'"')'

$ a2acode call "allow" --task bf667ad8-... --context 0e39fb1a-... --request 53a0a493...
shell said from the terminal done
[completed]
```

(I shortened the interpreter path.) An approved command is not sandboxed. It runs as the server's user, and the only environment variables it inherits are `PATH`, `HOME`, `LANG`, `TMPDIR`, `TERM`, `SHELL`, `USER`, `TZ` and `LC_*` (`backends/terminal.py`), so the provider API key the server holds doesn't leak into it. The approval is where the security decision happens, so run the server as a user whose files you'd be fine with any approved command reading.

## Follow-up turns reuse the process

The A2A `contextId` maps to the agent session, and the ACP backend keeps one agent process alive per context. The test agent counts turns per process:

```text
$ a2acode call "hello"
context 9f0f6844-b74e-4ee6-adb5-5b77a50ab4c1
turn 1: done
[completed]

$ a2acode call "again" --context 9f0f6844-b74e-4ee6-adb5-5b77a50ab4c1
turn 2: done
[completed]
```

The second call goes to the same process, so there's no `npx` launch, no handshake, no `session/load`. If a new process does have to resume a session and the agent doesn't support `session/load`, the turn runs fresh and a status update says so. Pretending to remember would be worse.

## Discovery

The agent card at `/.well-known/agent-card.json` lists A2A `1.0` and `0.3` interfaces (JSON-RPC and HTTP+JSON) on the same URL, so clients built on a v0.3 SDK can still find the server and run tasks. `--sign-key` signs the card with JWS. `--auth-token-file` requires a bearer token on every request except the card fetch.

## What I checked

223 tests pass on my machine (`uv run pytest`). Everything in this post was run against the test ACP agent, not against Claude Code, Codex or Gemini. The README says the full mapping has been checked end to end against real Claude.

Source and issues: <https://github.com/kanywst/a2acode>
