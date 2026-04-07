# Auto-Scaling

M3TAL uses a simple boundary-based horizontal scaling engine via `scaling-agent.sh`.

It evaluates standard CPU rules defined in `config/scaling.json`:
- Scale UP: Container exceeds `cpu_threshold` and `CURRENT_REPLICAS < MAX`.
- Scale DOWN: Container drops below baseline threshold and `CURRENT_REPLICAS > MIN`.

The agent enforces a strict 5-minute cooldown to prevent flap-scaling loops.
