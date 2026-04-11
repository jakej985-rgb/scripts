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
    from progress_utils import ProgressBar, Spinner
except ImportError:
    YELLOW, RED, GREEN, BLUE, BOLD, END = ("", "", "", "", "", "")
    ProgressBar, Spinner = None, None

# Rex Auto-Fixer: Known repository remaps
KNOWN_REMAPS = {
    "maintainerr": "ghcr.io/maintainerr/maintainerr",
    "flaresolverr": "ghcr.io/flaresolverr/flaresolverr",
    "gluetun": "qmcgaw/gluetun",
    "tdarr": "ghcr.io/haveagitgat/tdarr",
    "komga": "gotson/komga:latest"
}

FALLBACK_TAGS = ["latest", "stable", ""]

def get_images_from_compose(file_path):
    results = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
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
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        pattern = re.compile(rf'image:\s*["\']?{re.escape(old_image)}["\']?')
        new_content = pattern.sub(f'image: {new_image}', content)
        if content != new_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return True
    except Exception:
        pass
    return False

def pull_image_with_progress(image, pbar: ProgressBar = None):
    cmd = ["docker", "pull", image]
    if pbar:
        pbar.update(pbar.current, f"(Pulling {image}...)")
    else:
        print(f"  {BLUE}---> Pulling {image}...{END}")

    # Enforce tag-aware pulls to avoid ambiguity
    if ":" not in image:
        image = f"{image}:latest"
        cmd = ["docker", "pull", image]

    process = subprocess.Popen(
        cmd, 
        stdout=sys.stdout, 
        stderr=subprocess.PIPE, # Capture stderr for error reporting
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    
    _, stderr = process.communicate()
    return process.returncode == 0, stderr

def attempt_heal(image, pbar: ProgressBar = None):
    base_name = image.split(':')[0] if ':' in image else image
    tag = image.split(':')[1] if ':' in image else None
    
    candidates = []
    if base_name in KNOWN_REMAPS:
        new_base = KNOWN_REMAPS[base_name]
        if tag: candidates.append(f"{new_base}:{tag}")
        for t in FALLBACK_TAGS:
            candidates.append(f"{new_base}:{t}" if t else new_base)
    for t in FALLBACK_TAGS:
        if t != tag:
            candidates.append(f"{base_name}:{t}" if t else base_name)

    seen = set()
    final_candidates = [x for x in candidates if not (x in seen or seen.add(x))]

    for cand in final_candidates:
        if pbar:
            pbar.update(pbar.current, f"(Trying fallback: {cand}...)")
        success, _ = pull_image_with_progress(cand)
        if success:
            return cand
    return None

def validate_images(pull=False, fix=False):
    print(f"{BLUE}{BOLD}[REX] Scanning for Docker images...{END}")
    
    image_entries = []
    # Use Path.rglob for pure path iteration
    for ext in ['*.yml', '*.yaml']:
        for path in DOCKER_DIR.rglob(ext):
            if "example" in str(path).lower(): 
                continue
            image_entries.extend(get_images_from_compose(path))

    if not image_entries:
        print(f"{YELLOW}[REX] No images found to validate.{END}")
        return True

    unique_images = sorted(list(set([img for img, _ in image_entries])))
    total_imgs = len(unique_images)
    print(f"{BLUE}[REX] Validating {total_imgs} unique images...{END}")
    
    failed_map = {}
    healed_map = {}
    
    # Progress Bar for Image Processing
    pbar = ProgressBar(total_imgs, prefix="[REX] Validating:") if ProgressBar else None
    
    for idx, image in enumerate(unique_images, 1):
        if pbar:
            pbar.update(idx - 1, f"({image})")
        else:
            print(f"  {BLUE}[{idx}/{total_imgs}]{END} Checking {image}...")
            
        inspect_cmd = ["docker", "image", "inspect", image]
        result = subprocess.run(inspect_cmd, capture_output=True)
        
        if result.returncode == 0:
            if pbar: pbar.update(idx, f"({image} - Local)")
            continue
            
        if pull:
            success, err = pull_image_with_progress(image, pbar)
            if success:
                if pbar: pbar.update(idx, f"({image} - Pulled)")
            else:
                healed_image = attempt_heal(image, pbar)
                if healed_image:
                    healed_map[image] = healed_image
                    if pbar: pbar.update(idx, f"({image} -> {healed_image})")
                else:
                    failed_map[image] = err
                    if pbar: pbar.update(idx, f"({image} - Failed)")
        else:
            failed_map[image] = "Image not found locally. Use --pull to verify remote reachability."
            if pbar: pbar.update(idx, f"({image} - Missing)")

    if healed_map and fix:
        print(f"\n{BLUE}{BOLD}[REX] Applying auto-fixes...{END}")
        for old_img, new_img in healed_map.items():
            affected_paths = [path for img, path in image_entries if img == old_img]
            for path in set(affected_paths):
                if patch_compose_file(path, old_img, new_img):
                    print(f"  {GREEN}V{END} Patched {os.path.basename(path)}: {old_img} -> {new_img}")

    if failed_map:
        print(f"\n{RED}{BOLD}[REX] ERROR: Image validation failed for {len(failed_map)} images:{END}")
        for img, err in failed_map.items():
            print(f"  {BOLD}{img}{END}: {err[:100]}...")
        return False

    print(f"\n{GREEN}{BOLD}✨ All images verified.{END}")
    return True

if __name__ == "__main__":
    do_pull = "--pull" in sys.argv
    do_fix = "--fix" in sys.argv
    if not validate_images(pull=do_pull, fix=do_fix):
        sys.exit(1)
    sys.exit(0)
