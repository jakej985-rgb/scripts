# Implementation Plan — Universal Proxy Network Enforcement (V1)

Fix Traefik routing failures by eliminating Docker network fragmentation and enforcing a single shared ingress network (`proxy`) across all routed services.

---

## 🎯 Objective

Ensure **ALL externally routed services** are reachable by Traefik via a **single shared Docker network (`proxy`)**, eliminating:

- `unable to find IP address`
- `server is ignored`
- Traefik 404 errors

---

## 🧠 Root Cause

Docker Compose creates **default networks per stack**:

- `media_default`
- `control-plane_default`
- `app_default`

Even when `proxy` is added, services remain attached to these defaults, causing:

- Traefik selecting wrong network OR
- No usable IP on `proxy`

---

## 🟢 Phase 1 — Define Global Proxy Network

### Create (or verify) external proxy network:

```bash
docker network create proxy
```

---

## 🔵 Phase 2 — Enforce Proxy Network in ALL Compose Files

### 🔴 REQUIRED: Add to EVERY compose file

```yaml
networks:
  proxy:
    external: true
```

---

### 🔴 For EVERY routed service (Radarr, Sonarr, etc.)

```yaml
services:
  radarr:
    networks:
      - proxy
```

---

### 🔴 Add REQUIRED Traefik label

```yaml
labels:
  - traefik.enable=true
  - traefik.docker.network=proxy
  - traefik.http.services.radarr.loadbalancer.server.port=7878
```

---

## 🟡 Phase 3 — Remove Default Network Leakage

### ❌ Problem:

Docker auto-attaches `default` network

---

### ✅ Solution (explicit override)

Add at bottom of compose:

```yaml
networks:
  default:
    name: none
```

OR ensure ONLY `proxy` is referenced.

---

## 🔴 Phase 4 — Internal Services Isolation

For DB/internal-only services:

```yaml
networks:
  app_internal:
    driver: bridge
```

```yaml
services:
  db:
    networks:
      - app_internal
```

---

### 🔥 Rule:

| Service Type     | Networks             |
| ---------------- | -------------------- |
| Public (Traefik) | proxy                |
| Internal only    | app_internal         |
| Hybrid (API)     | proxy + app_internal |

---

## 🟢 Phase 5 — Rebuild Infrastructure

```bash
docker compose down
docker compose up -d
```

---

## 🧪 Phase 6 — Verification

---

### ✅ Network Validation

```bash
docker inspect radarr | grep -A5 Networks
```

**Expected:**

```text
"proxy": {
  "IPAddress": "..."
}
```

---

### ❌ MUST NOT see:

* `media_default`
* `control-plane_default`

---

### ✅ Traefik Log Cleanliness

```bash
docker logs traefik
```

**No more:**

```text
unable to find the IP address
server is ignored
```

---

### ✅ Routing Truth Test

```bash
curl -H "Host: radarr.${DOMAIN}" http://localhost
```

**Expected:**

* HTML response OR redirect
* NOT `404 page not found`

---

## 🧱 Phase 7 — Optional (Recommended Hardening)

---

### Add Audit Rule (future improvement)

In `audit.py`:

* FAIL if service:

  * is NOT on proxy
  * OR has NO IP on proxy

---

### Add Check:

```python
if "proxy" not in container_networks:
    CRITICAL
```

---

## 💥 Final Architecture

```text
[ Cloudflare ]
        ↓
[ cloudflared ]
        ↓
[ Traefik ]  ← proxy network
        ↓
[ ALL SERVICES ] ← proxy network
```

---

## 🧠 One-Line Rule

> If Traefik cannot see the container on `proxy`, it does not exist.

---

## ✅ Definition of Done

* All routed containers attached to `proxy`
* No Traefik IP errors
* `curl Host` test passes
* Domain resolves externally
