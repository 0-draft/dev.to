"""Encode a DCHP request, transcripts and response from openid/dchp @ 4ddd238.

Integer keys follow the CDDL in draft/digital-credentials-harmonized-presentation.md
unless noted. Keys and crypto material are placeholders: nothing here signs or
encrypts. The point is the bytes that both sides must agree on.
"""
import base64
import hashlib

import cbor2


def enc(obj):
    # RFC 8949 Section 4.2.1 core deterministic encoding (shortest ints,
    # definite lengths, map keys sorted bytewise).
    return cbor2.dumps(obj, canonical=True)


def h(b):
    return hashlib.sha256(b).digest()


# --- RequestPayload: one scenario, satisfied by an mDL OR an SD-JWT VC ---------
MDL, PID = 1, 2  # CredentialRef
AGE = 1          # ScenarioRef
request_payload = {
    1: {  # ScenarioSets
        AGE: {
            1: True,              # mandatory
            2: [[MDL], [PID]],    # combinations: OR of AND
            3: ["org.example.purposes", 1],  # purpose_id
        }
    },
    2: {  # CredentialQueries
        MDL: {
            1: "mso_mdoc",
            2: ["org.iso.18013.5.1.mDL"],
            3: {  # elements_dict: ElementRef -> DataElementDef
                1: {1: ["org.iso.18013.5.1", "family_name"], 3: False},
                2: {1: ["org.iso.18013.5.1", "age_over_18"], 3: False},
                3: {1: ["org.iso.18013.5.1", "birth_date"], 3: False},
            },
            4: [[[1]], [[2], [3]]],  # family_name AND (age_over_18 OR birth_date)
        },
        PID: {
            1: "dc+sd-jwt",
            2: ["https://credentials.example.com/identity_credential"],
            3: {1: {1: ["age_equal_or_over", "18"], 3: False}},
            4: [[[1]]],
            5: {4: False},  # general_extensions.support_no_cryptographic_binding
        },
    },
    3: {  # encryption_context (no session encryption: DC API)
        1: {1: 2, -1: 1, -2: b"\x11" * 32, -3: b"\x22" * 32},  # COSE_Key EC2/P-256, placeholder
        2: b"\x33" * 16,                                        # nonce
        3: [35],  # placeholder COSE alg id; take the real HPKE value from draft-ietf-cose-hpke
    },
}
payload_bytes = enc(request_payload)
credential_request = enc({1: payload_bytes})  # no reader_auth in this run
print(f"RequestPayload: {len(payload_bytes)} bytes, CredentialRequest: {len(credential_request)} bytes")
print("RequestPayload hex:", payload_bytes.hex())

request_hash = h(payload_bytes)
print("request_hash:", request_hash.hex())

# --- Transcripts over the DC API ------------------------------------------------
origin = "https://verifier.example"
for label, cb in [("CDDL on main (dc_api_origin = 7)", {7: origin}),
                  ("prose table / PR #76 (dc_api_origin = 8)", {8: origin})]:
    reader_tt = enc({1: request_hash, 2: cb})
    wallet_tt = enc({1: request_hash, 2: cb})  # encryption_ref absent: main context
    nonce = h(wallet_tt)
    print(f"\n{label}")
    print("  ReaderTransactionTranscript:", reader_tt.hex())
    print("  KB-JWT nonce, hex      :", nonce.hex())
    print("  KB-JWT nonce, base64url:", base64.urlsafe_b64encode(nonce).rstrip(b"=").decode())

# --- Response envelope (before encryption) --------------------------------------
sd_jwt = "eyJhbGciOiJFUzI1NiJ9.e30.sig~WyJzYWx0IiwiYWdlX2VxdWFsX29yX292ZXIiLHsiMTgiOnRydWV9XQ~eyJhbGciOiJFUzI1NiJ9.e30.sig"
envelope_main = {1: {PID: {1: "dc+sd-jwt", 2: sd_jwt}}, 2: {AGE: [PID]}}
envelope_pr77 = {1: [{1: "dc+sd-jwt", 2: sd_jwt, 3: [PID]}], 2: {AGE: [PID]}}
print("\nEnvelope on main  :", enc(envelope_main)[:24].hex(), "...")
print("Envelope under #77:", enc(envelope_pr77)[:24].hex(), "...")
