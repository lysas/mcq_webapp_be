"""
Authentication & Multi-Tenant Middleware Module
================================================
Provides JWT authentication token creation, verification, password hashing,
and tenant security context isolation for FastAPI endpoints.
"""

import os
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

JWT_SECRET = os.environ.get("JWT_SECRET", "super-secret-saas-key-2026")
ALGORITHM = "HS256"

security_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Hashes password using PBKDF2 with SHA256."""
    salt = "marksheet_ai_salt_2026"
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies plain password against stored hash."""
    return hash_password(plain_password) == hashed_password


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a lightweight JWT representation token string."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=24))
    to_encode.update({"exp": int(expire.timestamp())})
    
    # Lightweight token format for local deployment without external pyjwt dependency
    import base64, json
    payload_str = base64.b64encode(json.dumps(to_encode).encode()).decode()
    sig = hashlib.sha256(f"{payload_str}.{JWT_SECRET}".encode()).hexdigest()
    return f"{payload_str}.{sig}"


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decodes and validates JWT token."""
    import base64, json
    try:
        parts = token.split(".")
        if len(parts) != 2:
            raise ValueError("Invalid token format")
        payload_str, sig = parts
        expected_sig = hashlib.sha256(f"{payload_str}.{JWT_SECRET}".encode()).hexdigest()
        if sig != expected_sig:
            raise ValueError("Signature verification failed")
        payload = json.loads(base64.b64decode(payload_str.encode()).decode())
        if datetime.utcnow().timestamp() > payload.get("exp", 0):
            raise ValueError("Token expired")
        return payload
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid or expired authentication token: {str(e)}")


def get_current_user_tenant(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer)
) -> Dict[str, Any]:
    """
    Enforces tenant context isolation.
    Returns payload containing org_id, user_id, and role.
    If no token provided, returns default demo tenant context.
    """
    if not credentials:
        return {
            "organization_id": "org_default_demo",
            "user_id": "user_demo_examiner",
            "role": "EXAMINER"
        }
    return decode_access_token(credentials.credentials)
