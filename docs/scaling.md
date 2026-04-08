# Auto-Scaling

M3TAL uses a boundary-based horizontal scaling engine managed by the `scaling.py` agent.

---

## Scaling Logic

It evaluates standard CPU rules defined in `control-plane/state/scaling.json`.

* **Scale UP**: If a container exceeds the `cpu_up` threshold, the system increases the replica count.
* **Scale DOWN**: If a container drops below the `cpu_down` threshold, the system reduces the replicas to the baseline.

---

## Stability Guardrails

The scaling agent enforces a strict **5-minute persistent cooldown** per service to prevent "flapping" or rapid oscillation during workload spikes. Scaling state is persisted across agent restarts to ensure continuity.
