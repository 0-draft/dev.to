---
title: 'goi: Japanese Words People Know but Rarely Say, Each With Its Sources'
published: true
description: 'A small bilingual glossary of Japanese idioms, proverbs and four-character compounds. Each word has a page with its meaning, origin, an example and the URLs it was checked against, and asks you to guess the meaning first.'
tags:
  - showdev
  - japanese
  - astro
  - webdev
series: ShowDev
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/goi/cover.png?v=c8996d13'
id: 5038055
---

There is a layer of Japanese that most people recognize and almost nobody says: 関の山, 日下開山, 痘痕も靨. You read them, you get the gist, you never reach for them. And the gist is often wrong.

goi is a glossary of those words. 68 of them right now, each on its own page with a meaning, an origin, an example sentence and the sources it was checked against, in English and Japanese.

- Source: <https://github.com/0-draft/goi>
- Site: <https://0-draft.github.io/goi/> (English) and <https://0-draft.github.io/goi/ja/> (Japanese)

![The goi top page: the word of the day, 板に付く, above an index in kana order that can be filtered by Sumo, The stage, Buddhism, History, Trade and money, Body and mind, Animals, Everyday life, or Often misunderstood](./assets/goi/index.png?v=bd4831fc)

## Guess first

A word page doesn't show the meaning. It shows two options and waits.

![The page for 日下開山: the headword drawn in a character grid, the reading ひのしたかいさん, and two options, "never, ever" and "peerless champion"](./assets/goi/word.png?v=1eecf8f1)

For most words the wrong option is another entry's gloss, picked by a seed from the word's id so it stays the same between builds. Your answer is kept in `localStorage`, so the page opens already answered next time. "Just show me" skips the question.

日下開山 is "peerless champion", usually another name for a yokozuna. 日下 is the whole realm, 開山 the founder of a temple. In 1682 calling yourself 天下一 was banned, and martial artists and performers started using this instead.

## Words people get backwards

Six words were asked about in the Agency for Cultural Affairs public opinion survey on Japanese. For those, the two options are the survey's own options, and after you answer the page shows how people across Japan picked, with the year, `n` and a link to the PDF.

Some of the numbers from `src/data/words.json`:

| Word | Original meaning | Picked original | Picked the other one | Survey |
| --- | --- | --- | --- | --- |
| 姑息 | a stopgap | 17.4% | 73.9% (underhanded) | FY2021, n=3579 |
| 役不足 | the role is too light for the person | 45.1% | 48.9% (too heavy) | FY2024, n=3498 |
| 気が置けない | no need to hold back | 47.4% | 44.3% (have to hold back) | FY2025, n=3777 |

So if you answer 姑息 wrong, you're with three quarters of the country.

## One entry

Every word is one object in a single JSON file. 関の山 ("the most one can manage"), trimmed:

```json
{
  "id": "seki-no-yama",
  "word": "関の山",
  "reading": "せきのやま",
  "kind": "慣用句",
  "meaning": "どう頑張ってもそこまでが限度、という精一杯のところ。",
  "example": "この予算では現状維持が関の山だ。",
  "sources": [
    { "label": "和樂web", "url": "https://intojapanwaraku.com/rock/culture-rock/164072/" },
    { "label": "地域文化資産ポータル（関の山車）", "url": "https://bunkashisan.ne.jp/bunkashisan/24_mie/7294.html" }
  ],
  "themes": ["everyday"],
  "en": { "gloss": "the most one can manage", "...": "..." }
}
```

The origin has two competing theories (the Seki Shrine floats were too lavish to outdo, or they filled the whole width of the post town's street), so both are given as theories. 痘痕も靨 ("love is blind") cites its first known use, a sharebon from 1779, and notes that saying it to the couple themselves can give offense.

English pages keep the Japanese headword, reading and example, and add a gloss, meaning, origin and a translated example.

The schema is Zod, and it is strict about what counts as done. A word needs a reading, a meaning, at least one source, English text and one or two themes. A word that can't be pinned down yet keeps a `pending` reason and gets no page. There is one right now:

```json
{
  "word": "いたい言葉",
  "pending": "どの言葉を指しているか特定できていない。「痛い言葉」なのか、別の言葉の聞き違いなのか確認中。"
}
```

That is: not sure which word this is, or whether it was misheard. The build and the tests fail on data that doesn't match the schema.

## The rest

- Astro, static output, on GitHub Pages
- Search runs in the browser. It normalizes with NFKC and turns katakana into hiragana, so セキノヤマ finds 関の山. Prefix matches on the headword or reading rank first, then substring matches, then matches in the gloss, meaning or romaji, so `love is blind` and `abata` both work
- OGP images per word and per language, rendered at build time with satori and resvg. For the survey words the image leads with the figure ("Only 17.4% in Japan chose the original meaning")
- Playwright with axe, Lighthouse CI, and visual regression tests that run only inside CI's Playwright container, because fonts render differently per OS. The screenshots above are those baselines (web fonts are blocked in that run, so the page falls back to the container's fonts)

Source, and issues if you think a meaning or an origin is wrong: <https://github.com/0-draft/goi>
