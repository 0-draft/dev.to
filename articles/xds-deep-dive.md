---
title: 'xDS Deep Dive: Dissecting the "Nervous System" of the Service Mesh'
published: true
description: 'xDS is the dynamic configuration protocol powering Istio and Envoy. How on earth does it stream configurations to thousands of proxies without restarts? From ACK/NACK and ADS to SotW vs Delta, we dive deep into the actual implementation.'
tags:
  - envoy
  - servicemesh
  - kubernetes
  - istio
series: Service Mesh
cover_image: "https://raw.githubusercontent.com/kanywst/dev.to.kanywst/refs/heads/main/articles/assets/xds-deep-dive/cover.png"
---

# Introduction

I was debugging Istio routing the other day, and honestly, I had a moment where I felt a bit "creeped out."

You tweak a `VirtualService` YAML file, hit `kubectl apply`, and within seconds, the routing rules across hundreds of Envoy proxies scattered throughout the cluster switch over perfectly.

There's no process restart. You aren't running `nginx -s reload`. Rolling out configuration changes to thousands of hosts happens in seconds, and **even if you push a completely broken YAML, it magically rolls back to a safe state on its own.**

It feels like magic, but naturally, there's an incredibly gritty mechanism running behind the scenes. That mechanism is **xDS (xDiscovery Service)**.

You might think of it as just "Envoy's config protocol," but xDS has long escaped Envoy's borders. Today, it's standardized as the **"Universal Data Plane API" (the lingua franca of L4/L7 networking)** by the CNCF xDS API Working Group, heavily used by gRPC (Proxyless) and Cilium's ztunnel. As of 2026, it is the absolute most important protocol to understand if you want to talk about service mesh.

We are going to read through this from top to bottom—covering why static configuration is a nightmare, the dependency chain of LDS/RDS/CDS/EDS, and the ACK/NACK rollback mechanism that saves us from outages.

---

## 0. Prerequisites: Why use an "API" to push configurations?

### Envoy and Protocol Buffers

The decisive difference between Envoy and traditional reverse proxies like Nginx or HAProxy is that Envoy was built from the ground up on the premise that **configuration will be injected externally, in real-time, via gRPC.**

Envoy doesn't do service discovery on its own. The control plane (like Istio's `istiod`) watches Kubernetes `Pods` and `Services`, translates them into strongly-typed **Protocol Buffers (proto3)** messages that Envoy understands, and streams them over HTTP/2 gRPC. By using gRPC streaming instead of JSON polling, it achieves incredibly low latency and type safety.

---

## 1. The Despair of Static Configuration and the Awakening of xDS

If you were to configure Envoy statically, you’d end up writing an `envoy.yaml` file like this:

```yaml
static_resources:
  listeners:
  - name: my_listener
    address:
      socket_address: { address: 0.0.0.0, port_value: 8080 }
    # ...filter configs...
  clusters:
  - name: my_backend
    type: STRICT_DNS
    load_assignment:
      cluster_name: my_backend
      endpoints:
      - lb_endpoints:
        - endpoint:
            address:
              socket_address: { address: 10.0.1.15, port_value: 8080 }
```

In the idyllic days when you only had 10 Pods, this was fine. But in today's Kubernetes environments, Pods scale every second, they fluctuate due to HPA, and IPs change constantly as nodes are retired. **Every time a backend IP changes, are you going to rewrite the config files for all proxies and restart their processes?** That's pure insanity. Connections would drop, latency would spike, and the system would collapse.

That is exactly why dynamic configuration (xDS) is mandatory.

![dynamic configuration](./assets/xds-deep-dive/dynamic.png)

With xDS, Envoy can seamlessly start routing traffic to new Pod IPs with absolutely zero restarts.

---

## 2. The Core 5 Discovery Services

The "x" in xDS is a wildcard. The protocol is heavily segmented into five major services (APIs) based on the scope of the configuration.

These aren't just parallel configuration items—they have **strict dependencies (pointers)** on one another. Grasping this dependency chain is step one to mastering xDS.

* **LDS (Listener)**: Which port should we listen on?
* **RDS (Route)**: Which path routes to where?
* **CDS (Cluster)**: What are the connection settings for the destination service?
* **EDS (Endpoint)**: What are the actual IP addresses of that service?
* **SDS (Secret)**: What certificate data (e.g., for TLS termination) do we need?

Let's look at how they point to each other at the YAML/code level.

### ① LDS → Pointing to RDS

LDS creates the entry point, defining "Listen for HTTP on port 8080." However, instead of hardcoding IP destinations for the traffic, it embeds a **reference (name) to the RDS**.

```yaml
# Data streamed from LDS (Listener Discovery Service)
name: my_listener
address:
  socket_address: { address: 0.0.0.0, port_value: 8080 }
filter_chains:
- filters:
  - name: envoy.filters.network.http_connection_manager
    typed_config:
      rds:
        route_config_name: my_routes  # ← [KEY] Refers to RDS resource "my_routes"
```

### ② RDS → Pointing to CDS

RDS is the "signboard." Called up by LDS as `my_routes`, this config evaluates HTTP paths or headers and returns **a logical cluster name (a reference to CDS)**. Istio's `VirtualService` gets translated into this layer.

```yaml
# Data streamed from RDS (Route Discovery Service)
name: my_routes
virtual_hosts:
- name: api_host
  domains: ["api.example.com"]
  routes:
  - match: { prefix: "/v1/" }
    route: { cluster: api-v1-cluster }  # ← [KEY] Refers to CDS resource "api-v1-cluster"
```

### ③ CDS → Pointing to EDS

CDS defines the *nature* of the designated cluster. It determines the load balancing algorithm (Round Robin, etc.) and circuit breaker thresholds. This is the domain of Istio's `DestinationRule`.

It still doesn't write down specific IP addresses here; it **delegates the final resolution to EDS**.

```yaml
# Data streamed from CDS (Cluster Discovery Service)
name: api-v1-cluster
type: EDS                           # ← [KEY] Declares we will fetch endpoints dynamically via EDS
eds_cluster_config:
  eds_config: { ads: {} }           # (Requests EDS via ADS)
lb_policy: ROUND_ROBIN
```

### ④ Touching Down at EDS

Finally, EDS returns the **actual IP addresses of the Pods** tied to that cluster. Because clusters scale up and down, EDS is the most aggressively updated component in xDS.

```yaml
# Data streamed from EDS (Endpoint Discovery Service)
cluster_name: api-v1-cluster
endpoints:
- lb_endpoints:
  - endpoint:
      address:
        socket_address: { address: 10.0.1.15, port_value: 8080 }  # ← Actual IP
  - endpoint:
      address:
        socket_address: { address: 10.0.1.22, port_value: 8080 }  # ← Actual IP
```

### ⑤ Encrypting via SDS (mTLS) and Zero-Downtime Rotation

Once the destination IP is pinned down, we don't just blindly fire the packet. In modern service meshes, mTLS (mutual TLS) encryption between Pods is mandatory. This is where **SDS (Secret Discovery Service)** steps onto the stage.

Inside the CDS definition, it dictates "use this specific TLS context when talking to this cluster." Envoy then uses SDS to dynamically fetch the certificate (SVID) and private key straight into memory.
What's spectacular here is **certificate rotation**. Before a certificate expires, you historically had to restart the web server process. With SDS, the microsecond a new certificate is issued, it is flashed into memory via xDS, enabling **100% zero-downtime, automated certificate rotation**. Because this is highly sensitive secret data, this specific stream is strictly gated and protected.

```yaml
# Conceptual data streamed from SDS (Secret Discovery Service)
name: default
tls_certificate:
  certificate_chain: { inline_string: "-----BEGIN CERTIFICATE-----\n..." }
  private_key: { inline_string: "-----BEGIN PRIVATE KEY-----\n..." }
```

In short, a packet perfectly traces the configuration pointers in the exact order of **LDS → RDS → CDS → EDS (+ SDS)**, encrypts itself, secures routing, and takes flight.

![xds flow](./assets/xds-deep-dive/xds.png)

You must never forget this "dependency order." It is the exact reason why ADS (Aggregated Discovery Service), which we'll discuss later, exists.

---

## 3. Surviving Broken Configs: The ACK/NACK Flow

In an architecture where dynamic configs are blasted out to thousands of proxies, pushing a "bad config" causes apocalyptic damage. What happens if the control plane sends a malformed JSON or a conflicting route setting?

Does Envoy bug out and crash? ...Absolutely not.
xDS is armed with a fiercely robust rollback mechanism called **"NACK" (Negative Acknowledgement)**.

xDS communication is a bidirectional gRPC stream. When a `DiscoveryResponse` arrives from the control plane, Envoy attempts to apply it. It then packages the result into a `DiscoveryRequest` and shoots it back to the control plane.

![nack](./assets/xds-deep-dive/nack.png)

The absolute beauty of this design is that **even if a NACK occurs, Envoy's stream does NOT sever; it just keeps humming along using the last-known-good config (v1)**.
Even if an operator brutally applies a flawed `VirtualService` to Kubernetes, Envoy essentially says "screw this," returns a NACK, and existing traffic doesn't drop a single millisecond. It simply waits idly for a corrected config to be pushed.

Two control fields are the key players here: `nonce` and `version_info`.

* **`nonce`**: A simple ID that says, "Hey, which specific update payload are you giving me the validation result for?"
* **`version_info`**: The factual state that says, "As a result, what version of the config am I currently running?"

If Envoy simply parrots back the latest `version_info` the server sent, it's categorized as an "ACK (Success)." If it returns an older version number, the server realizes it's a "NACK (Failure)." It’s brilliantly simple, yet ruthlessly effective.

---

## 4. Why We Need ADS (Aggregated Discovery Service)

Earlier, I mentioned that LDS → RDS → CDS → EDS share a strict dependency chain.

What would happen if you subscribed to these four APIs via **completely separate gRPC streams** asynchronously from the control plane? Naturally, due to network latency or processing timing, their arrival order would scramble.

**Imagine the worst-case scenario.**
A new RDS (route setting) arrives first. It says, "route traffic to `cluster-B`". Envoy eagerly updates its settings and tries to shove traffic towards `cluster-B`. However, the streams for CDS and EDS (the actual definition and IPs of `cluster-B`) are lagging slightly behind and haven't hit Envoy yet.

As a result, Envoy concludes "the destination cluster doesn't exist" and **starts aggressively throwing 503 Service Unavailable errors**. A service mesh where 503s run rampant every time a configuration changes is completely unusable.

### The Fix: Bundling the Streams (ADS)

To prevent this "temporary inconsistency in an eventually consistent system," **ADS (Aggregated Discovery Service)** was forged.

ADS multiplexes (aggregates) the requests and responses for ALL xDS resource types (LDS/RDS/CDS/EDS) into **a single solitary gRPC stream**.

![ads](./assets/xds-deep-dive/ads.png)

By bundling everything into one stream, the control plane gains the ability to enforce perfect Sequencing: **"I will force Envoy to apply CDS/EDS first, and I won't send RDS until I get the ACKs back."**
Istio's control plane (`istiod`) uses this ADS approach by default to stream configurations safely.

---

## 5. SotW vs Delta: Taming the Infinite Endpoint Explosion

Looking back at the history of xDS brings us to another massive evolutionary fork: *how* the configs are sent.

### The Limits of State of the World (SotW)

Early xDS utilized a model called **SotW (State of the World)**. When Envoy asks "Tell me the current endpoints," the server responds by sending back **"the entire, exhaustive list of endpoints"** every single time.

Let's assume you have a cluster of 1,000 Pods, and a single Pod scales out, making it 1,001.
In the SotW model, `istiod` beams out the **full list of 1,001 IP addresses** to every single Envoy proxy. The 1,000 unmodified records are re-transmitted entirely. This is a colossal waste of network bandwidth and CPU horsepower. Once your cluster scales large enough, the control plane literally chokes and dies.

### The Dawn of Incremental (Delta) xDS

This crisis birthed **Delta xDS**.
When returning subscription requests, the server now sends **"only the diff from the last state (added IPs, removed IPs)."**

* SotW: `[IP_A, IP_B, IP_C]` (If B is deleted, it resends `[IP_A, IP_C]`. Items missing from the list are implicitly assumed deleted.)
* Delta: `removed_resources: ["IP_B"]` (Explicitly sends ONLY the deletion directive.)

Because the server must maintain an in-memory cache tracking the individual state of every single client, the backend implementation becomes drastically more complex. However, the performance gains are monumental. Modern service meshes circa 2026 (like recent versions of Istio) securely default to Delta xDS.

---

## 6. Beyond Routing: Advanced xDS Use Cases

When discussing xDS, it's impossible to ignore the fact that **xDS is no longer an "Envoy-exclusive routing protocol."** As of 2026, the xDS ecosystem has wildly expanded beyond basic routing and breached into non-Envoy clients.

### 6.1 Dynamic Injection of Extensions (ECDS)

**ECDS (Extension Config Discovery Service)** is a mechanism to dynamically push "extension filters" (like WebAssembly) directly into Envoy.
For example, you write a proprietary Wasm module that applies custom obfuscation to a specific HTTP header, and you stream it via ECDS. This lets you **hot-reload and inject brand-new Wasm modules into every proxy safely, while they are running**, without touching LDS or RDS at all.

### 6.2 Streaming Runtime Variables (RTDS)

**RTDS (Runtime Discovery Service)** skips routing altogether and instead streams "runtime variables" (think of it as a virtual file system).
Need to flip a new feature ON/OFF (feature toggles) or temporarily throttle a specific user's rate limits? You use RTDS. It instantly propagates single variable tweaks to thousands of proxies without forcing an application rebuild or redeploy.

### 6.3 Building Proprietary Control Planes (`go-control-plane`) & Case Studies

Because the xDS specs are fully open (defined in Protobuf), it's highly common for massive-scale environments to ditch off-the-shelf products like Istio and **build their very own bespoke xDS control planes**.

Libraries provided by the Envoy project, like `go-control-plane`, shoulder the agonizing implementation burdens of operating an xDS gRPC server (handling streams, snapshot caching, etc.). By wiring this up, companies can construct proprietary control planes that use "internal corporate databases" as the Source of Truth, governed by heavily customized business logic.

**Tech Giant Case Studies:**
For companies wrestling with horribly complex "brownfield" infrastructure, these custom control planes are a lifeline.

* **Stripe**: They operate an internal service mesh using HashiCorp Consul as the Source of Truth for service discovery. They built a custom control plane that snags data from Consul, compiles it into xDS parameters, and streams it to Envoy.
* **Netflix**: To manage their astronomical fleet of microservices, Netflix built a custom foundation fused with Eureka (their service registry). By aggressively utilizing `On-Demand Cluster Discovery (ODCDS)`, they dynamically inject *only* the settings Envoy actually needs, shattering the scaling boundaries of giant clusters.
* **Airbnb / Uber**: They bake custom logic into their bespoke control planes to rein in legacy, non-containerized workloads that refuse to submit to Kubernetes, and to shove highly specialized, company-specific L7 routing logic straight into the proxy tier.

The meta isn't just "deploy Istio and call it a day." It’s "translate your company's proprietary domain logic into xDS, the universal language, and stream it." That is the absolute frontline of the service mesh today.

### 6.4 The "Proxyless gRPC" Paradigm

The ultimate evolution of this is **Proxyless gRPC**.
Instead of deploying an Envoy (sidecar) next to your application, **the gRPC library itself seamlessly acts as an xDS client**.

![Proxyless gRPC](./assets/xds-deep-dive/proxyless-grpc.png)

By generating a gRPC channel using the unique `xds:///my-service` URI scheme, the gRPC library quietly connects to the control plane (like `istiod`) under the hood, pulls down EDS configs, and blasts direct HTTP/2 requests right to the optimal Pod from *within your own application process*.
Because you bypass the sidecar entirely, you prune network hops, slashing latency and devouring far less CPU. *This* is the true essence of xDS earning the title "Universal Data Plane API".

---

## Conclusion

Behind the wizardry of an infrastructure that magically swaps over seconds after you smash `kubectl apply`, lies this heavily gritty, battle-tested mechanism.

The rigid hierarchy of LDS/RDS/CDS/EDS enforcing dependencies.
The indestructible ACK/NACK flow shielding the system from crippled configurations.
The sequencing and stream multiplexing of ADS preventing nasty 503 hiccups.
And the adoption of Delta xDS breaking the chains of scalability limits.

It is precisely because these gears mesh in such miraculous balance that we get to casually enjoy things like "zero downtime traffic shifting" and "canary releases."
xDS is no longer just Envoy's internal protocol. It is the absolute, most vital "nervous system" anchoring modern, cloud-native network architecture.

## References

* [Envoy xDS REST and gRPC Protocol (Official Documentation)](https://www.envoyproxy.io/docs/envoy/latest/api-docs/xds_protocol)
* [xDS API Overview - Envoy](https://www.envoyproxy.io/docs/envoy/latest/api/api)
* [CNCF xDS API Repository](https://github.com/cncf/xds)
* [gRPC Proxyless Service Mesh](https://grpc.io/docs/guides/xds/)
