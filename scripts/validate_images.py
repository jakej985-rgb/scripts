#!/usr/bin/env python3
import os
import sys
import subprocess
import yaml
from pathlib import Path

# Resolve repo root
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT / "scripts"))

try:
    from validate_env import YELLOW, RED, GREEN, BLUE, BOLD, END
except ImportError:
    YELLOW, RED, GREEN, BLUE, BOLD, END = ("", "", "", "", "", "")

DOCKER_DIR = REPO_ROOT / "docker"

def get_images_from_compose(file_path):
    """Extract unique image names from a compose file."""
    images = set()
    try:
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
            if data and 'services' in data:
                for service_name, config in data['services'].items():
                    image = config.get('image')
                    if image:
                        images.add(image)
    except Exception:
        pass
    return images

def validate_images(pull=False):
    """Rex Guardrail: Verify all Docker images are reachable and valid."""
    print(f"{BLUE}{BOLD}[REX] Scanning for Docker images...{END}")
    
    all_images = set()
    for root, dirs, files in os.walk(DOCKER_DIR):
        for file in files:
            if file.endswith('.yml') or file.endswith('.yaml'):
                if "example" in file.lower(): continue
                full_path = os.path.join(root, file)
                all_images.update(get_images_from_compose(full_path))

    if not all_images:
        print(f"{YELLOW}[REX] No images found to validate.{END}")
        return True

    print(f"{BLUE}[REX] Validating {len(all_images)} unique images...{END}")
    
    failed = []
    for image in sorted(all_images):
        # 1. Quick check if image exists locally
        inspect_cmd = ["docker", "image", "inspect", image]
        result = subprocess.run(inspect_cmd, capture_output=True)
        
        if result.returncode == 0:
            print(f"  {GREEN}✓{END} {image} (Local)")
            continue
            
        # 2. If not local, or if pull requested, try to pull metadata or pull it
        if pull:
            print(f"  {YELLOW}⟳{END} {image} (Pulling...)", end="\r")
            pull_cmd = ["docker", "pull", "--quiet", image]
            p_result = subprocess.run(pull_cmd, capture_output=True, text=True)
            
            if p_result.returncode == 0:
                print(f"  {GREEN}✓{END} {image} (Pulled successfully)   ")
            else:
                err = p_result.stderr.strip()
                print(f"  {RED}✗{END} {image} (Failed)               ")
                failed.append((image, err))
        else:
            print(f"  {RED}✗{END} {image} (Not found locally)")
            failed.append((image, "Image not found locally. Use --pull to verify remote reachability."))

    if failed:
        print(f"\n{RED}{BOLD}[REX] ERROR: Image validation failed for {len(failed)} images:{END}")
        for img, err in failed:
            print(f"  {BOLD}{img}{END}:")
            if "unauthorized" in err.lower() or "denied" in err.lower():
                print(f"    {YELLOW}Action: Login to registry required.{END}")
            elif "not found" in err.lower() or "404" in err.lower():
                print(f"    {YELLOW}Action: Verify image name/tag exists on registry.{END}")
            else:
                print(f"    {YELLOW}Reason: {err}{END}")
        return False

    print(f"\n{GREEN}{BOLD}✅ All images verified.{END}")
    return True

if __name__ == "__main__":
    do_pull = "--pull" in sys.argv
    if not validate_images(pull=do_pull):
        sys.exit(1)
    sys.exit(0)
