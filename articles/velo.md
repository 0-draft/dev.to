---
title: 'Velo: A Cross-Platform Network Speed Monitor Built with Go & Wails'
published: true
description: An open-source desktop tool to automatically monitor and visualize your internet connection speed over time.
tags:
  - showdev
  - wails
  - golang
  - vue
id: 3163195
date: '2026-01-10T19:14:18Z'
series: ShowDev
---

## Introduction

Have you ever felt your internet connection dragging, but you aren't sure if it's just a momentary glitch or a consistent pattern?

I built **Velo**, a desktop application that helps you track your network speed over time without the hassle of manually running speed tests in your browser.

In this post, I'll share why I built it, how it works, and the technology stack behind it.

## Links

- **GitHub Repository:** [github.com/kanywst/velo](https://github.com/kanywst/velo)

---

## What is Velo?

Velo is a network speed measurement tool designed to run as a desktop application.

It automatically runs a speed test once every hour to record your Download, Upload, and Latency metrics. It then visualizes this historical data on an interactive chart, allowing you to spot trends at a glance. You can, of course, trigger a manual measurement whenever you want.

**Fun fact:** The name `velo` comes from the Italian word *veloce*, which means "fast." Why Italian? Honestly, there’s no deep meaning—I was just looking for a name and thought it sounded cool!

![Velo Dashboard Example](https://raw.githubusercontent.com/kanywst/velo/main/assets/example.png)

## Motivation

I noticed that my internet connection tends to get sluggish at night.

Usually, when this happens, I open [FAST.com](https://fast.com/) to check the speed. However, opening a browser and typing in the URL every single time is tedious. More importantly, a single test only tells me the speed *right now*—it doesn't help me understand the trend or prove that "yes, it is consistently slow every night at 9 PM."

I wanted an application that would automatically measure and record the speed periodically so I could analyze the patterns.

While I know there are similar applications and more feature-rich monitoring tools out there, I believe that **reinventing the wheel is often the best way to learn.**

## Features

- **Speed Test**: Measures download speed, upload speed, and latency using `speedtest-go`.
- **Automatic Monitoring**: Runs in the background and tests speed every hour.
- **Visualization**: Displays your network history on an interactive Time vs. Speed chart.
- **Cross-Platform**: Works on macOS, Windows, and Linux.

## Tech Stack

To build this, I used **Wails**, which allowed me to write the backend in Go and the frontend using standard web technologies.

- **Framework:** [Wails v2](https://wails.io/)
- **Backend:** Go (v1.25+)
- **Frontend:** Vue.js (Node.js & npm)
- **Library:** `speedtest-go` for the core measurement logic.

## Getting Started

If you want to try it out or contribute, you can build it from the source.

### Prerequisites

- **Go** (v1.25 or later)
- **Node.js** & **npm**
- **Wails CLI**:

    ```bash
    go install github.com/wailsapp/wails/v2/cmd/wails@latest
    ```

### Installation & Running

1. **Clone the repository:**

    ```bash
    git clone [https://github.com/kanywst/velo.git](https://github.com/kanywst/velo.git)
    cd velo
    ```

2. **Install dependencies:**

    ```bash
    # Backend
    go mod tidy

    # Frontend
    cd frontend
    npm install
    cd ..
    ```

3. **Run in Development Mode:**

    ```bash
    wails dev
    ```

4. **Build for Production:**

    ```bash
    wails build
    ```

The binary will be generated in `build/bin`.

---

## Conclusion

Velo is a personal project born out of a simple need to verify my ISP's performance.

It is still very much a work in progress, and I suspect there are a few bugs lurking around! I plan to keep improving it and fixing issues as I find them.

Please give it a try and let me know what you think in the comments! If you find it useful (or just like the name), I would appreciate a star on GitHub.
