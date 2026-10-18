---
title: 'identity-deep-dive: A Daily, Scored Radar for OAuth WG, WIMSE, and OpenID Specs'
published: false
description: 'Following OAuth WG, WIMSE, and the OpenID Foundation by hand means checking Datatracker, mailing lists, and dozens of GitHub repos. identity-deep-dive collects all of it every day, scores each draft and repo with an explainable rubric, and publishes the ranked result as a static site.'
tags:
  - showdev
  - oauth
  - security
  - identity
series: ShowDev
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/identity-deep-dive-radar/cover.png?v=0e583817'
date: '2026-11-13T00:00:00Z'
id: 4869711
---

## Introduction

If you work on identity, the specs move under you. An OAuth WG draft enters Working Group Last Call, a WIMSE draft gets a new revision, an OpenID repo suddenly has a burst of PRs. Each of those is a signal that "now is the time to read this", but the signals are spread across IETF Datatracker, the mail archive, and about ninety GitHub repositories (65 under `openid`, 20 under `oauth-wg`, and 6 under `ietf-wg-wimse` on the day I checked).

I kept missing them, so I built **[identity-deep-dive](https://github.com/0-draft/identity-deep-dive)**: a pipeline that collects those sources every day, scores what it finds, and publishes the ranking at **[0-draft.github.io/identity-deep-dive](https://0-draft.github.io/identity-deep-dive/)**.

## Links

- **Site:** [0-draft.github.io/identity-deep-dive](https://0-draft.github.io/identity-deep-dive/)
- **Repository:** [0-draft/identity-deep-dive](https://github.com/0-draft/identity-deep-dive)

## What it tracks

| Track | Scope | Sources |
| --- | --- | --- |
| IETF WIMSE | Workload Identity in Multi System Environments | Datatracker, Mail Archive, GitHub |
| OAuth WG | OAuth Working Group drafts and their repos | Datatracker, Mail Archive, GitHub |
| OpenID | OpenID Foundation specifications and repos | GitHub |

## How it works

Every track runs the same four-stage pipeline from a GitHub Actions cron:

```text
Collect  ->  Normalize  ->  Score  ->  Report
  raw API       JSON         ranked      daily/weekly
  snapshots     merge        backlog     markdown
```

1. **Collect** pulls from Datatracker, the IETF mail archive, and the GitHub API.
2. **Normalize** merges the sources into one `state.json` per track.
3. **Score** ranks every draft or repo with weights that live in YAML, not code.
4. **Report** writes daily and weekly Markdown, and an Astro site renders the latest snapshot.

## Explainable scoring

The part I care about most is that every score explains itself. Here is the OAuth WG rubric, abridged from `tracks/oauth-wg/config/scoring.yaml`:

```yaml
lifecycle_points:
  - { match: "In Last Call",    points: 80 }
  - { match: "In WG Last Call", points: 70 }
  - { match: "IESG Evaluation", points: 70 }
  - { match: "WG Document",     points: 20 }

recency_points:
  - { within_days: 3,  points: 25 }
  - { within_days: 7,  points: 18 }
  - { within_days: 30, points: 8 }

activity:
  cap_points: 30
```

And here is the top candidate from the 2026-10-13 run, straight from `candidates.json`:

```json
{
  "draft_name": "draft-ietf-oauth-attestation-based-client-auth",
  "score": 125,
  "reasons": [
    "lifecycle: In WG Last Call (+70)",
    "updated within 3 days (+25)",
    "repo activity: 33 (+30)"
  ]
}
```

A draft in WG Last Call that was revised in the last three days and has an active repo is exactly the thing worth reading today, and the reasons say why it ranked first. If the weights feel wrong for your interests, you change the YAML, not the scorer.

## What one daily run looked like

These numbers are a single snapshot, the 2026-10-13 run, so they will have moved by the time you read this. The site always shows the latest run. That day the three tracks reported:

- **OAuth WG:** 11 active drafts. The top three were `attestation-based-client-auth` (125), `rfc7523bis` (90), and `sd-jwt-vc` (83).
- **WIMSE:** 8 active WG drafts, 16 related drafts, 68 mailing-list posts scanned. The newest WG draft was `draft-ietf-wimse-aims-00` (AI Identity Management System).
- **OpenID:** 65 public repos, 172 open PRs, and 1,521 open issues across the org. The top focus repo was `openid/authzen`.

## From radar to deep dive

The ranking is only the first half. When something crosses the threshold, the repo has templates for a deep dive (context, spec notes, an interop checklist, and a hands-on log), so reading a spec ends with notes I can return to instead of a closed browser tab. The first one, written in April 2026, covers [`draft-ietf-oauth-v2-1`](https://github.com/0-draft/identity-deep-dive/tree/main/tracks/oauth-wg/deep-dives/draft-ietf-oauth-v2-1). If WIMSE itself is new to you, I wrote a [WIMSE deep dive](https://dev.to/kanywst/wimse-workload-identity-in-multi-system-environments-deep-dive-standardizing-identity-5a12) earlier.

## Conclusion

If you follow OAuth, workload identity, or OpenID specs, the site gives you a ranked "what moved today" view without opening Datatracker. If a source or working group you care about is missing, issues and PRs are welcome: adding a track starts from `templates/new-track/`.
