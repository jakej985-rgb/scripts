import subprocess
import json
import os
import sys
import re
from pathlib import Path

# Advanced Infrastructure Auditor for M3TAL (v6.5.1 Tightened)
# Responsibility: Enforce Networking & Routing Contracts with Hard Invariants

# Attempting catastrophic import of paths module
try:
    from pathlib import Path
    import sys
    
    # Batch 16 Hardening: Force UTF-8 for Windows console resilience
    if sys.stdout.encoding.lower() != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except (AttributeError, Exception):
            pass

    # Path bootstrap (V6.5.2)
    p = Path(__file__).resolve()
    for parent in [p] + list(p.parents):
        if (parent / ".env").exists() and (parent / "docker").exists():
            if str(parent / "control-plane") not in sys.path:
                sys.path.append(str(parent / "control-plane"))
            break
            
    from agents.utils.paths import REPO_ROOT
except Exception as e:
    print(f"[X] FATAL: Critical path module missing or corrupted: {e}")
    sys.exit(1)

# Configuration Enforcement: NO FALLBACKS
DOMAIN = os.getenv("DOMAIN")
if not DOMAIN:
    print("[X] FATAL: DOMAIN environment variable is NOT set. Aborting audit.")
    sys.exit(1)

# Severity Levels
CRITICAL = "CRITICAL"
WARNING = "WARNING"
INFO = "INFO"

# Status Types
HEALTHY = "HEALTHY"
STARTING = "STARTING"
DEGRADED = "DEGRADED"
FAILED = "FAILED"

def is_enabled(val):
    """Normalize Docker label booleans."""
    v = str(val or "").lower().strip()
    return v in ("true", "1", "yes", "y")

def safe_host_match(host, domain):
    """Secure domain matching to prevent malicious overlap."""
    h = str(host or "").lower().strip()
    d = str(domain).lower().strip()
    return h == d or h.endswith("." + d)

class AuditScanner:
    def __init__(self, domain=None, strict=False):
        self.domain = domain or DOMAIN
        self.strict = strict
        self.inspect_cache = {}
        self.results = []
        self.status = HEALTHY

    def _get_inspect(self, container_id):
        """Defensive Docker inspection with caching and hard failure."""
        if container_id in self.inspect_cache:
            return self.inspect_cache[container_id]
        
        try:
            cmd = ["docker", "inspect", container_id]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=5)
            data = json.loads(result.stdout)[0]
            self.inspect_cache[container_id] = data
            return data
        except Exception as e:
            # V6.5.2 Hardening: Failures to inspect are recorded but not skipping
            self._add_issue(container_id, container_id, CRITICAL, 
                           f"Failed to inspect container: {e}", 
                           "Check Docker permissions or daemon health")
            return None

    def _normalize_labels(self, labels):
        """Safe label key/value normalization."""
        if not labels: return {}
        return {k.lower(): str(v) for k, v in labels.items()}

    def _add_issue(self, container, service_id, severity, message, hint=None):
        self.results.append({
            "service": service_id,
            "container": container,
            "severity": severity,
            "message": message,
            "hint": hint
        })
        
        # Status Resolution
        if severity == CRITICAL:
            self.status = FAILED
        elif severity == WARNING:
            if self.strict:
                self.status = FAILED
            elif self.status == HEALTHY:
                self.status = DEGRADED

    def scan(self):
        """Runs the audit loop across all managed containers + Tier 1 Tier."""
        try:
            cmd = ["docker", "ps", "-a", "--format", "{{.Names}}"]
            all_names = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.splitlines()
        except Exception as e:
            print(f"[X] FATAL: Docker daemon unreachable: {e}")
            sys.exit(1)

        # Tier 1 Invariants: MUST EXIST & BE HEALTHY
        TIER_1 = ["traefik", "cloudflared"]
        for t1 in TIER_1:
            if t1 not in all_names:
                self._add_issue(t1, t1, CRITICAL, f"Tier 1 component '{t1}' is MISSING.", 
                                f"Run 'm3tal run routing' to restore stack.")
                continue
            
            data = self._get_inspect(t1)
            if not data:
                # Issue already logged in _get_inspect
                continue
            
            state = data.get("State", {})
            if not state.get("Running"):
                self._add_issue(t1, t1, CRITICAL, f"Tier 1 component '{t1}' is NOT running.", 
                               "Ensure the container is started and not crashing.")
            
            networks = data.get("NetworkSettings", {}).get("Networks", {})
            if "proxy" not in networks:
                self._add_issue(t1, t1, CRITICAL, f"Tier 1 component '{t1}' is NOT on the proxy network.", 
                               "Correct the docker-compose.yml and rejoin the proxy subnet.")

        # Managed Services Scan
        for name in all_names:
            if name in TIER_1: continue # Handled by Tier 1 logic above

            data = self._get_inspect(name)
            if not data:
                # We record existence but can't check labels without inspect.
                # However, _get_inspect already added a CRITICAL issue.
                continue

            labels = self._normalize_labels(data.get("Config", {}).get("Labels", {}))
            
            # Scope to M3TAL managed only
            if "m3tal.stack" not in labels and "m3tal.managed" not in labels:
                continue

            service_id = labels.get("com.docker.compose.service") or name
            state = data.get("State", {})
            is_running = state.get("Running", False)
            is_optional = is_enabled(labels.get("m3tal.optional"))
            networks = data.get("NetworkSettings", {}).get("Networks", {})

            # 1. State Validation
            if not is_running:
                sev = WARNING if is_optional else CRITICAL
                msg = f"Service '{service_id}' is not running (State: {state.get('Status')})"
                hint = f"Run 'm3tal run {labels.get('m3tal.stack', 'all')}' to start."
                self._add_issue(name, service_id, sev, msg, hint)
                continue

            # 2. Networking Contract
            forbidden = [n for n in networks.keys() if n.endswith("_default") or n == "default"]
            if forbidden:
                msg = f"Service '{service_id}' is leaking default networks: {forbidden}"
                hint = "Add 'networks: default: name: none' to your docker-compose.yml."
                self._add_issue(name, service_id, WARNING, msg, hint)

            if "proxy" not in networks:
                msg = f"Service '{service_id}' is NOT attached to the 'proxy' network."
                hint = f"Service MUST join 'proxy' network. Found: {list(networks.keys())}"
                self._add_issue(name, service_id, CRITICAL, msg, hint)
            else:
                ip = networks["proxy"].get("IPAddress")
                if not ip:
                    # Lifecycle Awareness: Starting vs Detached
                    msg = f"Service '{service_id}' has joined 'proxy' but has no IPAddress yet."
                    hint = "Wait for container bootstrap or check for internal crash loops."
                    self._add_issue(name, service_id, WARNING, msg, hint)

            # 3. Routing Contract (If enabled)
            if is_enabled(labels.get("traefik.enable")):
                # Missing Internal Subnet Hint
                if labels.get("traefik.docker.network") != "proxy":
                    msg = f"Service '{service_id}' missing 'traefik.docker.network=proxy' label."
                    hint = f"Add label: - \"traefik.docker.network=proxy\" to {service_id}."
                    self._add_issue(name, service_id, CRITICAL, msg, hint)

                # Missing Port Enforcement
                found_port = any(k.endswith(".loadbalancer.server.port") for k in labels.keys())
                if not found_port:
                    msg = f"Service '{service_id}' missing explicit loadbalancer port label."
                    hint = f"Add label: - \"traefik.http.services.{service_id}.loadbalancer.server.port=XXXX\""
                    self._add_issue(name, service_id, CRITICAL, msg, hint)

                # Domain/Host Validation
                host_labels = [v for k, v in labels.items() if ".rule" in k and "host(" in v.lower()]
                for rule in host_labels:
                    found_hosts = re.findall(r"host\(`([^`]+)`\)", rule.lower())
                    for h in found_hosts:
                        if not safe_host_match(h, self.domain):
                            msg = f"Router rule for '{service_id}' uses unexpected domain: {h}"
                            hint = f"Domain MUST match '{self.domain}' or '*.{self.domain}'"
                            self._add_issue(name, service_id, WARNING, msg, hint)

        return self.results

    def report(self, fmt="text"):
        if fmt == "json":
            print(json.dumps({
                "status": self.status,
                "issues": self.results
            }, indent=2))
            return

        print("\n" + "="*60)
        print(f" M3TAL INFRASTRUCTURE AUDIT | STATUS: {self.status} (Strict: {self.strict})")
        print("="*60)

        if not self.results:
            print("  [OK] All managed services adhere to networking contracts.")
        else:
            for issue in self.results:
                icon = "[X]" if issue["severity"] == CRITICAL else "[!]"
                print(f"\n[{issue['severity']}] {icon} {issue['message']}")
                if issue["hint"]:
                    print(f"      Hint: {issue['hint']}")

        print("\n" + "="*60)
        print(f" Checked: {len(self.inspect_cache)} services")
        print(f" Status:  {self.status}")
        print("="*60 + "\n")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="M3TAL Infrastructure Auditor")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--strict", action="store_true", help="Fail on ANY warnings (CI/CD mode)")
    args = parser.parse_args()

    scanner = AuditScanner(strict=args.strict)
    scanner.scan()
    scanner.report(fmt="json" if args.json else "text")
    if scanner.status == FAILED:
        sys.exit(1)
