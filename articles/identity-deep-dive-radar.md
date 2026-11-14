---
title: 'identity-deep-dive: A Weekly Briefing and a Sourced Spec Map for OAuth, WIMSE, and OpenID'
published: true
description: 'Following OAuth WG, WIMSE, and the OpenID Foundation by hand means checking Datatracker, mailing lists, and about ninety GitHub repos. identity-deep-dive collects all of it every six hours, has Claude explain what changed, and keeps a map of 62 specs where every support claim cites an official page.'
tags:
  - showdev
  - oauth
  - security
  - identity
series: ShowDev
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/identity-deep-dive-radar/cover.png?v=49664009'
date: '2026-11-13T00:00:00Z'
id: 4869711
---

## Introduction

If you work on identity, the specs move under you. An OAuth WG draft goes to the IESG, a WIMSE draft gets a new revision, an OpenID repo switches a protocol's JSON properties to snake_case. Each of those is a signal that "now is the time to read this", but the signals are spread across IETF Datatracker, the mail archive, and about ninety GitHub repositories (66 under `openid`, 21 under `oauth-wg`, and 6 under `ietf-wg-wimse` in the 2026-11-14 run).

I kept missing them, so I built **[identity-deep-dive](https://github.com/0-draft/identity-deep-dive)**. It collects those sources every six hours, explains what changed, and keeps a map of where each spec stands and who documents support for it. The result is a static site at **[0-draft.github.io/identity-deep-dive](https://0-draft.github.io/identity-deep-dive/)**, in English and Japanese.

## Links

- **Site:** [0-draft.github.io/identity-deep-dive](https://0-draft.github.io/identity-deep-dive/)
- **Spec map:** [0-draft.github.io/identity-deep-dive/map/](https://0-draft.github.io/identity-deep-dive/map/)
- **Repository:** [0-draft/identity-deep-dive](https://github.com/0-draft/identity-deep-dive)

## What it tracks

| Track | Scope | Sources |
| --- | --- | --- |
| IETF WIMSE | Workload Identity in Multi-System Environments | Datatracker, Mail Archive, GitHub |
| OAuth WG | OAuth Working Group drafts and their repos | Datatracker, Mail Archive, GitHub |
| OpenID | OpenID Foundation specifications and repos | GitHub |

## What the site shows

- **This week:** three to five changes worth five minutes, most important first, each with why it matters. In the 2026-11-14 run the top one was RFC 10070, which tightens the audience rules for JWT client assertions and assertion grants.
- **Where the specs stand:** the IETF drafts the tracks follow, grouped by Datatracker state, from individual draft through WG last call, the IESG and the RFC Editor queue.
- **Topics:** how the drafts and repositories group, for example "workload credentials and proof of possession" or "agent delegation and attenuation".
- **Per-track pages:** the daily and weekly reports, and an explanation for each new revision, thread or PR.

## How it works

Every track runs the same pipeline from a GitHub Actions cron:

```text
Collect  ->  Normalize  ->  Score  ->  Report  ->  Explain  ->  Synthesize
  raw API       JSON         ranked      daily/weekly   Claude       picks +
  snapshots     merge        backlog     markdown       briefing     topic map
```

1. **Collect** pulls from Datatracker, the IETF mail archive, and the GitHub API.
2. **Normalize** merges the sources into one JSON state per track.
3. **Score** ranks every draft or repo with weights that live in YAML, not code.
4. **Report** writes daily and weekly Markdown.
5. **Explain** finds what is new since the last run (a draft revision, a mailing-list thread, a PR) and has Claude explain it from the source material: a headline, a summary grounded in the diff or message, a diagram of the mechanism, and links to related items in the other tracks.
6. **Synthesize** reads the recent explanations across tracks and picks the week's changes and topics.

The material Claude reads is written by third parties, so the workflow treats it as untrusted. The model runs in a job with read-only repository access and read-only tools. A second job with write access has no model in it: it validates the output and only then commits it. Every explanation and pick also carries a Japanese version.

## Explainable scoring

The ranking explains itself. Here is the OAuth WG rubric, abridged from `tracks/oauth-wg/config/scoring.yaml`:

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

And here is the top candidate from the 2026-11-14 run, from `candidates.json`:

```json
{
  "draft_name": "draft-ietf-oauth-sd-jwt-vc",
  "score": 118,
  "reasons": [
    "lifecycle: IESG Evaluation (+70)",
    "updated within 7 days (+18)",
    "repo activity: 81 (+30)"
  ]
}
```

If the weights feel wrong for your interests, you change the YAML, not the scorer.

## A spec map where every claim has a source

The [spec map](https://0-draft.github.io/identity-deep-dive/map/) covers 62 OAuth, OpenID, workload identity and credential specs in 11 layers, from grants and flows to security events. Each card says where the spec stands and how it relates to the others: what it builds on, profiles, extends or replaces. Of the 62, 25 are RFCs, 11 are OpenID Final specifications, one comes from another body, and the rest are IETF drafts at various stages.

The part I care about most is the "documented support" list. A vendor or project is listed only when its own documentation, or a standards body's page naming it, says it supports the spec. Each of the 211 claims stores the official URL and an exact phrase from that page. A weekly job with no model in it fetches every page and checks that the phrase is still there. If it is gone, the site says "not re-verified since" with the date instead of quietly showing stale support. Experimental, alpha and beta support is counted separately as preview.

For example, [DPoP](https://0-draft.github.io/identity-deep-dive/map/dpop/) currently lists eight: Okta, Auth0, Keycloak, Duende IdentityServer, node-oidc-provider, Spring Authorization Server, Spring Security and Authelia's oauth2-provider.

Most specs on the map also have an explainer: when you reach for it, the problem it solves, how it works, what it requires and what to watch out for, with section references. For 17 RFCs there is a side-by-side page with the official English text next to an unofficial Japanese translation.

## From radar to deep dive

The ranking feeds deep dives. Once a week a job takes the top candidate in each track that has no deep dive yet, has Claude draft one from the source text (context, spec notes, an interop checklist and a hands-on log), and opens it as a draft pull request. Nothing lands until a person has checked it against the primary sources.

Reading that closely pays off. The [WIMSE HTTP signature deep dive](https://0-draft.github.io/identity-deep-dive/ietf-wimse/deep-dives/draft-ietf-wimse-http-signature/) records that `draft-ietf-wimse-http-signature-08` tells recipients to validate the workload identity token "as specified in Section 5.1.4" of the workload credentials draft, which has no Section 5.1.4 in either -02 or -03. Validation is Section 5.1.3 in -03. There are nine deep dives so far, including OAuth 2.1, SD-JWT VC, Client ID Metadata Documents and OpenID4VCI. If WIMSE itself is new to you, I wrote a [WIMSE deep dive](https://dev.to/kanywst/wimse-workload-identity-in-multi-system-environments-deep-dive-standardizing-identity-5a12) earlier.

## Conclusion

If you follow OAuth, workload identity, or OpenID specs, the site gives you "what moved this week" without opening Datatracker, and the map tells you where a spec stands and who documents support for it, with a link you can check yourself. If a source, a spec or an implementation you care about is missing, issues and PRs are welcome. A new support claim needs an official URL and the exact phrase from that page.
