import os

TOKENS = {
    "YOUR_SECURE_ADMIN_TOKEN": "admin",
    "YOUR_SECURE_OPS_TOKEN": "operator",
    "YOUR_SECURE_VIEW_TOKEN": "viewer"
}

def get_role(token):
    return TOKENS.get(token)
