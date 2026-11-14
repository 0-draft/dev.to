"""Minimal SD-JWT VC issuer / holder / verifier, written against
draft-ietf-oauth-sd-jwt-vc-26 and RFC 9901. Standard library plus `cryptography`.

Nothing here touches the network. Metadata endpoints and DNS are dictionaries,
so every run prints the same verdicts (signatures and salts change per run).

Sections exercised:
  2.2   typ dc+sd-jwt, vct, claims that MUST NOT be disclosed
  2.4   RFC 9901 Section 7 processing + KB-JWT against cnf
  2.5   key discovery chosen by policy, not by the credential
  3/7.1 HTTPS-only retrieval, redirect and SSRF checks
  4     /.well-known/jwt-vc-issuer URL construction, issuer == iss
  5.3   retrieved vct must equal the reference, extends, cycles
  5.6   claim path processing, sd / mandatory, undisclosed array positions
  6     #integrity (SRI string, own verification procedure)
"""

import base64
import datetime
import hashlib
import ipaddress
import json
import os
import sys
from urllib.parse import urlsplit

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import (
    decode_dss_signature,
    encode_dss_signature,
)
from cryptography.x509.oid import NameOID


# ---------------------------------------------------------------- helpers
def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def unb64u(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def jwk_of(pub):
    n = pub.public_numbers()
    return {"kty": "EC", "crv": "P-256",
            "x": b64u(n.x.to_bytes(32, "big")), "y": b64u(n.y.to_bytes(32, "big"))}


def pub_of(jwk):
    return ec.EllipticCurvePublicNumbers(
        int.from_bytes(unb64u(jwk["x"]), "big"),
        int.from_bytes(unb64u(jwk["y"]), "big"), ec.SECP256R1()).public_key()


def sign_jws(priv, header, payload):
    si = b64u(json.dumps(header, separators=(",", ":")).encode()) + "." + \
        b64u(json.dumps(payload, separators=(",", ":")).encode())
    r, s = decode_dss_signature(priv.sign(si.encode(), ec.ECDSA(hashes.SHA256())))
    return si + "." + b64u(r.to_bytes(32, "big") + s.to_bytes(32, "big"))


def verify_jws(pub, jws):
    h, p, sig = jws.split(".")
    raw = unb64u(sig)
    der = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
    pub.verify(der, f"{h}.{p}".encode(), ec.ECDSA(hashes.SHA256()))  # raises on failure


def jose_parts(jws):
    h, p, _ = jws.split(".")
    return json.loads(unb64u(h)), json.loads(unb64u(p))


def digest(disclosure_b64: str) -> str:
    return b64u(hashlib.sha256(disclosure_b64.encode()).digest())


def disclosure(*items):
    return b64u(json.dumps([b64u(os.urandom(16)), *items]).encode())


class Reject(Exception):
    pass


# ---------------------------------------------------------------- the cast
NOW = 1_800_000_000
ISSUER = "https://pid.example/issuer"
issuer_key = ec.generate_private_key(ec.SECP256R1())
holder_key = ec.generate_private_key(ec.SECP256R1())
attacker_key = ec.generate_private_key(ec.SECP256R1())

# What the "network" serves. Keyed by full URL.
WEB = {
    "https://pid.example/.well-known/jwt-vc-issuer/issuer": {
        "issuer": ISSUER,
        "jwks": {"keys": [{**jwk_of(issuer_key.public_key()), "kid": "pid-2026"}]},
    },
}
# What DNS answers (made-up public addresses: the documentation ranges are
# not globally reachable, so is_global would reject them). Nothing connects.
# The attacker controls metadata.attacker.example.
DNS = {
    "pid.example": "34.117.20.10",
    "types.example": "34.117.20.11",
    "metadata.attacker.example": "169.254.169.254",
    "intranet.corp": "10.0.0.5",
}


# ---------------------------------------------------------------- Section 4 / 3 / 7.1
def well_known_url(iss: str) -> str:
    u = urlsplit(iss)
    if u.scheme != "https" or u.query or u.fragment:
        raise Reject(f"iss not usable for metadata: {iss}")
    if any(seg in (".", "..") for seg in u.path.split("/")):
        raise Reject(f"dot-segment in iss path: {iss}")
    path = u.path.rstrip("/")
    return f"https://{u.netloc}/.well-known/jwt-vc-issuer{path}"


def ssrf_check(url: str):
    u = urlsplit(url)
    if u.scheme != "https":
        raise Reject(f"not https: {url}")
    host = u.hostname or ""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        if host not in DNS:
            raise Reject(f"does not resolve: {host}")
        ip = ipaddress.ip_address(DNS[host])
    if not ip.is_global:
        raise Reject(f"{host} -> {ip} is not globally reachable")


def fetch(url: str, redirects=(), max_redirects=3):
    """Section 3: validate the URL and every redirect target before connecting."""
    chain = [url, *redirects]
    if len(redirects) > max_redirects:
        raise Reject("too many redirects")
    for hop in chain:
        ssrf_check(hop)
    final = chain[-1]
    if final not in WEB:
        raise Reject(f"404 at {final} (error content is never used)")
    return WEB[final]


# ---------------------------------------------------------------- issuance
NEVER_DISCLOSE = {"iss", "nbf", "exp", "cnf", "vct", "vct#integrity", "aka_vcts", "status"}


def issue(signer, header_extra=None, iss=ISSUER):
    d_given = disclosure("given_name", "Erika")
    d_birth = disclosure("birthdate", "1984-08-12")
    d_over18 = disclosure("age_equal_or_over", {"18": True})
    d_nat0 = disclosure("DE")
    d_nat1 = disclosure("FR")
    payload = {
        "_sd": sorted(digest(d) for d in (d_given, d_birth, d_over18)),
        "iss": iss,
        "iat": NOW - 86400,
        "exp": NOW + 86400 * 365,
        "vct": "https://types.example/pid/v1",
        "nationalities": [{"...": digest(d_nat0)}, {"...": digest(d_nat1)}],
        "_sd_alg": "sha-256",
        "cnf": {"jwk": jwk_of(holder_key.public_key())},
    }
    header = {"alg": "ES256", "typ": "dc+sd-jwt", **(header_extra or {})}
    jws = sign_jws(signer, header, payload)
    return jws, {"given_name": d_given, "birthdate": d_birth, "age": d_over18,
                 "nat0": d_nat0, "nat1": d_nat1}


def present(jws, disclosures, aud="https://verifier.example", nonce="n-0S6_WzA2Mj"):
    sd_jwt = jws + "~" + "".join(d + "~" for d in disclosures)
    kb = sign_jws(holder_key, {"alg": "ES256", "typ": "kb+jwt"}, {
        "iat": NOW, "aud": aud, "nonce": nonce,
        "sd_hash": b64u(hashlib.sha256(sd_jwt.encode()).digest()),
    })
    return sd_jwt + kb


# ---------------------------------------------------------------- verification
UNDISCLOSED = object()   # an array element whose Disclosure was not presented


def resolve_key(header, payload, policy):
    """Section 2.5: the recipient's policy picks the mechanism, the credential does not."""
    mech = policy.get(payload.get("iss"), policy.get("*"))
    if mech == "jwt-vc-issuer-metadata":
        md = fetch(well_known_url(payload["iss"]))
        if md["issuer"] != payload["iss"]:
            raise Reject("metadata issuer != iss")
        keys = md["jwks"]["keys"]
        k = next((k for k in keys if k.get("kid") == header.get("kid")), keys[0])
        return pub_of(k), payload["iss"]
    if mech == "x5c":
        ee = x509.load_der_x509_certificate(base64.b64decode(header["x5c"][0]))
        trusted = policy["x5c_anchors"]
        # Toy chain check: the end-entity must be issued by a configured anchor.
        anchor = next((a for a in trusted if a.subject == ee.issuer), None)
        if anchor is None:
            raise Reject("x5c chain does not end at a permitted trust anchor")
        anchor.public_key().verify(ee.signature, ee.tbs_certificate_bytes,
                                   ec.ECDSA(ee.signature_hash_algorithm))
        return ee.public_key(), ee.subject.rfc4514_string()
    raise Reject(f"no key discovery mechanism permitted for {payload.get('iss')}")


def verify(presentation, policy, aud="https://verifier.example", nonce="n-0S6_WzA2Mj"):
    *parts, kb = presentation.split("~")
    jws, discs = parts[0], [d for d in parts[1:] if d]
    header, payload = jose_parts(jws)
    if header.get("typ") != "dc+sd-jwt":
        raise Reject(f"typ is {header.get('typ')!r}")
    pub, issuer_id = resolve_key(header, payload, policy)
    try:
        verify_jws(pub, jws)
    except Exception:
        raise Reject("Issuer signature does not verify with the policy-selected key")

    by_digest = {digest(d): json.loads(unb64u(d)) for d in discs}
    sd_paths, hidden_keys = set(), {}

    def walk(node, path):
        if isinstance(node, dict):
            out = {}
            for dg in node.get("_sd", []):
                if dg in by_digest:
                    _, name, val = by_digest.pop(dg)
                    if path == () and name in NEVER_DISCLOSE:
                        raise Reject(f"{name} arrived in a Disclosure")
                    out[name] = walk(val, path + (name,))
                    sd_paths.add(path + (name,))
                else:
                    hidden_keys[path] = hidden_keys.get(path, 0) + 1
            for k, v in node.items():
                if k not in ("_sd", "_sd_alg"):
                    out[k] = walk(v, path + (k,))
            return out
        if isinstance(node, list):
            out = []
            for i, el in enumerate(node):
                if isinstance(el, dict) and set(el) == {"..."}:
                    sd_paths.add(path + (i,))
                    if el["..."] in by_digest:
                        _, val = by_digest.pop(el["..."])
                        out.append(walk(val, path + (i,)))
                    else:
                        out.append(UNDISCLOSED)
                else:
                    out.append(walk(el, path + (i,)))
            return out
        return node

    processed = walk(payload, ())
    if by_digest:
        raise Reject("Disclosure not referenced by any digest")

    kh, kp = jose_parts(kb)
    if kh.get("typ") != "kb+jwt":
        raise Reject("KB-JWT typ")
    try:
        verify_jws(pub_of(payload["cnf"]["jwk"]), kb)
    except Exception:
        raise Reject("KB-JWT not signed by the cnf key")
    sd_jwt = presentation[: len(presentation) - len(kb)]
    if kp["sd_hash"] != b64u(hashlib.sha256(sd_jwt.encode()).digest()):
        raise Reject("sd_hash mismatch")
    if kp["aud"] != aud or kp["nonce"] != nonce:
        raise Reject("KB-JWT aud/nonce")
    return issuer_id, processed, sd_paths, hidden_keys


# ---------------------------------------------------------------- Section 5.6.1.2
def eval_path(root, path):
    sel = [((), root)]
    for comp in path:
        nxt = []
        for p, el in sel:
            if el is UNDISCLOSED:
                continue                      # contents unknown: selects nothing deeper
            if isinstance(comp, str):
                if not isinstance(el, dict):
                    raise Reject(f"path {path}: string on non-object")
                if comp in el:
                    nxt.append((p + (comp,), el[comp]))
            elif comp is None:
                if not isinstance(el, list):
                    raise Reject(f"path {path}: null on non-array")
                nxt += [(p + (i,), v) for i, v in enumerate(el)]
            else:
                if not isinstance(el, list):
                    raise Reject(f"path {path}: index on non-array")
                if comp < len(el):
                    nxt.append((p + (comp,), el[comp]))
        sel = nxt
    return sel


def validate_claims(claims, processed, sd_paths, hidden_keys):
    for c in claims:
        sel = eval_path(processed, c["path"])
        sd = c.get("sd", "allowed")
        for p, _ in sel:
            if sd == "always" and p not in sd_paths:
                raise Reject(f"{c['path']} must be selectively disclosable")
            if sd == "never" and p in sd_paths:
                raise Reject(f"{c['path']} must not be selectively disclosable")
        if c.get("mandatory") and not sel:
            parent = tuple(x for x in c["path"][:-1])
            if hidden_keys.get(parent):
                continue        # may be one of the undisclosed digests: not evidence
            raise Reject(f"mandatory {c['path']} missing and nothing is hidden there")


# ---------------------------------------------------------------- Type Metadata
def sri(doc_bytes):
    return "sha256-" + base64.b64encode(hashlib.sha256(doc_bytes).digest()).decode()


def load_type(vct, integrity, published, seen=()):
    if vct in seen:
        raise Reject(f"extends cycle: {' -> '.join(seen + (vct,))}")
    raw = published[vct]
    if integrity and sri(raw) != integrity:
        raise Reject(f"#integrity mismatch for {vct}")
    doc = json.loads(raw)
    if doc["vct"] != vct:
        raise Reject(f"retrieved vct {doc['vct']} != reference {vct}")
    if "extends" not in doc:
        return {tuple(c["path"]): c for c in doc.get("claims", [])}
    parent = load_type(doc["extends"], doc.get("extends#integrity"), published, seen + (vct,))
    for c in doc.get("claims", []):
        key = tuple(c["path"])
        base = parent.get(key, {})
        if base.get("sd") in ("always", "never") and c.get("sd", base["sd"]) != base["sd"]:
            raise Reject(f"{list(key)}: child changes sd {base['sd']} -> {c.get('sd')}")
        if base.get("mandatory") and c.get("mandatory") is False:
            raise Reject(f"{list(key)}: child makes a mandatory claim optional")
        parent[key] = {**base, **c}       # properties combine, contents never merge
    return parent


# ---------------------------------------------------------------- the run
def show(label, fn):
    try:
        out = fn()
        print(f"  ACCEPT  {label}" + (f"  ({out})" if out else ""))
    except Reject as e:
        print(f"  REJECT  {label}: {e}")


def main():
    jws, d = issue(issuer_key, {"kid": "pid-2026"})
    h, p = jose_parts(jws)
    print("== issued SD-JWT header / payload")
    print(json.dumps(h))
    print(json.dumps({**p, "cnf": {"jwk": "..."}}, indent=2))

    pres = present(jws, [d["age"], d["nat1"]])
    print(f"\n== presentation: {len(pres)} chars, {pres.count('~')} '~', 2 of 5 Disclosures")
    policy = {ISSUER: "jwt-vc-issuer-metadata"}
    iss_id, processed, sd_paths, hidden = verify(pres, policy)
    shown = json.dumps(processed, default=lambda o: "<undisclosed>", indent=2)
    print(f"verified, Issuer = {iss_id}\n{shown}")

    print("\n== Section 4: well-known URL")
    for iss in ["https://pid.example", "https://pid.example/issuer/",
                "https://pid.example/tenant/1234", "https://pid.example/a/../b",
                "https://pid.example/?t=1"]:
        show(iss, lambda iss=iss: well_known_url(iss))

    print("\n== Section 3 / 7.1: URLs a credential can make you fetch")
    cases = [
        ("https://pid.example/.well-known/jwt-vc-issuer/issuer", ()),
        ("http://pid.example/.well-known/jwt-vc-issuer/issuer", ()),
        ("https://127.0.0.1/admin", ()),
        ("https://[::ffff:169.254.169.254]/latest/meta-data/", ()),
        ("https://metadata.attacker.example/pid", ()),
        ("https://intranet.corp/pid.json", ()),
        ("https://types.example/pid/v1", ("https://10.0.0.5/pid/v1",)),
        ("https://types.example/pid/v1", ("http://types.example/pid/v1",)),
    ]
    for url, redir in cases:
        label = url + (f" -> {redir[0]}" if redir else "")
        show(label, lambda url=url, redir=redir: (fetch(url, redir), None)[1])

    print("\n== Section 2.5 / 7.3: same iss, attacker-made x5c")
    ca_key = ec.generate_private_key(ec.SECP256R1())
    name = lambda cn: x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    t0 = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    t1 = datetime.datetime(2028, 1, 1, tzinfo=datetime.timezone.utc)
    def cert(subj, pub, iss_name, signer):
        return (x509.CertificateBuilder().subject_name(name(subj)).issuer_name(name(iss_name))
                .public_key(pub).serial_number(x509.random_serial_number())
                .not_valid_before(t0).not_valid_after(t1).sign(signer, hashes.SHA256()))
    ca = cert("Permitted PID CA", ca_key.public_key(), "Permitted PID CA", ca_key)
    # The attacker owns a leaf under the permitted CA (some other issuer's cert).
    leaf = cert("Some Other Issuer", attacker_key.public_key(), "Permitted PID CA", ca_key)
    x5c = [base64.b64encode(leaf.public_bytes(serialization.Encoding.DER)).decode()]
    forged, fd = issue(attacker_key, {"x5c": x5c}, iss=ISSUER)
    forged_pres = present(forged, [fd["age"]])

    def naive():
        _, fp = jose_parts(forged)
        hdr, _ = jose_parts(forged)
        mech = "x5c" if "x5c" in hdr else "jwt-vc-issuer-metadata"
        pol = {fp["iss"]: mech, "x5c_anchors": [ca]}
        iss_id, *_ = verify(forged_pres, pol)
        return f"trusted iss in payload says {fp['iss']}; cert says {iss_id}"
    show("naive: header has x5c, so use x5c", naive)
    show("policy: pid.example uses metadata",
         lambda: verify(forged_pres, {ISSUER: "jwt-vc-issuer-metadata"})[0])
    show("policy: x5c anchors, Issuer = cert subject",
         lambda: "Issuer = " + verify(forged_pres, {"*": "x5c", "x5c_anchors": [ca]})[0])

    print("\n== Section 5.6: claim metadata against the presentation")
    claims = [
        {"path": ["nationalities", None], "sd": "always"},
        {"path": ["age_equal_or_over"], "sd": "always"},
        {"path": ["given_name"], "mandatory": True, "sd": "always"},
        {"path": ["vct"], "sd": "never"},
    ]
    show("base PID claims", lambda: validate_claims(claims, processed, sd_paths, hidden))
    show("[\"age_equal_or_over\", \"18\"] declared sd=always (only its parent is a Disclosure)",
         lambda: validate_claims([{"path": ["age_equal_or_over", "18"], "sd": "always"}],
                                 processed, sd_paths, hidden))
    show("[\"nationalities\", 0, \"code\"] on an undisclosed element",
         lambda: (eval_path(processed, ["nationalities", 0, "code"]), None)[1])
    show("[\"vct\", 0] (index on a string)",
         lambda: eval_path(processed, ["vct", 0]))
    show("[\"exp\"] declared sd=always",
         lambda: validate_claims([{"path": ["exp"], "sd": "always"}], processed, sd_paths, hidden))
    show("mandatory [\"family_name\"] with no hidden digests left",
         lambda: validate_claims([{"path": ["family_name"], "mandatory": True}],
                                 processed, sd_paths, {}))

    print("\n== Section 5.3 / 5.6.5.1 / 6 / 7.4: extends chains")
    base = json.dumps({"vct": "urn:example:pid", "claims": claims}).encode()
    child_ok = json.dumps({"vct": "https://types.example/pid/v1", "extends": "urn:example:pid",
                           "extends#integrity": sri(base),
                           "claims": [{"path": ["nationalities", None], "mandatory": True}]}).encode()
    child_loosen = json.dumps({"vct": "https://types.example/pid/v1", "extends": "urn:example:pid",
                               "claims": [{"path": ["given_name"], "sd": "allowed"}]}).encode()
    child_optional = json.dumps({"vct": "https://types.example/pid/v1", "extends": "urn:example:pid",
                                 "claims": [{"path": ["given_name"], "mandatory": False}]}).encode()
    swapped = json.dumps({"vct": "https://types.example/other", "claims": []}).encode()
    a = json.dumps({"vct": "urn:a", "extends": "urn:b"}).encode()
    b = json.dumps({"vct": "urn:b", "extends": "urn:a"}).encode()
    tampered = base.replace(b'"always"', b'"allowed"', 1)

    T = "https://types.example/pid/v1"
    show("child adds mandatory, integrity matches",
         lambda: f"{len(load_type(T, None, {T: child_ok, 'urn:example:pid': base}))} claim rules")
    show("child flips given_name sd always -> allowed",
         lambda: load_type(T, None, {T: child_loosen, "urn:example:pid": base}))
    show("child sets mandatory given_name to false",
         lambda: load_type(T, None, {T: child_optional, "urn:example:pid": base}))
    show("parent served with sd edited",
         lambda: load_type(T, None, {T: child_ok, "urn:example:pid": tampered}))
    show("URL serves a document for another vct",
         lambda: load_type(T, None, {T: swapped}))
    show("urn:a extends urn:b extends urn:a",
         lambda: load_type("urn:a", None, {"urn:a": a, "urn:b": b}))


if __name__ == "__main__":
    sys.exit(main())
