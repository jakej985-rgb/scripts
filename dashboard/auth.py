import os

TOKENS = {
    "admin-token": "admin",
    "ops-token": "operator",
    "view-token": "viewer"
}

def get_role(token):
    return TOKENS.get(token)
