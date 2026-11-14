---
title: "aws-credentials: STS and SigV4 as a Site You Can Click Through"
published: false
description: "An interactive, bilingual site on where AWS temporary credentials come from and how requests are signed with them. The SigV4 signer runs in the browser and reproduces AWS's published examples byte for byte, which is how it found one AWS doesn't."
tags: ["showdev", "aws", "security", "iam"]
series: ShowDev
cover_image: "https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/aws-credentials/cover.png?v=6d24329a"
---

I already wrote an [AWS STS Deep Dive](https://dev.to/kanywst/aws-sts-deep-dive-19ha) and an [AWS SigV4 and SigV4A Deep Dive](https://dev.to/kanywst/aws-sigv4-and-sigv4a-deep-dive-12li). Some of it doesn't fit in prose. "Where does a call to `sts.amazonaws.com` get served?" depends on five inputs, and a paragraph can only walk one combination at a time. So I turned it into a site where you set the inputs and it draws the answer.

- Source: <https://github.com/0-draft/aws-credentials>
- Site: <https://0-draft.github.io/aws-credentials/> ([日本語](https://0-draft.github.io/aws-credentials/?lang=ja))

![The hero: pick who is asking STS for credentials and it prints their credential pass with an expiry countdown](./assets/aws-credentials/hero.png?v=320e0ecc)

Eleven chapters: why temporary keys, endpoints, all 11 STS APIs, credential paths (EC2, Lambda, ECS, IRSA, Pod Identity, Roles Anywhere, GitHub Actions, Identity Center, SAML, AssumeRoot and more), signing, sessions, trust policies, logs and limits, errors, a timeline and a glossary. Everything is in English and Japanese.

## The router

Since 2025-04-18, a global endpoint call is served in the caller's own Region, but only if the caller is in a Region enabled by default and the name was resolved by Amazon DNS in a VPC. Anything else still goes to `us-east-1`. And even when it is served locally, CloudTrail still logs it in `us-east-1` and `aws:RequestedRegion` is still `us-east-1`.

![The request router: EC2 in eu-north-1 calling sts.amazonaws.com through Amazon DNS, served in eu-north-1, logged in us-east-1](./assets/aws-credentials/router.png?v=08309d0a)

So a Region-deny SCP that doesn't allow `us-east-1` denies the call, even though nothing ever went to Virginia. Switch the caller to a laptop in Tokyo, or the resolver to public DNS, and the line moves to `us-east-1`.

## A signer that runs in the tab

The Signing chapter computes SigV4 with WebCrypto and SigV4a with `@noble/curves`, showing the canonical request, the string to sign, the four-step key derivation and the signature. The "break it" panel recomputes on every keystroke, so changing one byte of one header flips the result to `✗ SignatureDoesNotMatch: AWS would reject this`.

![The SigV4 lab: request on the wire, canonical request, string to sign, kDate to kSigning, and the final signature](./assets/aws-credentials/signer.png?v=44f45ce8)

The numbers on that screen are real. A separate Python signer, fed the same canonical request, gets the same hash and signature:

```text
f93528731eb8f001e3aa502ec66c1f69880be633bbf996372691e5e37ef01acb
0bd46ed0c9070981542dfb6a5b2852c97aec3cf7c5abea3c487181f9ebb57daf
```

## AWS's own example doesn't sign

The tests pin the signer to examples AWS publishes: Glacier's Create Vault and the S3 presigned `test.txt` URL, byte for byte. The Glacier page has a second example, the streaming Upload Archive call. Its canonical request reproduces. Its signature doesn't.

Rerun with a separate Python signer, fed the canonical request exactly as the page prints it:

```text
Create Vault    3ce5b2f2fffac9262b4da9256f8d086b4aaf42eba5f111c21681a65a127b7c2a   (page: same)
Upload Archive  e8ba379a747bc294584102fd2430f7a563696740882e149c87b15754e7c10a89   (page: b092397439375d59...)
```

The obvious explanation would be the two headers the page's request syntax shows but its canonical request leaves out, `x-amz-archive-description` and `x-amz-sha256-tree-hash`. Adding them gives a third value. The payload hash on the page is correct, only the signature is off. So the test asserts the canonical request against AWS and the signature against the independent implementation, with a comment saying which is which. Deleting the failing case would have been easier.

The notes in [`docs/signing/05-verification.md`](https://github.com/0-draft/aws-credentials/blob/main/docs/signing/05-verification.md) also say where the evidence is weaker. SigV4a key derivation has no AWS test vector, only pseudocode, so it is checked against a second implementation of that pseudocode. That rules out typos, not a shared misreading.

```text
$ npx vitest run
 Test Files  34 passed (34)
      Tests  284 passed (284)
```

## Paste an error

The Errors chapter matches the message you paste against known STS failures, in the browser. Role chaining over one hour has no error code of its own, so it is easy to misread as a permissions problem:

![The error decoder on a role-chaining ValidationError: what you see, why it happens, what to do](./assets/aws-credentials/errors.png?v=41f340c1)

## Keeping it current

STS changes quietly. Every fact on the site is pinned to a date (the last full check was 2026-11-11), and the research behind each number, with sources, is in [`docs/`](https://github.com/0-draft/aws-credentials/tree/main/docs). A monthly workflow opens an issue with the checklist to re-verify endpoint behavior, SDK defaults, Regions, quotas, condition keys and new launches. The last change it caught: since 2026-11-09, a `GetWebIdentityToken` JWT can be exchanged with `AssumeRoleWithWebIdentity` in another partition, so "credentials never cross partitions" had to go.

Not affiliated with AWS. Every key, token and account ID on the site is fake or one of AWS's published example values.

Source and issues: <https://github.com/0-draft/aws-credentials>
