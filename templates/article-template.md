---
# devto_sync: false makes devto-cli skip this file outright, so the template can
# never be published as an article even if it somehow reaches `dev push`.
# Delete this line when you copy the file into articles/.
devto_sync: false
title: "Article Title Here"
published: false
description: "A short description of the post."
tags: ["tag1", "tag2"]
# cover_image: "https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/<slug>/cover.png"
# series: My Series
# canonical_url: ""
# date: "2026-01-01T09:00:00Z"
---

<!--
  dev.to renders the frontmatter `title` as the page H1, so the body starts at
  `##`. A body-level `#` produces a second H1 and trips MD025.

  Frontmatter notes:
  - tags: at most 4, lowercase alphanumeric only. dev.to silently drops the 5th
    and lowercases the rest.
  - cover_image: must be an absolute raw URL. devto-cli does not rewrite it, so
    a relative ./assets/... path will not resolve on dev.to.
  - series: unquoted, and must match an existing series name exactly. Check
    INDEX.md first; a near-miss creates a second sidebar on dev.to.
  - date: only needed for scheduled publishing, alongside `published: false`.
-->

## Introduction

Open with the personal motivation or the discovery that made this worth writing.

## Core Concept

Explain the mechanism, driven by a diagram. Store D2 sources under
`articles/assets/<slug>/diagrams/NN-name.d2` and reference the rendered PNG:

![Diagram description](./assets/<slug>/diagrams/01-overview.png)

## Deep Dive

Implementation details, cited against real upstream source with file and line
references.

## Hands-on

Runnable commands with real measured output.

```bash
echo "replace me"
```

## Conclusion

What the reader can now do, and where to go next.
