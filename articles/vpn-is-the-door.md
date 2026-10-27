---
title: 'Ransomware in Japan: 61 of 92 Known Entry Points in 2025 Were VPN Appliances'
published: true
description: Japan's National Police Agency asked ransomware victims how the attacker got in. 61 of the 92 that knew named their VPN appliance; email accounted for two. I built a site that draws that on a floor plan and follows it through real cases and 31 exploited VPN flaws.
tags:
  - showdev
  - security
  - ransomware
  - vpn
series: ShowDev
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/vpn-is-the-door/cover.png?v=bbe4d321'
id: 4929020
date: '2026-10-27T14:47:29Z'
---

Japan's National Police Agency surveys ransomware victims about how the attacker got in. In 2025, 92 could say. 61 named their VPN appliance. Two named email.

Most security training is still about email. I built a site that shows where the intrusions actually started.

- Site: <https://0-draft.github.io/vpn-is-the-door/> (Japanese: <https://0-draft.github.io/vpn-is-the-door/ja/>)
- Source: <https://github.com/0-draft/vpn-is-the-door>

![Floor plan of a fictional company with one square per case stacked outside each opening: 61 at the VPN door, 19 at the remote desktop window, 10 at the loading door, 2 at the main entrance](https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/vpn-is-the-door/home-floor-plan.png?v=449f97c0)

One square per case, stacked outside the opening the attacker used.

## One company, drawn as a floor plan

The site follows a fictional 280-person parts maker. Email comes in through the main entrance and gets checked at reception. The VPN appliance is a door in the outer wall that lets staff in without passing reception; it opens into the corridor behind it.

## What happens after the door opens

[Chapter 2](https://0-draft.github.io/vpn-is-the-door/after-the-door/) is a scroll-driven plan: the door opens, Active Directory falls, backups are deleted, data leaves through the same door, and encryption comes last.

![Chapter 2 on desktop: step text on the left, the plan on the right with the route from the VPN door to the backup room](https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/vpn-is-the-door/scrolly-desktop.png?v=ce7699ca)

In 2025, 79 of the 99 Japanese victims that tried to restore from backup could not, and 48 found their backups encrypted too. The chapter also maps the published investigation report of an Osaka hospital onto the same steps.

## 31 exploited VPN flaws

[Chapter 3](https://0-draft.github.io/vpn-is-the-door/the-doors/#fig-3-7) lists 31 VPN and remote-access flaws from CISA's Known Exploited Vulnerabilities catalog (FortiGate, Ivanti Connect Secure, Citrix NetScaler, Palo Alto GlobalProtect, SonicWall and others). Selecting a row shows which part of the door it breaks.

![The door schedule: a detail drawing of the door on the left, Fortinet CVEs listed on the right](https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/vpn-is-the-door/door-schedule.png?v=809cfdce)

- 29 of the 31 are reachable before login, so MFA never comes into play.
- 19 were exploited before the vendor warned anyone.
- For 17, patching alone did not close the door: stolen credentials or sessions stayed valid, or the intruder's implant survived the update.

## Where each control actually helps

The last figure in [chapter 6](https://0-draft.github.io/vpn-is-the-door/what-to-do/#fig-6-5) lets you pick how the attacker gets in and which controls are on, then shows where the route stops.

![Phone view with a pre-auth flaw selected and MFA plus offline backup on: backups survive, but the leak and encryption still happen](https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/vpn-is-the-door/sandbox-phone.png?v=3d73041e)

MFA does nothing against a pre-auth flaw. An offline backup lets you recover from encryption but does not stop the leak.

## Cases, in the organizations' own words

[Chapter 4](https://0-draft.github.io/vpn-is-the-door/cases/) has 15 real incidents, including Asahi Group, ASKUL, three Japanese hospitals and Colonial Pipeline. Each is based only on the organization's own statement or an official investigation report. If an organization wrote "network device", the page says "network device". Nine of the 15 name a VPN appliance.

## How the numbers were checked

- NPA figures come from NPA's own statistics workbooks, sheet by sheet. Percentages are computed in one place and unit-tested against NPA's published roundings.
- Every KEV field was checked with `jq` against the catalog JSON; the 2026-numbered CVEs were also checked against the NVD API.
- Anything not confirmed in a primary source is left out. The 79 cited documents are listed on the [sources page](https://0-draft.github.io/vpn-is-the-door/sources/).

No exploit code or attack steps appear anywhere.

## How it's built

Astro 7, static, on GitHub Pages. No UI framework; the interactive figures are plain TypeScript. The floor plan is data, and a test fails if the intruder's route crosses a wall anywhere but a doorway. Search is Pagefind, and the OG images are drawn at build time with satori. CI runs axe, a link check that includes `#fragments`, and a Lighthouse budget. A weekly job compares the door schedule with the live KEV catalog.

If a number or attribution is wrong, open an issue with the source that shows it.
