---
title: 'S3 Atlas, Everything I Know About Amazon S3 on One Site'
published: true
description: 'An EN/JA site with 18 research chapters on Amazon S3, a cost calculator that prices one workload across every S3 class and 21 other services, 134 CLI recipes and 309 API operations.'
tags:
  - showdev
  - aws
  - s3
  - storage
series: ShowDev
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/s3-atlas/cover.png?v=ea55a2e4'
id: 5038064
date: '2026-11-14T21:50:30Z'
---

I wrote an [S3 deep dive](https://dev.to/kanywst/aws-s3-deep-dive-17f3) earlier this year. It was one article, and it kept growing questions it couldn't hold: what does this workload cost in Glacier Instant Retrieval versus R2, which `aws s3` commands delete things, who actually left S3 and why. So I kept going until it was a site.

- Source: <https://github.com/0-draft/s3-atlas>
- Live: <https://0-draft.github.io/s3-atlas/>

![S3 Atlas home page: the storage classes stacked as a water column, Express One Zone at the surface and Glacier Deep Archive at the bottom, with $/GB-month for each](./assets/s3-atlas/hero.png?v=95a1e6b0)

## Two halves, one source of truth

`docs/` has 18 chapters, about 15,000 lines per language. I researched them in Japanese and translated to English, and CI checks that every Japanese chapter has an English counterpart with the same number of headings. Each chapter ends with its references. Anything I could not confirm stays marked _unverified_ in the text; six of those marks are left in the English docs.

`data/` is the structured part, and the React app builds pages on it:

| Page | Data |
| --- | --- |
| Storage classes | 10 classes as layers of a water column |
| Cost calculator | every S3 class plus 21 other services |
| Competitors | 22 services: price sheet, feature matrix, profiles |
| Cases | 38 public cases, including Dropbox and 37signals leaving S3 |
| Timeline | 68 events, 2006-03-14 launch ($0.15/GB-month) to 2026-10-01 |
| Commands | 134 CLI, SDK and third-party recipes, 17 flagged destructive |
| API | 309 operations across S3, S3 Control, Tables, Vectors, Files, Outposts |

The header toggle switches every page, chapter and dataset to Japanese.

## The calculator

![Cost calculator with the 10 TB media library preset: Wasabi $82, Hetzner $98, Storj $108, Backblaze B2 $122, Cloudflare R2 $159 at the top, each bar split into storage, requests, retrieval and egress](./assets/s3-atlas/calculator.png?v=93b3c2ee)

It ignores free tiers for every provider so the comparison stays even. What it does not ignore is per-object overhead, which is where S3 class choice usually goes wrong. IA and Glacier Instant Retrieval bill anything under 128 KB as 128 KB. Glacier Flexible Retrieval and Deep Archive add 32 KB at the class price plus 8 KB at the Standard price for every object.

I ran the site's own `s3ClassCost` from `src/lib/cost.ts` against `data/` for 1 TB with 100k PUTs and 100k GETs, changing only the average object size:

```text
1 TB, 1024 KB average object
  S3 Standard                    $  24.09/month
  S3 Standard-Infrequent Access  $  13.90/month
  S3 Glacier Instant Retrieval   $   7.10/month
  S3 Glacier Deep Archive        $   6.27/month
1 TB, 16 KB average object
  S3 Standard                    $  24.09/month
  S3 Standard-Infrequent Access  $ 103.50/month
  S3 Glacier Instant Retrieval   $  35.77/month
  S3 Glacier Deep Archive        $  19.86/month
```

Same terabyte. At 16 KB objects, Standard-IA costs four times what Standard does.

Competitor rows carry their own catch where one exists. Wasabi wins the preset above at $7.99/TB-month with no egress or API fees, and its entry also lists the 90-day minimum, the 1 TB minimum charge, and the fair-use rule that egress stays free only while it is under what you store.

## Keeping it from going stale

Prices are us-east-1 list prices, checked against the AWS Price List API and vendor pricing pages as of 2026-10-03, and each data file carries a `verifiedDate`. `freshness.yml` runs on the 1st and 15th: it pulls the AWS What's New feed, lists S3 announcements newer than the last timeline entry, flags data files verified more than 120 days ago, and puts both in a tracking issue.

The hands-on labs chapter has 12 labs. Labs 1 to 3, 7, 9 and 12 were run against `pgsty/silo` (the community fork that kept building the MinIO server after MinIO stopped shipping images). The rest needed real AWS, so only their CLI arguments were checked against a moto server, and the chapter says so.

Locally:

```text
$ node scripts/validate-data.mjs
✓ data (10 files) and docs parity OK
$ npx vitest run
 Test Files  4 passed (4)
      Tests  43 passed (43)
```

S3 Atlas is an independent study guide, not affiliated with AWS. Corrections are welcome as issues: <https://github.com/0-draft/s3-atlas>
