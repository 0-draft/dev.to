---
title: 'whosent: A TUI That Shows Who Sent the Agent'
published: true
description: 'A request arrives from research-agent. whosent opens the delegation chain behind it (JWT act, Biscuit, UCAN or macaroons), traces it back to the human, and points at the hop where authority grew.'
tags:
  - showdev
  - go
  - security
  - oauth
series: ShowDev
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/whosent/cover.png?v=d1daa355'
id: 5038077
---

A request shows up from `research-agent`. The token says Alice. Between Alice and that agent there was a chat UI and a planner, three token exchanges, and the scope should have shrunk at each one. Decoding the JWT and squinting at nested `act` claims does not tell me whether it did.

I wrote [y509](https://dev.to/kanywst/y509-a-terminal-user-interface-tui-tool-for-viewing-and-analyzing-x509-certificate-chains-5fn6) for X.509 chains. whosent is the same idea for delegation chains.

- Source: <https://github.com/kanywst/whosent>
- Install: `brew install --cask kanywst/tap/whosent` or `go install github.com/kanywst/whosent/cmd/whosent@latest`

![whosent walking a JWT bundle that breaks at the last exchange, asking whether the last token may write files, then scrubbing the clock on a Biscuit token](./assets/whosent/demo.gif?v=9919135f)

## Scope from nowhere

`whosent demo` ships 41 scenarios across the four formats, and `demo --emit` writes any of them out as real files. This one is three exchanged JWTs where the last exchange gained a scope:

```text
$ whosent demo --emit fixture jwt-bundle-widened && cd fixture
$ whosent check tokens.json --trust trust.json --audience https://api.acme.example --at 2026-09-12T08:01:00Z
=== tokens.json · 3 links · JWT · issuer https://acme.okta.example, access token (RFC 9068)
    at 2026-09-12T08:01:00Z, skew 30s, audience https://api.acme.example

❌ INVALID: the chain breaks at link 2, and no authority reaches below it

  #  issuer → subject                   J1 J2 J3 J4 J5 J6 J7 J8 J9 J10 J11 J12
  0  alice@acme.example → chat-ui        ✓  ✓  ✓  ·  ✓  ·  ·  ·  ·   ·   ·   ·
  1  chat-ui → planner-agent             ✓  ✓  ✓  ·  ✓  ✓  ✓  ✓  ✓   ✓   ·   ·
  2  planner-agent → research-agent      ✓  ✓  ✓  ✓  ✓  ✓  ✓  ✗  ✓   ✓   ·   ·
     ✓ pass  ✗ fail  ! could not evaluate  ? not checked  - skipped  · does not apply

Findings
  ✗ J8 link 2: adds files:write, which token 1 did not hold [whosent bundle rule, derived from RFC 8693; not a procedure any specification defines (section 4.2, scope)]

How authority narrows
  0 → 1  chat-ui → planner-agent
      + exchanged: planner-agent now acts for alice@acme.example
      = scope files:read
      - scope files:write dropped
      = scope calendar:read
      ~ expires 20m sooner
  1 → 2  planner-agent → research-agent
      + exchanged: research-agent now acts for alice@acme.example
      = scope files:read
      - scope calendar:read dropped
      ✗ scope files:write was not in the token exchanged
      ~ expires 20m sooner
      i https://acme.okta.example → https://api.acme.example
          audience
      = kept  ~ narrowed  - dropped  + added  ✗ widened (violation)
```

Every signature is fine. The planner dropped `files:write`, and the research agent's token has it back. `check` evaluates every rule on every link instead of stopping at the first failure, so a chain with three faults shows all three.

Note the bracket on that finding. RFC 8693 does not define how to check a bundle of exchanged tokens against each other, so J7 to J10 are my rules, and the output says so.

The same question from the command line:

```text
$ whosent ask tokens.json --trust trust.json --audience https://api.acme.example --at 2026-09-12T08:01:00Z --scope files:write
DENIED (HYPOTHETICAL): the chain does not verify, so it permits nothing. Hypothetically, if it verified, the token would hold this

! the first token held files:write, token 1 dropped it, and re-adding it later does not bring it back

  link by link
  0  chat-ui                      holds
  1  planner-agent                lacks  token 1 does not hold files:write
  2  research-agent               holds
```

The research agent's token does hold `files:write`. whosent still says no, and says which link lost it. On a chain that verifies with every key, the answer is `AUTHORITATIVE` instead.

## The issuer's word is not a verified hop

One access token with nested `act` claims looks like a chain, but the prior actors are just what the issuer wrote (RFC 8693 section 4.1). whosent draws them that way:

```text
✅ VALID: every checkable rule holds, but 2 prior actors are the issuer's word, not verified hop by hop

  #  issuer → subject                   J1 J2 J3 J4 J5 J6 J7 J8 J9 J10 J11 J12
  0  alice@acme.example → chat-ui        ·  ·  ·  ·  ✓  ·  ·  ·  ·   ·   ·   ·   (asserted by the issuer, not verified)
  1  chat-ui → planner-agent             ·  ·  ·  ·  ✓  ·  ·  ·  ·   ·   ·   ·   (asserted by the issuer, not verified)
  2  planner-agent → research-agent      ✓  ✓  ✓  ✓  ✓  ·  ·  ·  ·   ·   ·   ·
```

If the token carries actor proofs (draft-mcguinness-oauth-actor-proofs) or an Actor Chain profile (draft-mw-oauth-actor-chain-03), and the actors' own keys are in the trust file, each hop becomes the actor's own signed word. A forged one fails:

```text
  ✗ J11 link 1: proof 1 (planner-agent): the signature does not verify against actor-planner-agent.json kid planner-agent-2026 [draft-mcguinness-oauth-actor-proofs-01 section 7; whosent fails the token on a rejected chain, where the draft only drops the evidence]
```

Drop the keys and nothing turns green. The same `okta-style` token without `--trust`:

```text
⚠️  INCOMPLETE: nothing failed, but some rules were not checked, so nothing is vouched for
...
  ? J2 link 2: no keys for issuer "https://acme.okta.example"; pass --jwks https://acme.okta.example=PATH [RFC 7515 section 5.2]
```

That exits `2`. VALID is `0`, INVALID is `1`, and `--strict` turns INCOMPLETE into `1` for CI. Keys only come from what you pass; a JWT's `jku`, `x5u`, `x5c` and `jwk` are ignored.

## Four formats, one view

| Format | One link is | Checked against |
| --- | --- | --- |
| JWT (`act`, ID-JAG, Txn-Tokens, Entra agent tokens) | a token or an `act` level | RFC 8693, the two actor drafts, whosent's bundle rules |
| Biscuit | a block | the spec's 38 sample tokens; Datalog evaluator is whosent's own |
| UCAN 1.0 | a delegation or the invocation | the spec's 1.0.0 fixtures |
| Macaroons (libmacaroons, Fly.io `FlyV1`) | a caveat | go-macaroon or superfly/macaroon, on every run |

The macaroon cross-check is live: if whosent and the reference library disagree on a token, it exits `70` and asks you to report it.

A UCAN that widens its command looks like this:

```text
❌ INVALID: the chain breaks at link 1, and no authority reaches below it
...
Findings
  ✗ U6 link 1: /msg is not under /msg/send, which the delegation above granted [https://github.com/ucan-wg/spec#command]
```

In the TUI, `t` opens a timeline of every link and `←` `→` move the clock, so you can watch a block or a delegation expire, `x` simulates revoking a link (Biscuit and UCAN, labelled as simulated and never fed to `check`), and `a` asks the same question as `whosent ask`, prefilled from the row you selected.

## Where it came from

whosent started as a viewer for [mandatum](https://dev.to/kanywst/mandatum-making-an-ai-agents-authority-a-chain-you-can-verify-1hoa), my own delegation format. Two days in, I dropped that format and kept the four that agents actually carry. mandatum is archived now. The viewer turned out to be the useful part.

Source and issues: <https://github.com/kanywst/whosent>
