---
title: 'AWS SigV4 and SigV4A Deep Dive'
published: false
description: 'A four-step breakdown of AWS SigV4 with an 80-line Python implementation, the asymmetric SigV4A (ECDSA P-256) that Multi-Region Access Point forced into existence, plus Chunked Upload, Presigned URL, and the Clock Skew traps that bite in production.'
tags:
  - aws
  - sigv4
  - security
  - signing
series: Amazon Web Services
---

## Introduction

Hitting S3 from `boto3`, I had never thought about SigV4. The SDK does everything. I knew an `Authorization: AWS4-HMAC-SHA256 ...` header was being assembled somewhere under the hood, but I had never built one by hand.

Multi-Region Access Point (MRAP) destroyed that complacency. The instant I hit S3 through MRAP from Lambda, an algorithm I had never seen called `AWS4-ECDSA-P256-SHA256` showed up instead of the usual SigV4, and the old `botocore` I had pinned locally crashed with `InvalidSignature`. AWS has two signing schemes: **SigV4** and **SigV4A**. The latter is asymmetric, using ECDSA instead of HMAC.

This article dissects both, in this order.

1. Why AWS uses a custom signature instead of Bearer Token
2. Background: what HMAC and SHA-256 contribute
3. The four SigV4 steps (Canonical Request / StringToSign / SigningKey derivation / Signature)
4. SigV4 written in 80 lines of Python
5. Chunked Upload (STREAMING-AWS4-HMAC-SHA256-PAYLOAD)
6. Streaming SigV4 (WebSocket / IoT MQTT)
7. What is inside a Presigned URL
8. SigV4A: asymmetric signing on ECDSA P-256
9. SigV4 vs SigV4A comparison
10. Clock Skew traps and debugging tips

---

## 1. Why a custom signature instead of Bearer Token

In the REST world, `Authorization: Bearer <token>` is the default. OAuth 2.0 is basically the same. Bearer means "whoever holds the token is legitimate", and if one is stolen it is over. Under HTTPS that is usually fine in practice, but AWS **explicitly refused that design**. There are three reasons.

![Bearer Token vs SigV4 design comparison](./assets/aws-sigv4-and-sigv4a-deep-dive/diagrams/01-bearer-vs-sigv4.png)

The three design goals.

- **Never put the Secret Key on the wire**: `SecretAccessKey` is an absurdly powerful credential. Sending it on every call is a non-starter. SigV4 does not sign with the Secret Key itself; it signs with a short-lived key derived from it through HMAC.
- **Replay protection**: the signature covers an **ISO8601 timestamp** and the **CredentialScope** (date + region + service), so it is bound to a moment in time and a place. A captured signature replayed the next day will not pass.
- **Tamper detection**: HTTP method, URI, query string, headers, and the SHA-256 of the body are all in the signed string. Flip a single byte in transit and the signature mismatches.

SigV4 proves three things at once: who sent it, when, and what was in it. Completely different model from Bearer.

---

## 2. Background: HMAC and SHA-256 in one paragraph

SigV4 sits on top of HMAC-SHA256. **SHA-256** compresses arbitrary-length input into a fixed 256-bit digest. It is a one-way function with collision resistance (you cannot produce two inputs with the same hash) and preimage resistance (you cannot reverse it). **HMAC** (Hash-based MAC) wraps a key around a message: `HMAC(key, msg) = SHA256(key XOR opad || SHA256(key XOR ipad || msg))`. Anyone without the key cannot reproduce the output. SigV4 chains HMAC four times to derive a signing key, then HMACs the StringToSign with it. The hex of that final HMAC becomes `Signature=...` in the Authorization header. SigV4A swaps only that last step from HMAC to ECDSA. Hold that mental model and the rest is detail.

---

## 3. The four SigV4 steps at a glance

![Four SigV4 steps overview](./assets/aws-sigv4-and-sigv4a-deep-dive/diagrams/02-four-steps-overview.png)

One step at a time from here.

---

## 4. Step 1: Building the Canonical Request

The signature only works if "the same request always serializes to the same string". Header order and URI escape variants have to be flattened out. That flattening is what the Canonical Request does.

```text
CanonicalRequest =
  HTTPRequestMethod + '\n' +
  CanonicalURI + '\n' +
  CanonicalQueryString + '\n' +
  CanonicalHeaders + '\n' +
  SignedHeaders + '\n' +
  HashedPayload
```

The rules for each element, in one diagram.

![Canonical Request normalization rules](./assets/aws-sigv4-and-sigv4a-deep-dive/diagrams/03-canonical-request-rules.png)

Three traps that bite hard.

- **URI encoded twice**: for AWS APIs other than S3, the path is URI-encoded **twice**. A frequent SDK bug. S3 is the only exception, encoded once.
- **Query string sort**: `b=2&a=1` becomes `a=1&b=2`. When the same key appears multiple times, sort the values too.
- **Header value trim**: strip leading and trailing whitespace, then collapse runs of internal whitespace to a single space. `Foo:  bar  baz` becomes `foo:bar baz`.

In Python.

```python
from urllib.parse import quote
import hashlib

def canonical_request(method, uri, query, headers, payload):
    # URI: encode once for S3, twice for others (this example assumes S3)
    canonical_uri = quote(uri, safe="/-_.~")

    # Query: sort by key, encode values
    items = sorted(query.items())
    canonical_query = "&".join(
        f"{quote(k, safe='-_.~')}={quote(v, safe='-_.~')}" for k, v in items
    )

    # Headers: lowercase + sort + value trim
    lower = {k.lower(): " ".join(v.split()) for k, v in headers.items()}
    sorted_keys = sorted(lower.keys())
    canonical_headers = "".join(f"{k}:{lower[k]}\n" for k in sorted_keys)
    signed_headers = ";".join(sorted_keys)

    # Payload: SHA256 hex
    hashed_payload = hashlib.sha256(payload).hexdigest()

    return (
        f"{method}\n{canonical_uri}\n{canonical_query}\n"
        f"{canonical_headers}\n{signed_headers}\n{hashed_payload}"
    ), signed_headers, hashed_payload
```

`canonical_headers` ends with `\n`, and the line after it brings another `\n`, so the serialized form has two newlines in a row. That is spec-correct. "Fix" it to a single newline and `SignatureDoesNotMatch` greets you immediately.

---

## 5. Step 2: Building the StringToSign

Once the Canonical Request exists, SHA256 it and combine the result with the signing scope (algorithm + datetime + region + service) into a single string. That is the StringToSign.

```text
StringToSign =
  Algorithm + '\n' +
  RequestDateTime + '\n' +
  CredentialScope + '\n' +
  HEX(SHA256(CanonicalRequest))
```

Concrete example.

```text
AWS4-HMAC-SHA256
20260517T120000Z
20260517/us-east-1/s3/aws4_request
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

`CredentialScope` has the shape `<date>/<region>/<service>/aws4_request`. That alone tells AWS "this signature is for this day, this region, and this service". A signature scoped to `s3` cannot be reused against `dynamodb`. That is the core of replay protection.

```python
import hashlib

def string_to_sign(amz_date, scope_date, region, service, canonical_req):
    algorithm = "AWS4-HMAC-SHA256"
    scope = f"{scope_date}/{region}/{service}/aws4_request"
    hashed_cr = hashlib.sha256(canonical_req.encode()).hexdigest()
    return f"{algorithm}\n{amz_date}\n{scope}\n{hashed_cr}", scope
```

`amz_date` is the basic ISO8601 form `20260517T120000Z` (no `-` or `:`). `scope_date` is just `20260517`. Mismatching them is a classic bug.

---

## 6. Step 3: Deriving the SigningKey (4-stage HMAC chain)

This is the heart of SigV4. You never sign with the Secret Key itself. You chain HMAC four times from the Secret Key to build **kSigning**, and sign with that.

![Four-stage HMAC chain that derives the signing key](./assets/aws-sigv4-and-sigv4a-deep-dive/diagrams/04-signing-key-derivation.png)

Why four stages. **Key separation**. kDate is "a key valid only for this day", kRegion is "valid only for this day and this region", and so on. Each stage narrows the scope further. Even if an attacker leaks kRegion, it cannot be used on another day or in another region. **The Secret Key is permanent, but kSigning is disposable, scoped to one day, one region, one service.**

```python
import hmac
import hashlib

def hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()

def signing_key(secret, scope_date, region, service):
    k_date = hmac_sha256(("AWS4" + secret).encode(), scope_date)
    k_region = hmac_sha256(k_date, region)
    k_service = hmac_sha256(k_region, service)
    k_signing = hmac_sha256(k_service, "aws4_request")
    return k_signing
```

The `"AWS4" + SecretAccessKey` prefix is hard-coded in the spec. Forget the `AWS4` and `SignatureDoesNotMatch` lands on the first request.

---

## 7. Step 4: Computing the Signature and the Authorization Header

The last step is just HMAC the StringToSign with kSigning and hex-encode it.

```python
def sign(k_signing: bytes, string_to_sign: str) -> str:
    return hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()
```

The Authorization header is assembled like this.

```text
Authorization: AWS4-HMAC-SHA256
  Credential=<AccessKeyId>/<scope>,
  SignedHeaders=<signed>,
  Signature=<hex>
```

A real example.

```text
Authorization: AWS4-HMAC-SHA256 Credential=AKIAIOSFODNN7EXAMPLE/20260517/us-east-1/s3/aws4_request, SignedHeaders=host;x-amz-content-sha256;x-amz-date, Signature=fe5f80f77d5fa3beca038a248ff027d0445342fe2855ddc963176630326f1024
```

`Credential` holds the AccessKeyId and the CredentialScope, `SignedHeaders` lists the signed header names with `;` separators, and `Signature` is the hex string. This is exactly what the SDK is assembling for you.

---

## 8. Full implementation: hitting S3 GetObject with SigV4

The four steps wired together in under 80 lines. Pure `urllib`, no SDK.

```python
import datetime
import hashlib
import hmac
import urllib.request
from urllib.parse import quote

ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
SECRET_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
REGION = "us-east-1"
SERVICE = "s3"
BUCKET = "kt-sigv4-demo"
KEY = "hello.txt"
HOST = f"{BUCKET}.s3.{REGION}.amazonaws.com"


def hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


def signing_key(secret, scope_date, region, service):
    k = hmac_sha256(("AWS4" + secret).encode(), scope_date)
    k = hmac_sha256(k, region)
    k = hmac_sha256(k, service)
    return hmac_sha256(k, "aws4_request")


def sigv4_get(bucket, key):
    now = datetime.datetime.now(datetime.timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    scope_date = now.strftime("%Y%m%d")
    scope = f"{scope_date}/{REGION}/{SERVICE}/aws4_request"

    method = "GET"
    canonical_uri = "/" + quote(key, safe="/-_.~")
    canonical_query = ""
    payload_hash = hashlib.sha256(b"").hexdigest()

    headers_to_sign = {
        "host": HOST,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
    }
    sorted_keys = sorted(headers_to_sign.keys())
    canonical_headers = "".join(f"{k}:{headers_to_sign[k]}\n" for k in sorted_keys)
    signed_headers = ";".join(sorted_keys)

    canonical_request = (
        f"{method}\n{canonical_uri}\n{canonical_query}\n"
        f"{canonical_headers}\n{signed_headers}\n{payload_hash}"
    )
    hashed_cr = hashlib.sha256(canonical_request.encode()).hexdigest()
    string_to_sign = f"AWS4-HMAC-SHA256\n{amz_date}\n{scope}\n{hashed_cr}"

    k_signing = signing_key(SECRET_KEY, scope_date, REGION, SERVICE)
    signature = hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()

    authorization = (
        f"AWS4-HMAC-SHA256 Credential={ACCESS_KEY}/{scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    req = urllib.request.Request(f"https://{HOST}/{key}", method=method)
    for h, v in headers_to_sign.items():
        req.add_header(h, v)
    req.add_header("Authorization", authorization)

    with urllib.request.urlopen(req) as resp:
        return resp.read()


if __name__ == "__main__":
    print(sigv4_get(BUCKET, KEY).decode())
```

Typical failures.

- Forgot `host` in headers_to_sign: SignatureDoesNotMatch
- `x-amz-date` and the date inside `Authorization` differ: SignatureDoesNotMatch
- Body is empty but you forgot to compute payload_hash: SignatureDoesNotMatch

The SDK does all of this correctly. When writing your own, the fastest debugging path is **byte-for-byte diff against what the SDK produces**.

---

## 9. End-to-end sequence: Client and Server verification

The server side (AWS) reproduces the exact same procedure to build the signature, then compares against what the client sent.

![Client signs and server reverifies sequence](./assets/aws-sigv4-and-sigv4a-deep-dive/diagrams/05-client-server-verification.png)

When AWS returns `SignatureDoesNotMatch`, **the response body contains the Canonical Request that AWS itself reconstructed**. That is gold for debugging. Diff your own Canonical Request against the one AWS built and the divergent element (header trim, URI encoding, missing header) pops out immediately.

---

## 10. Chunked Upload: STREAMING-AWS4-HMAC-SHA256-PAYLOAD

For large uploads to S3, hashing the entire body up front is not realistic. Hashing a 10 GB file before you even start sending it is a latency disaster. So S3 has a STREAMING mode where **each chunk is signed individually**.

The headers look like this.

```text
x-amz-content-sha256: STREAMING-AWS4-HMAC-SHA256-PAYLOAD
Content-Encoding: aws-chunked
x-amz-decoded-content-length: <original body size>
Content-Length: <size including chunk headers>
```

The body is chunked-transfer-style but with a custom format.

```text
10000;chunk-signature=<sig1>\r\n
<8192 byte chunk 1>\r\n
10000;chunk-signature=<sig2>\r\n
<8192 byte chunk 2>\r\n
...
0;chunk-signature=<sigN>\r\n
\r\n
```

Each chunk's signature is computed by chaining the previous chunk's signature with the current chunk's hash. Swap a chunk in the middle and every signature after it falls apart.

![Chunk signatures chained through previous-signature](./assets/aws-sigv4-and-sigv4a-deep-dive/diagrams/06-chunked-signature-chain.png)

The StringToSign gets a chunk-specific extension.

```text
AWS4-HMAC-SHA256-PAYLOAD
<amz-date>
<scope>
<previous-signature>
HEX(SHA256(""))
HEX(SHA256(chunk-data))
```

`previous-signature` is what closes the chain. The stream terminates with a **zero-byte chunk**. There is also a `STREAMING-AWS4-HMAC-SHA256-PAYLOAD-TRAILER` variant that appends trailer headers like CRC32C for an extra integrity check.

Writing this by hand is basically masochism. Let the SDK handle it. But knowing the mechanics makes questions like "why is Content-Length different from x-amz-decoded-content-length" trivial to answer.

---

## 11. Streaming SigV4: WebSocket / IoT MQTT

SigV4 also rides on **WebSocket** and **MQTT over WebSocket**, not just plain HTTP. IoT Core, API Gateway WebSocket, and CloudWatch Logs Live Tail all sit here.

These use a **Presigned URL form that embeds SigV4 into the connection URL's query string**. The `Authorization` header is hard to attach to a WebSocket Upgrade, so cramming everything into the URL lets the handshake complete in one round trip. With MQTT over WebSocket the URL ends up as `wss://<endpoint>/mqtt?X-Amz-Algorithm=...&X-Amz-Signature=...`.

The streaming case is special because **the connection lives for a long time**. The SigV4 signature itself is checked only once at connection establishment, so even after `X-Amz-Expires` passes, the existing connection keeps going (depending on the AWS implementation). Reconnecting requires a fresh signature.

---

## 12. What is inside a Presigned URL

A Presigned URL is **the Authorization header crammed into the query string**. Heavily used for "hand someone a URL and let the browser download the S3 object directly".

```text
https://kt-bucket.s3.us-east-1.amazonaws.com/report.pdf
  ?X-Amz-Algorithm=AWS4-HMAC-SHA256
  &X-Amz-Credential=AKIA.../20260517/us-east-1/s3/aws4_request
  &X-Amz-Date=20260517T120000Z
  &X-Amz-Expires=900
  &X-Amz-SignedHeaders=host
  &X-Amz-Signature=fe5f80f77d5fa3beca038a248ff027d0445342fe2855ddc963176630326f1024
```

Properties.

- **X-Amz-Expires**: in seconds. **Maximum 604800 (= 7 days)**. The 7-day cap exists because the SigV4 signing key rotates on roughly a 7-day cycle (kDate is per-day, but kSigning is valid for about 7 days).
- **X-Amz-SignedHeaders=host**: no body, no extra headers, so only host needs to be signed.
- **Payload hash handling**: presigned URLs use either `UNSIGNED-PAYLOAD` or the actual body hash. Looser than the header-based form.

Watch out for these.

- **A Presigned URL minted with IAM Role temporary credentials (e.g. STS AssumeRole) is capped by the credential's own lifetime**. `AssumeRole` defaults to 1 hour for `DurationSeconds`, configurable up to 12 hours, but once the SessionToken expires the URL dies. This is the standard root cause when someone passes `--expires-in 604800` and the URL still dies after 1 hour.
- If you are handing the URL to a browser, mint it with an **IAM User long-term key** or raise the Role's MaxSessionDuration. EC2 Instance Profile lands in the same trap: IMDS auto-rotates, but after the rotation any URL signed with the previous credentials is dead.

---

## 13. SigV4A: the asymmetric variant

Now the main event. The instant you hit **Multi-Region Access Point (MRAP)**, the SDK silently flips from SigV4 to SigV4A. The algorithm name is `AWS4-ECDSA-P256-SHA256`. It uses **ECDSA (Elliptic Curve Digital Signature Algorithm)** with NIST P-256 instead of HMAC.

![SigV4A keypair derivation from SecretAccessKey](./assets/aws-sigv4-and-sigv4a-deep-dive/diagrams/07-sigv4a-kdf.png)

### How it actually works

SigV4A **derives an ECDSA P-256 keypair from the SecretAccessKey through a KDF**. The spec uses `input_key = "AWS4A" || sk`, the label `AWS4-ECDSA-P256-SHA256`, the `akid` (AccessKeyId) as context, and runs a counter that iterates until the derived scalar lands below the P-256 order `n`. The resulting scalar `c` becomes the private key as `k = c + 1`, and the public key is `Q = k * G`. The verifier needs only the public key to check the signature. The canonical implementation lives in `key_derivation.c` in `awslabs/aws-c-auth`.

### Why Multi-Region forces this

MRAP is a representative endpoint for a set of buckets across multiple regions, and any request can be routed to any of them. SigV4 **bakes the region name directly into CredentialScope**, so a signature minted for `us-east-1` simply cannot be verified at `us-west-2`.

SigV4A **drops the region segment from CredentialScope entirely** and replaces it with the **`X-Amz-Region-Set`** header that declares "this signature is valid in us-east-1, us-west-2, and eu-west-1". CredentialScope changes like this.

```text
SigV4:  20260517/us-east-1/s3/aws4_request
SigV4A: 20260517/s3/aws4_request   (region segment removed)
```

The `X-Amz-Region-Set` value is a comma-separated list like `us-east-1,us-west-2`, and wildcards like `us-east-*` or a bare `*` are allowed too.

On top of that, every region can verify independently with only the public key. **Distributing a symmetric HMAC key to every region is a security risk** (compromise one region and they all leak), which is exactly where asymmetric signing pays off.

### Is the ECDSA here deterministic

Standard ECDSA needs a fresh random nonce `k` for every signature (the same input produces different signatures each time). Bias or reuse of `k` is a fatal mistake that leaks the private key. SigV4A's implementation lives in AWS Common Runtime (`awslabs/aws-c-auth` + `aws-c-cal`), and the nonce comes from the OS RNG, so **the same request produces a different signature on every call**. Whether it follows RFC 6979 (deterministic ECDSA) is not stated explicitly in public docs. "`awscrt` handles the nonce correctly" is enough to know in practice.

### Rolling your own is brutal

ECDSA has heavy math, so if you go custom, use the `cryptography` library. AWS officially recommends `aws-crt` (a C library bound into Python through `awscrt`). `botocore` treats `awscrt` as an **optional dependency**. Install with `pip install botocore[crt]` (or `pip install boto3[crt]`) and SigV4A kicks in automatically against MRAP. Plain `boto3` without the crt extra crashes against MRAP with `MissingDependencyException`.

---

## 14. SigV4 vs SigV4A side by side

| Item                       | SigV4                                                        | SigV4A                                                                                                  |
| -------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------- |
| Algorithm name             | `AWS4-HMAC-SHA256`                                           | `AWS4-ECDSA-P256-SHA256`                                                                                |
| Key type                   | Symmetric (HMAC)                                             | Asymmetric (ECDSA P-256)                                                                                |
| Key derivation             | 4-stage HMAC chain (kDate to kRegion to kService to kSigning) | One-shot KDF with a counter to derive an ECDSA keypair (label `AWS4-ECDSA-P256-SHA256`, input `AWS4A` + secret) |
| Region in CredentialScope  | Fixed (e.g. `us-east-1`)                                     | Segment removed. `X-Amz-Region-Set` header declares the regions (wildcards allowed)                     |
| Verification               | AWS recomputes the same HMAC from the same Secret            | AWS verifies the ECDSA signature with the public key                                                    |
| Main use case              | Any single-region API call                                   | Multi-Region Access Point, replication paths                                                            |
| Signature determinism      | Deterministic (same input gives same signature)              | Non-deterministic (`awscrt` uses a random nonce)                                                        |
| Performance                | HMAC is ultra-light (microseconds)                           | ECDSA is heavier (milliseconds)                                                                         |
| 7-day Presigned URL        | Supported                                                    | Supported (same conditions)                                                                             |
| SDK support                | All SDKs                                                     | Through `aws-crt` (Python needs `botocore[crt]`; Go/Java/JS bundle it)                                  |

For working developers the only thing that matters in practice: **the moment MRAP enters the picture the SDK flips to SigV4A; everything else stays on SigV4**. You almost never reach for SigV4A by hand.

---

## 15. SigV4 vs SigV4A: scope and verifier differences in one figure

![SigV4 vs SigV4A scope and verifier comparison](./assets/aws-sigv4-and-sigv4a-deep-dive/diagrams/08-sigv4-vs-sigv4a-scope.png)

SigV4 assumes **1 request = 1 region**, so HMAC is enough. SigV4A is built around **1 request landing in any of several regions**, which makes a shared HMAC untenable and forces ECDSA. That is the structural difference.

---

## 16. The Clock Skew trap

SigV4's `CredentialScope` carries `<date>` and `x-amz-date` carries a second-precision timestamp. AWS rejects requests whose timestamp is **more than ±15 minutes off the current time** (the S3 docs state this explicitly; the tolerance varies slightly by service).

Three classic ways to step on this.

- **Docker container NTP drift**: when the container is not NTP-synced, host clock skew kills you instantly. Containers with no visible `hwclock` and no `ntpd` are the worst offenders. Lambda is fine because AWS keeps it in sync.
- **EC2 with chrony missing**: AL2023 ships `chronyd` by default, but custom AMIs that strip it out drift over time. Point chrony at `169.254.169.123` (Amazon Time Sync Service) and the problem disappears.
- **Old Lambda layers / virtualized clocks**: BPF-based sandboxes where the clock is pinned. Upgrading the Lambda runtime usually fixes it.

Error examples.

```text
SignatureDoesNotMatch:
  The request signature we calculated does not match the signature you provided.
  Check your key and signing method.
RequestTimeTooSkewed:
  The difference between the request time and the current time is too large.
```

`RequestTimeTooSkewed` is always clock skew, 100%. `SignatureDoesNotMatch` is either clock skew or a Canonical Request construction bug.

---

## Conclusion

SigV4 solves "request signing that detects tampering and replay without ever exposing the secret". Chain HMAC four times to derive a signing key, SHA256 the Canonical Request to build a StringToSign, then HMAC the whole thing for the final signature. Write the four steps by hand once and everything the SDK was hiding finally becomes visible.

SigV4A is **SigV4 extended to multi-region by going asymmetric (ECDSA P-256)**. Strip the region from CredentialScope, declare the regions in `X-Amz-Region-Set`, and let each region verify independently with the public key. The SDK flips to it automatically when MRAP is involved, so you basically never reach for it by hand.

The two real-world traps are always the same: **clock skew** and **canonical-request normalization mistakes**. Read the exact error message (`RequestTimeTooSkewed` vs `SignatureDoesNotMatch` vs `AccessDenied`) and diff your Canonical Request against the one AWS echoes back. Get that far and SigV4 stops biting.
