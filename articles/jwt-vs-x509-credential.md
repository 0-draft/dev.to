---
title: 'JWT (Access Token) vs X.509 Deep Dive: How to Choose What You Present as a Credential'
published: false
description: 'When you authorize a service or a user, the thing you hand over comes in two broad flavors: a JWT (a bearer access token) and an X.509 certificate (mTLS). They look unrelated, but a single axis explains both: bearer or proof-of-possession. Diagram-heavy, readable top to bottom so you can actually pick one.'
tags:
  - security
  - authentication
  - jwt
  - tls
series: Workload Identity
id: 3907384
---

## Introduction

I was poking around a service mesh when something struck me as odd.

Inside the mesh, Pod-to-Pod traffic authenticated with **mTLS**: both sides showed each other an X.509 certificate. But the same request, when it came from outside through an API Gateway, carried a **JWT** in `Authorization: Bearer eyJ...`. Same job ("who are you, and may you come in"), yet the thing being handed over changed depending on where you stood.

At first I assumed it was just historical mess. The more I dug, though, the more it turned out to be a clean split that comes down to **one axis**: "bearer, or proof-of-possession?"

This article lines up JWT (access tokens) and X.509 (mTLS) from the angle of "what do you present as a credential," and walks through when to pick which, top to bottom. It starts from the basics, so you can follow it even if you are not deep into OAuth or TLS.

---

## Setup: what "present a credential to get authorized" actually means

Let me get the vocabulary straight first. The "getting authorized" scene that runs through this whole article has three actors.

![Three actors: issuer, presenter, verifier, and the allow/deny decision](./assets/jwt-vs-x509-credential/diagrams/01-setup-three-actors.png)

- **Issuer**: creates the credential and hands it out. For a JWT that is the IdP (authorization server); for X.509 it is the Certificate Authority (CA).
- **Presenter**: holds the credential it received and shows it to the other side on every request.
- **Verifier**: checks whether the presented credential is genuine and whose it is, then decides to let it through or reject it.

A "credential" is the **ID badge** you present in step 2. It is structurally the same as showing your driver's license to prove your age. The question is what you use as that badge. Here the path forks into two families.

- **JWT (access token)**: a signed JSON, sent in the `Authorization` header.
- **X.509 certificate**: a digital certificate presented during the TLS handshake. The "m" in mTLS (mutual) is exactly this.

The two differ in how they look and where they ride, but the essential difference is a single thing. That is next.

---

## The core: bearer, or proof-of-possession

Every difference grows from here. Credentials split into two kinds by "can you use it just by holding it."

- **Bearer type**: anyone holding the thing can use it. Like **cash**. Drop your cash and whoever picks it up can spend it. JWT access tokens are basically this.
- **Proof-of-possession type**: showing the thing is not enough. You have to **prove every time** that it is really yours. Closer to a **bank card with a PIN**. Steal the card and you still cannot move money without the PIN (the private key). X.509 + mTLS is this.

![Bearer type is usable once stolen; proof-of-possession needs the private key](./assets/jwt-vs-x509-credential/diagrams/02-bearer-vs-pop.png)

This one picture is the most important in the article. Almost everything else is a consequence of it.

- If a JWT is stolen, the thief gets to act as "you" directly (a replay attack). That is why the standard move for JWTs is to **keep their lifetime short** so the damage window stays small.
- An X.509 certificate is more or less public information, but you cannot open a TLS session without holding the **matching private key**. Sniff the wire and copy the certificate, and you still cannot impersonate "you," because you lack the private key.

"So just always use X.509, right?" Not quite. Proof-of-possession carries its own costs (distributing, storing, and rotating private keys, plus the proxy problem covered later). That is exactly why you need to choose.

---

## Cracking each one open

Now that the axis is clear, let me look at the two real artifacts.

### JWT (access token): a signed JSON flowing through the app layer

A JWT is a string split into three parts by `.`.

```text
eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9 . eyJzdWIiOiJzdmMtYSIsImF1ZCI6... . SflKxwRJSMeKKF2QT4f...
|------------ header -----------|    |--------- payload --------|    |----- signature ----|
  alg (sign method), typ              sub (who), aud (for whom), exp    signed with private key
```

The verifier checks the signature using the key set the issuer publishes (the **JWKS**: JSON Web Key Set). The point is that the **verifier does not have to call the issuer**. If the signature checks out, it can trust the token's contents (who, until when, for whom). This is **stateless verification**. Delivery is via an HTTP header.

There are also access tokens whose contents are not a JWT, the **opaque tokens**. For those the verifier calls the issuer's introspection endpoint on every request to confirm validity (stateful). When this article says "access token," it means the **JWT form** that supports the stateless verification above.

```text
GET /api/orders HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJhbGciOiJSUzI1NiI...
```

Since this lives at the application layer (L7), anything that speaks HTTP can carry it. A proxy or a Gateway can pass it straight through as "just a header." That matters later.

### X.509 certificate: an identity proven during the TLS handshake

X.509 is presented in the middle of opening a TLS connection. Ordinary HTTPS has only the server present a certificate, but in **mTLS** the client presents one too, and on top of that **proves possession by signing with its private key**.

![mTLS handshake: the client proves key possession before any HTTP data flows](./assets/jwt-vs-x509-credential/diagrams/03-mtls-handshake.png)

The verifier walks the certificate up to a CA it trusts (the **trust bundle**) to confirm legitimacy, and then uses the `CertificateVerify` signature to confirm the peer "really holds the private key." The defining trait is that authentication finishes **before a single byte of application data flows**, and this is transport-layer (closer to L4) work.

That pins down where each one lives: a JWT is **data flowing through the app layer**, and X.509 is **an identity carved into the connection itself**.

---

## Lining them up on seven axes

With both artifacts in view, let me put them side by side. First a table for the big picture, then notes on the axes that matter most.

| Axis | JWT (access token) | X.509 (mTLS) |
| --- | --- | --- |
| Trust model | Bearer | Proof-of-possession |
| Theft resistance | Weak (steal it, use it) | Strong (useless without the private key) |
| Layer it works at | App layer (L7 / HTTP header) | Transport layer (TLS handshake) |
| Survives a proxy / LB | Yes (just a header) | No (mTLS is terminated there) |
| Verification | Check signature via JWKS (stateless) | CA chain (trust bundle) + signature check |
| Revocation | Let it expire via a short `exp` | CRL / OCSP, or short-lived certs |
| Operational cost | Low (no key distribution) | High (distribute, store, renew keys). Automated in a mesh |

Three axes are worth expanding.

### Axis 1: can it cross a proxy

This is the one that bites hardest in production. mTLS is authentication bound to "**this point-to-point connection**." Put an L7 load balancer or API Gateway in the middle that terminates TLS, and the client's identity **vanishes** there. From a service deeper than the Gateway, the peer is the Gateway, not the original client.

![At a TLS-terminating proxy, mTLS identity vanishes while a JWT passes through as a header](./assets/jwt-vs-x509-credential/diagrams/04-proxy-traversal.png)

A JWT is "data," so the Gateway can forward it deeper as a header untouched. So **if you want to carry identity end to end across several proxy hops, use a JWT**. That is the answer to the mystery from the opening: cross the Gateway and it becomes a JWT.

### Axis 2: how you revoke

When you want to cancel a credential, the two strategies are inverted.

- **JWT**: once a signed token is out, the verifier never calls the issuer, so "revoke it after the fact" is hard. So you make the lifetime **short from the start** (minutes to tens of minutes) and wait for a leaked one to expire on its own. A long-lived JWT is a red flag.
- **X.509**: you can announce "this certificate is no longer valid" via a revocation list (**CRL**) or **OCSP**. But the verifier has to go check that, which is operationally heavy. So rather than leaning on CRLs, the current trend is to make the **certificate itself short-lived** (SPIRE defaults to one hour, for example) and reissue it frequently.

The funny part is that both roads end up in the same place: "**keep it short-lived to dodge the problem.**"

### Axis 3: operational cost

X.509 means handing a private key to each workload, storing it safely, and renewing it on a schedule. That is the real source of "certificates are painful." But today a service mesh like Istio or Linkerd, or SPIFFE/SPIRE, does **this distribution and renewal fully automatically**. The old common sense that "mTLS is operationally heavy," from the days of handing out certificates by hand, has largely faded in a mesh.

The JWT side does not need to distribute a private key to clients (only the issuer holds the signing key), and the verifier just pulls the public key from the JWKS. The barrier to adoption is low.

---

## Know how each one breaks

Before you choose, it helps to know how each gets defeated, so your judgment does not wobble. The entry point for an attacker is completely different between the two.

- **JWT `alg:none`**: the biggest landmine in JWT. Set the header `alg` to `none` and a buggy implementation may accept "valid even without a signature," a classic vulnerability. You close it with a sane library and an operational rule that pins the allowed `alg` (the SPIFFE JWT-SVID spec limits `alg` to nine values and rejects `none` and the symmetric `HS*` family).
- **JWT theft and replay**: the bearer curse. Minimize the damage with a short `exp`, sending over TLS, and never logging it.
- **X.509 private key leak**: since possession of the private key is the whole basis of proof, a leaked key is game over. So keep keys off plain disk, ideally locked inside a TPM / HSM or in memory, and rotate them by keeping them short-lived.
- **X.509 CA compromise**: take over the CA and you can mint any fake identity. Managing the trust bundle matters.

X.509 says "as long as you protect the private key, being watched on the wire is fine." JWT says "as long as you protect the channel (TLS) it is easy to adopt, but a leak means instant impersonation." The point you have to defend is different.

---

## The hybrid: bearer ergonomics + proof-of-possession strength

"I want the convenience of a JWT, but I do not want it used after being stolen." Two mechanisms answer that greed. Both bolt proof-of-possession onto a JWT.

![Cert-bound tokens and DPoP both add proof-of-possession to a plain JWT](./assets/jwt-vs-x509-credential/diagrams/05-hybrid-pop.png)

- **Certificate-bound access token (RFC 8705)**: at issuance, the hash (thumbprint) of the client certificate is stamped into the token. The verifier checks that "the thumbprint written in the token" matches "the certificate on the mTLS connection it currently holds." A stolen token alone is useless because you cannot open the matching mTLS connection. Used in high-security domains like Open Banking.
- **DPoP**: for situations where you cannot run mTLS, it binds the token to a key the client holds, at the app layer. A "proof" signed with that key is attached per request, and the verifier cross-checks it against the token.

In short, "bearer or PoP" is not 0 or 1. You can **add PoP to a JWT and slide toward the middle**. But every addition costs implementation and operational effort, so for the first decision the plain two-way split is enough.

---

## Choosing by example: the SPIFFE guidance makes it concrete

**SPIFFE**, the standard for workload identity, carries both formats: the certificate flavor **X509-SVID** and the JWT flavor **JWT-SVID**. And the guidance in its docs is blunt, which makes a ready-to-use decision rule. Summarized:

> Because they are susceptible to replay attacks, use X.509-SVIDs whenever possible. Use JWT-SVID when mTLS is not practical, such as when an L7 proxy or load balancer sits between workloads.

Walk a worked example. An order service calls an inventory service.

- **Inside the mesh, Pod to Pod, direct**: no L7 proxy in between, and the sidecar rotates certificates for you. Use **X509-SVID (mTLS)**. Sniffing is useless without the private key, so it resists replay.
- **Across an API Gateway from outside, or with an L7 LB in between**: mTLS gets terminated at the Gateway and identity vanishes. Put a **JWT-SVID** in a header and carry it end to end. In return, keep `exp` short (a few minutes) to bound the theft risk.

![Decision tree: proxy in between, key automation, and replay defense lead to JWT or X.509](./assets/jwt-vs-x509-credential/diagrams/06-decision-tree.png)

In real production the standard is a hybrid: "JWT (OAuth) at the user edge, mTLS between services." You do not have to commit to one. The right answer is to **choose per boundary using the decision tree above**.

---

## Quick reference

To put the decision in one place.

| When | Pick | Why |
| --- | --- | --- |
| Service to service, direct inside a mesh | X.509 + mTLS | Auto-renewal works, resists replay |
| Crossing an L7 proxy / Gateway | JWT | mTLS is terminated and identity vanishes; a JWT survives as a header |
| From a browser / mobile | JWT | Distributing a private key to the client is impractical |
| Many services trust the same issuer | JWT | Verifiable via JWKS, no certificate distribution |
| Strong defense against replay needed | X.509, or a cert-bound / DPoP JWT | Close the bearer weakness with proof-of-possession |
| Must revoke immediately | X.509 (CRL/OCSP), or a short-lived JWT | JWT is bad at after-the-fact revocation; substitute short lifetimes |

And the one line to remember goes back to the first picture.

**A JWT works if you hold it (bearer). X.509 works if you hold it and can prove it with the private key (proof-of-possession).** Almost every other difference follows from that.

---

## Conclusion

- The two families of credential you hand over for authorization, JWT (access token) and X.509 (mTLS), can be organized along one axis: **bearer or proof-of-possession**.
- A JWT is easy and crosses proxies, but a stolen one gets used. So you protect it by keeping it **short-lived**.
- X.509 is strong, useless even if sniffed without the private key, but its weaknesses are that **identity is cut off at a proxy** and that **keys need operating**. In a mesh, automation makes the operations light.
- If you want both, you can bolt proof-of-possession onto a JWT with **RFC 8705 certificate-bound tokens** or **DPoP**.
- In practice it is not either-or; you **choose per boundary with the decision tree**. SPIFFE's "X.509 whenever possible, JWT when a proxy is in the way" works directly as the rule.

Next time you look at your own system, go boundary by boundary and check, "is what flows here a bearer, or a proof-of-possession?" If a long-lived bearer token is flowing along a near-plaintext path, that is your most dangerous spot.
