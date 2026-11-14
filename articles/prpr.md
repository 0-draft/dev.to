---
title: prpr, a Terminal List of Every Open GitHub Pull Request I Can See
published: false
description: My open pull requests live under my own account, an org, and other people's projects. prpr puts all of them on one screen, opens one with enter, and waves goodbye when it merges.
tags: ["showdev", "github", "go", "tui"]
series: ShowDev
cover_image: "https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/prpr/cover.png?v=c3fc7ae2"
---

My open pull requests are spread out: my own repositories, the `0-draft` org, and upstream projects I send patches to. Review requests come from all three. GitHub's pulls page shows what I opened or was asked to review, but not everything open in the orgs I belong to, so checking meant a handful of tabs.

prpr is one terminal screen with all of it. Enter opens the pull request in the browser. When it merges, it leaves the list with a 🎉.

- Source: <https://github.com/kanywst/prpr>
- Install: `brew install kanywst/tap/prpr`, `scoop install prpr` (bucket `kanywst/scoop-bucket`), or `go install github.com/kanywst/prpr@latest`

![prpr walking through the list, opening the detail pane, filtering, switching tabs, and showing a merge banner](./assets/prpr/demo.gif?v=12699baf)

The recording runs `prpr --demo`, which serves a fixed fixture list instead of GitHub, so nobody's real account ends up in a GIF.

## No config

prpr reuses `gh auth login`, so there is no token to set up. At start it asks GitHub for your login and every org you are in, then runs one search per owner plus two more:

```text
is:pr is:open archived:false user:<owner>
is:pr is:open archived:false author:<you>
is:pr is:open archived:false user-review-requested:<you>
```

The last two catch your patches to other people's projects and review requests from orgs you are not in. Anything outside the watched owners goes in the `elsewhere` tab, next to all, mine, to review, drafts and bots. Dependabot and Renovate stay in bots unless one asks you for a review by name.

The searches run separately, four at a time, instead of OR-ed into one query. An org that enforces SAML SSO your token is not authorized for then costs only its own pull requests: it is named in the header and the rest of the list stays up.

A config file exists for when you want something else (`owners`, `exclude_owners`, `interval`, `issues`). Unknown keys are an error, so a typo does not silently do nothing:

```text
$ prpr --config config.yaml
prpr: config.yaml: yaml: unmarshal errors:
  line 2: field intervall not found in type config.Config
```

## Saying goodbye without lying

A pull request missing from a refresh is not necessarily merged, and several of the fix commits in the log are about that. The search that covers it may have failed, hit the 60-result cap, or come back partial because GitHub withheld nodes the token cannot read. Or it only dropped out of `user-review-requested` because I submitted my review.

prpr handles each case differently:

- a covering search failed: the pull request is carried over from the last refresh, no lookup
- a covering search was partial: carried over, and its state is looked up anyway, since a partial answer can repeat on every refresh and would otherwise pin a merged pull request to the list for good
- a covering search hit the cap: its state is looked up, and nothing is shown if it is still open
- only the review request held it: it leaves quietly
- otherwise: one GraphQL lookup asks how it ended, and the banner says so

```text
┃ 🌸 prpr  kanywst · 0-draft                                                             ⟳ 61s ┃
┃ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ ┃
┃ ▸ all 3  │  mine 2  │  to review 1  │  elsewhere 0  │  drafts 1  │  bots 0                   ┃
┃                                                                                              ┃
┃ ✨ 🎉 0-draft/api#127 fix: nil deref on empty body merged! nice one 🎊                       ┃
```

That is the repository's render test (`go test ./internal/ui -run TestDumpRender -v`) against its fixtures. A closed one gets 🌙, and one that only stopped matching the search gets 👋.

The last list is cached on disk, so prpr shows it instantly on start while the first refresh runs. Anything that merged while it was closed still gets its banner then.

## What else changes on the row

| Icon | Meaning |
| --- | --- |
| 🟢 / 🟡 / 🔴 / ⚪ | Checks passing / running / failing / none |
| ✅ / 🔁 / 👀 | Approved / changes requested / review requested |
| 💥 | Conflicts with its base branch |
| 🆕 | Joined the list since you last looked |
| 🔔 | Its checks, review or conflict state changed since you last looked |

🆕 and 🔔 clear once the cursor lands on the row, and both count what changed while prpr was closed. 🔔 compares the icon, not the raw state, so a change the row cannot show does not ring.

`/` filters by title, repository, author, `#number` and labels. `d` opens a detail pane with branch, diff stat, reviewers and body. `--issues` mixes open issues in as 🎫, and polling pauses while the terminal is not focused.

Source and issues: <https://github.com/kanywst/prpr>
