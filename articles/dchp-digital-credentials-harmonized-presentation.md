---
title: "DCHP: One CBOR Request for mdoc and SD-JWT VC, In Person and Online"
published: true
description: "OpenID and ISO SC17 WG10 are writing one request/response protocol to replace the split between ISO 18013-5 and OpenID4VP. The CDDL, the transcript that binds it together, and why the key for dc_api_origin decides your KB-JWT nonce today."
tags: ["identity", "security", "openid", "cbor"]
cover_image: "https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/dchp-digital-credentials-harmonized-presentation/cover.png"
---

A wallet that holds a mobile driving licence today speaks two protocols for the same credential. At a shop counter it answers an ISO/IEC 18013-5 `DeviceRequest` over BLE. On a website it answers an OpenID4VP Authorization Request, through the browser's Digital Credentials API. Different request languages, different session binding, different response containers.

The OpenID Foundation's Digital Credentials Harmonized Presentation (DCHP) Working Group is writing one protocol to cover both, jointly with ISO/IEC JTC 1/SC 17 WG 10. One CBOR request, one CBOR response, for ISO mdoc and SD-JWT VC, in person and online.

I read the Editor's Copy at the head of `main` and encoded a request from it. The first thing I hit: the prose table puts `dc_api_origin` at integer key 8 and the CDDL puts it at key 7. That one key changes the transcript hash, which is the KB-JWT `nonce`. Two implementations that each follow "the spec" will reject each other.

My full notes, with every open PR and issue tracked, are at [identity-deep-dive: openid/dchp](https://0-draft.github.io/identity-deep-dive/openid/deep-dives/dchp/).

## What you are reading

Everything below is from [openid/dchp](https://github.com/openid/dchp) at commit `4ddd238` (9 November 2026), which was still the head of `main` when I checked on 15 November 2026. The Document History says `-00`. The README says the Editor's Copy "is not an approved Working Group Draft".

The Introduction says the text started as an initial contribution that "was accepted as a starting point, but it doesn't yet constitute consensus on its full content". Every core clause opens with the same note:

| Clause | Consensus issue | State on 15 Nov 2026 |
| --- | --- | --- |
| Credential Request | [#24](https://github.com/openid/dchp/issues/24) | open, one comment (F2F notes, 31 Aug) |
| Response Encryption | [#25](https://github.com/openid/dchp/issues/25) | open, no comments |
| Reader Authentication | [#26](https://github.com/openid/dchp/issues/26) | open, no comments |
| Transaction Transcript | [#27](https://github.com/openid/dchp/issues/27) | open, no comments |
| Credential Response | [#28](https://github.com/openid/dchp/issues/28) | open, no comments |

If you implement any of it, pin the commit.

One more thing before the CDDL. Every message is a CBOR map with small integer keys. `credential_types` and `ScenarioSets` are labels in the document, not bytes on the wire. The working group said this directly when it classed the casing PR [#83](https://github.com/openid/dchp/pull/83) as "editorial PR only since map keys are ints, i.e., field names are not normative". The integers are the protocol.

## The flow

![DCHP flow: the verifier builds RequestPayload, ReaderTransactionTranscript and optional reader_auth; sends CredentialRequest; the wallet rebuilds the transcript, selects credentials, builds a WalletTransactionTranscript per credential, binds it into DeviceAuth or the KB-JWT nonce, HPKE-encrypts the envelope when there is no session encryption, and returns CredentialResponse. Red boxes are steps the spec leaves open.](./assets/dchp-digital-credentials-harmonized-presentation/diagrams/01-flow.png)

Red boxes are where the text is incomplete or contradicts itself. That is three of the nine steps.

Three ideas carry the design:

1. The request is a set of queries plus a small boolean language over them, independent of credential format. Format specifics live in annexes that plug into CDDL sockets.
2. Neither side sends a transcript. Both build it independently from the request bytes and from what each observed about the channel (QR code, NFC handover, OpenID4VP `client_id`, web origin). If they disagree, signatures and decryption fail.
3. That same transcript is fed into everything: the reader's signature, the HPKE response encryption, and the credential's own holder binding.

## The request

From the "Request CDDL" section:

```cddl
CredentialRequest = {
  payload:        1 => bstr,      ; CBOR-encoded RequestPayload
  ? reader_auth:  2 => COSE_Sign, ; Optional reader authentication (detached payload)
  * int => any                    ; RFU extensions
}

RequestPayload = {
  ScenarioSets:                     1 => { + ScenarioRef => ScenarioSet },
  CredentialQueries:                2 => { + CredentialRef => CredentialQuery },
  ? encryption_context:             3 => EncryptionContext,
  ? additional_encryption_contexts: 4 => { + int => EncryptionContext },
  * int => any                      ; RFU extensions
}

ScenarioSet = {
  mandatory:    1 => bool,
  combinations: 2 => [ + CredentialCombination ],
  purpose_id:   3 => [ controlled_id: tstr, + int ],
  ? extensions: 4 => { * int / tstr => any },
  * int => any
}

CredentialCombination = [ + CredentialRef ]

CredentialQuery = {
  credential_format:    1 => tstr,
  credential_types:     2 => [ + tstr ],
  elements_dict:        3 => { + ElementRef => DataElementDef },
  requested_elements:   4 => ElementLogic,
  ? general_extensions: 5 => generalExtensions,
  ? format_extensions:  6 => $formatExtensions, ; Socket
  ? encryption_ref:     7 => int,
  * int => any
}

DataElementDef = {
  path:               1 => [ + tstr ],
  ? value_match:      2 => any,
  intent_to_retain:   3 => bool,
  * int => any
}

; Conjunctive Normal Form (CNF): AND of OR of AND
ElementLogic = [ + OrGroup ]
OrGroup      = [ + AndGroup ]
AndGroup     = [ + ElementRef ]
```

The payload travels as a byte string, not a nested map. That is deliberate: the verifier signs and hashes exactly those bytes, and the wallet hashes what it received without re-encoding.

Here is the request I encoded for the hands-on below: "family name and (age over 18 or birth date) from an mDL, or age over 18 from an SD-JWT VC".

![Anatomy of the example RequestPayload: key 1 ScenarioSets holds one ScenarioSet with combinations [[1],[2]]; key 2 CredentialQueries holds query 1 (mso_mdoc, org.iso.18013.5.1.mDL, three elements, requested_elements [[[1]],[[2],[3]]]) and query 2 (dc+sd-jwt, one element, support_no_cryptographic_binding false).](./assets/dchp-digital-credentials-harmonized-presentation/diagrams/02-request-anatomy.png)

Two levels of logic, and they compose differently:

- Across credentials, a `ScenarioSet` is OR of AND. `combinations: [[1], [2]]` means "query 1 alone, or query 2 alone". `[[1, 3]]` would mean "both 1 and 3". The wallet satisfies one combination per scenario.
- Inside a credential, `requested_elements` is AND of OR of AND. `[[[1]], [[2],[3]]]` reads: element 1, and (element 2 or element 3). The spec's own second example, `[Street address] AND ([Full name] OR ([Given name] AND [Family name]))`, is why the innermost level exists.

`credential_types` became an array in PR [#61](https://github.com/openid/dchp/pull/61) (4 November 2026). It is defined as pure sugar. A query with n types "shall be processed as equivalent to" n single-type queries, and every combination that references it is copied n times, one per instance. The rationale in the text is size: one query for v1 and v2 of the same credential type. If you implement it, implement the expansion literally. A combination `[[1, 2]]` where query 1 has two types becomes two combinations.

`general_extensions` carries the cross-format knobs: `issuer_identifiers` (key 1, today only `x509_ref`, an array of Authority Key Identifiers), `allow_multiple` (2), `credential_auth_data` (3) and `support_no_cryptographic_binding` (4). `encryption_ref` routes a credential's response to an entry in `additional_encryption_contexts`. The text's example is an identity credential encrypted to one backend and a payment credential to another, inside one response.

## What the format annexes pin down

Since PR [#57](https://github.com/openid/dchp/pull/57) (9 November 2026) the core says nothing about mdoc or SD-JWT. It lists ten things a "credential format definition" must specify, and two annexes do that:

| | `mso_mdoc` | `dc+sd-jwt` |
| --- | --- | --- |
| `credential_types` entry | mdoc `DocType`, case-sensitive | `vct`, case-sensitive; inheritance undecided ([#53](https://github.com/openid/dchp/issues/53)) |
| `path` | exactly `[NameSpace, DataElementIdentifier]` | "To be completed" ([#52](https://github.com/openid/dchp/issues/52)) |
| `x509_ref` matches | AKI `keyIdentifier` of a cert in `IssuerAuth` `x5chain` | AKI `keyIdentifier` of a cert in the `x5c` header |
| `format_extensions` | `issuer_alg_values`, `device_alg_values` (COSE ints) | `sd-jwt_alg_values`, `kb-jwt_alg_values` (JWS strings) |
| Holder binding | `DeviceAuth` | KB-JWT |
| No binding allowed when | `support_no_cryptographic_binding` is `true` (non-key-bound mdoc) | same flag; otherwise a KB-JWT "shall" be present |
| `data` in response | `bstr .cbor Document` | `tstr`, compact `<JWT>~<Disclosure>~...~<KB-JWT>` |
| Transcript binding | inside `SessionTranscript`, derivation open ([#10](https://github.com/openid/dchp/issues/10)) | KB-JWT `nonce` = SHA-256(WalletTransactionTranscript), encoding and `aud` open ([#10](https://github.com/openid/dchp/issues/10)) |
| Value matching, transaction data | open (#9, #4) | open (#9, #4) |

Two mdoc rules are worth reading closely. The wallet, not the verifier, decides whether an element comes back issuer-signed or device-signed, within the MSO's `KeyAuthorizations`. And a wallet may answer a request for an element with a substitute where that element's definition allows it, which is how `age_over_NN` works in 18013-5. Both `issuer_identifiers` and the non-key-bound mdoc text carry editor's notes tying them to the second edition of ISO/IEC 18013-5, the latter "to be checked against the published text" ([#56](https://github.com/openid/dchp/issues/56)).

The SD-JWT `path` is `[ + tstr ]`, which cannot index an array. On 5 November the working group had "no objection" to widening it to `[ + tstr / int / null / bool / bstr ]`. On 15 November no PR for it was open.

## The transcript

```cddl
ReaderTransactionTranscript = {
  request_hash:    1 => bstr,          ; SHA-256 of CBOR-encoded RequestPayload bytes
  channel_binding: 2 => ChannelBinding,
  * int / tstr => any
}

WalletTransactionTranscript = {
  request_hash:         1 => bstr,
  channel_binding:      2 => ChannelBinding,
  ? encryption_context: 3 => int,      ; the encryption_ref from CredentialQuery
  * int / tstr => any
}
```

18013-5's `SessionTranscript` is a fixed-order array. DCHP makes it a map and relies on deterministic CBOR (RFC 8949 Section 4.2) for a unique encoding. The text says that is "the key difference" from 18013-5. It also means both sides must pick the same deterministic rule. RFC 8949 has two: Section 4.2.1 sorts map keys bytewise, and Section 4.2.3 describes the older length-first ordering from RFC 7049. They coincide for small integer keys and diverge once keys differ in encoded length. Open PR [#64](https://github.com/openid/dchp/pull/64) pins 4.2.1 and adds that transcripts "are never transmitted".

`ChannelBinding` is where the transport shows up: at most one engagement field (how the session started: QR, reverse QR, NFC handover, OpenID4VP `request_uri` or `client_id`, DC API origin) and at most one transmission field (BLE, NFC, Wi-Fi Aware). This is the anti-replay mechanism. A request relayed from `https://evil.example` produces a different `dc_api_origin`, so a different transcript, so the KB-JWT nonce the verifier expects never matches.

The problem is that `main` has two numberings for it:

![ChannelBinding integer keys in the prose table versus the CDDL at 4ddd238, and after open PR #76. Keys 1-4 agree; nfcv2_handover is missing from the CDDL, which shifts oidc4vp_request_uri, oidc4vp_client_id and dc_api_origin down by one. PR #76 aligns these to the prose. The transmission fields (ble_gatt vs ble_uuid, ble_l2cap uint vs map, keys 12-15 only in the CDDL) still differ after PR #76.](./assets/dchp-digital-credentials-harmonized-presentation/diagrams/03-channelbinding-keys.png)

Issue [#75](https://github.com/openid/dchp/issues/75) reports the engagement mismatch, and open PR [#76](https://github.com/openid/dchp/pull/76) renumbers the CDDL to the prose (adding `cce_handover` at 5 and renaming `oidc4vp_*` to `openid4vp_*`). Neither touches the transmission rows. In the prose, key 10 is `ble_gatt` and key 11 is a bare `uint` PSM. In the CDDL, key 10 is `ble_uuid` and key 11 is a map `{1 uuid, 2 psm}`, and keys 12 to 15 exist only in the CDDL. For an in-person BLE L2CAP session, the two documents still produce different bytes after #76.

### Where the transcript is used

Reader authentication is a `COSE_Sign` over a detached payload: "the raw CBOR-encoded `RequestPayload` together with the transaction transcript". How the two are combined is not specified, and neither is how the reader's key reaches the wallet. Open PR [#65](https://github.com/openid/dchp/pull/65) puts an X.509 `x5chain` (RFC 9360) in the protected header of the `COSE_Signature`.

Response encryption has two answers in the same document. The bullet list under "Transaction Transcript" says the `ReaderTransactionTranscript` is "used in reader authentication and response encryption". The "Use in Protocol Operations" table says the `WalletTransactionTranscript` for that credential is "supplied as info parameter for HPKE". The CDDL comments claim response encryption for both. The wallet variant differs only by `encryption_context`, so the bytes differ whenever a credential uses `encryption_ref`, and only then. That kind of disagreement passes a single-backend test and breaks in multi-key routing.

Response encryption itself is conditional: mandatory when there is no session-layer encryption ("DC API, scheme-based"), not applicable over 18013-5 BLE/NFC sessions. HPKE is mandated for non-post-quantum use, "potentially based on draft-ietf-cose-hpke".

## The response

```cddl
CredentialResponse = {
  ? unencrypted:  1 => Envelope,
  ? encrypted:    2 => [ + COSE_Encrypt ], ; Each item decrypts to bytes .cbor Envelope
  * int => any
}

Envelope = {
  credentials:    1 => { + CredentialRef => CredentialItem },
  scenarios:      2 => { + ScenarioRef   => [ + CredentialRef ] },
  * int => any
}

CredentialItem = {
  credential_format: 1 => tstr,
  data:              2 => $CredentialData,   ; Socket
  * int => any
}
```

Each envelope is self-contained. A credential needed in two envelopes (because two queries route to two keys) is duplicated. `credentials` is keyed by the same `CredentialRef` integers as the request, so the verifier maps answers back to queries with no extra lookup.

That keying has a flaw: a map key is unique, so one query can return only one credential, which contradicts `allow_multiple`. And one credential answering two queries must be copied. Open PR [#77](https://github.com/openid/dchp/pull/77) changes `credentials` to `[ + CredentialItem ]`, adds `query_refs: 3 => [ + QueryRef ]` to each item, and renames `CredentialRef` to `QueryRef`. If it merges, every response parser written against `main` breaks: the first bytes of the envelope go from `a2 01 a1 ...` (map) to `a2 01 81 ...` (array).

## Hands-on: encoding it

I wrote the request above in Python with `cbor2` (6.3.0, `canonical=True`), computed both transcripts for a DC API session from `https://verifier.example`, and compared the two `ChannelBinding` numberings. No signing or encryption, the keys are placeholders, and the HPKE algorithm id is a placeholder too. The point is the bytes both sides must agree on. Script and `run.sh` are in [`articles/assets/dchp-digital-credentials-harmonized-presentation/`](https://github.com/0-draft/dev.to/tree/main/articles/assets/dchp-digital-credentials-harmonized-presentation).

```bash
$ ./run.sh
RequestPayload: 400 bytes, CredentialRequest: 405 bytes
request_hash: 68bcbd1618d152da4387a26ad0fe5d499988cb4e7a5b9e6e835ff353f023438a

CDDL on main (dc_api_origin = 7)
  ReaderTransactionTranscript: a2015820 68bcbd16...f023438a 02a107 7818 68747470733a2f2f...
  KB-JWT nonce, hex      : 4f75d175bea2d3a3fd3ed287c86ebd11ed35385e830d4aedf40aee47ca21e88c
  KB-JWT nonce, base64url: T3XRdb6i06P9PtKHyG69Ee01OF6DDUrt9AruR8oh6Iw

prose table / PR #76 (dc_api_origin = 8)
  ReaderTransactionTranscript: a2015820 68bcbd16...f023438a 02a108 7818 68747470733a2f2f...
  KB-JWT nonce, hex      : 2e6e9cd458b28759c3580ddd89ff802f601c3afabce1c6a6ab6581a1f792d6d5
  KB-JWT nonce, base64url: Lm6c1Fiyh1nDWA3dif-AL2AcOvq84camq2WBofeS1tU

Envelope on main  : a201a102a2016964632b73642d6a777402787065794a6862 ...
Envelope under #77: a20181a3016964632b73642d6a777402787065794a686247 ...
payload match: True
```

(I split and shortened the transcript hex by hand to show the fields; the script prints it whole.)

The transcripts differ in one byte, `07` vs `08`, and the nonces share nothing. The request is 405 bytes for two queries with four elements, small enough for a QR-initiated BLE exchange or a DC API call.

`payload match: True` is the check that `cbor2`'s canonical mode is the encoding I think it is. `check_encoding.py` re-encodes the same payload with a separate 30-line encoder that sorts map keys bytewise per RFC 8949 Section 4.2.1, and the bytes match. In this payload every key is one byte long, so length-first ordering would give the same result. That is exactly why a test like this can pass between two libraries that disagree in general.

Also note the two nonce encodings. The spec says the nonce is the SHA-256 of the transcript, but a JWT claim is a string, and whether that string is hex, base64url or something else is open (#10). Pick one and you have implemented a guess.

## What is still open

- Transcript mapping into mdoc `SessionTranscript`, the KB-JWT `nonce` encoding and `aud`: issue [#10](https://github.com/openid/dchp/issues/10). The chairs proposed a dedicated transcript call for 16 November 2026, 14:00 UTC. Until this closes, neither format's holder binding can be implemented end to end.
- Prose vs CDDL keys: [#75](https://github.com/openid/dchp/issues/75) / PR #76 for engagement fields; nothing filed for the BLE transmission fields as far as I can see.
- Deterministic CBOR rule: PR #64.
- Reader key conveyance: PR #65.
- Response shape: PR #77.
- `reader` to `verifier` naming, including `reader_auth` to `verifier_auth`: PR [#81](https://github.com/openid/dchp/pull/81). Names only, keys unchanged.
- SD-JWT `path`, `vct` inheritance, non-X.509 SD-JWT issuers, value matching, transaction data: #52, #53, an editor's note, #9, #4.
- Security Considerations: absent. PR [#85](https://github.com/openid/dchp/pull/85) adds a "To be completed" placeholder so that a WG Draft can be published.
- Publication: a WG Draft -00 ([#72](https://github.com/openid/dchp/issues/72)) was deferred on 4 November by "approx. 1-2 months". On the ISO side the route is a Publicly Available Specification or a PSDO publication ([#13](https://github.com/openid/dchp/issues/13)). The `Internet-Draft` header in the source is toolchain scaffolding, and a comment in the file says it is "NOT a claim that this is an IETF document".

## If you are building a wallet or verifier now

The request model is the part I would prototype against: scenarios over queries, CNF over elements, the `credential_types` expansion, per-query encryption routing. It is small and the annexes make the mdoc side concrete.

I would not ship anything that hashes a transcript yet. The `ChannelBinding` keys, the HPKE info input, the deterministic encoding rule and the nonce string all have two or more readings on `main`, and each one silently changes bytes that the other side computes independently. Record the commit you implement, put both numberings behind a flag, and watch #10 and #76.
