---
title: 'gmk(Git Mark): Stop Typing Git URLs'
published: true
description: 'A stylish, interactive CLI to bookmark and clone your favorite Git repositories.'
tags:
  - showdev
  - rust
  - cli
  - git
id: 3176769
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/gmk/gmk_meme.png'
date: '2026-01-16T14:19:04Z'
series: ShowDev
---

## 😫 The Problem

We've all been there. You find an amazing library on GitHub, you star it, and then... you forget about it. Two weeks later, you need it for a project.

* "What was that repo called again?"
* *Search through GitHub stars...*
* *Copy URL...*
* `git clone https://github.com/long-org-name/complex-repo-name.git`

It’s friction. It breaks your flow.

## 🚀 The Solution: gmk (Git Mark)

I built **[gmk](https://github.com/kanywst/gmk)** to solve this exact problem. It's a blazing fast, interactive CLI tool written in **Rust** that lets you bookmark repositories once and clone them anywhere, instantly.

![gmk demo](https://raw.githubusercontent.com/kanywst/gmk/main/assets/demo.gif)

## ✨ Features

* **🔖 Bookmark & Forget**: Just run `gmk set <url>`. It automatically parses the owner and repo name.
* **🔍 Fuzzy Finder**: Powered by **[skim](https://github.com/lotabout/skim)**. Type a few characters to find any repo instantly.
* **🌿 Smart Cloning**:
  * Press `Enter` to clone the default branch.
  * Press `Ctrl + b` to interactively specify a branch (e.g., `dev` or `v2`).
* **⚡ Zero Friction UI**: The interface appears inline and clears itself away after use, keeping your terminal clean.

## 📦 Installation

### Homebrew (macOS / Linux)

```bash
brew tap kanywst/gmk https://github.com/kanywst/gmk
brew install gmk
```

### Cargo (Rust)

```bash
cargo install gmk
```

## 🎮 How to use

1. **Save a repo**:

    ```bash
    gmk set https://github.com/rust-lang/rust.git
    ```

2. **Clone it later**:
    Just type `gmk`.

    ```bash
    gmk
    # Fuzzy finder appears... select 'rust' and hit Enter!
    ```

## 🛠️ Built with Rust 2026

This project was a great playground to explore modern Rust CLI practices:

* **[Clap v4](https://crates.io/crates/clap)** for argument parsing.
* **[Skim](https://crates.io/crates/skim)** for the fuzzy finding engine.

## 🤝 Open Source

I'd love to hear your feedback or see your PRs!

👉 **[Give it a star on GitHub](https://github.com/kanywst/gmk)**
