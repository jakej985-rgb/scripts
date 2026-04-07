# Agents

M3TAL's pipeline relies on independent, stateless bash scripts acting as specialized agents:

- **monitor.sh**: Health and presence checks
- **metrics-agent.sh**: Time-series stat aggregation
- **analyzer.sh**: System intelligence and failure prediction
- **anomaly-agent.sh**: CPU/MEM metric thresholds
- **decision-engine.sh**: Orchestrates when actions should fire
- **action-agent.sh**: Executes the Docker level fixes
- **reconcile.sh**: Enforces cluster state declarations
- **scaling-agent.sh**: Autoscales services
- **telegram-agent.sh**: Remote notification and approvals
