---
title: 'Microsegmentation Deep Dive'
published: true
description: 'Perimeter defense no longer stops ransomware spreading sideways. One article on why VLAN/Firewall hit a wall, the four implementation patterns (hypervisor / agent / cloud-native / Identity), and how VMware NSX, Illumio, Akamai Guardicore, Cilium, and Google BeyondCorp each solved it, all at the resolution of implementation and ops.'
tags:
  - security
  - zerotrust
  - networking
  - kubernetes
series: "Zero Trust"
cover_image: "https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/microsegmentation-deep-dive/cover.png"
---

## Introduction

A few years back, an SRE I know said this to me:

> "The firewall on the outside is hardened to hell. But once you're in, it's over. Inside the LAN, everything from Pod-to-Pod to SMB just flows."

You cannot defend a modern system by making the outside stronger. You have to slice the inside of the LAN, the gaps between Pods and containers, the East-West traffic between VMs, into many small zones and police each one. That is **microsegmentation**.

This article tries to nail down microsegmentation at the resolution of implementation and operations, not as a vibe-word. Why VLAN and firewall hit a wall, how the four implementation styles (hypervisor / agent / cloud-native / Identity) actually differ, and how players like VMware NSX, Illumio, Akamai Guardicore, Cilium, and Google BeyondCorp each took their own shot at the problem.

---

## 0. Prerequisites for reading this

A quick glossary for terms used later. Skip if you already know them.

### North-South traffic and East-West traffic

Traffic crossing the boundary of a data center or cluster is **North-South**. A user's browser hitting a web server, for example. Traffic *inside* the data center, server to server, Pod to Pod, container to container, is **East-West**.

In modern systems, East-West dwarfs North-South in both volume and variety. With microservices, containers, and data lakes, a single user request often fans out into dozens of internal API calls. A perimeter firewall sees none of that East-West.

### Zero Trust and "Never Trust, Always Verify"

The idea of throwing out the assumption that "the internal LAN is trusted." Every connection is treated as if it were external, and authorization happens every time based on identity, device state, and context. NIST SP 800-207 is the de facto standard spec.

Microsegmentation is the main piece of "how do you actually implement Zero Trust at the network layer."

### PEP / PDP (Policy Enforcement Point / Policy Decision Point)

The core model defined by NIST SP 800-207.

- **PDP (Policy Decision Point)**: the "brain" that evaluates policy and returns allow/deny. Internally split in two.
  - **PE (Policy Engine)**: the decision logic itself.
  - **PA (Policy Administrator)**: opens and closes sessions based on PE's verdict.
- **PEP (Policy Enforcement Point)**: the "hand" that actually applies the PDP's decision to the wire.

In microsegmentation, the PEP is something sitting right next to each workload: the host OS firewall, the hypervisor's virtual NIC, a sidecar proxy, an eBPF program. The PE consumes identity, device posture, threat intel, behavioral baselines, and so on.

![PEP and PDP model](./assets/microsegmentation-deep-dive/diagrams/01-pep-pdp-model.png)

Comparing microsegmentation products comes down to two axes: **where you put the PEP** and **what signals the PDP can use to decide**. The four implementation styles in the next sections all map onto one corner of this picture.

### VLAN, ACL, Security Group

The classic cast of segmentation. VLANs split broadcast domains at L2. ACLs (Access Control List) sit on routers and switches and permit traffic per IP/port. In cloud, Security Groups act as stateful L3/L4 ACLs. All of them are IP/location-based, which (we will see) is exactly the root cause of today's pain.

### IP-based vs Identity-driven

What you use as the *subject* of a policy.

- **IP-based**: "allow `10.0.1.0/24` to reach `10.0.2.5:443`." The address is the subject. VLAN, ACL, and traditional firewalls all live here.
- **Identity-driven**: "allow Pods with `role=web` to reach Pods with `role=db` on `tcp/5432`." A label or a cryptographic ID is the subject.

In a world where Pod IPs churn every minute because of autoscaling and rescheduling, IP-based policy cannot keep up. Identity-driven exists precisely to dodge that problem.

### L3/L4 control vs L7 control

How deep the firewall looks before it decides.

- **L3/L4**: IP address and port/protocol. "Allow `tcp/5432` from `10.0.1.0/24`." VLAN, ACL, Security Group, nftables, classic NSX.
- **L7**: HTTP method, URL path, gRPC method, Kafka topic, etc. "Allow only `POST /api/payment`, block `DELETE`." Service meshes (Istio / Envoy), Cilium's L7 policy, Cisco Secure Workload reach into this layer.

L7 control lets you cut off SQL injection or unauthorized admin-API calls one layer earlier.

### SPIFFE / SPIRE and SVID

A spec (SPIFFE) for giving workloads a *cryptographic ID instead of an IP*, plus its reference implementation (SPIRE). A URI of the form `spiffe://trust-domain/workload-path` gets embedded into the **URI SAN (Subject Alternative Name)** field of an X.509 cert. That cert is called an **SVID (SPIFFE Verifiable Identity Document)**.

During an mTLS handshake, you read the URI SAN out of the peer's SVID and decide "the peer is `spiffe://prod/cart`, so allow." That is the foundation of identity-driven microsegmentation.

### eBPF

A Linux kernel mechanism for safely running small programs inside the kernel. Cilium uses it to do packet filtering, policy evaluation, and L7 observation in one pass, all in kernel space.

### Application Dependency Map (ADM)

The core feature of agent-based products like Illumio. It aggregates flow telemetry from every host and automatically draws "**which workload talks to which workload, on which port**." If you start enforcement without first looking at this map, your policy will halt the business the moment it lands (more on this in section 5).

---

## 1. Why "macro" stopped being enough

A quick walk through the history. Microsegmentation did not pop out of nowhere; it is the endpoint of 20 years of "make the segments smaller."

### 1.1 The castle wall era (perimeter-only)

The classic 2000s network: a single wall between the LAN and the internet.

![Castle wall perimeter model](./assets/microsegmentation-deep-dive/diagrams/02-castle-wall.png)

The problem is obvious. **Once anyone steps inside the wall, the inside is flat.** The moment an attacker owns one workstation, every internal DB, every printer, every dev server is theirs.

### 1.2 VLAN + firewall zones (macrosegmentation)

The next generation split the LAN into rough chunks with VLANs and per-zone firewalls.

![VLAN and firewall zones](./assets/microsegmentation-deep-dive/diagrams/03-vlan-zones.png)

A real step forward, but "inside the zone" is still flat. Once an attacker is on the web tier, the other web servers in the same VLAN are wide open. In an era where one service has fanned out into dozens or hundreds of workloads, this granularity does not cut it.

### 1.3 Microsegmentation (per-workload)

The endpoint: **every single workload gets its own firewall.**

![Per-workload PEP](./assets/microsegmentation-deep-dive/diagrams/04-per-workload-pep.png)

Three things matter here:

1. **The PEP sits right next to the workload.** Not a physical firewall box. The host OS filter, the hypervisor's virtual NIC, a sidecar proxy, an eBPF program.
2. **Default deny.** "Anything not explicitly allowed is dropped" is the starting position.
3. **Policy is written per application.** "Web to Cart," using services or roles as subjects.

### 1.4 Macro vs micro

| Item | Macro (VLAN/Zone) | Micro (Workload) |
| --- | --- | --- |
| Granularity | Subnet / zone | Workload / Pod / process |
| Subject | IP, subnet | Service name, label, SPIFFE ID |
| Mainly guards | North-South | East-West |
| Policy lifetime | Long, pinned to IP | Dynamic, driven by ID |
| Resistance to lateral movement | Weak inside the zone | Cuts per workload |
| Number of firewalls | A handful to dozens | Hundreds to hundreds of thousands (logically) |

The point is not "macro becomes unnecessary," it is "microsegmentation adds one more layer of finer defense inside the macro."

---

## 2. NotPetya and ransomware pressed the "decision button"

The thing that pushed microsegmentation from "idea" to "product category" was **NotPetya** in 2017. Once you understand how that incident unfolded, the sudden global appetite for investment makes sense.

### 2.1 What happened

![NotPetya lateral movement sequence](./assets/microsegmentation-deep-dive/diagrams/05-notpetya-sequence.png)

Damage came to roughly $300M for Maersk alone, and over $10B globally (Forrester / Armis estimates). Merck, FedEx's TNT Express, Mondelez, and Reckitt got dragged in too.

### 2.2 What would have happened with microsegmentation

A single-line equivalent policy, "never permit SMB 445/tcp between workstations," would have shut down the main lateral path (EternalBlue over SMB). The secondary spread after Mimikatz hijacked the DC could have been localized too, if admin paths were narrowed to "from jump host only." Forrester's post-mortem said it plainly: microsegmentation and fine-grained internal controls should be rolled out as part of a Zero Trust strategy.

After that, alongside Zero Trust, microsegmentation became a board-level topic as "the precondition for lowering your ransomware insurance premium." Gartner forecasts that **by 2026, 60% of organizations pursuing Zero Trust will use multiple forms of microsegmentation in combination** (the same figure was under 5% three years prior).

---

## 3. The four implementation styles

There are dozens of vendors, but architecturally they cluster into four families.

![Four implementation styles](./assets/microsegmentation-deep-dive/diagrams/06-four-styles.png)

### 3.1 A. Hypervisor (VMware NSX)

The classic for VM-heavy shops. Every ESXi host has a **Distributed Firewall (DFW)** baked into the hypervisor kernel, doing stateful filtering right at the VM's virtual NIC (vNIC).

![NSX hypervisor DFW](./assets/microsegmentation-deep-dive/diagrams/07-nsx-hypervisor.png)

What stands out:

- **The app does not change.** No agent inside the guest OS. The policy "moves with the VM" on vMotion (the session table travels too).
- **Near line-rate** (close to the physical NIC's theoretical throughput). Being a kernel module, the perf hit is minimal.
- The weakness is VMware lock-in, plus the fact that you need a different stack the moment physical servers, containers, or cloud VMs enter the picture.

### 3.2 B. Agent (Illumio / Akamai Guardicore / Cisco Secure Workload)

Drop a lightweight agent into every host OS, and have it drive the OS-native firewall (Windows Filtering Platform, Linux nftables/iptables, macOS pf).

![Agent-based microsegmentation](./assets/microsegmentation-deep-dive/diagrams/08-agent-style.png)

Illumio collects telemetry from its agents (VEN: Virtual Enforcement Node), auto-builds an **Application Dependency Map (ADM)**, and uses that as the canvas for writing policy. Akamai Guardicore ships its own light kernel module, plus differentiators like **deception (decoys)** and an **agentless mode powered by NVIDIA BlueField DPUs** (Data Processing Units that run segmentation on the server's NIC). Cisco Secure Workload (formerly Tetration, renamed in 2020) traces back to slurping flows out of data center switch ASICs and learning behavior with ML.

What stands out:

- **Infrastructure-agnostic.** The same abstraction (labels/tags) works across on-prem, bare metal, cloud, and containers.
- **Strong visualization via ADM.** Real value shows up before policy: "let's see what is actually talking to what."
- The weakness is "you have to run an agent on every host." OS version compatibility, updates, and support windows for legacy OSes (Windows Server 2003 and friends) become operational pain.

### 3.3 C. Cloud-native (Security Group / NSG / NetworkPolicy)

Take the mechanisms cloud providers and orchestrators already ship with, and lean on them hard for microsegmentation purposes.

![Cloud-native Security Groups](./assets/microsegmentation-deep-dive/diagrams/09-cloud-native-sg.png)

The thing about AWS Security Groups is that **you can put an SG where an IP would normally go**. Writing `source=sg-web` effectively gives you role-based policy. Azure NSG and GCP VPC Firewall Rules have the same trick. On the Kubernetes side, `NetworkPolicy` plays this role: write allow rules with `podSelector` and `namespaceSelector`, and the policy tracks Pod IP changes for you.

What stands out:

- **Effectively free** to start. Cloud-standard, no extra agent.
- The weakness is central policy management and org-wide consistency. Once SGs hit five digits, humans cannot manage them by hand. You need a higher layer like AWS Firewall Manager, OPA, or Kyverno. Also, no L7 control (you cannot permit by HTTP method).

### 3.4 D. Identity-driven (Cilium / Istio + SPIFFE)

The newest family. **The subject of policy is not an IP, it is a cryptographic ID.**

![Identity-driven with Cilium and SPIFFE](./assets/microsegmentation-deep-dive/diagrams/10-identity-driven.png)

With Cilium, Pod IPs can change, but the **Cilium Identity (a numeric value)** computed from labels stays stable. eBPF looks at the Identity attached to a packet to decide allow/deny, so "Cart Pod restarted and got a new IP" does not break policy.

With Istio + SPIFFE, each sidecar (Envoy) receives an SVID. At mTLS time, the URI SAN is read and compared against `principals` in an `AuthorizationPolicy` (e.g. `cluster.local/ns/prod/sa/cart`).

What stands out:

- **Doesn't fall apart when IPs are ephemeral.** Pod churn, autoscaling, serverless-style dynamic environments, all fine.
- **L7 control** is on the table (HTTP method/path, gRPC methods, Kafka topics).
- The weakness is the learning curve, and the need to run a CA / Identity layer underneath.

### 3.5 Comparison

| Style | Example | Main PEP | Subject | Strength | Weakness |
| --- | --- | --- | --- | --- | --- |
| Hypervisor | VMware NSX | vNIC (DFW) | VM tag | Perf, follows VM moves | VMware only |
| Agent | Illumio, Akamai | OS firewall | Label | Cross-environment, ADM | Agent ops |
| Cloud-native | AWS SG, K8s NetworkPolicy | Cloud / CNI | SG / label | Cheap, standard | No L7, weak central mgmt |
| Identity-driven | Cilium, Istio | eBPF / sidecar | SPIFFE ID, label | Great for dynamic env, L7 | Learning curve |

Large orgs **mix all of these**. SG at the AWS edge, Cilium inside the Kubernetes layer, NSX for data center VMs, Illumio agents on the legacy Windows servers. The "60% using multiple forms" in Gartner's 2026 forecast is exactly this.

---

## 4. How large enterprises actually use it

Spec sheets only get you so far. Five real-world cases.

### 4.1 Google: BeyondCorp (identity-driven across the whole company)

In late 2009, Google got hit by a Chinese state-sponsored campaign known as **Operation Aurora**. Initial intrusion was a **spear-phishing email plus an Internet Explorer zero-day (CVE-2010-0249)**: clicking the malicious link planted the Hydraq trojan. From that beachhead, attackers moved laterally across Google's flat internal network and walked out with intellectual property, source code included. Google went public in January 2010.

Google's answer was **BeyondCorp**. They flipped the premise 180 degrees:

- Stop treating the internal LAN as a trusted zone. Throw out the VPN.
- Don't authorize by "what network are you on," authorize every request based on **user ID + device ID + posture**.
- Microsegmentation is the core feature that stops malware moving from a user toward an app.

![Google BeyondCorp access flow](./assets/microsegmentation-deep-dive/diagrams/11-beyondcorp-sequence.png)

The key here: the AP (Access Proxy) is the **PEP sitting in front of every app**, and apps are reachable only via the AP. Whether you're on the office LAN is irrelevant. This is identity-driven microsegmentation taken to its logical extreme.

A commercial version is sold externally as **BeyondCorp Enterprise**.

### 4.2 Maersk: rebuilding after NotPetya

Maersk's global ops were down for roughly 10 days after NotPetya. They **rebuilt 45,000 PCs and 4,000 servers in about 10 days** (per Bleeping Computer reporting). Post-mortems (CSO Online, ComputerWeekly) point to SMB v1 and Windows domain admin paths running flat across the org, which let the malware spread sideways.

Specific details of the post-incident security rebuild are limited in public reporting, but Maersk's then-CISO repeatedly said in conference talks and interviews that "the same attack still works against plenty of other companies." That pushed the Maersk case into the canonical reference for "this is when microsegmentation plus Zero Trust investment took off industry-wide."

### 4.3 A Global 250 bank: SWIFT compliance with Illumio

From Illumio's official case study. A Global 250 bank needed to comply with **SWIFT CSP (Customer Security Programme)**, which required closing every SWIFT-related server into a "per-host logical isolation zone."

The traditional path (physical firewalls):

- Weeks of lead time per rule change.
- Mismatch with DevOps speed.
- Extra hardware cost.

How Illumio solved it:

1. Deploy the agent in observation mode across every SWIFT-related host.
2. Use the **Application Dependency Map** to visualize real traffic.
3. Generate policy from observed flows.
4. Gradually flip to enforcement mode.

Illumio's framing of the bank's stance: "**you cannot write policy for traffic you do not understand, so start from the ADM.**" The bank is now extending Illumio into SDLC (Software Development Life Cycle: dev, test, staging environments) too, using it to stand up isolated test environments for remote vendors.

### 4.4 A major healthcare org: protecting 6,000 assets and medical IoT (Akamai Guardicore)

From Akamai's case study. Over 6,000 assets, plus bedside monitors and medical IoT, all sharing a flat network. Lateral movement toward patient data and payment data was the headline risk.

Why Guardicore:

- It's a software overlay, so no infrastructure changes were needed.
- The same policy language works across on-prem and AWS.
- Even devices that cannot host an agent (medical IoT, etc.) can be covered by flow observation.

### 4.5 A global manufacturer: SMB control across 2,000 workstations (Akamai Guardicore)

Another Akamai case. A manufacturer with mixed "office + factory" sites worldwide, slicing up a flat workstation network in stages.

The first phase rolled Guardicore out to 2,000 workstations. The IT security team's quote: "**network visibility improved by 1,000%.**" They cut off **pass-the-hash** (the classic move of replaying a stolen Windows password hash to authenticate remotely) and ransomware spreading workstation-to-workstation over SMB by making SMB between workstations default-deny.

---

## 5. Implementation pitfalls (where projects die on Day 1 / Day 2)

Picking the right product does not save you. The places where projects get stuck are pretty consistent.

### 5.1 "Policy without visibility" always breaks something

A lot of teams get cocky after a PoC and flip enforcement in production. The blast radius is huge, and the root cause is always the same: **you put in default-deny without first understanding what is talking to what.** Without 2 to 4 weeks (months, for business systems) in observation mode collecting flows, then policy generation, then staged rollout, you will almost certainly take down a production system and watch the project get frozen.

That is the same reason Illumio insists "**the ADM is the protagonist; policy is derived from the ADM**," and the reason Cisco Secure Workload makes a song and dance about ML-based behavior learning. The rule is **Discovery, then Modeling, then Enforcement**, in that order.

### 5.2 Label design decides your fate

With both agent and identity-driven styles, policy is written as set algebra over labels. Dirty labels produce exponentially dirty policy.

A practical axis set:

- **environment**: prod / staging / dev
- **application**: payments / cart / catalog
- **role / tier**: web / app / db / cache
- **data classification**: pii / pci / public
- **region** (optional): us-east-1 / ap-northeast-1

Lock in a plan to attach at least these four axes to every asset *before* enforcement starts. Re-labeling later is, in practice, impossible.

### 5.3 The last 10% is the hardest

Discovery explains most of the traffic. The remaining 10%:

- Yearly batch jobs that have not run during the observation window.
- Legacy systems that were supposed to be retired but are still running.
- Traffic that only fires during a DR cutover.
- Stray scripts a developer set up on their own.

Deciding "the observation window never saw it, so deny" leads to the yearly batch tipping over a production system. The opposite, "allow everything just in case," makes the whole exercise pointless.

In practice:

1. Run in `alert-only` mode for a while (let traffic through but log it).
2. Stay in observation mode for one full business cycle (e.g. 13 months).
3. Triage every unsanctioned flow that surfaces in that window.
4. Then, finally, flip to enforcement.

The organization and management who can accept that rhythm matter more than the technology choice.

### 5.4 Don't try to do everything at once

A project that tries to segment the entire organization in one swing almost always fails. Elisity's and Gartner's guides list "**tried to do everything at once and stalled**" as the most common failure mode.

What actually works is roughly four phases:

1. **Phase 1**: Crown jewels (SWIFT, payment DB, KMS, CA, etc.). Small blast radius, but very expensive if down.
2. **Phase 2**: Production app tiers (Web / App / DB).
3. **Phase 3**: Endpoint and office networks.
4. **Phase 4**: OT and legacy systems (the hardest).

Start with the Crown Jewels, where business impact is biggest and flows are most knowable, and expand outward. Each phase is 3 to 6 months. Be ready for 18 to 36 months total.

---

## Conclusion

If you only take three things away:

1. **Microsegmentation is about stopping lateral movement.** Look at East-West (inside), not at the North-South boundary.
2. **Move from IP-based to ID-based.** Stop extending VLAN/ACL; redesign around labels, SPIFFE IDs, IAM roles.
3. **Visibility before enforcement.** Reverse Discovery -> Modeling -> Enforcement and the project gets pickled.
