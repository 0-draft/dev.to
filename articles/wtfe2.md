---
title: 'Lettering Programming Comics in Japanese, Only Where the License Allows It'
published: true
description: 'wtfe2 erases the English lettering from xkcd, TurnOff.us, Browserling, Bonkers World and Abstruse Goose strips and sets Japanese in its place. Sites whose terms don''t allow that get a retelling and a link, and a CI check keeps it that way.'
tags:
  - showdev
  - astro
  - opensource
  - japanese
series: ShowDev
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/wtfe2/cover.png?v=ddf1db1f'
id: 5038078
date: '2026-11-14T21:50:56Z'
---

Every "funny programming comics" list I have seen is a wall of English links. I wanted to hand some of those strips to people who don't read English, lettered the way a translated manga is: English taken out of the art, Japanese drawn in.

Most of those strips can't legally be redrawn. So the site has two kinds of entries, and the license picks which one a comic gets.

- Source: <https://github.com/0-draft/wtfe2>
- Site: <https://0-draft.github.io/wtfe2/> (Japanese at `/ja/`)

![TurnOff.us "git submodules adoption flow": the original on the left, the Japanese edition on the right](./assets/wtfe2/compare-git-submodules.png?v=5d6a3a15)

*"git submodules adoption flow" by Daniel Stori, [turnoff.us](https://turnoff.us/geek/git-submodules/), [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). Right: Japanese adaptation by wtfe2, same license. The comic images in this article are under their creators' licenses, not this article's.*

## Twelve sites, five that allow it

| Site | License | On wtfe2 |
| --- | --- | --- |
| xkcd | CC BY-NC 2.5 | 21 strips lettered |
| Browserling | CC BY-NC 4.0 | 6 strips lettered |
| TurnOff.us | CC BY-NC-SA 4.0 | 4 strips lettered |
| Bonkers World | CC BY-NC-ND 3.0, translations allowed with credit | 2 strips lettered |
| Abstruse Goose | CC BY-NC 3.0 US | 2 strips lettered |
| CommitStrip | non-commercial use with link and credit | 2 strips shown as published, Japanese subtitles |
| SMBC | no reuse terms published | retold, linked |
| Existential Comics | no reuse terms published | retold, linked |
| MonkeyUser | all rights reserved | retold, linked |
| The Daily WTF | copyright Inedo Publishing | retold, linked |
| The Oatmeal | copyright Matthew Inman | retold, linked |
| PHD Comics | reprints by permission only | retold, linked |

A strip gets lettered only if its license allows adaptation, or the site explicitly allows translation (Bonkers World is ND, but its about page says translating with credit is fine). "No terms published" is not permission, so SMBC and Existential Comics get the same treatment as the all-rights-reserved sites: the strip retold panel by panel in my own words, and a link.

CommitStrip was the one I had to read twice. Its about page says you can use the strips for any non-commercial purpose, including illustrating a blog post, "as long as you aren't just duplicating our content for the sake of it". That is permission to show a strip. Redrawing its lettering is something else. So its two strips appear exactly as published, with the Japanese underneath as subtitles.

Abstruse Goose's own site went offline in 2023. A community archive on GitHub kept the strips and the license they were published under, so the comic pages credit the archive and name the original address as plain text.

Where a linked site publishes terms, the page quotes them verbatim, next to the date I checked them. And because every adapted comic is NC, the site has no ads, sponsorships or affiliate links.

## The rule is a CI check

`src/data/sites.json` gives each site a `tier` (`translated` or `linked`) and a `terms.kind`. `scripts/validate-data.ts` refuses a translated site whose terms don't allow adaptation or translation, a comic whose license label differs from its site's, a shown strip from a site whose terms don't allow showing it, and any image in `public/comics/` or `public/strips/` that nothing uses.

To see it fire, I flipped CommitStrip to `translated` and dropped one of its strips into `public/comics/`:

```text
$ node scripts/validate-data.ts
4 problem(s):
  - sites/commitstrip: only sites that allow adaptation or translation may be adapted
  - explainers/commitstrip-a-very-comprehensive-and-precise-spec.json: commitstrip is adapted, so its strips belong in comics/, not explainers/
  - explainers/commitstrip-west-side-project-story.json: commitstrip is adapted, so its strips belong in comics/, not explainers/
  - public/comics/commitstrip-spec.jpg: image is not used by any comic entry
```

On the real data:

```text
$ node scripts/validate-data.ts
ok: 35 comics, 12 explainers, 12 sites
```

## Erasing lettering without erasing the drawing

Each strip lists its lettering as regions: a box in image pixels, the English verbatim, and the Japanese with line breaks chosen by hand.

```json
{
  "box": [536, 286, 273, 153],
  "en": "do you\nneed it?",
  "ja": "それ、\n必要?",
  "size": 56.5,
  "align": "center",
  "lineHeight": 1.2
}
```

Filling the box with white would also cut the flowchart diamond the text sits in. `scripts/plates.ts` works on connected ink strokes instead. It flood-fills each dark stroke it finds in the box, even past the box edge. A stroke that stays inside (with 2 px of slack) is lettering and goes. A stroke that leaves the box is drawing and stays. Faint anti-aliasing is cleaned up afterwards, except within 2 px of a kept stroke.

The plate for the submodules strip. Every diamond, arrow and border survived, and so did the artist's signature, because it sits outside every box:

![The clean plate of the git submodules strip: the flowchart with all text removed, the Daniel Stori signature still in the corner](./assets/wtfe2/plate-git-submodules.png?v=8d8b5ade)

*Plate derived from "git submodules adoption flow" by Daniel Stori, [turnoff.us](https://turnoff.us/geek/git-submodules/), [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/).*

From a local run:

```text
$ node scripts/plates.ts
turnoff-git-submodules: erased 89 strokes, kept 12 crossing the boxes
xkcd-927-standards: erased 141 strokes, kept 26 crossing the boxes
xkcd-974-the-general-problem: erased 51 strokes, kept 14 crossing the boxes
...
```

Lettering that touches a panel border uses `"erase": "rect"` instead, which wipes everything inside a box kept off the border.

## Japanese as text, not pixels

The Japanese is not baked into the image. `ComicStage.astro` sets each region as an absolutely positioned span over the plate, placed in percentages and sized in container-query units (`cqi`), so it scales with the picture and can be selected and searched.

The Playwright suite opens every Japanese comic page at desktop and mobile widths, waits for the real fonts, and fails if any line overflows its region. It did fail on CI once: Linux rasterized Klee One a few percent wider than macOS and pushed a balloon in xkcd 1513 out of its box. Lettering is now set at 96% of the fitted size.

Each page also has a transcript in both languages, xkcd's hover text translated, a switch back to the original lettering, and the credit line the license asks for.

If you made one of these comics and want something changed or removed, open an issue on the repo. Requests from creators come first.

Source and issues: <https://github.com/0-draft/wtfe2>
