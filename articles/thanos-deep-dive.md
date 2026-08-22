---
title: 'Thanos Deep Dive: Breaking Through Prometheus''s ''Limitations'''
published: true
description: 'Thanos solves the challenges of ''long-term storage'' and ''High Availability (HA)'' in Prometheus. We thoroughly dissect the architecture of how components like Sidecar, Store Gateway, and Compactor coordinate and utilize object storage.'
tags:
  - prometheus
  - thanos
  - o11y
  - s3
series: O11y
id: 3199342
cover_image: 'https://raw.githubusercontent.com/0-draft/dev.to/refs/heads/main/articles/assets/thanos/thanos-meme.png'
date: '2026-01-26T15:03:28Z'
---

## Introduction

Prometheus is a wonderful tool, but as operations grow in duration and scale, you inevitably hit two major barriers.

1. **The Barrier of Long-term Storage**: Local disk capacity is limited. Even if asked, "I want to see data from a year ago," it is already gone.
2. **The Barrier of Availability (HA)**: Prometheus becomes a single point of failure. If you configure HA (two parallel servers), data becomes duplicated, causing graphs to look jagged.

**Thanos** solves these challenges by utilizing **"Object Storage (such as S3)"** and a **"Microservices Architecture."**

In this article, we will deep dive into the architecture with diagrams to see how each Thanos component coordinates to achieve infinite storage and global querying.

---

## 1. Architecture Overview

Thanos is not a single binary, but a collection of components for specific roles.

![thanos](./assets/thanos/thanos1.png)

---

## 2. Component Deep Dive

Let's look at the role of each component.

### 1. Thanos Sidecar

**"The Courier Next to Prometheus"**

It runs in the same Pod (or server) as Prometheus.

* **Upload**: It detects blocks (every 2 hours) written to disk by Prometheus and immediately uploads them to S3. This allows Prometheus's main disk usage to be minimized (keeping only the last few hours).
* **Proxy**: It receives requests from `Thanos Query` and returns Prometheus's latest data (in-memory data).

### 2. Thanos Store Gateway

**"The Gatekeeper Making S3 Data Searchable"**

It exposes massive amounts of past data in S3 to `Thanos Query` as if it were local.
By caching parts of the data index locally, it reduces access counts to S3 and achieves high-speed querying.

### 3. Thanos Compactor

**"The Storage Organizer"**

It operates on data in S3 in the background.

* **Downsampling**: 15-second precision is unnecessary for "data from a year ago." By thinning out (downsampling) data to "1-hour averages" or "5-minute averages," long-term queries become blazing fast.
* **Compaction**: It merges and organizes small blocks.
* **Retention**: It deletes data that has passed a configured retention period (e.g., 1 year).

### 4. Thanos Query (Querier)

**"The Unified Query Layer Bundling Everything"**

Grafana and similar tools connect to this component.

* **Global View**: It collects data from multiple Sidecars (current) and Store Gateways (past), combines them, and returns the result.
* **Deduplication**: In an HA configuration with two Prometheus servers, the same data is sent from both. However, the Querier automatically performs **Deduplication**, returning a clean single line.

---

## 3. Data Flow: "Write" and "Read"

Let's organize how data flows and how it is read.

### The Write Path

![write](./assets/thanos/write.png)

### The Read Path

When a query comes in asking, "I want to see data from the past month":

![read](./assets/thanos/read.png)

---

## 4. Hands-on: Local Demo with Docker Compose

Running Thanos locally as a standalone binary is difficult because it involves many components and requires S3. The standard approach is to use Docker Compose to launch the entire suite alongside a pseudo-S3 (MinIO).

This time, we will use the latest **Prometheus v3.9.1** and **Thanos v0.40.1** to create a fully functional configuration.

### Step 1: Create Configuration Files

First, create a working directory and prepare the following three configuration files.

#### 1. `prometheus.yml`

`external_labels` are mandatory so that the Thanos Sidecar can identify the data.

```yaml
global:
  scrape_interval: 5s
  external_labels:
    monitor: 'prom-1'
    cluster: 'test-cluster'

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

```

#### 2. `bucket_config.yaml`

This contains the connection information for MinIO (S3-compatible storage).

```yaml
type: S3
config:
  bucket: "thanos"
  endpoint: "minio:9000"
  insecure: true
  access_key: "minio"
  secret_key: "melovethanos"
```

#### 3. `docker-compose.yaml`

To avoid permission-related troubles, we will configure this to run with `user: root`. We use the `mc` container to automatically create the bucket.

```yaml
version: '3.7'

services:
  # 1. Prometheus
  prometheus:
    image: prom/prometheus:v3.9.1
    container_name: prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - --config.file=/etc/prometheus/prometheus.yml
      - --storage.tsdb.min-block-duration=2h
      - --storage.tsdb.max-block-duration=2h
      - --web.enable-lifecycle
      - --web.enable-admin-api
    ports:
      - "9090:9090"

  # 2. Thanos Sidecar (Upload & Proxy)
  sidecar:
    image: thanosio/thanos:v0.40.1
    container_name: sidecar
    user: root
    command:
      - sidecar
      - --tsdb.path=/prometheus
      - --prometheus.url=http://prometheus:9090
      - --objstore.config-file=/etc/thanos/bucket_config.yaml
    volumes:
      - ./bucket_config.yaml:/etc/thanos/bucket_config.yaml
      - prometheus_data:/prometheus
    depends_on:
      - minio
      - prometheus

  # 3. Object Storage (MinIO)
  minio:
    image: minio/minio
    container_name: minio
    environment:
      MINIO_ROOT_USER: minio
      MINIO_ROOT_PASSWORD: melovethanos
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"
      - "9001:9001"

  # Bucket Creator (One-shot)
  mc:
    image: minio/mc
    container_name: mc
    depends_on:
      - minio
    entrypoint: >
      /bin/sh -c "
      /usr/bin/mc alias set myminio http://minio:9000 minio melovethanos;
      /usr/bin/mc mb myminio/thanos;
      exit 0;
      "

  # 4. Thanos Store Gateway (Historical Data Access)
  store:
    image: thanosio/thanos:v0.40.1
    container_name: store
    user: root
    command:
      - store
      - --data-dir=/data
      - --objstore.config-file=/etc/thanos/bucket_config.yaml
      - --grpc-address=0.0.0.0:10901
      - --http-address=0.0.0.0:10902
    volumes:
      - ./bucket_config.yaml:/etc/thanos/bucket_config.yaml
      - store_data:/data
    depends_on:
      - minio
    ports:
      - "10902:10902"

  # 5. Thanos Querier (Global View)
  querier:
    image: thanosio/thanos:v0.40.1
    container_name: querier
    command:
      - query
      - --endpoint=sidecar:10901
      - --endpoint=store:10901
    ports:
      - "9091:10902"
    depends_on:
      - sidecar
      - store

volumes:
  prometheus_data:
  store_data:
```

### Step 2: Startup and Verification

```bash
docker-compose up -d
```

After startup, access `http://localhost:9091` (Thanos Querier), and a UI similar to Prometheus will appear.
To check the status of the Store API, click **Stores** in the top menu. Both the Sidecar and the Store Gateway should be marked as "UP".

With this, the complete stack of "Prometheus (Latest) + MinIO (Past) + Thanos (Unified)" is now running in your local environment.

![handson](./assets/thanos/thanos-handson.png)

---

## Conclusion

Thanos is the "standard expansion pack" for breaking through Prometheus's limits.

1. **Sidecar**: Escapes data to S3.
2. **Store Gateway**: Makes S3 data readable.
3. **Compactor**: Compresses and organizes data.
4. **Querier**: Bundles everything and removes duplicates.

If you understand this architecture, petabyte-scale metrics infrastructure is nothing to be afraid of.
