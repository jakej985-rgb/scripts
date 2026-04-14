import subprocess
import json
import os
import sys
import re
import requests
from pathlib import Path
from typing import Dict, List, Any

# M3TAL Traefik Contract Enforcer (v1.0.0)
# Responsibility: Correlate Docker Labels with Traefik Runtime API

# Attempting catastrophic import of paths
try:
    p = Path(__file__).resolve()
    for parent in [p] + list(p.parents):
        if (parent / ".env").exists() and (parent / "docker").exists():
            if str(parent / "control-plane") not in sys.path:
                sys.path.append(str(parent / "control-plane"))
            break
    from agents.utils.paths import REPO_ROOT
except Exception as e:
    print(f"❌ FATAL: Critical path module missing or corrupted: {e}")
    sys.exit(1)

DOMAIN = os.getenv("DOMAIN")
TRAEFIK_API = "http://localhost:8080/api"

# Severity levels
CRITICAL = "CRITICAL"
WARNING = "WARNING"
INFO = "INFO"

# Classification Types
TYPE_A = "TYPE A — Not Detected (Labels vs API mismatch)"
TYPE_B = "TYPE B — Router Inactive (No entrypoint/binding)"
TYPE_C = "TYPE C — Backend Broken (Service/Port issue)"
TYPE_D = "TYPE D — Rule Mismatch (Routing mismatch)"

class TraefikAuditor:
    def __init__(self, domain=None, strict=False):
        self.domain = domain or DOMAIN
        self.strict = strict
        self.results = []
        self.traefik_data = {"routers": {}, "services": {}}
        self.status = "HEALTHY"

    def _fetch_traefik_api(self):
        """Queries the Traefik API for runtime state."""
        try:
            # Fetch Routers
            r_res = requests.get(f"{TRAEFIK_API}/http/routers", timeout=3)
            if r_res.status_code == 200:
                for r in r_res.json():
                    self.traefik_data["routers"][r["name"]] = r
            
            # Fetch Services
            s_res = requests.get(f"{TRAEFIK_API}/http/services", timeout=3)
            if s_res.status_code == 200:
                for s in s_res.json():
                    self.traefik_data["services"][s["name"]] = s
            return True
        except Exception as e:
            self._add_issue("traefik", "traefik", CRITICAL, 
                           f"Traefik API unreachable at {TRAEFIK_API}: {e}", 
                           "Ensure Traefik is running and port 8080 is mapped.")
            return False

    def _add_issue(self, container, service_id, severity, message, hint=None, category=None):
        self.results.append({
            "service": service_id,
            "container": container,
            "severity": severity,
            "message": message,
            "hint": hint,
            "category": category
        })
        if severity == CRITICAL:
            self.status = "FAILED"
        elif severity == WARNING and self.status == "HEALTHY" and self.strict:
            self.status = "FAILED"

    def audit(self):
        print(f"[*] [AUDIT] Starting Traefik Contract Verification for {self.domain}...")
        
        # 1. Sync Traefik API
        if not self._fetch_traefik_api():
            return self.results

        # 2. Scan Containers
        try:
            cmd = ["docker", "ps", "-a", "--format", "{{.Names}}"]
            all_names = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.splitlines()
        except Exception as e:
            self._add_issue("docker", "daemon", CRITICAL, f"Docker daemon unreachable: {e}")
            return self.results

        for name in all_names:
            try:
                inspect_cmd = ["docker", "inspect", name]
                inspect_res = subprocess.run(inspect_cmd, capture_output=True, text=True, check=True)
                data = json.loads(inspect_res.stdout)[0]
                labels = {k.lower(): v for k, v in data.get("Config", {}).get("Labels", {}).items()}
            except: continue

            # Filter for M3TAL managed routed services
            if "m3tal.stack" not in labels: continue
            if labels.get("traefik.enable") != "true": continue

            service_id = labels.get("com.docker.compose.service") or name
            stack = labels.get("m3tal.stack")
            networks = data.get("NetworkSettings", {}).get("Networks", {})
            
            # PHASE 1: Label Contract
            required_keys = [
                "traefik.enable",
                "traefik.docker.network",
                f"traefik.http.routers.{service_id}.rule",
                f"traefik.http.routers.{service_id}.entrypoints",
                f"traefik.http.services.{service_id}.loadbalancer.server.port"
            ]
            missing_labels = [l for l in required_keys if l not in labels]
            if missing_labels:
                self._add_issue(name, service_id, CRITICAL, 
                               f"Missing Traefik labels: {', '.join(missing_labels)}",
                               f"Standardize labels for stack '{stack}'.")
            
            if labels.get("traefik.docker.network") != "proxy":
                self._add_issue(name, service_id, CRITICAL, 
                               f"Invalid label: traefik.docker.network={labels.get('traefik.docker.network')}",
                               "Must be set to 'proxy'.", TYPE_A)
            
            # PHASE 1: Network Contract
            if "proxy" not in networks:
                self._add_issue(name, service_id, CRITICAL, 
                               "Service NOT attached to 'proxy' network.",
                               f"Update {stack}/docker-compose.yml to join 'proxy'.", TYPE_A)
            
            # PHASE 1: Domain Check
            rule = labels.get(f"traefik.http.routers.{service_id}.rule", "")
            if rule and f"host(`{service_id}.{self.domain}`)" not in rule.lower():
                if "host(" in rule.lower():
                     self._add_issue(name, service_id, WARNING, 
                                    f"Host rule mismatch. Found: {rule}",
                                    f"Expected Host(`{service_id}.{self.domain}`)", TYPE_D)

            # PHASE 2: Runtime Correlation
            # Traefik router name is usually service@docker or just service
            router_name = f"{service_id}@{labels.get('com.docker.compose.project', stack)}"
            # Fallback to simple matching if compose names vary
            found_router = None
            for rname, rdata in self.traefik_data["routers"].items():
                if service_id in rname:
                    found_router = rdata
                    break
            
            if not found_router:
                self._add_issue(name, service_id, CRITICAL, 
                               "Container is UP but NOT visible in Traefik API.",
                               "Verify traefik.enable=true and traefik.docker.network=proxy.", TYPE_A)
            else:
                # Check backend status
                status = found_router.get("status")
                if status != "enabled":
                    self._add_issue(name, service_id, CRITICAL, 
                                   f"Router exists but is INACTIVE (Status: {status})",
                                   "Check for entrypoint or service linking errors.", TYPE_B)
                
                # Check service health
                svc_name = found_router.get("service")
                if svc_name not in self.traefik_data["services"]:
                    self._add_issue(name, service_id, CRITICAL, 
                                   f"Router linked to missing service: {svc_name}",
                                   "Verify service name in labels.", TYPE_C)

        return self.results

    def report(self):
        print("\n" + "="*70)
        print(f" M3TAL TRAEFIK CONTRACT AUDIT | STATUS: {self.status}")
        print("="*70)

        if not self.results:
            print(f"  {GREEN}[OK] All managed services are correctly routed via Traefik.{END}")
        else:
            for issue in self.results:
                icon = "[X]" if issue["severity"] == CRITICAL else "[!]"
                print(f"\n{icon} [{issue['severity']}] {issue['service'].upper()}")
                if issue["category"]: print(f"   Category: {issue['category']}")
                print(f"   Message:  {issue['message']}")
                if issue["hint"]: print(f"   Hint:     {issue['hint']}")

        print("\n" + "="*70)
        print(f" Status: {self.status}")
        print("="*70 + "\n")

# Console formatting
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
END = "\033[0m"

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="M3TAL Traefik Auditor")
    parser.add_argument("--strict", action="store_true", help="Fail on warnings")
    args = parser.parse_args()

    auditor = TraefikAuditor(strict=args.strict)
    auditor.audit()
    auditor.report()
    if auditor.status == "FAILED":
        sys.exit(1)
