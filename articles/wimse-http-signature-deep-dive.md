---
title: 'WIMSE HTTP Signatures Deep Dive: Proof of Possession That Survives the Load Balancer'
published: true
description: 'draft-ietf-wimse-http-signature profiles RFC 9421 so a workload signs each request with the key in its WIT. What is covered, why @authority is not, how wimse-aud, wimse-sign-response and wimse-req-nonce work, and what a real verifier rejects.'
tags:
  - security
  - identity
  - microservices
  - cryptography
series: Workload Identity
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/wimse-http-signature-deep-dive/cover.png?v=752f9590'
id: 5038204
date: '2026-11-14T22:24:28Z'
---

The first thing I noticed in draft-ietf-wimse-http-signature is a component it leaves out. The profile signs the method, the path, the query, the body digest and the token, but not `@authority`. A spec whose whole job is binding a request to its recipient does not sign the recipient's host name.

That is on purpose, and it explains most of the design. The draft exists for calls that go through TLS-terminating proxies and load balancers, and those boxes rewrite the authority all the time. If `@authority` were signed, every such hop would break verification. So the recipient goes into a signature parameter, `wimse-aud`, which no proxy touches.

I signed and verified requests with [wimsey](https://github.com/kanywst/wimsey), my Rust implementation of the WIMSE drafts, which is listed in the draft's Implementation Status section. If you need the WIMSE background first (WIT, WPT, trust domains), I covered it in [the WIMSE deep dive](https://dev.to/kanywst/wimse-workload-identity-in-multi-system-environments-deep-dive-standardizing-identity-5a12). My full notes on this draft, including the -07 to -08 diff, are on [identity-deep-dive](https://0-draft.github.io/identity-deep-dive/ietf-wimse/deep-dives/draft-ietf-wimse-http-signature/).

## Where the draft stands

Checked on 2026-11-15 against the datatracker and the draft repository:

| Item | State |
| --- | --- |
| Latest revision | -08, 2026-10-20 |
| WG state | Submitted to IESG for Publication |
| IESG state | AD Evaluation (AD: Charles Eckel, shepherd: Justin Richer) |
| Intended status | Proposed Standard |
| Authors | Joe Salowey, Yaron Sheffer |
| Merged for -09 | a client may reuse a server-generated `nonce` from `Accept-Signature` (#369) |
| Open | #421 (CONNECT `@authority` default port), #420 (example nonces), #419 (test vectors), #417 (intro wording) |

So the text is close to final. The -08 changes turned several loose points into MUSTs, and those are the parts that will break a -07 implementation.

## The shape of the exchange

WIMSE has two application-layer options that both carry a WIT. The WPT draft is the DPoP-style one: a separate JWT proof in a header. This draft instead uses HTTP Message Signatures ([RFC 9421](https://www.rfc-editor.org/rfc/rfc9421)): the caller signs the HTTP message itself with the private key whose public half sits in the WIT's `cnf.jwk`. The server can sign the response the same way with its own WIT. Appendix C of the draft gives response signing as one of the reasons to pick this option over WPT.

![Request and response flow through a TLS-terminating load balancer](./assets/wimse-http-signature-deep-dive/diagrams/01-request-response-flow.png?v=ca4ccca6)

The order on the server side is fixed by Section 3. The WIT is validated first, before the signature is touched, because the verification key comes out of the WIT. The message "is not processed further before it has been fully validated". Any failure, WIT or signature, returns the same 400.

## What a signed request looks like

This is the draft's own example (Section 3.7.1, generated from `includes/sigs-request.txt` at tag `draft-ietf-wimse-http-signature-08`, WIT shortened):

```http
GET /gimme-ice-cream?flavor=vanilla HTTP/1.1
Host: svcb.example.com
Signature: sig1=:wfnk8T0ysp3a6bvqZAoeBoa2dFgRHooSel8jIAbKnbIP13cpy/O1J6xAYkziiUnVQ+NlMoR+ANDBHRwoB7ZIAA==:
Signature-Input: sig1=("@method" "@path" "@query" "workload-identity-token");created=1789405135;expires=1789405435;nonce="abcd1111";tag="wimse-workload-to-workload";wimse-aud="https://svcb.example.com/gimme-ice-cream";wimse-sign-response
Workload-Identity-Token: eyJhbGciOiJFZDI1NTE5Iiwia2lkIjoiaXNzdWVyLWtleSIsInR5cCI6IndpdCtqd3QifQ.eyJjbmYiOnsiandrIjp7ImFsZyI6IkVkMjU1MTki...
```

Everything that matters is in `Signature-Input`. The covered components are the list in parentheses, and the signature parameters follow it. RFC 9421 puts that whole string into the signature base as the last line, `@signature-params`, so the parameters are signed too. That is the mechanism the draft relies on: `wimse-aud` is "protected by the signature and is not affected by hop-by-hop rewriting of the request URI" (Section 3.2).

Don't copy `nonce="abcd1111"`. -08 requires a CSPRNG nonce with at least 64 bits of entropy (96 recommended). Eight hex characters are 32 bits at most, and these are not random. Issue #420 asks for a note next to the examples saying so. It is still open.

Here is every field in the request, with the values from a request I signed with wimsey:

![Field-by-field anatomy of a WIMSE Signature-Input](./assets/wimse-http-signature-deep-dive/diagrams/02-signature-input-anatomy.png?v=a872a5e8)

Points that are easy to get wrong:

- `@query` is always covered. With no query string its value is `?`, per RFC 9421 Section 2.2.7. The first version of the independent test vectors in issue #419 left out the leading `?` in four vectors, and they had to be regenerated.
- `@path` and `@query` are separate components, not `@request-target`.
- `Content-Digest` (RFC 9530) is mandatory whenever there is a body, and the receiver MUST recompute it from the bytes it actually got. The signature alone only proves the header wasn't changed.
- `keyid` and `alg` MUST NOT appear. The key travels in the WIT, and the algorithm is `cnf.jwk.alg`. The recipient then rejects an algorithm that its local policy does not accept for that trust domain (Section 3.1).
- The WIMSE signature is found by `tag="wimse-workload-to-workload"`, never by label. An intermediary may add its own signature next to it, but two signatures carrying this tag is a reject.

## Why `@authority` is out, and what replaces it

Section 3 says it directly: "TLS-terminating proxies and load balancers commonly rewrite the authority ..., so signing it would break those deployments. Recipient binding is carried instead by the mandatory `wimse-aud` signature parameter."

The audience moves from something derived from the message to something the sender states. By default the sender uses the target URI without query or fragment, "as known to the sender". The recipient compares it against its own configured list using RFC 3986 Section 6.2.1 Simple String Comparison, which is byte for byte. `https://svcb.example.com/orders/` and `https://svcb.example.com:443/orders` are different strings and do not match. If a service answers to several spellings, each one goes into its configuration. The recipient "MUST NOT derive an acceptable audience from untrusted request fields such as `Host`", which would put the rewritten-authority problem back in.

CONNECT is the one exception. Its target is `host:port`, with no path or query, so senders cover `@method` and `@authority` and MUST NOT cover `@path` or `@query`. This was added in -08 (#368). It already has a follow-up: the issue #419 vector P-04 signed `@authority` as `svcb.example.com:443`, while RFC 9421 Section 2.2.3 normalizes by dropping the default port. The vector author corrected P-04 to `svcb.example.com` on 2026-11-13, and Yaron Sheffer opened PR #421 to spell this out in the draft. That PR is still open. The draft also doesn't say what the default `wimse-aud` is for a CONNECT target.

## Signing it for real

wimsey 0.10.1 (commit `56b0705`), built with `cargo build -p wimsey-cli` in a temp dir:

```bash
wimsey key generate --out issuer.jwk
wimsey key generate --out pop.jwk
wimsey wit issue --issuer-key issuer.jwk --cnf-key pop.jwk \
  --sub wimse://example.org/svcA --iss https://issuer.example > wit.txt

printf '{"scoop":2}' > body.json
wimsey httpsig sign --pop-key pop.jwk --method POST \
  --authority svcb.example.com --path /orders --query flavor=vanilla \
  --header 'Content-Type: application/json' --body-file body.json \
  --wit "$(cat wit.txt)" --aud https://svcb.example.com/orders --sign-response
```

```text
Signature-Input: wimse=("@method" "@path" "@query" "content-type" "content-digest" "workload-identity-token");created=1794693733;expires=1794694033;nonce="b07a6d06c25627ea5b2d82539553a606";tag="wimse-workload-to-workload";wimse-aud="https://svcb.example.com/orders";wimse-sign-response
Signature: wimse=:OWmFBgYixdL0OTnt/lTjz+cF6pQR9J03tMarf5xmLPGMEqTXL/5PGIIQdh1dhlYlHERifhzfLyjB7yofJM/hCg==:
```

The component list grew on its own: `content-type` and `content-digest` were added because the request has them. The nonce is 128 random bits. `wimse-sign-response` is a bare parameter, which is how RFC 8941 serializes Boolean true. The label is `wimse` and not `sig1`, which a WIMSE verifier doesn't care about.

The WIT it carries decodes to:

```json
{"iss":"https://issuer.example","sub":"wimse://example.org/svcA","iat":1794693733,"exp":1794697333,
 "jti":"8efd56d4ee2764a51547736ef2426c5f",
 "cnf":{"jwk":{"alg":"Ed25519","kty":"OKP","crv":"Ed25519","x":"oN8oHnsKsJRgLjqSJ3_YqhWbuQ3jMpNBG8yB1_AYbls"}}}
```

The WIT lives an hour (`exp - iat = 3600`) and the signature five minutes. Section 3 calls out that the two lifetimes are separate: `expires` is "typically much shorter" than the WIT's `exp`.

Then I verified that one signature with `wimsey httpsig verify`, changing one thing each time:

![What wimsey accepted and rejected](./assets/wimse-http-signature-deep-dive/diagrams/03-what-breaks.png?v=79041f68)

```bash
# SI / SG hold the Signature-Input and Signature values from above.
# The LB rewrote the authority; same signature.
wimsey httpsig verify --issuer-jwk issuer.jwk --wit "$(cat wit.txt)" \
  --method POST --authority svcb.internal:8443 --path /orders --query flavor=vanilla \
  --header 'Content-Type: application/json' --body-file body.json \
  --signature-input "$SI" --signature "$SG" --aud https://svcb.example.com/orders
```

```text
{
  "label": "wimse",
  "sub": "wimse://example.org/svcA"
}
```

The rewrite passed. Then I signed the same request with `--cover` including `@authority`, and the same rewrite failed with `signature verification failed`. That is the reason Section 3 leaves the component out, shown in two commands.

The body-swap row needs care. If the attacker swaps the body but leaves the signed `Content-Digest` header alone, the signature is still valid. The rejection comes only from the receiver recomputing the digest: `content-digest does not match the body`. I ran into the same thing with vector N-04 in issue #419, whose text said the swap "also makes the signature fail". It doesn't. A verifier that checks the signature and skips the digest recomputation accepts the swapped body.

## The signed response

The CLI only signs requests, so for the response I wrote a short program against the `wimsey-httpsig` crate. The request base, then the response base for a 404 that answers it:

```text
"@method": GET
"@path": /gimme-ice-cream
"@query": ?flavor=vanilla
"workload-identity-token": eyJ0eXAiOiJ3aXQrand0IiwiYWxnIjoiRWQyNTUxOSJ9...
"@signature-params": ("@method" "@path" "@query" "workload-identity-token");created=1794700000;expires=1794700300;nonce="6f1c0e9a4b2d7f3e8a5c1b90";tag="wimse-workload-to-workload";wimse-aud="https://svcb.example.com/gimme-ice-cream";wimse-sign-response
```

```text
"@status": 404
"@method";req: GET
"@path";req: /gimme-ice-cream
"@query";req: ?flavor=vanilla
"content-type": text/plain
"content-digest": sha-256=:OgY1punOtuXr2fZzBu3pJFuBvtCWUjQA3GD0Uy/O7YI=:
"workload-identity-token": <svcB WIT>
"@signature-params": ("@status" "@method";req "@path";req "@query";req "content-type" "content-digest" "workload-identity-token");created=1794700001;expires=1794700301;nonce="d93a7c01e5b84f2a6c0d1e77";tag="wimse-workload-to-workload";wimse-req-nonce="6f1c0e9a4b2d7f3e8a5c1b90"
```

Two things bind the response to its request. The `;req` components pull method, path and query from the request into the response's signature base. `wimse-req-nonce` copies the request's `nonce`. There is no `wimse-aud` on a response: wimsey's `check_response_profile` rejects one if it is there.

```text
client A, own nonce        -> Ok("wimse")
replayed to other request  -> Err(RequestNonceMismatch)
lifted onto /gimme-sorbet  -> Err(InvalidSignature)
```

The draft is careful about what this guarantees. Response signing is a MUST for the server only when the request carried `wimse-sign-response` or local policy requires it. If the client didn't ask, server-side signing is "opportunistic from the client's point of view": a middlebox that strips the signature leaves a plain response, and the client MUST accept it. Appendix A.4 makes the same point about deletion. An attacker dropping a request/response pair goes undetected unless the client asked for signing and rejects unsigned replies. `Accept-Signature` doesn't create that obligation. Only `wimse-sign-response` does, and the server treats it as authoritative when both are present.

## Errors: three problem types, one deliberate blind spot

-08 Section 3.6 replaced "a status code such as 400" with:

| Situation | Status | Problem type (`https://iana.org/assignments/http-problem-types#...`) |
| --- | --- | --- |
| WIT or signature fails, for any reason | 400 | `wimse-signature-invalid` |
| Signed response required, server has no signing support | 501 | `wimse-signed-response-unsupported` |
| Signed response required, server can't sign this one (streamed, huge) | 400 | `wimse-signed-response-unavailable` |

The first row MUST NOT say which check failed, so a probe can't tell a bad WIT from a bad signature. 401 is NOT RECOMMENDED, because it would need a `WWW-Authenticate` challenge and an `Authorization` retry, which don't fit a WIT. In the last two rows the server MUST NOT fall back to an unsigned 200.

One gap: problem details are only SHOULD. A client that doesn't accept them gets a bare 400 for both "your signature is bad" and "I can't sign this response", and the draft doesn't discuss that.

## What's still unsettled

- Verifier handling of `keyid` and `alg`: the draft only says senders MUST NOT use them. The #419 vectors expect a reject. Yaron Sheffer's personal view on the list was that "a MUST NOT in any security RFC should be rejected by the recipient", but the text doesn't say it. wimsey rejects both (`HttpSigError::ForbiddenParameter`). A verifier that ignores them is not clearly non-conformant today.
- A dangling reference: Sections 3 and 3.6 point to "Section 5.1.4" of the workload-creds draft for WIT validation. The cited -02 has no 5.1.4: its 5.1.3 is a note on `iss`. The validation procedure is 5.1.3 "Validating the WIT" in workload-creds-03, which came out after -08.
- Nonce format: -08 sets entropy but not encoding or length, and a recipient has no way to check entropy. For -09 the main branch also lets a client reuse a server-generated nonce from `Accept-Signature`, as long as that value meets the same bar.
- Replay caches are MAY and per validator. The draft says it plainly: "Without such sharing, replay to a different cluster member can still succeed." The short `expires` is what actually bounds replay.
- Re-signing at an intermediary is out of scope. A proxy that has to change a covered component has no WIMSE way to do it.

## If you're implementing this

The parts that broke or nearly broke in practice were all small byte-level things: the `?` in `@query`, the `:443` in a CONNECT `@authority`, a trailing slash in `wimse-aud`, a digest nobody recomputed. The signature math was never the problem. Two things worth doing:

1. Run your verifier against the independent vectors in [issue #419](https://github.com/ietf-wg-wimse/draft-ietf-wimse-s2s-protocol/issues/419) (v4, archived on Zenodo, now includes a boundary case at `expires + 1`).
2. Make `wimse-aud` a configured list on the recipient, and add tests that a trailing slash and an explicit default port are rejected.

The draft is in AD Evaluation now, so this is a good time to send the WG what you find while the text can still change.
