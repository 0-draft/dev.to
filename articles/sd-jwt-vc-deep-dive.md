---
title: 'SD-JWT VC Deep Dive: vct, Issuer Keys, Type Metadata, and the URLs a Credential Makes You Fetch'
published: true
description: 'draft-ietf-oauth-sd-jwt-vc-26 turns RFC 9901 SD-JWT into a credential format. What it adds on the wire, how a verifier picks the Issuer key, why a credential is also a list of URLs, and what changed during IESG review.'
tags:
  - oauth
  - security
  - identity
  - jwt
series: OAuth
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/sd-jwt-vc-deep-dive/cover.png?v=ebf61197'
id: 5038207
date: '2026-11-14T22:24:57Z'
---

I started reading SD-JWT VC as a token format and finished reading it as an HTTP client spec. A received credential carries an `iss` URL, a `vct` URL, and through Type Metadata an open-ended chain of `extends` URLs plus logos, background images and SVG templates. The verifier is expected to fetch some of those. Whoever built the credential chose every one of those URLs, and with the metadata mechanism the first fetch happens before the signature can even be checked.

The other surprise was the pace. My notes were written against -23 on 4 November 2026. By 6 November the draft was at -26, and two of the open questions in those notes had been answered in the text. Everything below is checked against -26 (Datatracker and the [oauth-wg/oauth-sd-jwt-vc](https://github.com/oauth-wg/oauth-sd-jwt-vc) source at commit `d167baa`) and [RFC 9901](https://www.rfc-editor.org/rfc/rfc9901) on 15 November 2026. Section numbers are -26's.

Full notes, interop checklist and ballot tracking: [identity-deep-dive: draft-ietf-oauth-sd-jwt-vc](https://0-draft.github.io/identity-deep-dive/oauth-wg/deep-dives/draft-ietf-oauth-sd-jwt-vc/).

## What the draft adds to RFC 9901

RFC 9901 tells you how to hide a claim behind a salted digest and how a Holder proves possession with a KB-JWT. It says nothing about which claims a credential has or what they mean (draft Section 1.2). SD-JWT VC fills that gap:

| Addition | Where | What it is |
| --- | --- | --- |
| `typ: dc+sd-jwt`, `application/dc+sd-jwt` | 2.1, 2.2.1 | Explicit type. The old `vc+sd-jwt` transition note was dropped in -19 |
| `vct` | 2.2.2.1 | Credential type, a case-sensitive Collision-Resistant Name, REQUIRED |
| `aka_vcts` | 2.2.2.2 | Other types this credential also is |
| Claims that can never be hidden | 2.2.2.3 | `iss`, `nbf`, `exp`, `cnf`, `vct`, `vct#integrity`, `aka_vcts`, `status` |
| Issuer key discovery | 2.5, 4 | JWT VC Issuer Metadata at a well-known URI, or inline `x5c` |
| HTTP retrieval and SSRF rules | 3, 7.1 | Applies to every URL the spec makes you dereference |
| Type Metadata | 5, 6 | A JSON document per `vct`: display, rendering, per-claim `mandatory` / `sd` rules |

Here is what goes over the wire. I generated it with the script in [`assets/sd-jwt-vc-deep-dive/`](https://github.com/0-draft/dev.to/tree/main/articles/assets/sd-jwt-vc-deep-dive) (`run.sh`, standard library plus `cryptography`, no network):

![Anatomy of an SD-JWT VC presentation: Issuer-signed JWT with header, never-disclosable claims and digests; Disclosures the Holder chose; KB-JWT with aud, nonce and sd_hash](./assets/sd-jwt-vc-deep-dive/diagrams/01-anatomy.png?v=f862ecde)

```json
{"alg": "ES256", "typ": "dc+sd-jwt", "kid": "pid-2026"}
{
  "_sd": [
    "AbW5m0GNLc4PK-jU7HLjmfmHAL-ZNMNdD9AGeWBFjuw",
    "SQlRLSxYJNJ30OV0-XTP2VTul8XtL1Xlfoec5380Q6U",
    "gCW7f9I0jjm2ukPxzXnTGav43ZUeckZbGhxHkmiqJYo"
  ],
  "iss": "https://pid.example/issuer",
  "iat": 1799913600,
  "exp": 1831536000,
  "vct": "https://types.example/pid/v1",
  "nationalities": [
    {"...": "76xcktTALCtgwVaJ6eGyxlFFO_jw6Oz10DXd-pABy8g"},
    {"...": "wyeXqvPn6O9vYBKfmtHA_1uD7f4VuXh1qFmiv28UJxs"}
  ],
  "_sd_alg": "sha-256",
  "cnf": {"jwk": "..."}
}
```

The three `_sd` digests hide `given_name`, `birthdate` and `age_equal_or_over`. Each `nationalities` element is hidden on its own. The Holder sent two of the five Disclosures (`age_equal_or_over` and `"FR"`), and after verification the payload looks like this (`iat`, `exp` and `cnf` omitted):

```json
{
  "age_equal_or_over": {"18": true},
  "iss": "https://pid.example/issuer",
  "vct": "https://types.example/pid/v1",
  "nationalities": ["<undisclosed>", "FR"]
}
```

Keep that `"<undisclosed>"` slot in mind. Most SD-JWT libraries drop undisclosed array elements when they build the processed payload. SD-JWT VC's claim metadata rules need the position back (more below).

## `vct` and `aka_vcts`: type is not authority

`vct` is the type and also the version. Section 2.2.2.1 says an incompatible change should get a new value (`urn:example:eudi:pid:aendgard:1` becomes `:2`).

`aka_vcts` exists because Type Metadata is optional. A Verifier that asked for `urn:example:eudi:pid` and received `vct: urn:example:eudi:pid:aendgard:1` cannot always fetch metadata to learn that one extends the other, so the Issuer lists the general type itself:

```json
{
  "vct": "urn:example:eudi:pid:aendgard:1",
  "aka_vcts": ["urn:example:eudi:pid"]
}
```

For type matching, a Holder or Verifier "treats" the credential as any of these types. That word was "SHOULD treat" in -23. Éric Vyncke's DISCUSS asked why it was not a MUST, and -25 rewrote it as a plain statement. The array MUST NOT repeat the `vct` value, and there is no `aka_vcts#integrity` because nothing is fetched from those values (2.2.2.2).

The rule implementers will get wrong is in 7.7. Neither `aka_vcts` nor an `extends` chain says the Issuer is allowed to issue that type. An attacker can mint `urn:example:attacker:pid` that extends `urn:example:eudi:pid`, sign it with a valid key of its own, and every type check passes. The draft makes Issuer authorization a separate MUST: check who the Issuer is and whether it is accredited for the type, independently of the type hierarchy.

Both claims are always visible to the Verifier (8.2). A national PID `vct` tells every Verifier your country even when you only disclosed `age_equal_or_over`.

## Verification is RFC 9901 plus one policy decision

Section 2.4 is short. Run RFC 9901 Section 7. RFC 9901 Section 7.1 step 2.c says "Validate the Issuer and that the signing key belongs to this Issuer", and SD-JWT VC says that check MUST be satisfied with a key discovery mechanism "permitted for the Issuer according to policy". If Key Binding is required, verify the KB-JWT with the key in `cnf`. If `status` is present, it SHOULD be checked, and a sentence added after -23 says a Verifier that skips it "accepts that risk according to its policy".

One quiet change: `cnf` without `sub` or `iss`. RFC 7800 Section 3 says a JWT with `cnf` must contain one of them. SD-JWT VCs often have neither (`iss` is optional when `x5c` identifies the Issuer, `sub` is often omitted for privacy). Up to -23 the draft "explicitly overrides" RFC 7800 without saying it updates it. Mike Bishop held a DISCUSS on that. In -24 the header gained `Updates: 7800 (if approved)` and a new Section 2.2.2.3.1, "Confirmation Claim Independence", and his DISCUSS cleared. If your JWT library enforces RFC 7800 Section 3 strictly, it will reject valid SD-JWT VCs.

## Finding the Issuer key

Two mechanisms are defined. Ecosystems can add or override others (2.5).

### JWT VC Issuer Metadata

When `iss` is an HTTPS URL, insert `/.well-known/jwt-vc-issuer` between host and path, after stripping a trailing `/` (4.1). `iss` must have no query, no fragment and no dot-segments (4). The script's URL builder:

```text
ACCEPT  https://pid.example               (https://pid.example/.well-known/jwt-vc-issuer)
ACCEPT  https://pid.example/issuer/       (https://pid.example/.well-known/jwt-vc-issuer/issuer)
ACCEPT  https://pid.example/tenant/1234   (https://pid.example/.well-known/jwt-vc-issuer/tenant/1234)
REJECT  https://pid.example/a/../b: dot-segment in iss path
REJECT  https://pid.example/?t=1: iss not usable for metadata
```

The response (example from Section 4.2):

```http
HTTP/1.1 200 OK
Content-Type: application/json
Cache-Control: max-age=3600

{
   "issuer":"https://example.com",
   "jwks":{
      "keys":[
         {
            "kid":"doc-signer-05-25-2022",
            "kty": "EC", "crv": "P-256",
            "x": "b28d4MwZMjw8-00CG4xfnn9SLMVMM19SlqZpVb_uNtQ",
            "y": "Xv5zWwuoaTgdS6hV43yI6gBwTnjukmFQQnJ_kCxzqk8"
         }
      ]
   }
}
```

Exactly one of `jwks` and `jwks_uri`. `issuer` MUST be identical to `iss` or nothing in the response may be used (4.3). That check is what stops `https://evil.example` from serving metadata that claims another Issuer's keys.

### Inline `x5c`

The end-entity certificate's key verifies the signature, and the chain is validated per RFC 7515 Section 4.1.6 and RFC 5280 against a trust anchor permitted for that Issuer. Since -24 the text says it outright: a certificate is "not a trust anchor merely because it is included" in `x5c`. Under this mechanism the Issuer is the certificate subject, not `iss`.

### When a credential carries both

This was the sharpest open question in my -23 notes. Section 2.5 said `iss` need not match the certificate, and Section 7.3 said the `iss`-to-key relationship must be kept. Mahesh Jethanandani and Roman Danyliw both flagged the conflict. -24 resolved it:

> The recipient's policy determines which mechanism applies to an Issuer; the SD-JWT VC does not. [...] A recipient MUST NOT treat inputs of other mechanisms as identifying the Issuer unless its policy binds them to that identity

![Decision table: Verifier policy rows (metadata, x5c, x5c with iss binding, header-driven) against credential contents columns (HTTPS iss only, x5c only, both) with the resulting Issuer identity or rejection](./assets/sd-jwt-vc-deep-dive/diagrams/03-key-policy.png?v=f3fc402e)

The bottom row is the bug this prevents. I built it: an attacker holds any leaf certificate under a CA the Verifier accepts for `x5c`, puts `iss: https://pid.example/issuer` in the payload, and signs with its own key.

```text
== Section 2.5 / 7.3: same iss, attacker-made x5c
  ACCEPT  naive: header has x5c, so use x5c  (trusted iss in payload says https://pid.example/issuer; cert says CN=Some Other Issuer)
  REJECT  policy: pid.example uses metadata: Issuer signature does not verify with the policy-selected key
  ACCEPT  policy: x5c anchors, Issuer = cert subject  (Issuer = CN=Some Other Issuer)
```

The naive verifier lets the header pick the mechanism, so the signature checks out, and then it hands `iss` downstream as the Issuer. The third line is also an ACCEPT, which is correct: the credential is a valid one from "Some Other Issuer". What matters is that the identity passed downstream is the certificate subject. Section 7.3 now says it directly: "any holder of a certificate under a permitted trust anchor can include an arbitrary `iss` value". If you want to accept both and still use `iss`, bind them with a Subject Alternative Name or a configured mapping and verify that binding.

## A credential is a list of URLs

![What one credential can make a verifier GET: well-known metadata, jwks_uri, Type Metadata, each extends parent, and rendering resources, with the checks that apply to every hop](./assets/sd-jwt-vc-deep-dive/diagrams/02-fetch-graph.png?v=516172ea)

Section 3 was added in -19 and applies one set of rules to every retrieval: Issuer metadata, `jwks_uri`, Type Metadata, `extends` parents, logos, background images, SVG templates.

- `https:` only. Rendering `uri` values may also be `data:`.
- If you follow redirects, cap the count, never follow to non-HTTPS, and validate every redirect target the same way as the original URL.
- Bound each retrieval in time and size. Validate the format before processing.
- Never use the body of a 4xx/5xx as the document.

Section 7.1 defines "validate". Refuse hosts whose addresses are not globally reachable per the IANA IPv4 and IPv6 Special-Purpose Address Registries (-26 cites the registries; -23 cited RFC 6890), refuse internal host names, and resolve DNS names and check the resolved address too. My checker runs the check on every hop:

```text
== Section 3 / 7.1: URLs a credential can make you fetch
  ACCEPT  https://pid.example/.well-known/jwt-vc-issuer/issuer
  REJECT  http://pid.example/.well-known/jwt-vc-issuer/issuer: not https
  REJECT  https://127.0.0.1/admin: 127.0.0.1 is not globally reachable
  REJECT  https://[::ffff:169.254.169.254]/latest/meta-data/: not globally reachable
  REJECT  https://metadata.attacker.example/pid: -> 169.254.169.254 is not globally reachable
  REJECT  https://intranet.corp/pid.json: -> 10.0.0.5 is not globally reachable
  REJECT  https://types.example/pid/v1 -> https://10.0.0.5/pid/v1: not globally reachable
  REJECT  https://types.example/pid/v1 -> http://types.example/pid/v1: not https
```

The IPv4-mapped IPv6 line is the one hand-rolled CIDR lists miss. Python's `ipaddress.is_global` handles it. Two practical gaps that the spec leaves to you: checking the resolved address and then letting your HTTP client resolve again opens a DNS rebinding window, so connect to the address you checked. And a long chain of `extends` is not bounded by anything in -26. Section 3 bounds each request and Section 7.4 catches cycles, but a 500-deep acyclic chain passes both. Mahesh Jethanandani suggested a depth cap in his ballot comment. It is not in -26, so set one yourself.

Fetching is also a privacy problem. A malicious Issuer can mint a per-Holder `iss` like `https://example.com/issuer/holder-1234` and see each verification as a hit on its well-known endpoint (8.3). The draft's advice is to pin Issuer identifiers and to not follow remote key references in `cnf` (`x5u`, `jku`, URL `kid`) at all.

## Type Metadata

Optional, unless your policy or ecosystem says otherwise (5.7). If you do process it, process it fully, including every `extends` parent, before using any of it. Here is the spec's example of a document reached from `vct` (5.1):

```json
{
  "vct":"https://betelgeuse.example.com/education_credential/v42",
  "name":"Betelgeuse Education Credential - Version 42",
  "description":"This is our education credential. Don't panic.",
  "extends":"https://galaxy.example.com/galactic-education-credential/v2",
  "extends#integrity":
    "sha256-ilOUJsTultOwLfz7QUcFALaRa3BP/jelX1ds04kB9yU="
}
```

### Identity and integrity of the document

The retrieved document's `vct` MUST be identical to the reference you fetched it by: the credential's `vct` for the first document, the child's `extends` value for each parent (5.3). Without that, a URL can serve someone else's type definition.

`vct#integrity`, `extends#integrity` and `uri#integrity` use the W3C SRI string syntax but not SRI's algorithm (Section 6). You hash the octets of the response with the strongest algorithm listed that you support, compare, and reject on mismatch or on no supported algorithm. SRI's browser algorithm depends on CORS. This one MUST NOT. A document fetched under an integrity value may be cached indefinitely, keyed by that value, even if the response said `no-store` (5.3.4). Without integrity, RFC 9111 caching applies.

### Claim metadata

Each entry in `claims` addresses claims with a `path` array: a string selects a key, `null` selects all array elements, an integer selects an index (5.6.1). The processing rules in 5.6.1.2 distinguish errors from empty selections. A string on a non-object, or `null` or an integer on a non-array, aborts with an error. A missing key or index just drops that element.

`mandatory: true` means the Issuer MUST include the claim. `sd` is `always`, `allowed` (default) or `never`. If processing a `path` errors, if a mandatory claim is provably absent, or if a claim's selective disclosability does not match `sd`, the credential MUST be rejected (5.6, 5.7). Since -21, a malformed `display` or `svg_id` no longer causes rejection. Only `claims`, `path`, `mandatory` and `sd` do.

Three details from Section 5.6 shape the implementation:

1. A Verifier MUST NOT treat a missing selectively disclosable claim as evidence the Issuer left out a mandatory one. The Holder may simply not have disclosed it.
2. Array indexes count undisclosed elements. `["nationalities", 1]` is `"FR"` even though element 0 never arrived. That is why your SD-JWT processor must keep the positions.
3. A claim is selectively disclosable only if it is itself a Disclosure. A child of a disclosed object is not.

All three in the script's output, run against the presentation from earlier:

```text
== Section 5.6: claim metadata against the presentation
  ACCEPT  base PID claims
  REJECT  ["age_equal_or_over", "18"] declared sd=always (only its parent is a Disclosure)
  ACCEPT  ["nationalities", 0, "code"] on an undisclosed element
  REJECT  ["vct", 0] (index on a string): index on non-array
  REJECT  ["exp"] declared sd=always: must be selectively disclosable
  REJECT  mandatory ["family_name"] with no hidden digests left
```

"base PID claims" includes `given_name` as `mandatory` and `sd: always`. The Holder did not disclose it, and the check passes because two digests at the top level are still hidden. The last line only rejects because I gave the validator a payload with no undisclosed digests left, which is the only state in which a Verifier can actually prove absence.

### `extends`: tighten, never loosen

A child inherits the parent's claim metadata. For the same `path`, properties combine with the child winning, but the contents of a property are never merged: a child `display` array replaces the parent's (5.6.5). Two limits (5.6.5.1): `sd` may move from `allowed` (or omitted) to `always` or `never` and nowhere else, and `mandatory` may go from false to true but not back. Type-level `display` has a different rule: if the child defines it, the parent's is ignored entirely (5.5.2).

```text
== Section 5.3 / 5.6.5.1 / 6 / 7.4: extends chains
  ACCEPT  child adds mandatory, integrity matches  (4 claim rules)
  REJECT  child flips given_name sd always -> allowed
  REJECT  child sets mandatory given_name to false
  REJECT  parent served with sd edited: #integrity mismatch for urn:example:pid
  REJECT  URL serves a document for another vct: retrieved vct https://types.example/other != reference https://types.example/pid/v1
  REJECT  urn:a extends urn:b extends urn:a: extends cycle: urn:a -> urn:b -> urn:a
```

Trust in all of this is only as good as the Publisher (7.8). Type Metadata can come from the `vct` URL, a registry, an ecosystem-defined method, or a local cache, and the draft tells Consumers not to assume it is accurate unless the Publisher is authoritative for that type.

### Rendering

`display` is per locale (with an optional `dir` for bidi text since -20) and may carry a `rendering` object with a `simple` method (logo, background image, colors) or `svg_templates`. SVG templates use `{{svg_id}}` placeholders, only in text content, with at least `& < > " '` escaped (5.5.1.2.2):

```xml
<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
  <text x="10" y="20">Street address: {{address_street_address}}</text>
</svg>
```

The Consumer MUST NOT execute code in the template and MUST sandbox the display if it cannot reliably prevent execution (7.10). An `svg_id` may not sit on a `path` containing `null`, since that path can select several values. External references inside the SVG are a tracking channel, same as the metadata fetches. Servers SHOULD send `X-Content-Type-Options: nosniff` and a restrictive CSP like `default-src 'none'` because these documents are also reachable from plain browsers (7.2).

## What your policy has to decide

The draft defers a lot to "policy". If you are building a Verifier, these are the decisions it leaves to you, each with a concrete failure if you skip it:

| Decision | Draft section | If you leave it open |
| --- | --- | --- |
| Key mechanism per Issuer, never from the credential | 2.5, 7.3 | Any cert holder under your anchors can claim any `iss` |
| Trust anchors per Issuer for `x5c` | 2.5 | A self-signed `x5c` passes |
| Which Issuers may issue which `vct` | 7.7 | `extends` and `aka_vcts` become a type-spoofing path |
| Whether Type Metadata is required | 5.7 | Required but unfetchable must reject. Optional but fetched must still be fully processed |
| Redirect cap, time and size bounds, `extends` depth | 3, 7.4 | Unbounded fan-out from one credential |
| Address checks on every hop, connect to the checked IP | 7.1 | SSRF into cloud metadata or internal services |
| Status checking | 2.4 | Revoked credentials accepted, by policy |

## Where the draft stands (15 November 2026)

Datatracker shows -26 (6 November), IESG state "IESG Evaluation::AD Followup", Proposed Standard, `Updates: 7800 (if approved)`. The ballot page still lists Éric Vyncke's DISCUSS on -23 (the `SHOULD treat` and the status `SHOULD`), which -25 and -26 were written to answer, and notes the document has enough positions to pass once it is resolved. Mike Bishop moved to No Objection on -24.

Answered since -23: the RFC 7800 relationship (now `Updates`), `iss` plus `x5c` (policy selects, other inputs do not identify the Issuer), RFC 5280 chain validation, and `x5c` certificates not being trust anchors.

Still not in -26, from ballot comments:

- No allow-list escape from Section 7.1 for closed or enterprise deployments where the Issuer lives on a private address. Mahesh Jethanandani raised it. As written, such a deployment is non-conformant.
- No cap on `extends` depth or total retrievals per credential.
- Issuer metadata and Type Metadata are still served as `application/json`, not a dedicated media type (Mike Bishop's comment).
- Nothing says explicitly that the `issuer == iss` check holds regardless of the redirect chain the metadata came through. Implement it that way anyway.

If you have test vectors from -22, regenerate them: -23 re-signed the examples, and the KB-JWT `iat` and `sd_hash` values changed. The protocol did not.

The script and `run.sh` are in [`articles/assets/sd-jwt-vc-deep-dive/`](https://github.com/0-draft/dev.to/tree/main/articles/assets/sd-jwt-vc-deep-dive). It is under 500 lines, and every verdict above comes from one run of it. If your verifier gives a different answer on any of those lines, one of us has a bug, and I would like to know which.
