# 🔧 Env Integration Migration Guide

All scripts should now use centralized config via:

```bash
source "$(dirname "$0")/lib/env.sh"
```

## Required changes

### Replace:
- source .env
- hardcoded paths
- hardcoded thresholds

### Use:
- $BACKUP_DIR
- $CPU_THRESHOLD
- $MEM_THRESHOLD
- $DISK_THRESHOLD

---

## Example

OLD:
```bash
if [ "$MEM" -gt 90 ]; then
```

NEW:
```bash
if [ "$MEM" -gt "$MEM_THRESHOLD" ]; then
```

---

## Required file

```bash
cp connections.env.example connections.env
```

---

## Notes

- All scripts now depend on connections.env
- System will exit if missing
- This prevents broken automation
