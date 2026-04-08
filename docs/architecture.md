# Architecture

M3TAL uses a decentralized, agent-based orchestration system.

---

## The Sense-Think-Act Pipeline

The control plane is organized into a pipeline of specialized Python agents.

* **Monitor** → Collects container health data.
* **Analyzer** → Interprets anomalies and health scores.
* **Decision Engine** → Applies scaling and recovery rules.
* **Reconciler** → Executes state changes via Docker.

---

## Operational Guardrails

All actions are:

* **Rate Limited**: Enforced via stateful cooldowns.
* **Leadership Locked**: Only the master node can execute destructive actions.
* **Retry Controlled**: Failed actions trigger exponential backoff.
