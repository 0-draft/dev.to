---
title: 'A Blackjack Table That Lives in a README, Dealt by GitHub Actions'
published: false
description: 'Every decision is a GitHub issue, the dealer is a workflow, and the table is the README. Each click is priced exactly from the cards left in the shoe, and the dealer''s hole card does not exist until it is turned over.'
tags:
  - showdev
  - python
  - githubactions
  - gamedev
series: ShowDev
date: '2026-11-15T00:00:00Z'
id: 4856990
---

## Introduction

README games are an old GitHub trick: a link opens an issue, a workflow reads it, and the README redraws. Chess and tic-tac-toe have been done many times. I wanted one where the game itself had something to say, so I built a blackjack table that tells you, after every click, exactly what that decision was worth.

**[Play it here](https://github.com/0-draft/blackjack#blackjack).** Nothing to install, no account beyond the GitHub one you already have.

## Links

- **Table:** [github.com/0-draft/blackjack](https://github.com/0-draft/blackjack#blackjack)
- **Source:** `scripts/blackjack.py` (the game) and `scripts/bjmath.py` (the calculator) in the same repo

## How a hand is played

Pick a chip. The link opens an issue whose title is already filled in, something like `bj|bet 1 12` (bet 1 unit on hand 12). Press Submit and:

```text
issue opened  ->  blackjack.yml  ->  blackjack.py  ->  commit README  ->  close issue
 "bj|bet 1 12"     (only titles       deal, price,      table redrawn     with a note on
                    starting bj|)      update state                       what it was worth
```

Within about half a minute the table has moved, and the issue is closed with a comment like this one, from the hand I dealt while writing this:

```text
Hand 12 for 1u.

When that chip went down the running count was +0 with 4.9 decks left,
so the true count was +0.0. A shoe like that is worth about -0.12% a unit,
measured over 200 million rounds of these rules, so 1u on it was worth
-0.001 units before a card came out.
```

There is one table and one hand at a time, so whoever clicks next is the player. Every link carries the hand number, so a stale link from an earlier hand is refused instead of being applied to whatever is on the table now. Runs that write the README share one concurrency group with `queue: max`, so three people clicking at once are served in order instead of the middle one being dropped.

## The hole card does not exist

The state file `.github/blackjack.json` is public. If the dealer's second card were in it, anyone could read ahead. So it is not drawn at all. From the comment in `blackjack.py`:

> It is not drawn until the moment it is turned over, so there is nothing in this repository to read ahead, which is stricter than a real table, where the dealer has already seen it.

The peek is still honest. When the dealer shows an ace or a ten, the game rolls whether the hole card completes a natural, using the real proportion of tens (or aces) left in the shoe. Only if it does is the card drawn right then. Otherwise the hand goes on, and when the hole card is finally turned over it is drawn from the shoe with the natural-making cards weighted out.

The shoe itself is stored only as the list of cards that have come out of it. What is left is the difference, so the state cannot disagree with the discard tray printed under the table, and counting is the game: every card that has left the shoe is listed, and nothing on the page tells you the count.

## Pricing every click exactly

A strategy chart answers "what is best on average over a fresh six-deck shoe". That is the wrong question halfway through a shoe. `bjmath.py` works in compositions (how many aces, twos, ..., tens remain) and enumerates every outcome, so each action is priced for this shoe and no other:

- Cards are drawn without replacement all the way down, including the dealer's.
- The calculator is never allowed to see the hole card. Enumerate it, take the best action inside each branch, and sixteen against a ten starts "standing when the dealer has sixteen", a quarter of a unit no player can collect. Every decision is averaged over the hole cards the player cannot tell apart.
- The peek is priced. A dealer ace that has been checked is known not to be covering a ten, which slightly raises the chance of a ten arriving for the player too.

The one deliberate approximation is splitting: each split hand is priced as if it were alone. That is the standard treatment, worth a few thousandths of a unit.

Because every decision has an exact value, the table can keep score of something more interesting than wins: it adds up how many units each player has lost to mistakes, as opposed to bad luck, and prints the total under the table.

## How do I know the numbers are right?

A wrong board is visible. A wrong expected value just quietly tells strangers that the worse play was better. So the calculator is checked three ways in `tests/test_bjmath.py`:

1. **Against an independent Monte Carlo** that deals a real shuffled shoe with a physical hole card and rejection sampling for the peek. It shares no code with the calculator.
2. **Against the published basic strategy chart.** All 260 cells have to fall out of the numbers from a full shoe, without the calculator ever being told what the chart says.
3. **Against its own past answers**, so a change that moves a number has to be deliberate.

The full chart and a long simulation take about four minutes, too slow for every pull request, so `calculator.yml` runs them nightly and on any change that touches the calculator or the chart.

The card art is generated by `scripts/make_cards.py` and committed. `checks.yml` regenerates it on every pull request and fails if the committed SVGs drift from their generator.

## The rules

Six decks, dealer stands on soft 17, double after split, late surrender, blackjack pays 3 to 2, shuffled at a 75% cut card. Every hand ever played is kept in `.github/blackjack-log.txt`.

## Conclusion

It started life in my profile README and now has [its own repo](https://github.com/0-draft/blackjack#blackjack). So far every hand on it is mine, which is the part I would like to change: go deal one. A click opens a prefilled issue, Submit plays it, and the closing comment tells you what your decision was worth.
