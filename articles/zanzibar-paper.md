---
title: 'The Zanzibar Paper, Side by Side With Eight Translations'
published: true
description: 'A static site that puts the USENIX ATC ''19 Zanzibar paper next to Japanese, Chinese, Korean, Spanish, French, German and Portuguese translations, one paragraph per row, with a validator that rejects a translation that changes a tuple or drops a paragraph.'
tags:
  - showdev
  - authorization
  - translation
  - astro
series: ShowDev
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/zanzibar-paper/cover.png?v=b028b44e'
id: 5038067
date: '2026-11-14T21:50:52Z'
---

A machine-translated PDF of the Zanzibar paper reads fine until you hit the sentence about zookies or userset rewrites. Then you need what the authors actually wrote, and the translation doesn't tell you which English sentence it came from.

So I put the two next to each other.

- Source: <https://github.com/0-draft/zanzibar-paper>
- Live: <https://0-draft.github.io/zanzibar-paper/>

![The Japanese reading page: section list on the left, the original English paragraph and its Japanese translation in two columns on the same row](./assets/zanzibar-paper/reading-ja.png?v=65573062)

## One row per paragraph

The original is on the left, your language on the right, one paragraph per row. The languages are Japanese, Simplified and Traditional Chinese, Korean, Spanish, French, German and Brazilian Portuguese. `/en/` shows the original alone.

Every paragraph has a ¶ link, and switching language keeps you on the paragraph you were reading. You can hide either column. Figures 2 to 5 are vector crops of the PDF, not redraws. Figure 1 and both tables are text, so you can copy the namespace config and the latency numbers.

## The English is a transcription, typos included

`content/en.yaml` is the PDF typed out and split into blocks with stable ids (`s2-1-p1`, `tab-1`, ...). The authors' typos stay: "continously", "efficently", "oustanding", "uses cases". It is not my paper to edit.

A translation file holds only strings under the same ids:

```yaml
blocks:
  author-note:
    text: "Google 在籍中に行った研究。"
  abstract:
    text: "概要"
```

## The validator

The thing I worried about with AI-drafted translations was not bad Japanese. It was a translation that reads well and quietly changes a tuple, a number or a citation. `pnpm validate` compares every translation against the source block by block: same ids, same shapes, and identical code spans, TeX and link targets.

Clean run on the current repo:

```text
$ node scripts/validate-content.ts
✓ en + 8 translation(s): de, es, fr, ja, ko, pt-BR, zh-Hans, zh-Hant
```

I changed `doc:readme` to `doc:README` inside a code span in the Japanese Table 1:

```text
$ node scripts/validate-content.ts ja
✗ ja:tab-1.rows[0][1] code/math/link tokens differ
    en: code:doc:readme
    ja: code:doc:README

1 problem(s)
```

Then deleted one paragraph:

```text
$ node scripts/validate-content.ts ja
✗ ja: missing block "s1-p2" (p)

1 problem(s)
```

It also rejects a CJK paragraph left in English. What it cannot see is a translation that is well formed and says something else. Each translation got a separate pass that compared it with the English block by block for meaning drift, dropped clauses and changed numbers. That pass found the Korean rendering *staleness* with the same word as *latency* in 14 blocks. On pull requests, a Claude review reads the diff for the same kind of thing.

The rest of CI is ordinary: Biome, `astro check`, Vitest (287 tests pass locally), textlint for the Japanese, markdownlint, Playwright with axe on a desktop and a phone viewport, and an offline link check.

## Guides and ecosystem pages

Besides the paper there are 24 pages in each of the nine languages: background guides (access control models, relation tuples, zookies, Leopard, listing, modeling, ordering without TrueTime) and one page each on SpiceDB, OpenFGA, Permify, Ory Keto, Topaz, Warrant and in-house systems, plus a comparison. These are marked on the page as written for the site with AI assistance and not part of the paper.

My own longer take on the paper is in [Google Zanzibar Deep Dive](https://dev.to/kanywst/google-zanzibar-deep-dive-handling-2-trillion-acls-in-under-10ms-f06).

## Licensing

The repo's code is MIT. The paper's text, figures and tables are not: the README and `LICENSE` say they remain the work of the authors (© 2019) and are not covered by the MIT license. Every reading page says the translation is unofficial and not affiliated with or endorsed by Google, USENIX or the authors. The original is free to read at [USENIX](https://www.usenix.org/conference/atc19/presentation/pang).

If you find a mistranslation, [open an issue](https://github.com/0-draft/zanzibar-paper/issues/new?labels=translation) with the paragraph's ¶ link.
