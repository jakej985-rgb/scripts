# Architecture

M3TAL uses an agent-based system:

- Monitor → collects data
- Analyzer → interprets
- Decision Engine → applies rules
- Action Agent → executes

All actions are:
- rate limited
- locked
- retry-controlled
