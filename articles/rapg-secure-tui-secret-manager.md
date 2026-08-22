---
title: 'Rapg: TUI-based Secret Manager'
published: true
description: 'A secure, TUI-based secret manager for developers who want to inject secrets directly into processes without writing them to disk.'
tags:
  - showdev
  - cli
  - go
  - security
id: 3185168
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/rapg/rapg_meme.png'
date: '2026-01-20T12:19:15Z'
series: ShowDev
---

# Introduction

We've all been there. You join a new project, and the first thing you hear is:
*"Check the pinned message in Slack for the `.env` file."*

Or maybe you have five different versions of `.env.local` scattered across your drive, and you're terrified of accidentally committing one to GitHub.

As developers, we know we shouldn't keep cleartext secrets on our disks, yet we do it every day because the "proper" enterprise solutions are often too heavy for local development.

**That's why I built [Rapg](https://github.com/kanywst/rapg).**

## What is Rapg?

**Rapg** is a developer-first secret manager that lives in your terminal. It bridges the gap between a personal password manager and a DevOps secret store.

Instead of managing text files, you store your secrets in a secure, local vault. When you need to run your app, Rapg injects those secrets directly into the process environment.

**No text files. No accidental commits. Just code.**

![Demo](https://raw.githubusercontent.com/kanywst/rapg/refs/heads/master/demo-v2.gif)

## The Killer Feature: Process Injection

The core philosophy of Rapg is that **secrets should only exist in memory**.

Instead of sourcing a `.env` file, you simply wrap your command with `rapg run`:

```bash
# Before: Relying on a file meant to be ignored
$ npm start

# After: Secrets injected on-the-fly
$ rapg run -- npm start
```

When you run this, Rapg:

1. Unlocks your vault (asking for your master password if not cached).
2. Decrypts only the secrets meant for the environment (e.g., `DB_PASSWORD`, `STRIPE_KEY`).
3. Spawns your process (`npm start`) with these variables added to its environment.

The secrets never touch your disk. Once the process dies, the secrets are gone.

## A TUI for the Modern Era

CLI tools shouldn't be painful to use. Rapg is built with [Bubble Tea](https://github.com/charmbracelet/bubbletea), giving it a beautiful, keyboard-centric interface.

You can:

- **Search** your secrets instantly.
- **Generate** strong, random passwords.
- **Copy** 2FA/TOTP codes without reaching for your phone.
- **Audit** your vault for password reuse.

## Under the Hood: Bank-Grade Security

For the security-minded, here is how Rapg keeps your data safe. It adheres to a **Zero-Knowledge Architecture**:

1. **Argon2id**: Your master password is never stored. We use Argon2id (RFC 9106) to derive an encryption key. This makes brute-force attacks computationally expensive.
2. **AES-256-GCM**: All data is encrypted with Authenticated Encryption. This ensures that your data is not only secret but also hasn't been tampered with.
3. **Memory Protection**: We use [memguard](https://github.com/awnumar/memguard) to prevent sensitive keys from being swapped to disk or read by other processes.

## Advanced Tools

Rapg isn't just a vault; it's a toolkit.

### Security Audit

Ever wonder how many services are using that same old password from 2018?

```bash
$ rapg audit
⚠️  Reuse Detected! The following passwords are used in multiple places:
...
```

### Migration

Moving from another tool? You can import from CSV or export to `.env` (if you *really* must).

```bash
$ rapg import lastpass_export.csv
```

## Try It Out

Rapg is open source and written in Go. You can install it right now:

```bash
go install github.com/kanywst/rapg/cmd/rapg@latest
```

Initialize your vault, add your first secret, and stop worrying about where your `.env` file is.

I'd love to hear your feedback! Check out the repository, star it if you find it useful, or open an issue if you find a bug.

👉 **[GitHub Repository](https://github.com/kanywst/rapg)**
