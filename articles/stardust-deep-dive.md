---
title: 'Stardust: The dashboard that transforms GitHub trends from "search" to "monitoring"'
published: true
description: 'For engineers tired of constantly switching between languages, we''ve launched "Stardust" - a dashboard that lets you simultaneously monitor multiple GitHub trends across different programming languages on a single screen.'
tags:
  - showdev
  - react
  - typescript
  - github
series: ShowDev
id: 3217098
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/stardust/stardust.png'
date: '2026-02-01T15:01:02Z'
---

## Introduction

[GitHub Trending](https://github.com/trending) is an excellent resource, but its user experience isn't particularly optimized for engineers with broad interests across multiple languages.

You'll check Rust trends, then move on to Go, then perhaps look at TypeScript...
Each time, you need to click a dropdown, type in a language, and reload the page. This repetitive "language switching" process becomes noise in your daily information intake.

You want a more intuitive way to grasp the entire ecosystem you're interested in.
That's why we created **[Stardust](https://kanywst.github.io/stardust/)**.

![Stardust Dashboard](https://raw.githubusercontent.com/kanywst/stardust/refs/heads/main/assets/example.png)

👉 **Demo: [kanywst.github.io/stardust](https://kanywst.github.io/stardust/)**

## The Concept: From Serial to Parallel Processing

The fundamental difference between existing GitHub Trending and Stardust lies in how information is consumed.

While the standard UI operates in a "select one language at a time to dive deeper" (serial) approach, Stardust takes a "parallel monitoring" approach where you view multiple languages of interest side by side.

This "parallelization" reduces the cost of actively seeking out information, allowing you to simply glance at the screen while keeping track of trends.

## Key Features

* **Multi-Language Matrix**: Displays trends for major languages like Rust, TypeScript, Go, and Python in a grid format, enabling comparison without context switching.
* **Cinematic UI**: Uses Framer Motion for data visualization, aiming for an immersive design reminiscent of sci-fi movie interfaces.
* **Instant Interaction**: A Single Page Application (SPA) powered by React 19 and TanStack Query eliminates page load delays.

## Conclusion

Stardust is also an experiment in how simply changing the "presentation method" of information can dramatically improve information intake efficiency.

You can try it directly in your browser using the links below. We encourage you to check the "pulse" of your favorite programming languages.

* **App**: [https://kanywst.github.io/stardust/](https://kanywst.github.io/stardust/)
* **Repo**: [https://github.com/kanywst/stardust](https://github.com/kanywst/stardust)
