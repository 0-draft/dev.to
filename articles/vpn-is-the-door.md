---
title: "The door was the VPN: why ransomware in Japan comes in through VPN appliances"
published: false
description: "In 2025, 61 of the 92 Japanese ransomware victims that could say how the attacker got in named their VPN appliance. I drew the reasons as a break-in investigation report."
tags: ["showdev", "security", "ransomware", "vpn"]
series: ShowDev
cover_image: "https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/vpn-is-the-door/cover.png"
---

## Introduction

Japan's National Police Agency (NPA) asks every ransomware victim it handles how the attacker got in. In 2025, 92 victims could answer. 61 of them named their VPN appliance (66.3%). 19 named remote desktop. Email accounted for two.

Most security awareness material still starts with phishing email. The numbers point somewhere else, so I built a site that explains why the VPN appliance is the door, with every number traced back to a primary source.

**Read it:** [The door was the VPN](https://0-draft.github.io/vpn-is-the-door/) (Japanese: [扉はVPNだった](https://0-draft.github.io/vpn-is-the-door/ja/))

## Links

- **Site:** <https://0-draft.github.io/vpn-is-the-door/>
- **GitHub Repository:** [0-draft/vpn-is-the-door](https://github.com/0-draft/vpn-is-the-door)

## How it is put together

The site is drawn as a break-in investigation report about one fictional company, Minato Precision Co., Ltd., 280 staff, shown as an architectural floor plan. The VPN appliance is a door in the outer wall that lets staff in without passing reception. Every chapter returns to the same drawing.

Depth is marked the way architectural drawings mark it, by scale:

| Scale | Reader | What changes |
| --- | --- | --- |
| `S=1:500` | Executives | The building and its openings. Plain words, one decision per section. |
| `S=1:100` | IT managers | Rooms, the intruder's route, what the IT team would see. |
| `S=1:5` | Engineers | The door cut open. Real component names, ATT&CK IDs, advisories, logs. |

The chapters follow the order of an incident:

1. **Where they came in**: what the NPA counted, each opening in turn, 2021 to 2025.
2. **After the door opens**: a scroll-driven plan of the route from the door to encryption. In 2025, 79 of 99 victims that tried to restore from backup could not; in 48 the backups themselves were encrypted.
3. **The doors**: a filterable schedule of 31 KEV-listed vulnerabilities in VPN appliances from seven vendors (FortiGate, Ivanti Connect Secure, Citrix NetScaler, SonicWall and more).
4. **Cases**: 15 incidents where the organization itself, or an official report, said how the attacker got in. Nine name a VPN.
5. **For engineers**: what an SSL-VPN answers before login, why a patch does not evict an intruder (31 of 71 victims said their entry device was fully patched), and which evidence a reboot erases (only 25 of 102 victims kept all logs).
6. **What to do**: actions by owner, and a sandbox where each control cuts the intruder's route only at the point where it actually works. MFA stops a stolen password at the door and does nothing against a pre-auth flaw.

## What every number rests on

- NPA statistics come from the NPA's own statistical workbooks (`*_jousei_data.xlsx`), cited by sheet name. Percentages are computed in one place and unit-tested against the NPA's published roundings.
- Vulnerabilities were checked field by field against the CISA Known Exploited Vulnerabilities catalog. KEV's "Unknown" ransomware flag is shown as unknown, never as "no". A weekly job diffs the site's list against the live catalog.
- Incidents come only from the organization's own statements or official investigation reports. Where an organization said "network device" without naming a VPN, the site says "network device".
- The fictional company is labelled as a composite wherever it appears and is never mixed into a real case.
- No exploit code, payloads or attack steps appear anywhere. Vulnerability classes are described conceptually and link to the vendor advisory.

## Built with

Astro, static output on GitHub Pages, English and Japanese with text parity checked in CI. Playwright and axe run on every page on desktop and mobile, and Lighthouse runs against performance budgets.

If you spot a number or a case that is wrong or out of date, please open an issue on the repository. Corrections with a primary source are the most useful contribution.
