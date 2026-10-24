---
title: I Made Four Authorization Engines Answer the Same Questions
published: true
description: 'Cedar, OPA/Rego, Casbin and a Zanzibar-style ReBAC model, given identical rules and every possible request, with the disagreements drawn on screen. Runs entirely in the browser.'
tags:
  - showdev
  - authorization
  - security
  - webassembly
series: ShowDev
id: 4637146
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/authz-playground/cover.png'
date: '2026-09-12T07:11:35Z'
---

"Which authorization engine should I use" always gets answered with a table. Cedar is analyzable, Rego is expressive, Zanzibar is relationship-based. I could never feel the difference from any of it.

So I gave four of them the same rules and ran every possible request through all four at once.

- **Live demo:** [https://0-draft.github.io/authz-playground/](https://0-draft.github.io/authz-playground/)
- **Repo:** [0-draft/authz-playground](https://github.com/0-draft/authz-playground)

![One question, every engine, every hour of the day](./assets/authz-playground/day.png?v=47286c34)

One question, asked of every engine at every hour of the day. A raised line is allow. Red is where they disagree.

## Where ReBAC stops

The page adds one rule at a time. The owner can edit. Folder admins too. Then: only during business hours.

That third one is where ReBAC stops keeping up. `check(user, relation, object)` has three arguments and none of them holds a clock, so it goes on allowing edits at 3am while the other three deny them. Eight of 72 requests split.

That gap is why OpenFGA later added Conditions. Their announcement names time of day as the example relationships handle badly.

The playground now has that fix as a fifth row: the same Zanzibar model with an OpenFGA condition. The grant stays relational, and one more relation gates it:

```text
define within_hours: [user:* with business_hours]
define editor: (owner or admin from parent) and within_hours
```

It agrees with the other three on every request. It is still not free. A condition can only hang off a tuple, and business hours are about the request rather than any relationship, so every document needs a placeholder tuple whose only job is to carry the clock. The page rates it possible but forced, not native.

![The classic model and the conditional one, asked the same question at 08:00](./assets/authz-playground/graphs.png?v=09f1795d)

Add a document and Casbin needs its policy table regenerated, while ReBAC just gains a tuple and the model never moves.

## What broke

The projections are where I could lie without noticing, so they get checked twice: every engine runs every request and any disagreement is reported, and a separate implementation written from the requirement text alone checks they are not all wrong together.

Both earned their keep.

I gave the ReBAC model `viewer: owner or editor`, because obviously an editor can read too. The requirements never said that. Disagreements doubled and the comparison was quietly dishonest until the harness flagged it.

Worse, the request enumeration sampled 03:00, 10:00, 14:00 and 22:00, so neither edge of the business-hours window was ever evaluated. I moved one engine's window to 08:00-19:00 to see what would happen. All fourteen tests passed. The suite that existed to protect the comparison could not see the one boundary the whole thing rests on.

The fix was to sample both edges of the window and the hour either side of them, 08, 09, 17 and 18, plus a test that fails if any of those ever drops out of the enumeration. The 08:00-19:00 window now fails at once.

## How it runs

No backend. Cedar through its official wasm bindings, Casbin's TypeScript build, and about a hundred lines reimplementing the Zanzibar check algorithm. Rego is OPA itself compiled to `js/wasm`, so policies are compiled and evaluated live: 8 MB gzipped, loaded lazily, roughly 2 ms per evaluation after the first.

If you try that last one, restrict the builtins. I shipped the default set, which left `http.send` reachable from pasted Rego. It fired a request from the visitor's browser and deadlocked the Go runtime for the rest of the session.

Have a go at stage 3 and drag across the chart: [0-draft.github.io/authz-playground](https://0-draft.github.io/authz-playground/)
