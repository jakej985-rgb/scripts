# Contributing

M3TAL is an open-source autonomous control plane. We welcome contributions to our agents and dashboard.

---

## Guidelines

* Keep agents modular and independent.
* Avoid destructive automation that doesn't include a cooldown.
* Follow the existing "Sense-Think-Act" pipeline structure.

---

## Workflow

1. Fork the repository.
2. Create a feature branch.
3. Submit a Pull Request with technical documentation.

---

## Safety Rules

* No breaking structural changes without discussion.
* All new agents must be leadership-aware via `utils/guards.py`.
* All state changes must be atomic via `utils/state.py`.
