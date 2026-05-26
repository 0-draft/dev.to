---
title: 'IAM Roles Anywhere Hands-On: Hit AWS from On-Prem or Your Laptop Without AKIA Keys'
published: false
description: "When you're outside EC2/Lambda (home laptop, on-prem server, Raspberry Pi, Kubernetes) and you don't want long-lived keys (AKIA...) sitting around, IAM Roles Anywhere solves it by using an X.509 certificate as your AWS identity. I built a self-signed CA from scratch, registered it with Roles Anywhere, and pulled temporary credentials end-to-end in 60 minutes. Cost: $0."
tags:
  - aws
  - iam
  - sts
  - security
series: Amazon Web Services
---

## Introduction

You'll always have cases where you want to hit AWS from a home laptop or an on-prem server.

For a long time, the only way to give credentials to code running "outside AWS" was **"stick an IAM User's long-lived key (`AKIA...`) into an env var or config file."**

This sucks for a bunch of reasons.

- If the long-lived key leaks, attackers can use it forever
- Rotation is annoying enough that you end up using the same key for two years
- The "1 server = 1 IAM User" model breaks down (User limit, audit nightmare)
- CloudTrail can't tell you which physical machine made the call

**IAM Roles Anywhere** is the 2022 feature that fixes this. **By using an X.509 certificate as your identity to AWS**, you can pull temporary credentials without any IAM User or long-lived key in the picture.

![Before and after: long-lived key vs X.509 cert](./assets/aws-roles-anywhere-hands-on/diagrams/01-before-after.png)

This article does that **inside your Mac/Linux box**. **No real CA involved. We make one self-signed Root CA and issue one end-entity certificate**. We register only the Root CA's public certificate with AWS.

End state:

- Your laptop has a **certificate + private key** acting as your AWS identity
- Zero long-lived keys
- Temporary credentials (`ASIA...`) come back from AWS
- You hit S3 with them

Cost: **$0**. Roles Anywhere itself has no extra charge (per AWS docs). Certificates are generated locally, and creating Trust Anchor / Profile / Role is free.

Total time: about **60 minutes**. Each command has a one-line explanation, so this works even if X.509 / PKI is new to you.

## Prerequisites

- One AWS account
- AWS CLI (v2)
- A Mac or Linux terminal (`openssl` is preinstalled)
- Windows users: run this inside WSL2
- Theory background is in [AWS IAM Roles Anywhere Deep Dive](https://dev.to/kanywst/aws-iam-roles-anywhere-deep-dive)

If you've never touched X.509 / PKI, you can still follow along. Term cheatsheet first.

- **CA (Certificate Authority)**: the authority that issues certificates. Today, you are the CA
- **Root CA**: the topmost CA. Its private key signs end-entity certificates
- **End-entity certificate**: the actual certificate you use. Signed by the Root CA's private key
- **CN (Common Name)**: the "name" field of the certificate. Roles Anywhere Trust Policy can match on it

If you know "sign with private key, verify with public key," you have enough background.

---

## The whole flow

Plan in one diagram.

![End-to-end flow: from setup through cleanup](./assets/aws-roles-anywhere-hands-on/diagrams/02-whole-flow.png)

Build the PKI material by hand (Steps 1-2), connect it to AWS (Steps 3-5), then make actual calls (Steps 6-8).

---

## Step 0: Environment setup

### 0-1. Check the tools

```bash
openssl version
# OpenSSL 3.x.x (preinstalled on Mac/Linux)

aws --version
# aws-cli/2.x.x
```

If you don't have them:

- macOS: `brew install awscli` (OpenSSL ships with the OS)
- Linux: install via your package manager

### 0-2. Create a working directory

```bash
mkdir -p ~/roles-anywhere-handson
cd ~/roles-anywhere-handson
```

Every command from here runs inside this directory.

### 0-3. Put Account ID in an env var

```bash
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export REGION=us-east-1
echo $ACCOUNT_ID
```

---

## Step 1: Create a self-signed Root CA

You're the CA. We won't use a real one (DigiCert, Let's Encrypt, etc.). We'll generate a self-signed Root CA with `openssl`.

![Root CA creation: key then self-signed cert](./assets/aws-roles-anywhere-hands-on/diagrams/03-root-ca-steps.png)

### 1-1. CA private key

```bash
openssl genrsa -out ca.key 4096
```

This creates `ca.key`. **Never let this file leave your box**. It is literally the CA's body.

### 1-2. CA self-signed certificate

```bash
openssl req -x509 -new -nodes -key ca.key -sha256 -days 365 \
  -out ca.crt \
  -subj "/CN=handson-root-ca/O=Hands-On" \
  -addext "basicConstraints=critical,CA:TRUE" \
  -addext "keyUsage=critical,keyCertSign,cRLSign"
```

Gotcha: **`basicConstraints=CA:TRUE` is required**. Without it, registering this cert as a Trust Anchor fails with **`Incorrect basic constraints for CA certificate`**. `keyUsage` similarly needs CA values (`keyCertSign` + `cRLSign`).

`ca.crt` is your public certificate. This is what you upload to AWS. Inspect it:

```bash
openssl x509 -in ca.crt -text -noout | head -20
```

- `Subject: CN = handson-root-ca, O = Hands-On` is the name you set
- `Issuer:` is the same value (you signed yourself, so Subject = Issuer, which is what self-signed means)
- `Not Before / Not After:` give you a 365-day validity from today

That's your Root CA.

### 1-3. Why self-signed is fine here

For a browser TLS cert, "self-signed = don't trust" is the rule. But Roles Anywhere works on a model where **AWS only trusts the Root CAs you registered** (that's what a Trust Anchor is). Registering only your self-signed Root CA with AWS closes off a private trust loop. Only certificates derived from your CA work with AWS.

In production you'd use an internal PKI or AWS Private CA. For learning purposes, self-signed is enough.

---

## Step 2: Issue an end-entity certificate

Now that you have a CA, use it to issue the end-entity certificate (the actual one you'll use).

![End-entity cert issuance: key, CSR, then signed cert](./assets/aws-roles-anywhere-hands-on/diagrams/04-end-entity-steps.png)

### 2-1. End-entity private key

```bash
openssl genrsa -out client.key 2048
```

`client.key` is the **private key that lives on the machine making Roles Anywhere calls (your laptop today)**. This must also never leave the box.

### 2-2. Generate a CSR (Certificate Signing Request)

A CSR is the paper that says "I am this name, please sign me" sent to the CA.

```bash
openssl req -new -key client.key \
  -out client.csr \
  -subj "/CN=handson-client-01/O=Hands-On"
```

CN is `handson-client-01`. The Roles Anywhere Trust Policy can pin to "only certs with this CN," so this value matters.

### 2-3. Sign with the CA

The end-entity certificate needs two extensions Roles Anywhere requires. Pass them through an extension file using `openssl x509 -extfile`.

```bash
cat > client.ext <<'EOF'
basicConstraints = CA:FALSE
keyUsage = critical, digitalSignature
extendedKeyUsage = clientAuth
EOF

openssl x509 -req -in client.csr \
  -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out client.crt -days 90 -sha256 \
  -extfile client.ext
```

Gotcha: without `keyUsage = digitalSignature` and `extendedKeyUsage = clientAuth`, the Roles Anywhere CreateSession call fails with **`Untrusted certificate. Insufficient certificate`**. Both are required.

`client.crt` is now ready. 90-day validity.

Verify:

```bash
openssl x509 -in client.crt -text -noout | head -15
```

- `Subject: CN = handson-client-01` is the end-entity's name
- `Issuer: CN = handson-root-ca` proves the Root CA signed it

PKI material is now ready.

```text
ca.key    : Root CA private key (secret)
ca.crt    : Root CA public certificate (upload to AWS)
client.key: End-entity private key (lives on the client machine)
client.crt: End-entity public certificate (lives on the client machine)
client.csr: CSR (no longer needed, you can delete)
```

---

## Step 3: Register the Trust Anchor with AWS

Tell Roles Anywhere **"I trust this Root CA"**. That's a **Trust Anchor**.

### 3-1. Create one from the AWS Console

AWS Console → IAM → **Roles Anywhere** (bottom of the left nav) → **Manage** → **Create a trust anchor**.

- **Trust anchor name**: `handson-trust-anchor`
- **Source**: pick **External certificate bundle** (use the other option if you're using AWS Private CA)
- **Certificate bundle**: paste the contents of `ca.crt`. Print it with:

```bash
cat ca.crt
# Copy everything from -----BEGIN CERTIFICATE----- to -----END CERTIFICATE-----
```

- Click **Create trust anchor**

### 3-2. Or do it via CLI (optional)

If you hate the GUI:

```bash
CA_CERT_BODY=$(cat ca.crt)

aws rolesanywhere create-trust-anchor \
  --name handson-trust-anchor \
  --source "sourceType=CERTIFICATE_BUNDLE,sourceData={x509CertificateData=$(cat ca.crt | jq -Rs .)}" \
  --enabled \
  --region ${REGION}
```

The shell escaping is gnarly. Doing it from the Console is easier.

### 3-3. Save the Trust Anchor ARN

Copy the ARN shown on the post-creation page into an env var.

```bash
export TA_ARN="arn:aws:rolesanywhere:us-east-1:${ACCOUNT_ID}:trust-anchor/abc123..."
```

---

## Step 4: Create the IAM Role

This is the Role that Roles Anywhere will Assume on your behalf. **In the Trust Policy, set `rolesanywhere.amazonaws.com` as the Principal**.

### 4-1. Trust Policy

```bash
cat > trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Service": "rolesanywhere.amazonaws.com" },
    "Action": [
      "sts:AssumeRole",
      "sts:TagSession",
      "sts:SetSourceIdentity"
    ],
    "Condition": {
      "ArnEquals": {
        "aws:SourceArn": "${TA_ARN}"
      }
    }
  }]
}
EOF
```

Key points:

- **`Principal: { "Service": "rolesanywhere.amazonaws.com" }`**: not an IAM User or Role. The Principal is the Roles Anywhere AWS service
- **`Action: sts:AssumeRole + sts:TagSession + sts:SetSourceIdentity`**: Roles Anywhere doesn't just AssumeRole. It also injects Session Tags and Source Identity derived from the cert
- **`Condition: aws:SourceArn = Trust Anchor ARN`**: lock down the Assume to only happen through this specific Trust Anchor (Confused Deputy mitigation)

### 4-2. Create the Role and attach an Identity Policy

```bash
aws iam create-role \
  --role-name handson-rolesanywhere-role \
  --assume-role-policy-document file://trust-policy.json

cat > identity-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["s3:ListAllMyBuckets"],
    "Resource": "*"
  }]
}
EOF

aws iam put-role-policy \
  --role-name handson-rolesanywhere-role \
  --policy-name s3-list \
  --policy-document file://identity-policy.json
```

The Identity Policy is minimal. `s3:ListAllMyBuckets` only. Anything that proves "the credentials work" is fine.

### 4-3. Save the Role ARN

```bash
export ROLE_ARN=$(aws iam get-role --role-name handson-rolesanywhere-role --query 'Role.Arn' --output text)
echo $ROLE_ARN
```

---

## Step 5: Create the Roles Anywhere Profile

The **Profile** is the link between Trust Anchor and Role. It says "callers coming through this Trust Anchor can Assume this Role."

### 5-1. Create from the Console

IAM → Roles Anywhere → **Profiles** → **Create a profile**.

- **Profile name**: `handson-profile`
- **Roles**: select `handson-rolesanywhere-role`
- **Session policy** (optional): you can cap permissions here, leave it empty for now
- **Create profile**

### 5-2. Save the Profile ARN

```bash
export PROFILE_ARN="arn:aws:rolesanywhere:us-east-1:${ACCOUNT_ID}:profile/def456..."
```

The AWS side is done.

### 5-3. The trust structure you just built

![Trust structure from cert to temporary credentials](./assets/aws-roles-anywhere-hands-on/diagrams/05-trust-structure.png)

---

## Step 6: Install aws_signing_helper

The Roles Anywhere API doesn't use plain SigV4. It requires **certificate-based signing**. Writing this by hand every time is painful, so AWS ships an official helper binary.

### 6-1. Download

As of May 2026, the latest version is `1.8.3`. URLs are per platform.

macOS (Intel):

```bash
curl -O https://rolesanywhere.amazonaws.com/releases/1.8.3/X86_64/MacOS/Sonoma/aws_signing_helper
chmod +x aws_signing_helper
./aws_signing_helper version
```

macOS (Apple Silicon / M1, M2, M3):

```bash
curl -O https://rolesanywhere.amazonaws.com/releases/1.8.3/Aarch64/MacOS/Sonoma/aws_signing_helper
chmod +x aws_signing_helper
./aws_signing_helper version
```

Linux (x86_64):

```bash
curl -O https://rolesanywhere.amazonaws.com/releases/1.8.3/X86_64/Linux/Amzn2023/aws_signing_helper
chmod +x aws_signing_helper
./aws_signing_helper version
```

Linux (ARM64 / Raspberry Pi etc.):

```bash
curl -O https://rolesanywhere.amazonaws.com/releases/1.8.3/Aarch64/Linux/Amzn2023/aws_signing_helper
chmod +x aws_signing_helper
./aws_signing_helper version
```

Check for newer releases on [GitHub Releases](https://github.com/aws/rolesanywhere-credential-helper/releases). Just swap the version (`1.8.3`) in the URL.

### 6-2. What the helper does

The helper takes three things (Trust Anchor ARN, Profile ARN, Role ARN) as arguments, sends an HTTPS request signed with `client.crt` + `client.key` to Roles Anywhere, and returns `ASIA...` temporary credentials.

Common mix-up: **Roles Anywhere is not mTLS**. The TLS handshake is server-only. The client cert is never exchanged at the TLS layer (AWS does not send a `CertificateRequest`). Authentication happens at the **application layer**. The scheme extends SigV4 and is called `AWS4-X509-RSA-SHA256` (for RSA keys) or `AWS4-X509-ECDSA-SHA256` (for EC keys).

The request looks like this:

```text
POST https://rolesanywhere.<region>.amazonaws.com/sessions
Authorization: AWS4-X509-RSA-SHA256 Credential=..., Signature=...
X-Amz-X509: <base64 of client.crt>
Body: <JSON for CreateSession>
   ↑ Signature is the RSA signature over the Canonical Request, signed with client.key
```

Plain SigV4 signs with "HMAC using Secret Access Key." Roles Anywhere signs with "RSA using private key, with the certificate carried in `X-Amz-X509`." Think of it as SigV4 where the symmetric HMAC has been swapped for asymmetric RSA-Sign.

### 6-3. AWS verifies in two stages

"Does the Trust Anchor verify the body signature?" is a natural question. The answer is no. Verification splits in two.

1. **Chain validation (this is where the Trust Anchor matters)**: is the `client.crt` in `X-Amz-X509` derived from the Root CA registered as Trust Anchor? Are validity, KeyUsage, and EKU sane? If a CRL is configured, is the cert non-revoked? After this passes, AWS treats `client.crt` as trusted
2. **Signature verification**: extract the public key from the trusted `client.crt`, and verify the RSA signature on the request body with it. After this passes, AWS knows the holder of `client.key` sent the request

So **the public key in the Trust Anchor's `ca.crt` does not directly verify the request signature**. The Trust Anchor decides "do we trust `client.crt`?" and the actual request signature is verified by the public key inside `client.crt`.

After both pass, the Roles Anywhere service internally performs the equivalent of `sts:AssumeRole` and returns `ASIA...` (that's why the Trust Policy's Principal is `rolesanywhere.amazonaws.com`). **Clients never hit STS directly**.

The payoff: AWS never holds a copy of your private key. A regular long-lived key is a shared secret because Secret Access Key exists on both AWS and your side. Roles Anywhere is **asymmetric**, so AWS only ever sees the public key (= certificate). The only thing whose leak hurts you is your own `client.key`.

---

## Step 7: Pull temporary credentials and call AWS

### 7-1. Get credentials via credential-process

```bash
./aws_signing_helper credential-process \
  --certificate ${HOME}/roles-anywhere-handson/client.crt \
  --private-key ${HOME}/roles-anywhere-handson/client.key \
  --trust-anchor-arn ${TA_ARN} \
  --profile-arn ${PROFILE_ARN} \
  --role-arn ${ROLE_ARN}
```

On success, you get JSON back:

```json
{
  "Version": 1,
  "AccessKeyId": "ASIA...",
  "SecretAccessKey": "...",
  "SessionToken": "...(long)",
  "Expiration": "2026-05-24T13:00:00Z"
}
```

**Temporary credentials starting with `ASIA...`** are in your hands. Zero long-lived keys involved. Cert + private key alone got AWS to hand back temporary credentials. That's the core of Roles Anywhere.

### 7-2. Wire it into the AWS CLI

Running `aws_signing_helper credential-process` by hand every time is tedious. Drop a `credential_process` config into `~/.aws/config`.

```bash
cat >> ~/.aws/config <<EOF

[profile rolesanywhere-handson]
region = ${REGION}
credential_process = ${HOME}/roles-anywhere-handson/aws_signing_helper credential-process --certificate ${HOME}/roles-anywhere-handson/client.crt --private-key ${HOME}/roles-anywhere-handson/client.key --trust-anchor-arn ${TA_ARN} --profile-arn ${PROFILE_ARN} --role-arn ${ROLE_ARN}
EOF
```

Now the `aws` CLI invokes the helper automatically to fetch credentials.

```bash
aws s3 ls --profile rolesanywhere-handson
# bucket list shows up
```

Run `aws sts get-caller-identity --profile rolesanywhere-handson`:

```json
{
  "UserId": "AROA...:2a9902119721ab7b5c19a878c4c66af705895b42",
  "Account": "123456789012",
  "Arn": "arn:aws:sts::.../assumed-role/handson-rolesanywhere-role/2a9902119721ab7b5c19a878c4c66af705895b42"
}
```

**The long hex string at the tail of `UserId` and `Arn` is the end-entity certificate's serial number**. Not the CN (this trips people up). Roles Anywhere uses the **certificate serial number (big-endian hex, lowercase)** as the session name automatically. To confirm, compare with the lowercased output of `openssl x509 -in client.crt -noout -serial`.

The CN itself lands in `sourceIdentity` (visible in CloudTrail in the next section). Remember it as **"session name = serial, sourceIdentity = CN"** on two axes.

### 7-3. Verify in CloudTrail

Console → CloudTrail → Event history → Lookup attributes:

- **Event name**: `AssumeRole`

A Roles Anywhere AssumeRole event shows up.

```json
{
  "eventSource": "rolesanywhere.amazonaws.com",
  "userIdentity": {
    "type": "AWSService",
    "invokedBy": "rolesanywhere.amazonaws.com"
  },
  "requestParameters": {
    "profileArn": "...",
    "roleArn": "...",
    "trustAnchorArn": "...",
    "cert": "...(contents of end-entity cert)"
  },
  "responseElements": {
    "credentialSet": [{
      "sourceIdentity": "CN=handson-client-01"
    }]
  }
}
```

**`sourceIdentity` automatically carries the certificate's `CN`**. Even without ExternalId or explicit Source Identity config, Roles Anywhere stamps the CN as the audit trail for "who called this."

Downstream CloudTrail events (the S3 ls call, etc.) inherit `sessionContext.sourceIdentity = CN=handson-client-01`. In production, aggregating on this gives you "which physical server (= which certificate) made the call" in one query.

Other Subject fields (`O`, `OU`, etc.) don't land in `sourceIdentity`. They land in **`aws:PrincipalTag/x509Subject/<attribute>`** injected into the Session (used in Step 8).

---

## Step 8: Restrict Trust Policy by CN

Right now, **any end-entity certificate derived from the Root CA** can Assume the Role. In production you usually want "only certificates with this specific CN."

### 8-1. Add a CN match condition

Add an `aws:PrincipalTag/x509Subject/CN` condition to the Trust Policy.

```bash
cat > trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Service": "rolesanywhere.amazonaws.com" },
    "Action": [
      "sts:AssumeRole",
      "sts:TagSession",
      "sts:SetSourceIdentity"
    ],
    "Condition": {
      "ArnEquals": {
        "aws:SourceArn": "${TA_ARN}"
      },
      "StringEquals": {
        "aws:PrincipalTag/x509Subject/CN": "handson-client-01"
      }
    }
  }]
}
EOF

aws iam update-assume-role-policy \
  --role-name handson-rolesanywhere-role \
  --policy-document file://trust-policy.json
```

When Roles Anywhere parses the cert, it **auto-injects each Subject attribute as a Session Tag**. You can use `x509Subject/CN`, `x509Subject/O`, `x509Issuer/CN`, etc.

### 8-2. Verify behavior

Calling with the cert whose CN is `handson-client-01` works.

```bash
aws sts get-caller-identity --profile rolesanywhere-handson
# success
```

Calling with a cert that has a different CN (build `client2.key` / `client2.crt` and swap them in) returns **AccessDenied**.

```bash
# For comparison, build a cert with a different CN
openssl genrsa -out client2.key 2048
openssl req -new -key client2.key -out client2.csr -subj "/CN=other-client/O=Hands-On"
openssl x509 -req -in client2.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out client2.crt -days 90 -sha256

./aws_signing_helper credential-process \
  --certificate ${HOME}/roles-anywhere-handson/client2.crt \
  --private-key ${HOME}/roles-anywhere-handson/client2.key \
  --trust-anchor-arn ${TA_ARN} \
  --profile-arn ${PROFILE_ARN} \
  --role-arn ${ROLE_ARN}

# AccessDenied: cert passes the Trust Anchor (same CA derived) but fails
# the Role Trust Policy condition (CN=handson-client-01)
```

So **"trust one CA, split Roles per CN"**. Manage 100 servers with one CA but keep one Role per CN. That's how this scales in production.

---

## Step 9: Cleanup

Delete things at the end. Order matters because of dependencies (Profile → Trust Anchor → Role).

### 9-1. Delete AWS resources

```bash
# Delete Profile (from Console or via CLI)
PROFILE_ID=$(echo ${PROFILE_ARN} | awk -F/ '{print $NF}')
aws rolesanywhere delete-profile --profile-id ${PROFILE_ID} --region ${REGION}

# Delete Trust Anchor
TA_ID=$(echo ${TA_ARN} | awk -F/ '{print $NF}')
aws rolesanywhere delete-trust-anchor --trust-anchor-id ${TA_ID} --region ${REGION}

# Detach Role policy, then delete the Role
aws iam delete-role-policy --role-name handson-rolesanywhere-role --policy-name s3-list
aws iam delete-role --role-name handson-rolesanywhere-role
```

### 9-2. Delete local certificates

```bash
rm -rf ~/roles-anywhere-handson
```

### 9-3. Edit ~/.aws/config

```bash
# Open in an editor and remove the [profile rolesanywhere-handson] section
vim ~/.aws/config
```

Everything is gone. Zero bill.

---

## Summary

Built the full path for calling AWS from "outside AWS" without long-lived keys, by hand.

- **Build one self-signed Root CA** (2 openssl commands)
- **Issue an end-entity certificate** (3 openssl commands)
- **Register the CA cert as a Trust Anchor with AWS**
- **In the IAM Role's Trust Policy, trust `rolesanywhere.amazonaws.com`**
- **Bind Trust Anchor and Role via a Profile**
- **Drop `aws_signing_helper` locally and wire it into `credential_process`**
- **Per-CN role split inside one CA via `aws:PrincipalTag/x509Subject/CN` in the Trust Policy**

End state: zero long-lived keys (`AKIA...`) on your laptop. `ASIA...` temporary credentials come out of AWS. Revoke the certificate and access dies immediately. CloudTrail automatically stamps the CN into `sourceIdentity`.

What changes when this scales to production:

- **Switch the Root CA to AWS Private CA or your internal PKI**: with a self-signed CA, the CA private key's safety is now the whole trust loop's safety
- **Automate cert distribution**: every new CN needs a freshly issued end-entity cert. Use a pipeline (Step CA, Smallstep, HashiCorp Vault PKI)
- **Operate a CRL**: leaked certs need to die instantly

Roles Anywhere itself is a small API + official helper, but **the operational hard part is PKI lifecycle**.

What you might explore next:

- **Combine EKS Service Accounts with Roles Anywhere as an IRSA-free path**
- **Connect GitHub self-hosted runners to AWS via Roles Anywhere** (GitHub-hosted runners are better with OIDC)
- **Rotate end-entity certs every 24 hours using Smallstep**

## References

- [IAM Roles Anywhere User Guide](https://docs.aws.amazon.com/rolesanywhere/latest/userguide/introduction.html)
- [aws_signing_helper](https://docs.aws.amazon.com/rolesanywhere/latest/userguide/credential-helper.html)
- [Conditions on `aws:PrincipalTag/x509Subject/CN`](https://docs.aws.amazon.com/rolesanywhere/latest/userguide/trust-model.html)
- [AWS IAM Deep Dive (previous post)](https://dev.to/kanywst/aws-iam-deep-dive-2b81)
- [AWS STS Deep Dive (theory)](https://dev.to/kanywst/aws-sts-deep-dive)
- [IAM Roles Anywhere Deep Dive (theory)](https://dev.to/kanywst/aws-iam-roles-anywhere-deep-dive)
