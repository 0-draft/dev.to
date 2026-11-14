---
title: 'wtfe: Claims About Engineering Culture by Country, Each One Sourced and Rated'
published: false
description: A bilingual site about how software engineers in 14 countries and regions tend to work. Every claim cites a public source and carries a label for how much that source can carry.
tags:
  - showdev
  - career
  - culture
  - astro
series: ShowDev
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/wtfe/cover.png?v=4d9e66d8'
id: 5038063
---

"Japanese engineers avoid direct feedback." Follow that line back and you usually land on a summary of Erin Meyer's book, written by a language school or a training company.

I built a site where that sentence is allowed to stay, but has to say what it rests on.

- Source: <https://github.com/0-draft/wtfe>
- Site: <https://0-draft.github.io/wtfe/> (English), <https://0-draft.github.io/wtfe/ja/> (Japanese)

wtfe (Ways They Frame Engineering) covers Japan, South Korea, China, India, the US, the UK, Germany, France, the Nordics, the Netherlands, Israel, Brazil, Poland and Ukraine, across seven themes: design and quality, failure and risk, feedback and code review, hierarchy and decisions, communication and docs, work and careers, open source.

## Three labels

Every claim gets one of three labels. The rule is about the source, not about how plausible the claim sounds:

| Label | What earns it |
| --- | --- |
| Well attested | Official statistics, primary documents, large surveys read on the publisher's own page, peer-reviewed quantitative studies, an organization's own account of its own practice |
| Attested | Frameworks such as Meyer's Culture Map, a single reputable news report, Wikipedia, industry associations, qualitative studies |
| Thin | Blogs, forums, vendor and recruiter material, summary sites, single anecdotes. Kept only when nothing better exists |

A claim whose newest source is older than 2016 also gets a "dated" mark. That is computed at build time from the source years, not typed by hand.

Here is Japan's feedback and code review section:

![Japan's feedback section on wtfe: three claims labeled THIN with dashed rules, and one WELL ATTESTED claim about Hacobell and Future labelling review comments must, imo and nits, with its two sources expanded](./assets/wtfe/jp-feedback.png?v=9e171cdd)

The stereotype is there, as `jp-feedback-1`, and it is thin: both sources are a language school's blog and a book review. The only well-attested claim in the section is that two Japanese companies, Hacobell and Future, publish review rules that tag each comment with how strong it is (`must`, `imo`, `nits`). That is a company describing its own practice, so it gets the top label.

The same framework gets different labels depending on who you read it through. Germany's line on Meyer's Evaluating scale (`de-feedback-1`) cites a copy of Meyer's own chart and is Attested. Japan's line on the same scale cites summaries of the book and is Thin.

`kr-design-1` is Thin and dated, a single 2013 column:

> A 2013 ZDNet Korea column argued that the ppalli-ppalli ("hurry, hurry") culture leads to poor knowledge sharing, architectures that do not scale and dependence on particular developers, and so ends up slowing software development.

## Counting the corpus

Claims live in JSON, one file per country per language, validated with zod:

```json
{
  "id": "jp-feedback-4",
  "text": "Hacobell and Future publish review practices that mark how strong a comment is with labels such as must, imo and nits. Hacobell reports that this raised its team's psychological safety and development efficiency.",
  "confidence": "strong",
  "sources": [
    {
      "title": "Hacobell: Raising psychological safety just by labelling code review comments",
      "url": "https://zenn.dev/hacobell_dev/articles/code-review-comment-prefix",
      "year": 2023
    },
    {
      "title": "Future: Code review guidelines",
      "url": "https://future-architect.github.io/arch-guidelines/documents/forCodeReview/code_review.html"
    }
  ]
}
```

`strong` / `medium` / `weak` in the data render as Well attested / Attested / Thin on the page. I counted the English files at commit `993bb94`:

```text
303 claims
  strong (Well attested)   87
  medium (Attested)       175
  weak   (Thin)            41
  dated (newest source < 2016)  35
```

The validator checks the schema, that each claim id matches its country and theme, that the Japanese and English files have the same structure, and that no Japanese text is left in the English files:

```text
$ REQUIRE_EN=1 node scripts/validate-data.ts
ok: 14 ja, 14 en, 14 meta
```

Japanese is written first and English is translated from it. A weekly lychee job checks every source URL, and dead ones get fixed or swapped for an archived copy.

## Scales, with their provenance

The scale pages place each country on Meyer's eight Culture Map scales and Hofstede's six dimensions. Meyer positions are on a coarse seven-step grid, because that is about as precise as reading her charts gets. A filled dot was read off Meyer's own chart; a hollow dot came from reviews and summaries. On the home page, South Korea's Trusting position is hollow.

Hofstede values are the current ones from The Culture Factor. Older tables are still copied around the web, and some numbers moved a lot. The method page lists a few:

| Country | Dimension | Older table | Current |
| --- | --- | --- | --- |
| South Korea | Individualism | 18 | 58 |
| Germany | Individualism | 67 | 79 |
| Germany | Long-term orientation | 83 | 57 |

Japan's individualism went from 46 to 62, which is noted on the Japan page, since "Japan is strongly collectivist" depends on which edition you quote.

Compare pages take an ordered pair. `jp-vs-de` reads Germany from Japan and sorts by the largest gap:

![Hofstede rulers on the jp-vs-de compare page: Germany scores 43 points lower than Japan on long-term orientation, 29 lower on motivation towards achievement, 27 lower on uncertainty avoidance, 19 lower on power distance, 17 higher on individualism, and 2 lower on indulgence](./assets/wtfe/compare-hofstede.png?v=3190d6ae)

## What it is not

Taras, Steel and Kirkman (2016) found that roughly 80% of the variance in cultural values is within countries, not between them. Every country page opens with its own spread before any claim. For Japan, that includes the gap between system integrators and web companies, the "masakari" culture of blunt online criticism, and the fact that the Stack Overflow 2024 survey had 286 responses from Japan.

Corrections are welcome, especially from people working in these countries. Open an issue with the claim id (for example `de-hierarchy-2`) and a public source. Claims without a public source are not accepted.

Source and issues: <https://github.com/0-draft/wtfe>
