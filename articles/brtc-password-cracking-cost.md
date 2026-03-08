---
title: 'brtc: A CLI Tool to Convert Password Strength into "Time to Crack and a Real USD Invoice"'
published: true
description: More than just entropy calculation—I built a Go CLI tool to visualize how much it would cost if an offline attack were launched using modern hardware like an RTX 4090 or AWS clusters. Includes diagrams explaining the difference between online and offline attacks.
tags:
  - security
  - go
  - cli
  - showdev
series: ShowDev
id: 3325941
cover_image: "https://raw.githubusercontent.com/kanywst/dev.to.kanywst/refs/heads/main/articles/assets/brtc/cover.png"
---

## Introduction

If you're an engineer, you've likely debated "Is this password strong enough?" when designing a password policy.

The metric most commonly used in these discussions is **entropy (information density)**. For example, "It's an 8-character alphanumeric password, so the entropy is about 41 bits..." However, even when presented with this number, it's hard for non-engineers (or even engineers unfamiliar with infrastructure) to feel a visceral sense of danger.

That's why I created **[brtc (Brute-force Cost)](https://github.com/kanywst/brtc)**, a CLI tool that takes abstract entropy numbers and converts them into a "real invoice" (time and cloud compute costs) that anyone can understand: **"How much would it cost to brute-force this using modern computing resources (GPUs or clusters)?"**

---

## What is "Entropy"? (Quantifying Password Strength)

When discussing password strength, two things are essential: **Character Space ({% katex inline %} R {% endkatex %})** and **Length ({% katex inline %} L {% endkatex %})**.

For example, let's say a password is the 5-letter string `apple`, consisting solely of lowercase English letters (26 characters).
In this case, the maximum number of combinations to try in a brute-force attack is calculated with this simple formula:

{% katex %} 6 \text{ (character space)}^5 \text{ (length)} = 11,881,376 combinations {% endkatex %}

Roughly 11 million combinations. It seems like a staggering number that would take a human a lifetime to type manually, but for a computer, it's instantaneous.

To make this easier to handle in the world of computer processing, we express this as a power of 2 (bits), which is known as **Entropy**.
When the character space is {% katex inline %} R {% endkatex %} and the length is {% katex inline %} L {% endkatex %}, the entropy {% katex inline %} E {% endkatex %} is expressed by the following formula:

{% katex %} E = L \times \log_2(R) {% endkatex %}

In the case of our `apple` example, it would be {% katex inline %} 5 \times 4.700... \approx 23.50 {% endkatex %} bits.
In other words, when the entropy is calculated to be `23.50 bits`, it indicates that "the size of the space representing the possible patterns in a brute-force attack is roughly {% katex inline %} 2^{23.50} {% endkatex %}."
When you divide this entropy (the size of the space) by the literal "brute-force calculation speed of the hardware," the result is the "time to crack."

---

## What is `brtc`?

`brtc` is a Go-based tool that evaluates the complexity of a given string and calculates the **"time required to crack it"** and the **"total estimated cost (USD) if you rented that hardware in the cloud,"** under specified hardware models and hash algorithms (like bcrypt).

![demo](https://raw.githubusercontent.com/kanywst/brtc/refs/heads/main/assets/demo.gif)

※ **Estimated Cost** is automatically calculated by multiplying the on-demand/spot hourly rate of the specified hardware (e.g., AWS `p5.48xlarge`) by the time it takes to crack the password.

Rather than just warning stakeholders that "the strength is insufficient," saying **"If this password leaks, it will be cracked in about 50 days for $48,000 using AWS's monster instances"** is vastly more persuasive.

---

## Why Should We Care About Hardware Performance? (Attack Diagram)

Here, a common question arises:
**"Why do we need to worry about the computational speed of a GPU like the RTX 4090? A login screen will just block you with a WAF or account lock after 5 failed attempts anyway, right?"**

This is a misunderstanding stemming from confusing the general public's image of an "online attack" with the true threat: an "offline attack." Take a look at the sequence diagram below.

![attack diagram](./assets/brtc/attack-diagram.png)

As the bottom half of the diagram (②) shows, **the true threat to passwords begins "after the database is leaked."**

Once the data is taken, it's impossible to apply "account locks" or "rate limits" to the GPU sitting in the attacker's possession. The attacker can continuously run cracking calculations at the absolute physical limits of their hardware, with absolutely no interference.

This is exactly why we need **"string length and complexity" that can withstand pure computational resources (hardware brute force).**

---

## Why Do Attackers Use "GPUs" Instead of CPUs? (The Decisive Architectural Difference)

As shown in the sequence diagram above, the main player in an offline attack is not the web server, but the GPU in the attacker's hands.
But why go to the trouble of lining up multiple expensive, power-hungry GPUs? Because when it comes to the process of password cracking, there is an **"overwhelming difference in architectural aptitude"** between CPUs and GPUs.

![cpu vs gpu](./assets/brtc/cpu-vs-gpu.png)

### The Role and Limitations of CPUs (Central Processing Units)

* **Strengths (Roles/Pros):** Swiftly processing diverse and complex tasks sequentially—such as OS control, database transactions, and complex conditional branching. You could call them "the few and elite" who excel at logical thinking.
* **Weaknesses (Cons):** They physically have very few cores (typically 4–24 cores for consumers, and maybe a little over a hundred for servers). While individual processes (clock speed) are incredibly fast, there is a hard physical limit to the scale of "parallel processing" (doing the same task in massive quantities simultaneously).

### The Role and True Value of GPUs (Graphics Processing Units)

* **Strengths (Roles/Pros):** Simultaneously executing simple, independent calculations with minimal conditional branching, such as rendering screen pixels, using thousands to tens of thousands of cores all at once. They are "an army of tens of thousands of blue-collar workers" specialized in heavy lifting.
* **Weaknesses (Cons):** They become extremely slow when tasked with complex logical flows, or tasks where the processing path branches heavily based on the immediately preceding calculation result.

Brute-forcing password hashes is nothing more than repeating the simple, independent task of **"hashing a string and comparing it to the leaked hash."**
Therefore, while a CPU can only verify a few dozen passwords simultaneously, **modern GPUs like the RTX 4090 (equipped with 16,384 CUDA cores) can verify passwords by the tens of thousands in parallel per clock cycle**.

Assuming "It took 0.1 seconds to hash once in my local program (CPU), so a brute-force attack will take 100 years (it's safe)" is a fatal mistake. Attackers exploit this structural asymmetry by lining up multiple GPUs or cheaply renting spot instances from the cloud (like AWS P5 instances) to instantly burn through the entire password combination space using the brute force of parallel processing.

---

## The Cat-and-Mouse Game with Evolving Hardware

`brtc` features a variety of hardware profiles to simulate the attacker's budget and the passage of time.

* **`raspberry-pi-4`**: The minimum baseline. Even this can instantly crack older passwords.
* **`mac-m3`**: Standard Apple Silicon. Even an everyday Mac boasts astonishing compute power.
* **`gtx-1080ti`**: For historical comparison (the legendary GPU of 2017). You can see how passwords considered "safe" back then are no longer viable today.
* **`rtx-4090`**: The strongest class of GPU an individual could buy today.
* **`aws-p5.48xlarge`**: A cloud monster equipped with 8 H100s (costing around $40/hour at spot prices).

Even if you have the exact same "10-character alphanumeric" password, something that took the `gtx-1080ti` years to breach in 2017 will crumble in a matter of days or hours when targeted by a modern `rtx-4090` or a cloud cluster. Visualizing this **"decay of security due to technological advancement"** is the underlying theme of this tool.

Furthermore, professional attackers rarely use just a single GPU. With future expansion in mind, `brtc` is designed to visualize the projected threat from scaling multiple units (multiplying parallel counts), such as a **"custom cluster of 8 RTX 4090s."** Compute power can literally be expanded by "throwing money at it."

---

## Using it as a "Gatekeeper" in CI/CD Pipelines

`brtc` is designed not just for manual CLI checks, but to be integrated directly into CI/CD pipelines.
By using the `--fail-under-time` flag, it acts as a gatekeeper that says: **"Fail the build if a password (secret) is committed that can be cracked in under X amount of time."**

```yaml
# Example: .github/workflows/security.yml
steps:
  - name: Check strength of test secrets added by developers
    run: |
      # Do not allow weak passwords that can be cracked in under 1 month (1mo) to pass CI
      brtc --fail-under-time 1mo "dev_password_123"
```

This allows you to mechanically block mistakes like "hardcoding a terribly weak password just because it's for a development environment" before the code review even happens.
It also supports `--output json` for automation tools and `--output sarif`, which is the standard for static analysis tools.

---

## Conclusion

They say "security is invisible," but by replacing it with **"units of money"**—cloud compute billing and processing time—it suddenly becomes a very real threat right in front of your eyes.

If your project ever debates "What should our password policy be?" or "Is the stretching cost of our hashing algorithm (bcrypt or Argon2) currently sufficient?", I highly recommend calculating the "price tag" of that password using `brtc`.

👉 **[GitHub Repository](https://github.com/kanywst/brtc)**

If you have Go installed, you can try it on your machine instantly with this one-liner:

```bash
go install github.com/kanywst/brtc@latest
```
