import os
import sys
import time
import random
import subprocess
import requests
import concurrent.futures
from pathlib import Path

# Advanced Health Validator for M3TAL
# Responsibility: Verify End-to-End Routing (Truth Tests)

def find_root():
    anchor = ".env"
    curr = Path(__file__).resolve()
    for parent in [curr] + list(curr.parents):
        if (parent / anchor).exists():
            return parent
    return Path.cwd()

ROOT = find_root()

class HealthValidator:
    def __init__(self, services=None, domain=None):
        self.domain = domain or os.getenv("DOMAIN", "m3tal-media-server.xyz")
        self.services = services or [] # List of service dicts with 'id' and 'domain'
        self.results = {}
        self.base_url = "http://localhost" # Testing Traefik internally

    def _probe_service(self, service):
        """Standard probe with jittered retries and timeout."""
        sid = service["id"]
        host = service.get("host") or f"{sid}.{self.domain}"
        
        # Dashboard is usually at 'm3tal.domain'
        if sid == "m3tal-dashboard": 
            host = f"m3tal.{self.domain}"
        
        headers = {"Host": host}
        
        for attempt in range(2):
            try:
                # 2s timeout as per V6.3 spec
                response = requests.get(self.base_url, headers=headers, timeout=2)
                if response.status_code < 500:
                    return sid, "HEALTHY", f"Status: {response.status_code}"
                return sid, "FAILED", f"Status: {response.status_code}"
            except Exception as e:
                if attempt < 1:
                    # Defensive Jitter: Randomized sleep (0.2s - 0.5s)
                    time.sleep(0.2 + random.random() * 0.3)
                    continue
                return sid, "FAILED", str(e)

    def _internal_bridge_test(self):
        """Validates the Cloudflared -> Traefik path."""
        try:
            # Wrapped with 3s timeout to prevent CLI hang
            cmd = ["docker", "exec", "cloudflared", "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "http://traefik:80"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            code = result.stdout.strip()
            if code.startswith("2") or code.startswith("3") or code.startswith("4"): # Any valid HTTP response
                return "cloudflared-bridge", "HEALTHY", f"Internal resolution OK ({code})"
            return "cloudflared-bridge", "FAILED", f"HTTP {code}"
        except Exception as e:
            return "cloudflared-bridge", "FAILED", f"Bridge Timeout/Failure: {str(e)}"

    def run_full_test(self):
        """Executes parallel probes across all services."""
        print(f"\n--- [TRUTH TEST] Routing Validation for {self.domain} ---")
        
        all_checks = []
        
        # 1. Internal Path
        all_checks.append(self._internal_bridge_test())

        # 2. Parallel Service Probes
        if self.services:
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                future_to_service = {executor.submit(self._probe_service, s): s for s in self.services}
                for future in concurrent.futures.as_completed(future_to_service):
                    all_checks.append(future.result())

        # 3. Correlation & Reporting
        failed = False
        for name, status, detail in all_checks:
            icon = "[OK]" if status == "HEALTHY" else "[FAIL]"
            print(f"{icon} {name:20} -> {status:8} ({detail})")
            if status == "FAILED": failed = True
            self.results[name] = {"status": status, "detail": detail}
        
        print("-" * 50)
        return not failed

def run_standalone():
    # Attempt to auto-discover services from Audit if none provided
    # Avoid circular import at top level
    try:
        from config.audit import AuditScanner
        scanner = AuditScanner()
        issues = scanner.scan()
        
        # Extract services with Traefik enabled
        # This uses the normalization from V6.4
        system_services = []
        for issue in scanner.results:
            # If audit found it, we should test it
            # But let's only test running containers
            pass # The loop below is better

        # Real discovery from inspect cache
        routed = []
        for name, data in scanner.inspect_cache.items():
            labels = scanner._normalize_labels(data.get("Config", {}).get("Labels", {}))
            if labels.get("traefik.enable") == "true":
                sid = labels.get("com.docker.compose.service") or name
                # Extract Host rule if possible
                host = None
                for k, v in labels.items():
                    if ".rule" in k and "host(" in v.lower():
                        import re
                        m = re.search(r"host\(`([^`]+)`\)", v.lower())
                        if m: host = m.group(1)
                
                routed.append({"id": sid, "host": host})

        validator = HealthValidator(services=routed)
        success = validator.run_full_test()
        sys.exit(0 if success else 1)
        
    except ImportError:
        # Fallback for minimal testing
        validator = HealthValidator(services=[{"id": "m3tal-dashboard"}])
        validator.run_full_test()

if __name__ == "__main__":
    run_standalone()
