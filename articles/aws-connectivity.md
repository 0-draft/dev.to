---
title: 'AWS Connectivity: Every Road From Your Network Into AWS, on One Map'
published: false
description: 'A bilingual explainer site that puts VPN, Direct Connect, SD-WAN, the AWS hubs, PrivateLink and hybrid DNS on one road map, with labs that run the documented rules: route selection per hub, quotas as you scale, Tokyo prices, MTU.'
tags:
  - showdev
  - aws
  - networking
  - cloud
series: ShowDev
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/aws-connectivity/cover.png?v=113d0034'
id: 5038049
---

Every AWS networking page I read was correct and covered one service. Site-to-Site VPN on one page, Transit Gateway on another, Cloud WAN on a third. None of them answered the question I actually had: with this office, these VPCs and this budget, which road do the packets take, and what does AWS do when there are two?

So I drew all the roads on one map and made each one drivable.

- Source: <https://github.com/0-draft/aws-connectivity>
- Site: <https://0-draft.github.io/aws-connectivity/> ([日本語](https://0-draft.github.io/aws-connectivity/?lang=ja))
- Direct Connect deep dive: <https://0-draft.github.io/aws-connectivity/direct-connect/>

![The AWS Connectivity map: every road from your network into AWS, here stepping a packet over Site-to-Site VPN, with a note that ESP wrapping drops the inner MTU to 1446](./assets/aws-connectivity/map.png?v=03d30f65)

The map at the top carries the internet, VPN, Direct Connect, SD-WAN, people (Client VPN and friends), PrivateLink, hybrid DNS and Outposts. Pick a road and step a packet along it, hop by hop. Below that are 18 exits, one per topic. Each lab asks you to predict what AWS will do before it shows you.

This used to be two sites, `on-ramp` (the map) and `cross-connect` (Direct Connect only). On 2026-11-08 I merged them into one repo with two pages, so the map's Direct Connect exit is a summary that links into the deep dive instead of repeating it. The old URLs no longer serve.

## Same routes, three hubs, three answers

This is the lab I built the site for. You advertise the same prefix over Direct Connect and a BGP VPN, then switch the hub that receives them.

![The path selection lab on Cloud WAN: DX advertises 10.0.0.0/16 with AS_PATH 3, VPN 1 advertises the same /16 with AS_PATH 1, and the ladder shows DX knocked out at "Shortest AS_PATH", so the result is VPN 1](./assets/aws-connectivity/path-selection.png?v=b784d311)

The ladder is a pure function, `decide(hub, dst, adverts)` in `src/features/routing/engine.ts`, encoded from each hub's documented evaluation order. I ran it directly against two scenarios:

```text
# DX prepended x3 vs BGP VPN, same /16, dst 10.0.1.5
vgw       winner=dx steps=type:-vpn
tgw       winner=dx steps=type:-vpn
cloudwan  winner=vpn steps=aspath:-dx
# static VPN backup, DX not prepended
vgw       winner=dx steps=type:-vpn
tgw       winner=vpn steps=type:-dx
cloudwan  winner=dx steps=unsupported:-vpn
```

First block: a virtual private gateway and a Transit Gateway compare route type before AS_PATH, so DX wins no matter how much you prepend. Cloud WAN compares AS_PATH and MED first and route type last, so the prepend works and the VPN takes the traffic. If you move from TGW to Cloud WAN and keep your old prepend habits, your primary path changes.

Second block: the "backup" VPN is static. On a VGW, DX still wins. On a Transit Gateway, a static VPN route is a static route, and static beats every propagated route, DX included. Your backup is now the primary. On Cloud WAN the question doesn't come up, because a static VPN can't attach at all.

The other presets cover a VPN that steals a more specific /24, DX going down (and the 90-second BGP hold timer if you have no BFD), and ECMP across two VPNs, which a VGW never does.

## Where each hub design runs out

The Hubs exit has a scale lab: VPCs, Regions and sites on sliders, four designs side by side. Same input to `plan()` in `src/features/hubs/scale.ts`, 40 VPCs across 3 Regions from 4 sites:

```text
vgw       hubs=40 attach=40 vifs=160 interRegion=0 reachesAll=false $0/mo
   HARD A private VIF attaches to a VGW in the same Region only: VPCs in other Regions are unreachable this way.
   soft More than 5 VGWs in a Region (default quota, adjustable).
dxgw      hubs=42 attach=40 vifs=8 interRegion=0 reachesAll=true $0/mo
   HARD 20 VGWs per DX gateway (hard): you need 2 DX gateways and a VIF from every site to each.
   soft More than 5 VGWs in a Region (default quota, adjustable).
   HARD Each VPC route table takes at most 100 propagated routes from its VGW (hard), however many prefixes the VIF accepts.
tgw       hubs=4 attach=43 vifs=4 interRegion=3 reachesAll=true $2351/mo
   soft 3 Transit Gateway peerings between Regions, static routes only: no automatic failover between Regions.
cloudwan  hubs=4 attach=41 vifs=4 interRegion=0 reachesAll=true $3789/mo
   soft Every core network edge bills $0.50/hour in every Region, traffic or not.
```

The dollar figures are hub charges only (attachment-hours or core network edges, Tokyo list price, 730 hours). The free designs are free because they hit hard quotas or leave VPCs unreachable. That trade is what I wanted on one screen.

## Toll booths

The Cost exit prices each road for one month of traffic from Tokyo to your data center. At 5,000 GB, no Transit Gateway:

```text
internet     $570
internetNat  $925.26
vpn          $605.04
hosted50m    $226.17
hosted500m   $343.7
hosted1g     $434.22
dx1g         $413.05
dx10g        $1768.66
flat10g      $8000.8
```

A 1 Gbps dedicated port pays for itself against the internet's first tier ($0.114/GB vs DX's $0.041/GB) at about 2,850 GB a month. A 50 Mbps hosted connection breaks even at about 290 GB. Not included: tax, the carrier circuit, colocation and partner fees.

## MTU

The MTU exit has a header inspector and a packet-size lab. What happens to a 1500-byte and a 9001-byte packet with DF set, per path, from `src/features/mtu/mtu.ts`:

```text
internet     mtu=1500 mss=1460 pmtud=yes clamp=false 1500=>fits 9001=>pmtud
vpnGcm       mtu=1446 mss=1406 pmtud=no clamp=tgw 1500=>blackhole 9001=>blackhole
vpnCbc       mtu=1406 mss=1366 pmtud=no clamp=tgw 1500=>blackhole 9001=>blackhole
privateVif   mtu=9001 mss=8961 pmtud=undocumented clamp=false 1500=>fits 9001=>fits
transitVif   mtu=8500 mss=8460 pmtud=no clamp=true 1500=>fits 9001=>blackhole
connect      mtu=1476 mss=1436 pmtud=undocumented clamp=false 1500=>unknown 9001=>unknown
privatelink  mtu=8500 mss=8460 pmtud=no clamp=true 1500=>fits 9001=>blackhole
```

On a VPN that 1500-byte packet is dropped silently and the connection hangs. A Transit Gateway clamps the TCP MSS for you; a VGW is not documented to. Jumbo frames that work on a private VIF (9001) blackhole on a transit VIF (8500).

## Direct Connect, up close

The second page drives one road part by part: the physical path from your router through the cage and cross connect to the DX router, LOA-CFA ordering, LAG members and MACsec (`should_encrypt` vs `must_encrypt`), VIF types, the DX gateway's allowed-prefix lab, a BGP lab with `7224:7x00` communities that warns when your outbound choice disagrees with AWS's inbound one, a failure lab for the four resiliency models, a price estimator, and a glossary with the official English and Japanese console names.

## How it is kept honest

Every number on the site traces to a research note in [`docs/`](https://github.com/0-draft/aws-connectivity/tree/main/docs), each with links to the AWS documentation, What's New post or Price List API entry it came from. Facts were verified on 2026-10-10 (2026-10-12 for the deep dive), and prices, quotas and launches re-checked on 2026-11-09. A workflow opens a monthly issue to do that again.

The logic behind each lab (path selection, scale, cost, MTU, resiliency, LAG) is plain TypeScript with Vitest tests next to it. `npx vitest run` passes 244 tests. CI also runs Playwright with axe WCAG 2.2 AA checks on desktop and phone, in English and Japanese, light and dark.

It is an independent explainer, not affiliated with AWS. Prices and quotas move; check the docs before you buy a circuit.

If a number on it is wrong or stale, open an issue: <https://github.com/0-draft/aws-connectivity/issues>
