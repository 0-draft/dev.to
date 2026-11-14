---
title: 'OpenID4VCI Deep Dive: 1.0 Final, the Errata, Interactive Authorization in 1.1, and Server-to-Server'
published: true
description: 'OpenID for Verifiable Credential Issuance 1.0 went Final in September 2025. The repo now carries three more texts that disagree on the wire: a 1.0 errata draft, a 1.1 draft with browserless Interactive Authorization, and a new Server-to-Server API. Both grant flows with real message names, and what changes after Final.'
tags:
  - openid
  - oauth
  - identity
  - security
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/openid4vci-deep-dive/cover.png?v=b4e9ff29'
id: 5038227
date: '2026-11-14T22:31:48Z'
---

In OpenID4VCI 1.0 Final, a Wallet that sends the wrong PIN gets `invalid_grant`. A Wallet whose Pre-Authorized Code has expired also gets `invalid_grant`. The Wallet can't tell "ask the user to type it again" from "this offer is dead", and the Final text puts no limit on how many PINs an attacker may try against one code.

Both have been addressed since, in two different documents with two different answers, and neither document is the text that was approved. That's the state of OpenID4VCI in late 2026: one Final spec, and three editor's drafts next to it that a peer might be following instead.

I checked everything against [openid/OpenID4VCI](https://github.com/openid/OpenID4VCI) at commit `21ffd6c` (27 October 2026) and the PRs it cites, on 2026-11-15. My full notes are on [Identity Deep Dive](https://0-draft.github.io/identity-deep-dive/openid/deep-dives/OpenID4VCI/).

## Four texts

| Text | Where | Status |
| --- | --- | --- |
| 1.0 Final | `openid-4-verifiable-credential-issuance-1_0-final.html`, git tag `1.0-final` | Approved 16 September 2025: 102 approve, 1 object, 12 abstain |
| 1.0 errata set 1 | `1.0/`, revision `-19` | Editor's draft |
| 1.1 | `1.1/`, revision `-01` | Editor's draft, "created with same text as 1.0 Final" and then extended |
| Server to Server | `s2s/`, revision `-01` | First draft merged 4 August 2026 (#753) |

All four belong to the OpenID Digital Credentials Protocols (DCP) working group. Section numbers below are from 1.0 unless I say 1.1 or s2s. 1.1 inserted a new Section 6, so everything after Section 5 shifts by one there.

## The model in one paragraph

The Credential Issuer is an OAuth Resource Server. Its one mandatory endpoint is the Credential Endpoint; a Nonce Endpoint, a Deferred Credential Endpoint, a Notification Endpoint and Credential Offers are optional (Section 3.1). The Wallet is the OAuth client. It finds the Authorization Server through `authorization_servers` in the issuer's metadata, gets an access token, and calls `POST /credential`. On top of plain OAuth, 1.0 adds four things (Section 3.2): the grant type `urn:ietf:params:oauth:grant-type:pre-authorized_code`, the RAR type `openid_credential`, the `issuer_state` authorization request parameter, and a `credential_offer_endpoint` in Wallet client metadata.

Everything format-specific (SD-JWT VC, mdoc, the W3C VCDM variants) is pushed into Appendix A. The flow is the same for all of them.

## Pre-Authorized Code Flow

The issuer has already identified the user through its own process (a bank login, a counter visit), so the Wallet never sees an Authorization Endpoint. It gets a code in a QR and trades it for a token.

![Pre-Authorized Code Flow: Credential Offer QR, tx_code by SMS, metadata fetch, Token Request with pre-authorized_code and tx_code, nonce, Credential Request with jwt proofs, 200 or 202](./assets/openid4vci-deep-dive/diagrams/01-pre-authorized-code-flow.png?v=6539fc3d)

The offer (Section 4.1.1). In a QR it is usually by reference (`credential_offer_uri`), because the by-value JSON doesn't fit; the two parameters MUST NOT appear together:

```json
{
  "credential_issuer": "https://credential-issuer.example.com",
  "credential_configuration_ids": ["UniversityDegreeCredential"],
  "grants": {
    "urn:ietf:params:oauth:grant-type:pre-authorized_code": {
      "pre-authorized_code": "adhjhdjajkdkhjhdj",
      "tx_code": {
        "description": "Please provide the one-time code which was sent to your mobile phone via SMS"
      }
    }
  }
}
```

`tx_code` here is an object, not the code. Its presence, even as `{}`, means "a Transaction Code is required". `input_mode` defaults to `numeric`, `length` is a UI hint, and `description` is capped at 300 characters. The code itself goes to the user over a second channel. Then the Token Request (Section 6.1):

```http
POST /token HTTP/1.1
Host: server.example.com
Content-Type: application/x-www-form-urlencoded

grant_type=urn:ietf:params:oauth:grant-type:pre-authorized_code
&pre-authorized_code=SplxlOBeZQQYbYS6WxSbIA
&tx_code=493536
&authorization_details=%5B%7B%22type%22%3A%20%22openid_credential%22%2C%20%22
    credential_configuration_id%22%3A%20%22UniversityDegreeCredential%22%7D%5D
```

There is no `client_id`. Client authentication is OPTIONAL for this grant, and an AS advertises whether it accepts anonymous requests with `pre-authorized_grant_anonymous_access_supported`.

That gives you the security model. The spec says it plainly in Section 13.6.1: the Pre-Authorized Code "is not bound to a certain session (as the Authorization Code Flow does with PKCE)". Whoever scans the QR first holds a bearer code. The offer itself is unauthenticated too: Section 13.5 says the Wallet MUST treat every value in it as untrusted and run the same issuer checks as if the user had started the flow. The `tx_code` is the only thing tying the code to the person who received the SMS. A 6-digit numeric `tx_code` is 10^6 guesses, and 1.0 Final says nothing about rate limiting them. That's the gap the errata closes, further down.

## Authorization Code Flow

This one is ordinary OAuth with PKCE, with two OpenID4VCI-specific parameters.

![Authorization Code Flow: optional offer with issuer_state, metadata, PAR with authorization_details of type openid_credential, browser /authorize, code, Token Request, credential_identifiers, Credential Request](./assets/openid4vci-deep-dive/diagrams/02-authorization-code-flow.png?v=298a2ebb)

The Wallet asks for credentials either by `scope` (taken from the `scope` field of the configuration in `credential_configurations_supported`) or with RAR:

```json
[
  {
    "type": "openid_credential",
    "credential_configuration_id": "UniversityDegreeCredential"
  }
]
```

If the issuer's metadata lists `authorization_servers`, the `locations` field MUST carry the Credential Issuer Identifier, because one AS can front several issuers (Section 5.1.1).

`issuer_state` is the hook back to an issuer-initiated offer. If the offer contained one and the Wallet picks this grant, the Wallet MUST send it back. The AS in turn MUST assume it may have been injected by an attacker (Section 5.1.3), because offers are unauthenticated.

The Token Response decides what the Wallet sends next, and this is the part implementations get wrong:

```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6Ikp..sHQ",
  "token_type": "Bearer",
  "expires_in": 86400,
  "authorization_details": [
    {
      "type": "openid_credential",
      "credential_configuration_id": "UniversityDegreeCredential",
      "credential_identifiers": [
        "CivilEngineeringDegree-2023",
        "ElectricalEngineeringDegree-2023"
      ]
    }
  ]
}
```

If `credential_identifiers` came back, the Credential Request MUST use `credential_identifier` and MUST NOT carry `credential_configuration_id`. If they didn't (the `scope` path, with an AS that doesn't return them), it's the other way round (Sections 3.3.4 and 8.2). One configuration can expand into several datasets; here, two degrees.

PKCE is unchanged; I wrote about it in [RFC 7636 Deep Dive](https://dev.to/kanywst/rfc-7636-deep-dive-how-pkce-kills-authorization-code-interception-attacks-91i).

## The Credential Endpoint, shared by both

If the issuer has a Nonce Endpoint, the Wallet first does `POST /nonce` with no access token and gets `{"c_nonce": "..."}` back with `Cache-Control: no-store` (Section 7). An issuer that wants nonces in proofs MUST run this endpoint. Then the Credential Request (Section 8.2):

```http
POST /credential HTTP/1.1
Host: server.example.com
Content-Type: application/json
Authorization: Bearer czZCaGRSa3F0MzpnWDFmQmF0M2JW

{
  "credential_identifier": "CivilEngineeringDegree-2023",
  "proofs": {
    "jwt": ["eyJ0eXAiOiJvcGVuaWQ0dmNpLXByb29mK2p3dCIs...", "eyJraWQiOi..."]
  }
}
```

A decoded `jwt` proof from Appendix F.1:

```json
{
  "typ": "openid4vci-proof+jwt",
  "alg": "ES256",
  "jwk": { "kty": "EC", "crv": "P-256", "x": "nUWAoAv3...", "y": "HskHU8Bj..." }
}.{
  "aud": "https://credential-issuer.example.com",
  "iat": 1701960444,
  "nonce": "LarRGSbmUPYtRYO6BQ4yn8"
}
```

`iss` is the `client_id`, and it MUST be omitted when the token came from an anonymous Pre-Authorized Code request. The other proof types are `di_vp` (nonce in `challenge`, issuer in `domain`) and `attestation`.

The array is the batch. Each key gets at most one credential, and every credential in one response shares the same Credential Format and Credential Dataset but SHOULD differ in key (Section 3.3.2). That is how a Wallet gets ten unlinkable copies of the same mDL. Different formats or datasets need separate requests.

The response is either `200` with `credentials: [{credential: ...}]`, or, when the issuer can't issue yet, `202` with `transaction_id` and `interval`. The 202 is a MUST, not a hint (Section 8.3). The Wallet then polls `POST /deferred_credential` with the `transaction_id`, and gets 200 or another 202 with the same id (Section 9).

Errors that matter in practice: `invalid_proof` covers a missing proof and a proof without the required `c_nonce`, while `invalid_nonce` means the nonce is there but stale, so the Wallet should fetch a new one and retry (Section 8.3.1.2). `credential_request_denied` is unrecoverable.

## What the 1.0 errata draft actually changes

The notes I started from listed the Document History entries. I wanted the whole picture, so I diffed tag `1.0-final` against `1.0/` at `21ffd6c`. That's the entire normative delta: 33 lines added, 7 removed.

- `202 OK` becomes `202 Accepted` in the deferred example (#722).
- "MUST but used" becomes "MUST be used" in Section 9.1.
- A paragraph in Section 14.2: if Cryptographic Key Binding isn't needed, the issuer omits `cryptographic_binding_methods_supported`, therefore also `proof_types_supported`, and the Wallet omits `proofs` (#714). This is the coupon and ticket case.
- The metadata URL rule for a trailing `/` is back (#775).
- New Section 13.6.3, Transaction Code Guessing (#686).

The trailing slash looks like nothing, but it changes which URL a Wallet fetches:

| Credential Issuer Identifier | 1.0 Final, read literally | errata `-19` and 1.1 |
| --- | --- | --- |
| `https://issuer.example.com/tenant` | `/.well-known/openid-credential-issuer/tenant` | same |
| `https://issuer.example.com/tenant/` | `/.well-known/openid-credential-issuer/tenant/` | `/.well-known/openid-credential-issuer/tenant` |
| `https://tenant.issuer.example.com` | `/.well-known/openid-credential-issuer` | same |

The rule used to be there. PR #527 rewrote the sentence to insert the well-known segment between host and path, RFC 8414 style, and the "remove any terminating `/`" clause got lost. Issue #744 points out that RFC 8414 Section 3.1 has the rule and Final is "silent", and its author says restoring it "would technically be a breaking change". It was raised with the conformance suite team as well. If your identifier ends in `/`, serve both paths until this settles.

Transaction Code Guessing is what the opening was about. Here is how the error behaviour now differs across the three 1.x texts:

![Decision table of Token Error responses for pre-authorized_code: wrong tx_code, too many attempts, expired code, missing tx_code, across 1.0 Final, errata -19 and 1.1 -01](./assets/openid4vci-deep-dive/diagrams/04-tx-code-errors.png?v=8bc4f7b0)

The new section says the AS SHOULD cap failed `tx_code` attempts per Pre-Authorized Code, invalidate the code once the cap is hit, treat `tx_code` as single-use, and return `invalid_grant` for a dead code. For a wrong code on a live grant, the errata text says the AS SHOULD return "an error indicating that the provided Transaction Code is invalid". It doesn't name one. Section 6.3 of the same errata draft still lists the wrong-`tx_code` case under `invalid_grant`, and an errata can't add an error code to a Final. The same PR (#686) gave 1.1 a real one, `invalid_tx_code` (1.1 Section 7.3). So a 1.0 Wallet still can't tell the two cases apart from the error code alone, and a 1.1 Wallet can.

## 1.1: Interactive Authorization

This is the main reason 1.1 exists. Some issuers want to see another credential before issuing: "present your PID, then I'll issue your mDL". In 1.0 that means a browser round trip in which the AS acts as an OpenID4VP Verifier, and the Wallet ends up presenting to a web page in another app. 1.1 Section 6 lets the Wallet do it natively, as a profile of [OAuth 2.0 for First-Party Applications](https://datatracker.ietf.org/doc/draft-ietf-oauth-first-party-apps/) (FPA, pinned at draft -04).

![Interactive Authorization: POST to the authorization challenge endpoint with interaction_types_supported, 403 insufficient_authorization with auth_session and openid4vp_request, presentation, second POST with auth_session and openid4vp_response, 200 authorization_code, Token Request](./assets/openid4vci-deep-dive/diagrams/03-interactive-authorization.png?v=6ec019e7)

The AS advertises `authorization_challenge_endpoint` in its metadata (that's the FPA name), and can set `require_interactive_authorization: true` if it accepts nothing else (1.1 Section 13.3). The Wallet's first request is a normal authorization request sent as a POST, plus `interaction_types_supported`, a comma-separated list of URNs:

- `urn:openid:dcp:ia:openid4vp_presentation`
- `urn:openid:dcp:ia:auth_via_web`

The AS answers with FPA's 403 (#781 moved it from 401 to match FPA -04):

```http
HTTP/1.1 403 Forbidden
Content-Type: application/json
Cache-Control: no-store

{
  "error": "insufficient_authorization",
  "interaction_type_required": "urn:openid:dcp:ia:openid4vp_presentation",
  "auth_session": "wxroVrBY2MCq4dDNGXACS",
  "openid4vp_request": {
    "response_type": "vp_token",
    "response_mode": "ia_post",
    "dcql_query": { "credentials": [ { "id": "some_identity_credential", "format": "dc+sd-jwt" } ] },
    "nonce": "n-0S6_WzA2Mj"
  }
}
```

The Wallet presents and POSTs back `auth_session` plus `openid4vp_response` to the same endpoint. That can repeat. When the AS is satisfied, it returns FPA's `200 {"authorization_code": ...}` and the rest is 1.0 again. `auth_via_web` is the escape hatch: the 403 carries a PAR-style `request_uri`, the Wallet opens a real browser (an embedded user agent is forbidden), and the redirect brings back either a `code` or an `auth_session` to continue with.

The binding rules are where the WG has spent the last six months:

- `auth_session` is REQUIRED only if the interaction type says so (#706). The Wallet MUST send the most recent one (#710). With DPoP, the AS MUST tie `auth_session` to the DPoP public key (#803), so a stolen session value is useless from another key.
- Session fixation (1.1 Section 6.2.1.4): the AS MUST bind the OpenID4VP `nonce` to the `auth_session` and check that the presentation used it.
- Forwarding (1.1 Section 6.2.1.5): a malicious AS could relay another AS's 403 to the Wallet and harvest the presentation. Two defences are given. If `expected_origins` is present, it MUST contain only the Origin of the challenge endpoint, and the Wallet checks it. The presentation's holder binding also names the challenge endpoint, and the AS checks that.
- `auth_via_web`: each `request_uri` is used once (#704), and a Wallet with concurrent sessions MUST send `state` (#797).

The draft text isn't settled yet, and three open items affect what goes on the wire:

1. The prose in 1.1 Section 6.2.1 says the AS sets `error_code` to `insufficient_authorization`. All four examples, and FPA -04 Section 5.2.2, use `error`. #819 (open) fixes the word. Implement `error`.
2. The holder-binding value for the forwarding defence differs by format. The SD-JWT VC section says the KB-JWT `aud` is the derived Origin with an `ia:` prefix, and gives `ia:https://example.com/authorize-challenge` as the example, which is a full URL. The JWT VC and Data Integrity sections say the endpoint URL. The mdoc section says the endpoint URL and "MUST NOT be prefixed with `ia:`". #812 (open, filed by someone profiling 1.1 for conformance work) lays this out and makes the right point about leniency: an AS that accepts either value to make interop work has quietly turned off the anti-relay check.
3. The Document History says `iae:`, `iae_post`, `interactive_authorization_endpoint` and `require_interactive_authorization_request`. The normative text says `ia:`, `ia_post`, `authorization_challenge_endpoint` and `require_interactive_authorization`. #811 (open) tracks this. Go by the normative text.

## 1.1: the smaller wire changes

- `invalid_tx_code` (1.1 Section 7.3), covered above.
- Credential Response gets `credential_metadata` (OPTIONAL, #721), and `credential_dataset_id` and `credential_dataset_tag` (RECOMMENDED, #472, merged 15 October 2026). The tag MUST be present when the id is, and MUST NOT be present otherwise. A Wallet holding credentials from dataset `8xR2vQpL9dKm4TzN` that sees a new tag knows the old batch is superseded. Before this, a Wallet had no standard way to tell a refresh from a new credential.
- The deferred response RECOMMENDS the same two dataset fields.
- PAR moves from an informative to a normative reference (1.0 only RECOMMENDS it), and Interactive Authorization is allowed in its place.

A 1.0 Wallet ignores the new response fields, since unknown parameters MUST be ignored. Problems only come up when the two sides disagree on a value that's actually checked: the error code, the metadata URL, the binding `aud`.

## Server to Server

The s2s draft solves a different problem. Some Wallet Providers run a backend and would rather it talk to the issuer than have every phone do so: phones are hard to update, have bad connectivity, and are a less trusted place to run issuance logic (s2s Section 4). The catch is that the backend shouldn't see the user's identity data or the credentials.

![s2s: Wallet Client builds a JWE-wrapped JWS with its Wallet Signing Key, Wallet Server relays it unread over mTLS to the Issuer Server, credentials come back encrypted to the Wallet Encryption Key](./assets/openid4vci-deep-dive/diagrams/05-s2s-visibility.png?v=9ceacce5)

It isn't OAuth at all. The Wallet Server and Issuer Server authenticate with mTLS on every endpoint (RFC 8705), send `Api-Version` with semantic versions and `Sunset` for retirement, require `x-request-id` for idempotency, and return RFC 9457 Problem Details. Anything that comes from the phone is a Client Encrypted Payload: a JWS signed with the Wallet Signing Key (WSK), wrapped in an HPKE JWE to the issuer. The inner `aud` is the JWK thumbprint of the encryption key, so a payload can't be re-wrapped to another recipient (s2s Section 5.5.2). The issuer encrypts credentials to the Wallet Encryption Key. The Wallet Server forwards ciphertext in both directions and adds its own risk signals as Verification Data.

Issuance happens in two phases. Verification (`/verification/initiate`, `/supplement`, `/status`, `/cancel`, plus `/verification/notify` back to the Wallet) ends in one of `APPROVED`, `REJECTED`, `DENIED`, `ADDITIONAL_INFO_REQUIRED`, `PENDING`, `EXPIRED`. Then `/credential/provision` returns instance ids and `/credential/get` fetches credentials. Lifecycle operations (`/credential/manage` for suspend, resume, unlink, and `/credential/status`) run in both directions.

This draft is moving fast. #809 converted every property to snake_case (merged 27 October). #810 renamed `session_id` to `wallet_id` and `credential_instance_id` to `credential_id`, and it merged on 10 November 2026, after the commit I pinned, so the current HEAD (`41c8c66`) already differs from `21ffd6c`. Deferred credentials with their own endpoint (#816) are still open. There are TODOs in the text for post-quantum algorithms and required curves. Treat it as a design document for now. Don't build to it yet.

## What I'd ship today

- Implement 1.0 Final. Accept both metadata paths when the identifier ends in `/`. On the AS, cap `tx_code` attempts and invalidate the code at the cap. The errata asks for it, and nothing in Final forbids it.
- Wallet side: treat `invalid_grant` after a `tx_code` entry as possibly fatal, and also accept `invalid_tx_code`, since a 1.1 AS will send it.
- Ignore unknown Credential Response fields, but store `credential_dataset_id` and `credential_dataset_tag` when they show up. They cost nothing and make refresh correct later.
- Interactive Authorization: prototype it, use `error`, and don't relax the binding `aud` check to work around #812.
- s2s: watch it.

Still open: whether #775's metadata rule ships as published errata or only in 1.1, how the WG settles `nonce` in key attestations (#678 currently says "at the Issuer's discretion" in its 1.0 text and "left to the Wallet" in 1.1), and when 1.1 goes to an Implementer's Draft. #687 is a personal timeline from a WG participant (jogu) that puts WG last call and a formal security analysis side by side, with the months marked "indicative".
