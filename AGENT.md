# 🧠 ANTIGRAVITY AGENT (Repo Self-Healing Spec)

> Autonomous path-fixing + repo maintenance agent for M3tal-Media-Server

---

## 🎯 Purpose

This agent enforces **path safety and execution reliability** across the repo.

It ensures:
- All scripts run from ANY location
- No hardcoded or fragile paths exist
- Missing runtime files are auto-created
- Repo remains stable without restructuring

---

## ⚠️ Core Rule (MANDATORY)

ALL paths MUST use:

```bash
$REPO_ROOT
```

Never use:
- ./relative paths
- absolute system paths (/home, /mnt, etc)
- assumptions about working directory

---

## 🧠 Repo Root Detection

Every script MUST detect repo root dynamically:

```bash
if git rev-parse --show-toplevel > /dev/null 2>&1; then
  REPO_ROOT="$(git rev-parse --show-toplevel)"
else
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi
```

---

## 🔧 AUTO-ROOT BLOCK (Required in all scripts)

```bash
# >>> AUTO-ROOT (antigravity)
if git rev-parse --show-toplevel > /dev/null 2>&1; then
  REPO_ROOT="$(git rev-parse --show-toplevel)"
else
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi
# <<< AUTO-ROOT
```

---

## 🔍 What the Agent Fixes

### 1. Path Normalization

Convert:

```bash
control-plane/state/leader.txt
```

→

```bash
"$REPO_ROOT/control-plane/state/leader.txt"
```

---

Convert:

```bash
./control-plane/agents/monitor.sh
```

→

```bash
"$REPO_ROOT/control-plane/agents/monitor.sh"
```

---

### 2. Remove Hardcoded Paths

Replace:

```bash
/home/... 
/mnt/...
```

→

```bash
"$REPO_ROOT/..."
```

---

### 3. Self-Heal Required Files

Ensure exists:

```bash
$REPO_ROOT/control-plane/state/leader.txt
```

Default content:

```
none
```

---

### 4. Ensure Directories

Create if missing:

- control-plane/state/
- control-plane/logs/

---

## 🔁 Execution Order

Antigravity MUST run first:

```bash
antigravity-agent.sh
monitor.sh
metrics.sh
anomaly-agent.sh
decision-engine.sh
reconcile.sh
registry.sh
```

---

## 🧪 Validation

Scripts must work when executed from:

- repo root
- subdirectories
- cron/docker

Test:

```bash
bash control-plane/agents/monitor.sh
```

---

## 🧾 Commit Behavior

If fixes are applied:

```bash
git add .
git commit -m "fix(antigravity): normalize paths + self-heal"
```

---

## 🚫 Constraints

DO NOT:
- reorganize repo
- rename files
- change architecture
- add dependencies

ONLY:
- fix paths
- inject root logic
- restore missing files

---

## 🧠 Behavior Model

This agent behaves like:

- Codex → modifies code safely
- Jules → understands repo structure
- Antigravity → prevents drift

---

## ✅ Done When

- All scripts use $REPO_ROOT
- No path-related failures exist
- Fresh clone runs without fixes

---
