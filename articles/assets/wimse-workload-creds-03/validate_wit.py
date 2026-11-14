"""WIT validator for draft-ietf-wimse-workload-creds-03, Section 5.1.3.

Runs the spec's own example WIT (Figure 2) plus a set of mutated tokens
through the six checks of Section 5.1.3, then through the same checks with
`exp` enforced. Needs only `cryptography`.

    python3 validate_wit.py
"""

import base64
import json
import pathlib
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import (
    decode_dss_signature,
    encode_dss_signature,
)

HERE = pathlib.Path(__file__).parent


def b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def ec_pub(jwk: dict) -> ec.EllipticCurvePublicKey:
    x = int.from_bytes(b64d(jwk["x"]), "big")
    y = int.from_bytes(b64d(jwk["y"]), "big")
    return ec.EllipticCurvePublicNumbers(x, y, ec.SECP256R1()).public_key()


# Section 5.1, "Example Identity Server Key" (public part only is published).
SPEC_IS_KEY = {
    "kty": "EC",
    "kid": "June 5",
    "crv": "P-256",
    "x": "kXqnA2Op7hgd4zRMbw0iFcc_hDxUxhojxOFVGjE2gks",
    "y": "n__VndPMR021-59UAs0b9qDTFT-EZtT6xSNs_xFskLo",
}

# A lab trust domain whose Identity Server key we generate, so we can sign
# mutated tokens. The attacker has a key too, but no trust domain binds it.
LAB_KEY = ec.generate_private_key(ec.SECP256R1())
ATTACKER_KEY = ec.generate_private_key(ec.SECP256R1())

# Section 3: preconfigured, out-of-band map trust domain -> anchors.
TRUST_ANCHORS = {
    "example.com": {"June 5": ec_pub(SPEC_IS_KEY)},
    "lab.example": {"lab-1": LAB_KEY.public_key()},
}

# Section 5.1: registry values that are asymmetric signature algorithms.
# EdDSA is Deprecated by RFC 9864 but still in the registry.
ASYM_SIG_ALGS = {
    "ES256", "ES384", "ES512", "PS256", "PS384", "PS512",
    "RS256", "RS384", "RS512", "Ed25519", "Ed448", "EdDSA",
}


class Reject(Exception):
    pass


def trust_domain(sub: str) -> str:
    scheme, sep, rest = sub.partition("://")
    if not sep or scheme not in ("wimse", "spiffe"):
        raise Reject("sub is not a Workload Identifier URI")
    return rest.split("/", 1)[0]


def validate(token: str, enforce_exp: bool) -> dict:
    # 1. single well-formed JWS compact serialization
    parts = token.split(".")
    if len(parts) != 3 or any("=" in p for p in parts):
        raise Reject("not one compact JWS")
    try:
        header = json.loads(b64d(parts[0]))
        claims = json.loads(b64d(parts[1]))
    except ValueError:
        raise Reject("not one compact JWS")

    # 2. sub present, exactly one Workload Identifier; it picks the anchors
    sub = claims.get("sub")
    if not isinstance(sub, str):
        raise Reject("sub not one identifier")
    anchors = TRUST_ANCHORS.get(trust_domain(sub))
    if anchors is None:
        raise Reject(f"no anchors for {trust_domain(sub)}")

    # 3. typ conveys wit+jwt
    if header.get("typ") not in ("wit+jwt", "application/wit+jwt"):
        raise Reject(f"typ is {header.get('typ')!r}")

    # 4. signature valid under those anchors (Section 3 key selection);
    #    `iss` is never dereferenced
    if header.get("alg") != "ES256":
        raise Reject(f"header alg {header.get('alg')!r} not accepted here")
    key = anchors.get(header.get("kid"))
    if key is None:
        raise Reject(f"kid {header.get('kid')!r} unknown")
    sig = b64d(parts[2])
    der = encode_dss_signature(
        int.from_bytes(sig[:32], "big"), int.from_bytes(sig[32:], "big")
    )
    try:
        key.verify(der, f"{parts[0]}.{parts[1]}".encode(), ec.ECDSA(hashes.SHA256()))
    except InvalidSignature:
        raise Reject("bad signature")

    # 5. cnf.jwk with an alg member, constrained as in Section 5.1
    jwk = claims.get("cnf", {}).get("jwk")
    if not isinstance(jwk, dict) or "alg" not in jwk:
        raise Reject("no cnf.jwk.alg")
    if jwk["alg"] not in ASYM_SIG_ALGS:
        raise Reject(f"cnf.jwk.alg {jwk['alg']}")

    # 6. unknown claims: ignored (nothing to do)

    # Not in the 5.1.3 list. Section 5.1 makes exp mandatory, Section 9.3.1
    # says the WIT MUST have a limited lifetime, 5.3 lists "expired" as an error.
    if enforce_exp and claims.get("exp", 0) < time.time():
        raise Reject(f"expired {time.strftime('%Y-%m-%d', time.gmtime(claims['exp']))}")
    return claims


def sign(header: dict, claims: dict, key) -> str:
    h = b64e(json.dumps(header, separators=(",", ":")).encode())
    c = b64e(json.dumps(claims, separators=(",", ":")).encode())
    r, s = decode_dss_signature(key.sign(f"{h}.{c}".encode(), ec.ECDSA(hashes.SHA256())))
    return f"{h}.{c}.{b64e(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"


def lab(**over) -> str:
    header = {"alg": "ES256", "kid": "lab-1", "typ": "wit+jwt"}
    claims = {
        "sub": "wimse://lab.example/orders",
        "exp": int(time.time()) + 3600,
        "cnf": {"jwk": {"kty": "OKP", "crv": "Ed25519", "alg": "Ed25519",
                        "x": "1CXXvflN_LVVsIsYXsUvB03JmlGWeCHqQVuouCF92bg"}},
    }
    header.update(over.pop("header", {}))
    for k, v in over.items():
        if v is None:
            claims.pop(k, None)
        else:
            claims[k] = v
    key = over.get("_key", LAB_KEY)
    claims.pop("_key", None)
    return sign(header, claims, key)


SPEC_WIT = (HERE / "spec-example-wit.txt").read_text().strip()
cnf_no_alg = {"jwk": {"kty": "OKP", "crv": "Ed25519", "x": "1CXXvflN_LVVsIsYXsUvB03JmlGWeCHqQVuouCF92bg"}}
cnf = lambda alg: {"jwk": {"kty": "OKP", "crv": "Ed25519", "alg": alg, "x": "1CXXvflN_LVVsIsYXsUvB03JmlGWeCHqQVuouCF92bg"}}

CASES = [
    ("spec Figure 2 WIT", SPEC_WIT),
    ("lab WIT, fresh", lab()),
    ("typ: JWT", lab(header={"typ": "JWT"})),
    ("sub as array of two URIs", lab(sub=["wimse://lab.example/a", "wimse://lab.example/b"])),
    ("sub in unconfigured domain", lab(sub="wimse://evil.example/orders")),
    ("iss -> attacker JWKS, attacker key", lab(iss="https://evil.example/jwks.json", header={"kid": "evil"}, _key=ATTACKER_KEY)),
    ("right kid, attacker key", lab(_key=ATTACKER_KEY)),
    ("cnf.jwk without alg", lab(cnf=cnf_no_alg)),
    ("cnf.jwk.alg: HS256", lab(cnf=cnf("HS256"))),
    ("cnf.jwk.alg: EdDSA (deprecated)", lab(cnf=cnf("EdDSA"))),
    ("iss: https://other-issuer.example", lab(iss="https://other-issuer.example")),
    ("unknown claim example.com/team", lab(**{"example.com/team": "payments"})),
    ("no iss, no jti", lab()),
    ("expired an hour ago", lab(exp=int(time.time()) - 3600)),
    ("four segments", lab() + ".AAAA"),
]

if __name__ == "__main__":
    print(f"{'case':36} {'5.1.3 only':36} {'5.1.3 + exp'}")
    for name, tok in CASES:
        row = []
        for enforce in (False, True):
            try:
                validate(tok, enforce)
                row.append("ACCEPT")
            except Reject as e:
                row.append(f"reject: {e}")
        print(f"{name:36} {row[0]:36} {row[1]}")
