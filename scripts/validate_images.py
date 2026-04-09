#!/usr/bin/env python3
import os
import sys
import subprocess
import yaml
import re
from pathlib import Path

# Resolve repo root
BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
DOCKER_DIR = REPO_ROOT / "docker"

sys.path.append(str(REPO_ROOT / "scripts"))
try:
    from validate_env import YELLOW, RED, GREEN, BLUE, BOLD, END
except ImportError:
    YELLOW, RED, GREEN, BLUE, BOLD, END = ("", "", "", "", "", "")

# Rex Auto-Fixer: Known repository remaps
# Maps short-hand image names to full registry paths
KNOWN_REMAPS = {
    "maintainerr": "ghcr.io/maintainerr/maintainerr",
    "flaresolverr": "ghcr.io/flaresolverr/flaresolverr",
    "gluetun": "qmcgaw/gluetun",
    "tdarr": "ghcr.io/haveagitgat/tdarr"
}

FALLBACK_TAGS = ["latest", "stable", ""] # empty means no tag

def get_images_from_compose(file_path):
    """Extract unique image names and their associated file path."""
    results = [] # list of (image_name, file_path)
    try:
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
            if data and 'services' in data:
                for service_name, config in data['services'].items():
                    image = config.get('image')
                    if image:
                        results.append((image, file_path))
    except Exception:
        pass
    return results

def patch_compose_file(file_path, old_image, new_image):
    """Overwrite the old image with new image in the source file."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Regex to find 'image: old_image' and replace it
        # We use a strict match to avoid partial replacements
        pattern = re.compile(rf'image:\s*["\']?{re.escape(old_image)}["\']?')
        new_content = pattern.sub(f'image: {new_image}', content)
        
        if content != new_content:
            with open(file_path, 'w') as f:
                f.write(new_content)
            return True
    except Exception as e:
        print(f"  {RED}Failed to patch {file_path}: {e}{END}")
    return False

def pull_image(image):
    """Wrapped docker pull with quiet output."""
    cmd = ["docker", "pull", "--quiet", image]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0, result.stderr.strip()

def attempt_heal(image):
    """Rex Auto-Fixer Logic: Try to find a valid alternative for a failed image."""
    base_name = image.split(':')[0] if ':' in image else image
    tag = image.split(':')[1] if ':' in image else None
    
    candidates = []
    
    # 1. Remap the base name if known
    if base_name in KNOWN_REMAPS:
        new_base = KNOWN_REMAPS[base_name]
        if tag: candidates.append(f"{new_base}:{tag}")
        for t in FALLBACK_TAGS:
            candidates.append(f"{new_base}:{t}" if t else new_base)
            
    # 2. Try original base name with fallback tags
    for t in FALLBACK_TAGS:
        if t != tag: # Skip if it was the original tag (which already failed)
            candidates.append(f"{base_name}:{t}" if t else base_name)

    # De-duplicate while preserving order
    seen = set()
    final_candidates = [x for x in candidates if not (x in seen or seen.add(x))]

    for cand in final_candidates:
        print(f"  [HEAL] Trying fallback: {cand}...", end="\r")
        success, _ = pull_image(cand)
        if success:
            print(f"  {GREEN}V [HEALED] Found alternative: {cand}{END}               ")
            return cand
            
    return None

def validate_images(pull=False, fix=False):
    """Rex Guardrail: Verify all Docker images are reachable and valid."""
    print(f"{BLUE}{BOLD}[REX] Scanning for Docker images...{END}")
    
    image_entries = [] # list of (image, path)
    for root, dirs, files in os.walk(DOCKER_DIR):
        for file in files:
            if file.endswith('.yml') or file.endswith('.yaml'):
                if "example" in file.lower(): continue
                full_path = os.path.join(root, file)
                image_entries.extend(get_images_from_compose(full_path))

    if not image_entries:
        print(f"{YELLOW}[REX] No images found to validate.{END}")
        return True

    unique_images = sorted(list(set([img for img, _ in image_entries])))
    print(f"{BLUE}[REX] Validating {len(unique_images)} unique images...{END}")
    
    failed_map = {} # image -> error
    healed_map = {} # old_image -> new_image
    
    for image in unique_images:
        # 1. Quick check if image exists locally
        inspect_cmd = ["docker", "image", "inspect", image]
        result = subprocess.run(inspect_cmd, capture_output=True)
        
        if result.returncode == 0:
            print(f"  {GREEN}V{END} {image} (Local)")
            continue
            
        # 2. If not local, or if pull requested, try to pull metadata or pull it
        if pull:
            print(f"  [PULLING] {image} ...", end="\r")
            success, err = pull_image(image)
            
            if success:
                print(f"  {GREEN}V{END} {image} (Pulled successfully)   ")
            else:
                # Rex Auto-Fixer: Attempt to heal
                healed_image = attempt_heal(image)
                if healed_image:
                    healed_map[image] = healed_image
                else:
                    print(f"  {RED}X{END} {image} (Failed to resolve)               ")
                    failed_map[image] = err
        else:
            print(f"  {RED}X{END} {image} (Not found locally)")
            failed_map[image] = "Image not found locally. Use --pull to verify remote reachability."

    # 3. Handle Healings/Fixes
    if healed_map and fix:
        print(f"\n{BLUE}{BOLD}[REX] Applying auto-fixes to compose files...{END}")
        for old_img, new_img in healed_map.items():
            # Find all files using this old image
            affected_paths = [path for img, path in image_entries if img == old_img]
            for path in set(affected_paths):
                if patch_compose_file(path, old_img, new_img):
                    print(f"  {GREEN}V{END} Patched {os.path.basename(path)}: {old_img} -> {new_img}")

    if failed_map:
        print(f"\n{RED}{BOLD}[REX] ERROR: Image validation failed for {len(failed_map)} images:{END}")
        for img, err in failed_map.items():
            print(f"  {BOLD}{img}{END}: {err}")
        return False

    print(f"\n{GREEN}{BOLD}✨ All images verified and self-healed.{END}")
    return True

if __name__ == "__main__":
    do_pull = "--pull" in sys.argv
    do_fix = "--fix" in sys.argv
    
    if not validate_images(pull=do_pull, fix=do_fix):
        sys.exit(1)
    sys.exit(0)
