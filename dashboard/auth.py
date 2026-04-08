import bcrypt
import json
import os

def get_role(token):
    if not token:
        return None
    
    users_path = os.environ.get("USERS_FILE", "dashboard/users.json")
    if not os.path.exists(users_path):
        # Fallback to hardcoded for startup/boot if file missing, 
        # but warn user in production logs
        return None

    try:
        with open(users_path) as f:
            users = json.load(f)
        
        for uname, data in users.items():
            # Check bcrypt hash
            if bcrypt.checkpw(token.encode(), data["token_hash"].encode()):
                return data["role"]
    except Exception:
        return None
        
    return None
