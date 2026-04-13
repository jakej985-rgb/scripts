import subprocess
import json
import os
import sys
import re
from pathlib import Path

# Core Infrastructure Auditor for M3TAL
# Responsibility: Enforce Networking & Routing Contracts

def find_root():
    anchor = ".env"
    curr = Path(__file__).resolve()
    for parent in [curr] + list(curr.parents):
        if (parent / anchor).exists():
            return parent
    return Path.cwd()

ROOT = find_root()

# Severity Levels
CRITICAL = "CRITICAL"
WARNING = "WARNING"
INFO = "INFO"

# Status Types
HEALTHY = "HEALTHY"
STARTING = "STARTING"
DEGRADED = "DEGRADED"
FAILED = "FAILED"

class AuditScanner:
    def __init__(self, domain=None):
        self.domain = domain or os.getenv("DOMAIN", "m3tal-media-server.xyz")
        self.inspect_cache = {}
        self.results = []
        self.status = HEALTHY

    def _get_inspect(self, container_id):
        """Defensive Docker inspection with caching."""
        if container_id in self.inspect_cache:
            return self.inspect_cache[container_id]
        
        try:
            cmd = ["docker", "inspect", container_id]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=5)
            data = json.loads(result.stdout)[0]
            self.inspect_cache[container_id] = data
            return data
        except Exception as e:
            return None

    def _normalize_labels(self, labels):
        """Safe label key/value normalization."""
        if not labels: return {}
        return {k.lower(): str(v).lower() for k, v in labels.items()}

    def _add_issue(self, container, service_id, severity, message, hint=None):
        self.results.append({
            "service": service_id,
            "container": container,
            "severity": severity,
            "message": message,
            "hint": hint
        })
        if severity == CRITICAL:
            self.status = FAILED
        elif severity == WARNING and self.status == HEALTHY:
            self.status = DEGRADED

    def scan(self):
        """Runs the audit loop across all managed containers."""
        try:
            cmd = ["docker", "ps", "-a", "--format", "{{.Names}}"]
            names = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.splitlines()
        except:
            print("[!] CRITICAL: Docker daemon unreachable.")
            sys.exit(1)

        for name in names:
            data = self._get_inspect(name)
            if not data:
                continue

            labels = self._normalize_labels(data.get("Config", {}).get("Labels", {}))
            
            # Scope to M3TAL managed only
            if "m3tal.stack" not in labels and "m3tal.managed" not in labels:
                continue

            service_id = labels.get("com.docker.compose.service") or name
            state = data.get("State", {})
            is_running = state.get("Running", False)
            is_optional = labels.get("m3tal.optional") == "true"
            networks = data.get("NetworkSettings", {}).get("Networks", {})

            # 1. State Validation
            if not is_running:
                sev = WARNING if is_optional else CRITICAL
                msg = f"Service '{service_id}' is not running (State: {state.get('Status')})"
                hint = f"Run 'm3tal run {labels.get('m3tal.stack', 'all')}' to start."
                self._add_issue(name, service_id, sev, msg, hint)
                continue

            # 2. Networking Contract
            if "proxy" not in networks:
                # Ghost Network Detection (Running but detached)
                msg = f"Service '{service_id}' is running but NOT attached to 'proxy' network."
                hint = "Add 'networks: - proxy' to the service in docker-compose.yml."
                self._add_issue(name, service_id, CRITICAL, msg, hint)
            else:
                ip = networks["proxy"].get("IPAddress")
                if not ip:
                    # Lifecycle Awareness: Starting vs Detached
                    msg = f"Service '{service_id}' has joined 'proxy' but has no IPAddress yet."
                    hint = "Wait for container bootstrap or check for internal crash loops."
                    self._add_issue(name, service_id, WARNING, msg, hint)

            # 3. Routing Contract (If enabled)
            if labels.get("traefik.enable") == "true":
                # Missing Internal Subnet Hint
                if labels.get("traefik.docker.network") != "proxy":
                    msg = f"Service '{service_id}' missing 'traefik.docker.network=proxy' label."
                    hint = f"Add label: - \"traefik.docker.network=proxy\" to {service_id}."
                    self._add_issue(name, service_id, CRITICAL, msg, hint)

                # Missing Port Enforcement
                port_key = f"traefik.http.services.{service_id}.loadbalancer.server.port"
                # Support generic service naming if literal fails
                found_port = any(k.endswith(".loadbalancer.server.port") for k in labels.keys())
                if not found_port:
                    msg = f"Service '{service_id}' missing explicit loadbalancer port label."
                    hint = f"Add label: - \"traefik.http.services.{service_id}.loadbalancer.server.port=XXXX\""
                    self._add_issue(name, service_id, CRITICAL, msg, hint)

                # Domain/Host Validation
                host_labels = [v for k, v in labels.items() if ".rule" in k and "host(" in v]
                for rule in host_labels:
                    # Extract domain(s) from Host(`...`)
                    found_hosts = re.findall(r"host\(`([^`]+)`\)", rule)
                    for h in found_hosts:
                        if h != self.domain and not h.endswith(f".{self.domain}"):
                            msg = f"Router rule for '{service_id}' uses unexpected domain: {h}"
                            hint = f"Replace with: Host(`{service_id}.{self.domain}`)"
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
        print(f" M3TAL INFRASTRUCTURE AUDIT | STATUS: {self.status}")
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
        print(f" Checked: {len(self.inspect_cache)} core services")
        print(f" Status:  {self.status}")
        print("="*60 + "\n")

if __name__ == "__main__":
    scanner = AuditScanner()
    scanner.scan()
    scanner.report()
    if scanner.status == FAILED:
        sys.exit(1)
