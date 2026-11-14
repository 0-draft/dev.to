---
title: 'Why Hackers Don''t Get Caught: A Sourced Visual Explainer, Layer by Layer'
published: true
description: 'A bilingual site that shows what each observer on the path can read, why so many named attackers are never arrested, and which layer gave way in 31 documented cases. Every claim has a source.'
tags:
  - showdev
  - security
  - privacy
  - tor
series: ShowDev
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/why-hackers-dont-get-caught/cover.png?v=c7e398ff'
id: 5038058
---

In February I wrote [Anonymity Technology: The 5 Layers of Defense](https://dev.to/kanywst/anonymity-technology-the-5-layers-of-defense-1ad9). It treated "not getting caught" as a technical problem: hold every layer, make no mistakes.

When I went back to the court filings to build this site, two things looked different. The people who were caught mostly slipped somewhere boring, years before it mattered. And a lot of the people who weren't caught aren't anonymous at all. They are named, charged, and living where no court will hand them over.

- Source: <https://github.com/0-draft/why-hackers-dont-get-caught>
- Site: <https://0-draft.github.io/why-hackers-dont-get-caught/> (English, and Japanese at `/ja/`)

![Three endings: never identified, identified but out of reach, and caught](./assets/why-hackers-dont-get-caught/endings.png?v=5fdb18b8)

## Who can see what

The home page opens with one figure. Pick a route (direct, VPN, Tor, VPN then Tor, Tor while logged in) and pick observers on it. The record below shows which fields each one can read: sender address, destination, content, timing, account. A black bar is hidden, a highlighter is readable, magenta points at the person.

![The who-can-see-what figure with Tor selected and the guard and exit relays chosen as observers: linkable by timing](./assets/why-hackers-dont-get-caught/vantage.png?v=487bb8c3)

The verdict comes from a small model in `src/lib/vantage.ts`. "Identified" means one observer sees both who and what. "Linkable by timing" means one holds the sender, another holds the destination, and both see timing. I ran it directly with Node against the cloned repo:

```text
VPN                observers=vpn          -> Identified
Tor                observers=guard        -> Not linkable
Tor                observers=guard+exit   -> Linkable by timing
Tor, logged in     observers=site         -> Identified
VPN, then Tor      observers=vpn          -> Not linkable
VPN, then Tor      observers=vpn+exit     -> Linkable by timing
Tor                observers=global       -> Linkable by timing
```

The first four are the presets under the figure. The default state is the third one, so the page makes its point before anyone clicks: two Tor relays that each see half the picture can be joined by timing. The fourth is the one most cases look like. The network layer did its job and the person signed in to their own account.

The addresses in the record are from the RFC 5737 documentation ranges, so nothing on the page names a real host.

## Seven layers

Behavior, identity, device, network, infrastructure, money, attribution. Each chapter says what the layer hides, how it gives way, and the common misconceptions, with drawn figures. The chapters open in a key-points view (headings, first paragraphs, figures, misconceptions in full) and one switch brings up the full text.

The identity chapter rebuilds the Ulbricht graph from the criminal complaint. In my February article I gave Silk Road a VPN timing story. The complaint is plainer: in October 2011 the Bitcoin Talk account that had promoted Silk Road posted a hiring ad asking for replies to `rossulbricht at gmail dot com`. That one post joins two clusters. How the FBI found the server is still disputed, and the case file says so instead of picking a side.

## Named, never arrested

The essay "Named, never arrested" counts ten US indictments from 2014 to 2025 of people hacking for, or on behalf of, a state: 60 names, 58 different people. As far as the public record shows, not one state officer among them has been arrested. Russia's constitution (Article 61) and China's Extradition Law (Article 8) both bar handing over their own nationals.

The people in the essay who did end up in an American court mostly travelled. Seleznev in the Maldives, Nikulin in Prague, Klyushin in Switzerland. Seleznev and Klyushin were later sent back to Russia in the August 2024 prisoner exchange.

"Never arrested" is inferred from the absence of any later DOJ announcement of an arrest, extradition or plea. The page states that method under the figure.

## Case files

31 documented cases, sorted onto one bar per layer by where investigators got through first:

![31 case files sorted by the layer that gave way first: money 8, network 6, infrastructure 6, identity 5, behavior 3, device 1, attribution 1, people 1](./assets/why-hackers-dont-get-caught/cases.png?v=d324280b)

Money is the biggest bar. Most of those are coins that eventually reached an exchange account in someone's own name. Each line opens to a background, the mechanism, the outcome, and the sources. Nine of the 31 carry a "disputed" block, where the public accounts disagree or the key detail comes from a researcher's blog rather than a filing.

The timeline is the figure I keep going back to. It puts the slip and the arrest on one axis:

![Timeline of when each slip happened and when the person was arrested or charged](./assets/why-hackers-dont-get-caught/timeline.png?v=04dde98e)

Vyacheslav Penchukov announced his daughter's birth, with her name and birth weight, in a crew chat in July 2009. The FBI later got those logs from the crew's chat server in Brooklyn. He was arrested in Geneva in October 2022. The reused email addresses that named Mikhail Matveev were nearly 14 years old by the time he was charged.

## Keeping it honest

Most of the CI checks the citations:

| Check | What it does |
| --- | --- |
| `pnpm validate:data` | every citation resolves, every source is cited, EN and JA chapters have the same sections, figures and citations, no Japanese left in English |
| `pnpm test` | Vitest on the observer model, i18n and the MDX parity helper |
| `pnpm test:e2e` | Playwright on desktop and mobile, axe (WCAG 2.1 AA), no horizontal scroll |
| `sources.yml` | weekly check of every source URL, one issue kept open for dead ones |
| `claude-review.yml` | PR review for claims against sources, scope, and EN/JA meaning |

The git log is mostly fixes of the form "cite the DOJ plea release for Penchukov" and "Benthall was arrested on 5 November 2014, not the day of the announcement".

## What it isn't

The site explains mechanisms and failure modes. It is not a setup guide and has no operational advice. If a page says something a source contradicts, open an issue with the page and the source.

Source and issues: <https://github.com/0-draft/why-hackers-dont-get-caught>
