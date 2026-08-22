---
title: 'Galick: I built the ultimate Load Testing tool (Go + Starlark)'
published: true
description: Why choose between performance and flexibility? Galick combines Go's speed with Starlark scripting for the best of both worlds.
tags:
  - showdev
  - go
  - performance
  - testing
series: ShowDev
id: 3185931
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/galick/vegeta.png'
date: '2026-01-20T18:45:48Z'
---

## Introduction

If you've ever needed to load test an API, you've likely faced **The Dilemma**.

You have two choices:

1. **Vegeta/Wrk**: Incredibly fast, low memory footprint, but... *dumb*. They hit static URLs. If you need to generate a dynamic payload, sign a request, or chain calls (login -> get token -> data), you're out of luck.
2. **K6**: Amazing scripting (JS), beautiful UX, but... *heavy*. Running a V8/Goja JavaScript VM for *every single virtual user* eats RAM for breakfast. Simulating 10k users on a single machine? Good luck.

I got tired of choosing between **performance** (Vegeta) and **flexibility** (K6).

So, I built **[Galick](https://github.com/kanywst/galick)**.

## What is Galick?

**Galick** is a high-performance load testing tool written in Go.

It solves The Dilemma by using **Starlark** (a dialect of Python) for scripting instead of JavaScript. Starlark is designed to be embedded in Go; it's thread-safe, lightweight, and doesn't require a heavy VM for each user.

![Galick Demo](https://github.com/kanywst/galick/raw/main/demo.gif)

With Galick, you get:

- **Vegeta-like Performance**: Uses Go's lightweight concurrency.
- **K6-like Flexibility**: Script dynamic scenarios in Python syntax.
- **Beautiful TUI**: Real-time metrics in your terminal (powered by Bubbletea).

## The "Secret Sauce": Starlark

Why Starlark?

When K6 runs a test, it spawns a JavaScript runtime for every virtual user. If you have 1,000 users, that's 1,000 JS environments. It's flexible, but expensive.

Galick uses **Starlark**, the configuration language used by Bazel. It's a subset of Python. It's deterministic, safe, and most importantly, it interacts seamlessly with Go structs without the heavy serialization overhead of a JS bridge.

Here is what a dynamic attack looks like in Galick:

```python
# attack.star
# This looks like Python, but it's Starlark!

def request():
    return {
        "method": "POST",
        "url": "https://httpbin.org/post",
        "body": '{"user_id": 123, "timestamp": "now"}',
        "headers": {"Authorization": "Bearer my-token"}
    }
```

Then run it:

```bash
galick --script attack.star --qps 1000 --duration 1m
```

Galick executes this script to generate requests on the fly, allowing for dynamic timestamps, random IDs, or calculated signatures, while maintaining massive throughput.

## Features at a Glance

### 1. Static Mode (The "Vegeta" Mode)

Sometimes you just want to hammer a URL. No script needed.

```bash
galick --url https://api.example.com --qps 500
```

### 2. Headless Mode (CI/CD)

The TUI is great for local debugging, but for CI pipelines, you want clean logs.

```bash
galick --url https://staging.api.com --headless
```

### 3. Native Docker Support

Drop it into your `docker-compose.yml` for integration tests.

```yaml
services:
  app:
    image: my-app
  load-test:
    image: ghcr.io/kanywst/galick:latest
    command: ["--url", "http://app:8080", "--duration", "30s"]
```

## Architecture: Standing on Giants

I didn't reinvent the wheel. Galick synthesizes the best parts of existing tools:

- **Pacing**: It uses a distributed pacing mechanism (inspired by Vegeta) to ensure mathematically precise request rates (e.g., exactly 500 QPS, not "roughly" 500).
- **Metrics**: It uses `HdrHistogram` to calculate P99 and P99.9 latencies with high fidelity, avoiding the "Coordination Omission" problem found in simpler tools.
- **UI**: The TUI is built with [Bubble Tea](https://github.com/charmbracelet/bubbletea), proving that CLI tools can be beautiful and functional.

## Try it out

Galick is open source. If you are a Go developer, or just need a solid load testing tool that doesn't eat all your RAM, give it a shot.

```bash
go install github.com/kanywst/galick/cmd/galick@latest
```

Or using Docker:

```bash
docker run --rm -it ghcr.io/kanywst/galick --url https://httpbin.org/get
```

I'm actively looking for feedback. Does Starlark feel intuitive? Is the TUI helpful? Let me know in the comments or on GitHub!

👉 **[GitHub Repository](https://github.com/kanywst/galick)**
