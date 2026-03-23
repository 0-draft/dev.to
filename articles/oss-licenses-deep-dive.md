---
title: OSS License Deep Dive
published: false
description: Graduate from "just slap MIT on it"
tags:
  - opensource
  - license
  - github
  - programming
series: OSS
id: 3386852
---

# Introduction

I've always been interested in OSS development.
But I was never that interested in licenses.

In this article, I'll dig into the **actual text** of major OSS licenses and uncover the real differences between them.

---

## 1. Two Major Camps: Copyleft vs Permissive

There are countless OSS licenses, but they fundamentally fall into just two camps.

![Major Camps](./assets/oss-licenses-deep-dive/major-campas.png)

**Permissive** — "As long as you keep the copyright notice, do whatever you want. Commercial use is fine, no obligation to disclose source code." A generous family of licenses.

**Copyleft** — "Software built with this code must guarantee the same freedoms." A family of licenses with propagation properties. Here, "propagation" means **requiring derivative works to adopt the same license (= disclose their source code)**. Strong Copyleft (GPL/AGPL) extends this obligation to the entire application, while Weak Copyleft (LGPL/MPL) only extends it to modifications of the library portion itself.

Whether the source code disclosure obligation propagates to derivative works is the single most important decision point in choosing a license.

---

## 2. The MIT License

The most widely adopted license on GitHub. Let's read the full text. It's surprisingly short.

```
Copyright (c) <year> <copyright holders>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

Just three paragraphs.

The key thing to notice is that the MIT License contains **absolutely no explicit mention of patents**.

You might wonder: "Aren't copyrights and patents the same thing?" They're completely different.

- **Copyright**: Protects the **expression** — the source code as written. The MIT License grants permission to use this copyrighted expression
- **Patent**: Protects the **algorithm or method** that the code implements. Even if you write the same algorithm from scratch without copying a single character, you can still infringe a patent

In other words, even if the MIT License says "you're free to use this code," if that code implements a patented algorithm, a situation can theoretically arise where **copyright is licensed but the patent is not**. In fact, in 2009, Microsoft sued TomTom alleging that the Linux kernel (licensed under GPLv2, with no explicit patent grant) infringed Microsoft's FAT file system patents. The case settled with TomTom taking a patent license. Being open source doesn't eliminate the risk of patent infringement lawsuits.

Whether MIT's broad language `to deal in the Software without restriction` implicitly includes a patent license is debated among legal scholars, with no definitive case law. This gray area is exactly what the next license — Apache 2.0 — was designed to resolve.

---

## 3. Apache License 2.0

Like MIT, it's a Permissive license, but designed to be more "enterprise-friendly." The reason Kubernetes, TensorFlow, and Android (AOSP) adopted it comes down to its **patent clause**.

### Patent Grant (Section 3) — Original Text

> Subject to the terms and conditions of this License, each Contributor hereby grants to You a perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable **(except as stated in this section)** patent license to make, have made, use, offer to sell, sell, import, and otherwise transfer the Work...

Three key points:

1. **Each contributor** grants a patent license (not just the original author, but all contributors)
2. The patent can be used **perpetually, worldwide, and royalty-free**
3. However, `(except as stated in this section)` — there's an exception

### Patent Retaliation Clause

That exception is this:

> If You institute patent litigation against any entity [...] alleging that the Work or a Contribution incorporated within the Work constitutes direct or contributory patent infringement, then any patent licenses granted to You under this License for that Work **shall terminate** as of the date such litigation is filed.

![Patent Retailiation Clause](./assets/oss-licenses-deep-dive/patent-retaliation-clause.png)

Crucially, **only the patent license terminates** — the copyright license itself remains.

You might think: "If the copyright license remains, what's the problem?" This is where it gets tricky. Your right to copy and distribute the code (copyright) remains, but you lose the **right to use the patented technology** that the code implements. This means you can legally possess and distribute the code, yet **running it to use the patented technology constitutes patent infringement**. Contributors (or their employers) are now in a position to bring patent infringement lawsuits against you.

This clause functions as a deterrent — a mutually assured destruction structure: "If you attack this OSS's patents, you lose your patent shield too."

### Additional Obligations Not Found in MIT

- **Stating changes**: If you modify a file, you must note that you made changes (Section 4(b))
- **NOTICE file propagation**: If the project includes a NOTICE file, derivative works must include its contents (Section 4(d))
- **No trademark rights**: The license grants no rights to use trademarks (Section 6)

In Kubernetes' case, the copyright holder is listed as "The Kubernetes Authors." This is because Google's CLA is a **license agreement**, not a copyright **assignment**, meaning individual contributors retain their copyrights.

---

## 4. The BSD License — The Non-Endorsement Clause Born from History

A Permissive license originating from UC Berkeley. Essentially almost identical to MIT, but historical circumstances produced two variations.

### BSD 2-Clause vs 3-Clause

The BSD License has two variations:

**BSD 2-Clause (Simplified BSD)** — Essentially equivalent to MIT:
1. Retain the copyright notice when redistributing source code
2. Include the copyright notice in documentation when redistributing binaries

**BSD 3-Clause (New BSD)** — In addition to the above two conditions:
3. **The names of copyright holders and contributors may not be used to endorse or promote derivative products without specific prior written permission**

This third condition is the heart of the 3-Clause. The original text:

> Neither the name of the copyright holder nor the names of its contributors may be used to **endorse or promote** products derived from this software without specific prior written permission.

This clause was born from incidents where products were marketed with claims like "This product uses UC Berkeley technology!" without permission. Since BSD 2-Clause is essentially equivalent to MIT, there's little compelling reason to choose BSD for new projects today.

---

## 5. GPL — The Copyleft Champion That Enforces "Freedom"

The legend that shaped the OSS world, and simultaneously the license that requires the most careful handling. Adopted by the Linux kernel (GPLv2), GCC, Git (GPLv2), and more.

### Understanding the Definition of "Convey" Precisely

To determine whether GPL obligations apply, you need to precisely understand "when does copyleft kick in?"

GPLv2's rule was that obligations arise when you "distribute." However, "distribute" is a term dependent on US copyright law, and it can mean different things under other countries' laws. There's no guarantee that courts in Germany or France would interpret "distribute" with the same scope as under US law.

GPLv3 solved this problem by defining its own terms independent of any specific country's legal framework:

- **Propagate**: Any activity that would constitute copyright infringement (copying, modifying, distributing, etc.). However, this excludes running on a computer or private modifications
- **Convey**: Any act that enables other parties to make or receive copies. **Network interactions are not included**

This last point is critically important:

> Mere interaction with a user through a computer network, with no transfer of a copy, **is not conveying**.

![GPL](./assets/oss-licenses-deep-dive/gpl.png)

### The Dynamic Linking Debate — FSF vs Linus Torvalds

Whether "linking" against GPL code makes your program a derivative work is one of the biggest controversies in OSS licensing.

**The FSF's position (strict)**:

> dynamic vs. static linking never makes any difference on the outcome of the analysis.

The FSF maintains that any program linked against a GPL library — whether statically or dynamically — is a derivative work and triggers GPL obligations.

**Linus Torvalds' position (pragmatic)**:

> "linking" is just a technical step, and as such is not the answer to whether something is derived or not.

Torvalds argues that the **substantive relationship** of the code matters, not the linking method. When a driver originally written for another OS is ported to Linux, "at what point does it become a derivative work?" cannot be determined by technical means alone.

> "derived work" is not what you or I define. It's what copyright law defines.

In practice, there is no definitive case law on this issue, and it remains a gray area. If you want to play it safe, following the FSF's interpretation is the prudent choice.

### Why the Linux Kernel Is "GPLv2 Only"

Many GPL projects specify "GPLv2 or any later version," but the Linux kernel deliberately adopts GPLv2 only. Torvalds has said:

> I simply don't want to be at the mercy of somebody else when it comes to something as important as the license.

Torvalds opposed GPLv3's anti-DRM/Tivoization clause (which prohibits restricting software modification on hardware), arguing that "hardware restrictions should be resolved by market forces, not enforced by licenses." Furthermore, even if they wanted to migrate to GPLv3, they would need consent from thousands of copyright holders — making it practically impossible.

---

## 6. LGPL — "Weak Copyleft" for Libraries

GPL's propagation is too strong for libraries. If glibc were GPL, every proprietary program on Linux would have to be GPL. The LGPL (Lesser GPL) solves this problem.

![LGPL](./assets/oss-licenses-deep-dive/lgpl.png)

LGPLv3 Section 4 permits "Combined Works" (your app + LGPL library) under these conditions:

1. Prominently notify that the library is covered by LGPL
2. Include copies of the GPL and LGPL license documents
3. **Allow users to replace the library** — this is the crux

The easiest way to satisfy condition 3 is **dynamic linking (shared libraries)**. If the library is a separate `.so` or `.dll` file, users can replace it themselves. With static linking, an obligation arises to provide object files enabling re-linking, which becomes cumbersome.

Notable LGPL projects: glibc, GTK, GStreamer, Qt (dual-licensed)

---

## 7. AGPL — The Strongest Copyleft That Closes the SaaS Loophole

GPL's "no obligation unless you Convey" rule became a major loophole in the SaaS era. As long as you run GPL code on a server and provide APIs or web interfaces, you're not "conveying" copies, so the source code disclosure obligation never triggers.

AGPLv3 closes this with Section 13:

> if you modify the Program, your modified version must prominently offer all users interacting with it remotely through a computer network [...] an opportunity to receive the Corresponding Source of your version

![AGPL](./assets/oss-licenses-deep-dive/agpl.png)

AGPL's power is immense. Google has **completely banned** the use of AGPL code in its internal policy:

> Code licensed under the GNU Affero General Public License (AGPL) MUST NOT be used at Google.
> — Google Open Source Policy

For Google, where Search, Gmail, Maps, YouTube, and everything else is a network service, any contamination by AGPL code risks triggering source disclosure obligations for their massive codebase.

---

## 8. License Compatibility — The Easiest Trap to Fall Into

When combining code under different licenses, **compatibility** issues arise. This is the most frequently overlooked point in practice.

The diagram below shows "Can code under the source license (arrow origin) be incorporated into a GPL project (arrow destination)?":

![License Compatibility](./assets/oss-licenses-deep-dive/license-compatibilicty.png)

### MIT/BSD → GPL: OK

MIT/BSD code can be incorporated into GPL projects. However, the resulting work as a whole becomes GPL (it gets "absorbed" by the more restrictive license).

### Apache 2.0 → GPLv2: NG

GPLv2 Section 6 states:

> You may not impose any further restrictions on the recipients' exercise of the rights granted herein.

Apache 2.0's patent retaliation clause imposes a condition on recipients: "if you file a patent lawsuit, you lose your patent license." The FSF determined this conflicts with GPLv2's prohibition on additional restrictions. When you incorporate Apache 2.0 code into a GPLv2 project and distribute it, you would need to pass along this patent condition, but GPLv2 doesn't allow that. Hence the incompatibility.

### Apache 2.0 → GPLv3: OK

GPLv3 was intentionally designed to solve this compatibility problem. Richard Stallman himself stated: "Apache 2.0 has patent clauses which are incompatible with GPL version 2; since I think those patent clauses are good, I made GPL version 3 compatible with them." GPLv3 Section 7 clearly distinguishes between "additional permissions" and "additional restrictions," establishing a framework that accommodates defensive clauses like patent retaliation.

### Practical Lesson

**The deeper your dependency chain, the more complex compatibility issues become.** For example, if your MIT project depends on Apache 2.0 Library A, and Library A depends on GPLv2 Library B, the incompatibility between Apache 2.0 and GPLv2 can result in a license violation.

---

## 9. Learning from History: License Change Controversies

In recent years, major OSS companies have changed licenses one after another, shaking the OSS community. These cases demonstrate just how important license choices are.

### React: BSD+Patents → MIT (2017)

Facebook released React under a custom "BSD+Patents" license. This license included a clause where **if you filed any patent lawsuit against Facebook (even patents unrelated to React), you would lose your right to use React**.

```
July 2017       Apache Software Foundation bans BSD+Patents in Apache projects
September 2017  WordPress (25% of all websites) announces it will stop using React
September 22, 2017  Facebook announces license change to MIT
```

A policy reversal just 8 days after WordPress' departure announcement. A case demonstrating just how powerful community pressure can be.

### MongoDB: AGPL → SSPL (2018)

In response to AWS launching a MongoDB-compatible managed service (DocumentDB), MongoDB changed from AGPL to SSPL (Server Side Public License).

SSPL's requirements are extreme: if you offer SSPL software as a service, you must release **the entire service stack** (including management tools, APIs, and infrastructure software) under SSPL.

Result:
- OSI (Open Source Initiative) refused to recognize SSPL as an open source license
- Fedora, Debian, and RHEL removed MongoDB from their repositories

### HashiCorp: MPL → BSL (2023)

In August 2023, HashiCorp changed Terraform, Vault, Consul, and all other products from MPL 2.0 to BSL (Business Source License).

```
August 10, 2023   HashiCorp announces license change to BSL
August 15, 2023   "OpenTF Manifesto" published → 33,000+ GitHub stars
August 25, 2023   Community decides to fork
September 20, 2023  Linux Foundation accepts OpenTofu (Terraform fork)
```

A fork launched in just 40 days. Over 140 companies and 700+ individuals expressed support, demonstrating strong resistance against "a single company locking up community contributions under a non-OSS license."

### Redis: BSD → RSALv2+SSPL → AGPL (2018–2025)

Redis' license journey encapsulates the difficulty of OSS licensing:

```
~2018           Redis Core: BSD 3-Clause (pure OSS)
August 2018     Optional modules only: Apache 2.0 + Commons Clause
February 2019   Modules changed to RSAL (Redis Source Available License)
March 20, 2024  Redis Core itself changed to RSALv2 + SSPL ← no longer OSS
March 28, 2024  Linux Foundation announces Valkey (fork of Redis 7.2.4)
                → Backed by AWS, Google Cloud, Oracle, etc.
May 2025        Redis 8.0 adds AGPLv3 as an additional option → returns to OSS
```

### Elasticsearch: Apache 2.0 → SSPL+ELv2 → AGPL Added (2021–2024)

Reacting to AWS offering "Amazon Elasticsearch Service" and leveraging Elastic's brand, Elastic changed from Apache 2.0 to SSPL+ELv2 in 2021. AWS forked Elasticsearch 7.10.2 and launched **OpenSearch**.

In September 2024, Elastic added AGPLv3 as a third license option, effectively returning to OSS. CEO Shay Banon stated that "Amazon has fully invested in the fork, and market confusion has largely been resolved."

### The Common Pattern

MongoDB, Elastic, and Redis all ultimately returned to OSI-recognized licenses (AGPL). **Restrictive licenses are effective short-term, but they come with the long-term cost of lost community trust and the rise of forks.**

---

## 10. Major License Comparison Summary

| License          | Type            | Commercial Use | Source Disclosure for Derivatives | Explicit Patent Protection | Practical Notes                                                |
| ---------------- | --------------- | -------------- | --------------------------------- | -------------------------- | -------------------------------------------------------------- |
| **MIT**          | Permissive      | ✅              | Not required                      | ❌                          | Simplest. Defenseless against patent risk                      |
| **Apache 2.0**   | Permissive      | ✅              | Not required                      | ✅                          | Must state changes & propagate NOTICE. Incompatible with GPLv2 |
| **BSD 3-Clause** | Permissive      | ✅              | Not required                      | ❌                          | Non-endorsement clause for advertising                         |
| **LGPL v3**      | Weak Copyleft   | ✅              | Library modifications only        | ✅                          | Safe with dynamic linking. Careful with static                 |
| **GPL v3**       | Strong Copyleft | ✅              | Entire work upon distribution     | ✅                          | No obligation for SaaS. Careful when distributing              |
| **AGPL v3**      | Strong Copyleft | ✅              | Including network provision       | ✅                          | Strongest copyleft. Google et al. ban it entirely              |

---

## 11. Hands-on: Auditing Licenses in Your Dependencies

Let's put this knowledge into practice by actually checking what licenses exist in your project's dependencies.

### For Node.js / npm Projects

```bash
# Install license-checker
npm install -g license-checker

# Display license summary for the project
license-checker --summary

# Detect GPL-family licenses (licenses requiring caution)
license-checker --onlyAllow 'MIT;Apache-2.0;BSD-2-Clause;BSD-3-Clause;ISC;0BSD' --failOn 'GPL-2.0;GPL-3.0;AGPL-3.0'
```

With the `--failOn` option, you can integrate this into your CI pipeline and fail the build the moment a GPL or AGPL package is detected.

### For Python Projects

```bash
# Install pip-licenses
pip install pip-licenses

# Display license list
pip-licenses --format=table --with-urls

# Detect GPL-family
pip-licenses --allow-only="MIT License;Apache Software License;BSD License;ISC License"
```

### Using SPDX Identifiers

[SPDX (Software Package Data Exchange)](https://spdx.org/licenses/) is the standard identifier system for licenses. It's used in `package.json` and `Cargo.toml`:

```json
// package.json
{
  "license": "MIT"
}
```

```toml
# Cargo.toml
[package]
license = "MIT OR Apache-2.0"
```

SPDX expressions use `OR` (choose either) and `AND` (must satisfy both) to represent compound licenses. In dual-licensed projects (e.g., Rust itself is `MIT OR Apache-2.0`), users can choose whichever suits them.

---

## Final Thoughts

> ⚠️ This article is a general overview for software developers and does not constitute legal advice. For actual integration into products, always consult your legal department or qualified professionals.

There's nothing wrong with "just use MIT." But whether you understand that choice is a **deliberate decision** makes a difference in your quality as an engineer.

- **Want your OSS to be widely used** → MIT or Apache 2.0
- **Want to protect users from patent risk** → Apache 2.0
- **Want to ensure improvements are contributed back** → GPL v3
- **Want contributions back even from SaaS usage** → AGPL v3
- **Want wide adoption as a library while ensuring improvements come back** → LGPL v3

Next time you create a repository on GitHub, pause for a moment at the LICENSE file selection screen. And next time you run `npm install`, try running `license-checker` once. Knowing the rules under which the giants' shoulders you stand on are provided is both a responsibility as an engineer and a shield to protect yourself.
