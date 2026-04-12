---
title: 'RFC 7636 Deep Dive: How PKCE Kills Authorization Code Interception Attacks'
published: false
description: 'A deep dive into RFC 7636. Thoroughly explaining the PKCE attack model, protocol details, S256 vs. plain, and security design.'
tags:
  - oauth
  - security
  - authentication
  - pkce
series: OAuth
id: 3489309
---

# Introduction

Last time, we tore apart the core mechanics of **RFC 6749 (Authorization Code Grant)**.

- [RFC 6749 Deep Dive: Understanding OAuth 2.0 Design Decisions from the Specification](https://dev.to/kanywst/rfc-6749-deep-dive-understanding-oauth-20-design-decisions-from-the-specification-2amb)

Hopefully, those fundamentals clicked. But here’s the thing: the second you try writing your own OAuth client or start poking around IdP dashboards, you almost inevitably smash into this weird, lingering mystery.

*"So... what exactly does this 'PKCE' thing protect against? Isn't the `state` parameter enough?"*

You'll see that "Require PKCE" toggle sitting right there in the console. An alarming number of developers blindly flip it to "ON" just because it sounds like a sensible security upgrade.
But if you can't instantly explain *why* you MUST use `S256`, or *how exactly* your access tokens would get hijacked without PKCE, then congrats. You're essentially just praying to a magic internet spell.

The true identity of this "feature everyone checks but nobody actually understands" is a clever cryptographic trick purposely built to shield authorization codes from the completely unhinged routing behavior of mobile OSes. **It perfectly kills interception attacks. It is RFC 7636.**

Consider this article the sequel to our RFC 6749 deep dive.
We’re going to rip through the original RFC 7636 spec, uncover the beautifully simple cryptography behind PKCE, and expose the "don't ever do this" configurations that could ruin your app.

---

## Scoping It Out

Where exactly does RFC 7636 fit in the sprawling OAuth 2.0 universe?

![scope](./assets/rfc7636-pkce-deep-dive/scope.png)

While RFC 6749 tells you "how to get a token," RFC 7636 tells you **"how to stop people from stealing it while you're trying to get it."** We'll assume you already know how the standard Authorization Code Grant works.

---

## 1. The Problem: Auth Code Interception Attacks

### 1.1 The Gap Between Server-Side Strictness and Mobile OS Chaos

If you've spent your career in backend web dev, you probably think, "As long as the IdP strictly validates the `redirect_uri`, we're bulletproof." And for server-side apps redirecting to a dedicated, TLS-secured `https://myapp.example.com/callback`, you'd be right.

But the minute you step into **native mobile apps (iOS / Android)**, everything falls apart. To receive the callback (the auth code) from the browser, native apps rely on **custom URI schemes** like this:

```text
myapp://oauth/callback?code=AUTH_CODE
```

There’s a fatal, gaping vulnerability here. The moment the auth server tells the browser to redirect to `myapp://`, **it completely surrenders control over which app on that phone actually catches the URL.** The ball gets thrown out of your safe, locked-down server environment and straight into the lawless wasteland of the mobile OS.

And guess what? Android and iOS do *not* guarantee custom URI schemes are unique.
A malicious app doesn’t have to pull off an Ocean's Eleven heist on your auth server. It just sits there. When it gets installed, it casually tells the OS (via a few lines of text in `Info.plist` or `AndroidManifest.xml`): *"Hey, I can open `myapp://` too."*

When the browser fires that redirect with your precious authorization code, the OS can't tell which app is the "real" one. The routing decision is a complete coin toss. If the OS capriciously hands it to the malicious app, your auth code is gone.

### 1.2 The Attack Sequence

RFC 7636 §1 sketches this out vividly.

![Attack Sequence](./assets/rfc7636-pkce-deep-dive/attack-sequence.png)

You might think, *"Does this actually happen in the wild, or is it just academic paranoia?"* RFC 7636 §1 delivers a cold reality check:

> While this is a long list of pre-conditions, the described attack has been observed in the wild.

### 1.3 Why Not Just Use Existing Defenses?

I know what you're thinking: *"Why not just authenticate with a `client_secret`?"*
Because **Public Clients (like mobile apps and SPAs) cannot keep a secret.** If you ship a hardcoded secret in a mobile binary, it will be extracted before you finish your morning coffee.

Since the attacker and the real app both show up at the Token Endpoint holding the exact same credentials (`code` + `client_id`), the auth server is blind. It has absolutely no way to tell the good guys from the bad guys.

---

## 2. The Core Concept of PKCE

The fix for this mess is so simple it almost feels anticlimactic.

1. The app starting the authorization request generates a **"one-time, highly random secret string,"** hashes it, and sends the **hash** with the request.
2. The auth server issues the code, tying it to that stored hash.
3. When exchanging the code for a token, the app must prove it's the real deal by presenting the **original, unhashed secret string**.

The attacker doesn't know the original string. It only lives in the RAM of the legitimate app. You can steal the code, but without the secret string, the auth server will slam the door in your face. That is PKCE.

---

## 3. PKCE Protocol Details

We can step right through the actual protocol (RFC 7636 §4) to see how this works.

![PKCE Protocol Details](./assets/rfc7636-pkce-deep-dive/pkce-protocol-details.png)

### 3.1 Generating the code_verifier (§4.1)

The `code_verifier` is a cryptographically secure random string that the client generates freshly for every single request.

- **Length**: 43 to 128 characters
- **Characters allowed**: `[A-Z]`, `[a-z]`, `[0-9]`, `-`, `.`, `_`, `~`
- **Entropy**: Recommended 256 bits

```python
import secrets
import base64

# Generate 32 bytes (256 bits) of pure randomness
random_bytes = secrets.token_bytes(32)

# base64url encode (remove padding)
code_verifier = base64.urlsafe_b64encode(random_bytes).rstrip(b'=').decode('ascii')

print(code_verifier)
# Example output: dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk
```

⚠️ **Never** use predictable pseudo-random number generators like `Math.random()`. Just don't.

### 3.2 Calculating the code_challenge (§4.2)

Next up, we derive the `code_challenge` from that `code_verifier`. The industry standard is `S256`.

```text
code_challenge = BASE64URL-ENCODE(SHA256(ASCII(code_verifier)))
```

The spec says you *MAY* use `plain` (i.e., no hashing) if some technical constraint absolutely prevents `S256`. To put it bluntly: **In the modern era, there is zero excuse to use `plain`. Ever.**

### 3.3 Hands-On: Auth & Token Requests

Staring at Mermaid diagrams gets boring fast. Let’s simulate the raw PKCE flow using your terminal and `curl`.

**① Authorization Request (via browser)**
The client includes `code_challenge` and `code_challenge_method` as parameters and redirects the user.

```bash
# The URL actually hit in the browser's address bar
curl -i "https://auth.example.com/authorize?\
response_type=code&\
client_id=my-native-app&\
redirect_uri=myapp://callback&\
state=xyz123&\
code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM&\
code_challenge_method=S256"
```

Behind the scenes, the server ties `E9Melhoa...` to the issued `code`, stores it, and returns a redirect back to the app.

**② Token Request**
The app, having caught the incoming authorization code, sends the `code_verifier` (which it kept safely tucked away in its own memory) straight to the Token Endpoint.

```bash
curl -X POST "https://auth.example.com/token" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "grant_type=authorization_code" \
     -d "client_id=my-native-app" \
     -d "redirect_uri=myapp://callback" \
     -d "code=AUTH_CODE_RECEIVED" \
     -d "code_verifier=dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
```

The server hashes the received `code_verifier` with SHA-256 and checks if it matches the stored `code_challenge`. If they match, congratulations—you get the access token.
If an attacker intercepted the `code` and sends it here, their `code_verifier` will be empty or garbage, and the server will mercilessly kick them out with an `invalid_grant`.

---

## 4. The Fatal Flaw of the "plain" Method

Why am I relentlessly telling you to avoid `plain`?
Because `plain` literally means `code_challenge = code_verifier`. You are passing your secret completely unhashed.

If the smartphone's HTTP history leaks, or if the auth request gets intercepted over a compromised TLS proxy, the attacker instantly sees your `code_challenge`. If you're using `plain`, they just got your `code_verifier` for free. Once they snatch the auth code, they have all the pieces, and your entire PKCE defensive wall collapses.

With `S256`, even if they intercept every single auth request and steal the `code_challenge`, trying to reverse-engineer the original `code_verifier` out of that SHA-256 hash requires a pre-image attack. Good luck with that. They'll be crunching hashes until the sun burns out.

**Using `plain` is essentially opting out of security while pretending you didn't.**

---

## 5. PKCE vs. The 'state' Parameter

"Wait, doesn't the `state` parameter prevent CSRF? Why do I need both?"
Simply put: **They block attacks coming from totally opposite directions.**

| Feature                 | `state` (RFC 6749)                                               | PKCE (RFC 7636)                                                 |
| ----------------------- | ---------------------------------------------------------------- | --------------------------------------------------------------- |
| **What it stops**       | CSRF (Auth code *injection*)                                     | Auth code *interception*                                        |
| **Attack direction**    | Attacker → Victim (Forces the attacker's code into your session) | Victim → Attacker (Steals your code for the attacker's session) |
| **Where it's verified** | Client-side (Your app checks the callback)                       | Server-side (Token Endpoint validates the verifier)             |

`state` ensures nobody shoves a sketchy auth code into your app. PKCE ensures nobody takes your auth code and uses it elsewhere. They aren't mutually exclusive. **You absolutely must use both.**

---

## 6. Security Design Details

### Why Doesn't S256 Use a Salt? (§7.3)

If you know anything about passwords, you know you need a salt. So why doesn't PKCE use one for its hashes?
Because the base entropy is already at lethal levels.

Passwords need salts because human-readable passwords have pathetically low entropy, leaving them wide open to pre-computation (rainbow table) attacks. A `code_verifier`, however, is 256 bits of pure cryptographic randomness. Brute-forcing it is physically impossible in our universe. Adding a salt achieves absolutely nothing except making your code messier.

### Surviving Downgrade Attacks (§7.2)

RFC 7636 has a strict rule:
> Clients MUST NOT downgrade to "plain" after trying the "S256" method.

If you send `S256` and the auth server throws an error, do *not* try to be helpful and resend the request using `plain`. That’s exactly how a Man-In-The-Middle attacker strips away your security (a downgrade attack). If `S256` fails, the flow is compromised. Kill it immediately.

---

## Conclusion

RFC 7636 is a breezy 20-page specification, but it fundamentally fixed one of the scariest vulnerabilities in the OAuth 2.0 ecosystem: delivering the authorization code.

To sum it up:

1. **Custom URI schemes on native apps are a free-for-all.** Anyone can register them.
2. **PKCE locks down the code** using a mathematical secret only the request initiator knows.
3. **Use S256.** Anyone telling you to use `plain` is reckless.

PKCE was initially pitched as an "optional extension for Public Clients." Today, under the current OAuth 2.0 Security Best Current Practice (BCP), **it is strictly mandatory for everyone**, even Confidential Clients sitting on secure backend servers.

Skipping PKCE in a modern system isn't an "option." It's just plain wrong.

## References

- [RFC 7636 - Proof Key for Code Exchange by OAuth Public Clients](https://datatracker.ietf.org/doc/html/rfc7636)
- [RFC 6749 - The OAuth 2.0 Authorization Framework](https://datatracker.ietf.org/doc/html/rfc6749)
- [RFC 8252 - OAuth 2.0 for Native Apps](https://datatracker.ietf.org/doc/html/rfc8252)
- [OAuth 2.0 Security Best Current Practice](https://datatracker.ietf.org/doc/html/rfc9700)
