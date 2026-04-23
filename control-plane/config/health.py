import os
import sys
import time
import random
import subprocess
import requests
import concurrent.futures
from pathlib import Path

# Advanced Health Validator for M3TAL (v6.5.1 Tightened)
# Responsibility: Verify End-to-End Routing (Truth Tests)

# Attempting catastrophic import of paths module
try:
    # Path bootstrap (V6.5.2)
    p = Path(__file__).resolve()
    for parent in [p] + list(p.parents):
        if (parent / ".env").exists() and (parent / "docker").exists():
            if str(parent / "control-plane") not in sys.path:
                sys.path.append(str(parent / "control-plane"))
            break
            
except Exception as e:
    print(f"❌ FATAL: Critical path module missing or corrupted: {e}")
    sys.exit(1)

class HealthValidator:
    def __init__(self, services=None, domain=None):
        self.domain = domain or os.getenv("DOMAIN")
        if not self.domain:
            raise RuntimeError("DOMAIN env var missing - cannot run Truth Test")
            
        self.services = services or [] 
        self.results = {}
        self.base_url = "http://localhost" 

    def _probe_service(self, service):
        """Standard probe with jittered retries and strict success criteria."""
        sid = service["id"]
        host = service.get("host") or f"{sid}.{self.domain}"
        
        # Dashboard mapping override
        if sid == "m3tal-dashboard": 
            host = f"m3tal.{self.domain}"
        
        headers = {"Host": host}
        
        # V6.5.2 Hardening: 3 attempts with jitter
        for attempt in range(3):
            try:
                # 2s timeout as per V6.3 spec
                response = requests.get(self.base_url, headers=headers, timeout=2)
                
                # V6.5 Hardening: Success = 200-399. 404 is a failure.
                if 200 <= response.status_code < 400:
                    return sid, "HEALTHY", f"Status: {response.status_code}"
                
                return sid, "FAILED", f"Status: {response.status_code} (Non-Success Routing)"
            except Exception as e:
                if attempt < 2:
                    time.sleep(0.5 + random.random() * 0.5) # Increased sleep
                    continue
                # V6.5 Hardening: Timeouts and connection errors are hard failures
                return sid, "FAILED", f"Reachability Error: {type(e).__name__}"

    def _internal_bridge_test(self):
        """Validates the Cloudflared -> Traefik path via internal EXEC."""
        try:
            # V6.5 Hardening: 3s subprocess timeout to prevent CLI lockup
            # V6.5 Hardening: Use wget as per container env spec (cloudflared is Alpine-based)
            cmd = ["docker", "exec", "cloudflared", "wget", "-qO-", "--spider", "http://traefik:80"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            code = "200" if result.returncode == 0 else "000"
            
            # 000 typically means curl failed to connect at all
            if code == "000":
                return "cloudflared-bridge", "FAILED", "Tunnel cannot reach Traefik (Connection Refused)"
            
            if code.startswith("2") or code.startswith("3"): # Only 2xx/3xx on the bridge
                return "cloudflared-bridge", "HEALTHY", f"Internal resolution OK ({code})"
            
            return "cloudflared-bridge", "FAILED", f"HTTP {code} (Internal Routing Error)"
        except Exception as e:
            return "cloudflared-bridge", "FAILED", f"Bridge Timeout/Failure: {str(e)}"

    def _internal_path_test(self, service):
        """Phase 5: Validates internal Traefik -> Backend reachability."""
        sid = service["id"]
        port = service.get("port")
        if not port:
            # Fallback for display, but we need port for wget
            return sid + "-internal", "INFO", "Missing port for internal test"
        
        try:
            # Audit Fix H4: Traefik v3 image has no wget. Use nc -z or sh socket check.
            cmd = ["docker", "exec", "traefik", "sh", "-c", f"nc -z {sid} {port}"]
            result = subprocess.run(cmd, capture_output=True, timeout=3)
            
            if result.returncode == 0:
                return sid + "-internal", "HEALTHY", f"Internal Link OK (Port {port})"
            return sid + "-internal", "FAILED", f"Traefik cannot reach {sid} on port {port}"
        except Exception as e:
            return sid + "-internal", "FAILED", f"Internal Test Error: {str(e)}"

    def run_full_test(self):
        """Executes parallel probes with correlated results."""
        # V6.5.2 Hardening: Initial Grace Period for Traefik bootstrap
        print(f"⏳ [TRUTH TEST] Warming up for {self.domain}...")
        time.sleep(1.5)
        
        print(f"\n--- [TRUTH TEST] Routing Validation for {self.domain} ---")
        
        all_checks = []
        
        # 1. Internal Path (The Backbone)
        all_checks.append(self._internal_bridge_test())

        # 2. Parallel Service Probes
        if self.services:
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                # Local Probes
                future_to_service = {executor.submit(self._probe_service, s): s for s in self.services}
                # Internal Path Probes (Phase 5)
                future_to_internal = {executor.submit(self._internal_path_test, s): s for s in self.services}
                
                for future in concurrent.futures.as_completed(list(future_to_service.keys()) + list(future_to_internal.keys())):
                    all_checks.append(future.result())

        # 3. Correlation & Reporting
        failed = False
        for name, status, detail in all_checks:
            icon = "[OK]" if status == "HEALTHY" else "[FAIL]"
            print(f"{icon} {name:25} -> {status:8} ({detail})")
            if status == "FAILED": failed = True
            self.results[name] = {"status": status, "detail": detail}
        
        print("-" * 65)
        return not failed

def run_standalone():
    try:
        from config.audit import AuditScanner, is_enabled
        scanner = AuditScanner()
        scanner.scan()
        
        # Reuse IDs and labels from Audit cache for 100% correlation
        routed = []
        for name, data in scanner.inspect_cache.items():
            labels = scanner._normalize_labels(data.get("Config", {}).get("Labels", {}))
            if is_enabled(labels.get("traefik.enable")):
                sid = labels.get("com.docker.compose.service") or name
                host = None
                port = None
                for k, v in labels.items():
                    if ".rule" in k and "host(" in v.lower():
                        import re
                        m = re.search(r"host\(`([^`]+)`\)", v.lower())
                        if m: host = m.group(1)
                    if ".loadbalancer.server.port" in k:
                        port = v
                
                routed.append({"id": sid, "host": host, "port": port})

        validator = HealthValidator(services=routed)
        success = validator.run_full_test()
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"❌ FATAL: Health engine failure: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_standalone()
