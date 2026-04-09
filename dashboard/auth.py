import bcrypt
import json
import os

def get_role(token):
    if not token:
        return None
    
    users_path = os.environ.get("USERS_FILE", "dashboard/users.json")
    if not os.path.exists(users_path):
        return None

    try:
        with open(users_path) as f:
            users = json.load(f)
        
        # Support list format (Audit fix 1.1 — align with server.py and init.py)
        if isinstance(users, list):
            for user in users:
                if bcrypt.checkpw(token.encode(), user["token_hash"].encode()):
                    return user.get("role", "viewer")
        elif isinstance(users, dict):
            # Legacy dict format backward compatibility
            for uname, data in users.items():
                if bcrypt.checkpw(token.encode(), data["token_hash"].encode()):
                    return data["role"]
    except Exception:
        return None
        
    return None
