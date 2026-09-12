---
title: I Made Four Authorization Engines Answer the Same Questions
published: false
description: 'Cedar, OPA/Rego, Casbin and a Zanzibar-style ReBAC model, given identical rules and every possible request, with the disagreements drawn on screen. Runs entirely in the browser.'
tags:
  - showdev
  - authorization
  - security
  - webassembly
series: ShowDev
id: 4637146
---

"Which authorization engine should I use" always gets answered with a table. Cedar is analyzable, Rego is expressive, Zanzibar is relationship-based. I could never feel the difference from any of it.

So I gave four of them the same rules and ran every possible request through all four at once.

- **Live demo:** [https://0-draft.github.io/authz-playground/](https://0-draft.github.io/authz-playground/)
- **Repo:** [0-draft/authz-playground](https://github.com/0-draft/authz-playground)

![The divergence map](https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/authz-playground/map.png?v=0d6c7044)

One square is one request, one row per engine, filled means allowed. Pink is where they disagree.

## Where it breaks

The page adds one rule at a time. The owner can edit. Folder admins too. Then: only during business hours.

That third one is where ReBAC stops keeping up. `check(user, relation, object)` has three arguments and none of them holds a clock, so it goes on allowing edits at 3am while the other three deny them. Eight of 72 requests split.

That gap is why OpenFGA later added Conditions. Their announcement names time of day as the example relationships handle badly.

The same rules side by side are worth as much as the decisions:

![The same requirements in four languages](https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/authz-playground/proj.png?v=7c8e686d)

Add a document and Casbin needs its policy table regenerated, while ReBAC just gains a tuple and the model never moves.

## Two bugs worth confessing

The projections are where I could lie without noticing, so they get checked twice: all four engines run every request and any disagreement is reported, and a separate implementation written from the requirement text alone checks they are not all wrong together.

Both earned their keep.

I gave the ReBAC model `viewer: owner or editor`, because obviously an editor can read too. The requirements never said that. Disagreements doubled and the comparison was quietly dishonest until the harness flagged it.

Worse, the request enumeration sampled 03:00, 10:00, 14:00 and 22:00, so neither edge of the business-hours window was ever evaluated. I moved one engine's window to 08:00-19:00 to see what would happen. All fourteen tests passed. The suite that existed to protect the comparison could not see the one boundary the whole thing rests on.

## How it runs

No backend. Cedar through its official wasm bindings, Casbin's TypeScript build, and about a hundred lines reimplementing the Zanzibar check algorithm. Rego is OPA itself compiled to `js/wasm`, so policies are compiled and evaluated live: 8 MB gzipped, loaded lazily, roughly 2 ms per evaluation after the first.

If you try that last one, restrict the builtins. I shipped the default set, which left `http.send` reachable from pasted Rego. It fired a request from the visitor's browser and deadlocked the Go runtime for the rest of the session.

Have a go at stage 3 and drag the hour slider: [0-draft.github.io/authz-playground](https://0-draft.github.io/authz-playground/)
