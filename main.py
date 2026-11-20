import os
import uvicorn
from dotenv import load_dotenv
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Dict, List

load_dotenv()

from schemas import LoginRequest, RefreshRequest, TokenResponse

import jwt
from fastapi import FastAPI, HTTPException, status, Form, File, UploadFile
from fastapi.security import HTTPBearer
from fastapi.openapi.utils import get_openapi
from pwdlib import PasswordHash



from db.crud.user_data_table import create_user


# --------------------------------------------------
# Configuration
# --------------------------------------------------

app = FastAPI(title="Authentication API", version="1.0.0")

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("Set the JWT_SECRET_KEY environment variable.")

ALGORITHM = os.getenv("JWT_ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")
REFRESH_TOKEN_EXPIRE_DAYS = os.getenv("REFRESH_TOKEN_EXPIRE_DAYS")

APP_USERNAME = os.getenv("APP_USERNAME", "user@example.com")
APP_PASSWORD = os.getenv("APP_PASSWORD")

if not APP_PASSWORD:
    raise RuntimeError("Set the APP_PASSWORD environment variable.")

password_hasher = PasswordHash.recommended()
APP_PASSWORD_HASH = password_hasher.hash(APP_PASSWORD)

bearer_scheme = HTTPBearer(auto_error=False)

# In-memory refresh-token session store.
# Key: SHA-256 hash of refresh token.
# Value: username and expiration time.
refresh_sessions: Dict[str, dict] = {}
sessions_lock = Lock()





# --------------------------------------------------
# Token Utilities
# --------------------------------------------------

def create_access_token(username: str) -> str:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": username,
        "iat": now,
        "exp": expires_at,
        "type": "access",
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_tokens(username: str) -> TokenResponse:
    access_token = create_access_token(username)
    refresh_token = generate_refresh_token()

    token_hash = hash_refresh_token(refresh_token)
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=REFRESH_TOKEN_EXPIRE_DAYS
    )

    with sessions_lock:
        refresh_sessions[token_hash] = {
            "username": username,
            "expires_at": expires_at,
        }

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# --------------------------------------------------
# API 1: Login
# --------------------------------------------------

@app.post(
    "/api/auth/login",
    response_model=TokenResponse,
)
def login(request: LoginRequest):
    username_matches = secrets.compare_digest(
        request.email.lower(),
        APP_USERNAME.lower(),
    )

    password_matches = password_hasher.verify(
        request.password,
        APP_PASSWORD_HASH,
    )

    if not (username_matches and password_matches):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    return issue_tokens(request.email.lower())


# --------------------------------------------------
# API 2: Refresh Token
# --------------------------------------------------

@app.post(
    "/api/auth/refresh",
    response_model=TokenResponse,
)
def refresh_token(request: RefreshRequest):
    token_hash = hash_refresh_token(request.refresh_token)
    now = datetime.now(timezone.utc)

    with sessions_lock:
        session = refresh_sessions.get(token_hash)

        if session is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or already-used refresh token",
            )

        if now >= session["expires_at"]:
            del refresh_sessions[token_hash]

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token expired. Please log in again.",
            )

        username = session["username"]

        # Consume the old refresh token before issuing a replacement.
        # This prevents it from being reused successfully.
        del refresh_sessions[token_hash]

    return issue_tokens(username)


# --------------------------------------------------
# File Upload API
# --------------------------------------------------

@app.post("/api/upload")
async def upload_file(
    username: str = Form(..., description="Username of the uploader"),
    files: list[UploadFile] = File(..., description="Files to upload"),
):
    return {
        "username": username,
        "total_files": len(files),
        "filenames": [file.filename for file in files],
    }


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
    )

    # Convert the schema to a format Swagger UI recognizes
    for component in schema.get("components", {}).get("schemas", {}).values():
        for prop in component.get("properties", {}).values():
            targets = [prop]

            if prop.get("type") == "array":
                targets.append(prop.get("items", {}))

            for target in targets:
                if target.get("contentMediaType") == "application/octet-stream":
                    target.pop("contentMediaType", None)
                    target["format"] = "binary"

    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi


# --------------------------------------------------
# Optional: Protected API example
# --------------------------------------------------

@app.get("/api/protected")
def protected_api(
    credentials=__import__(
        "fastapi"
    ).Depends(bearer_scheme),
):
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"require": ["sub", "exp", "iat", "type"]},
        )

        if payload["type"] != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )

        return {
            "message": "Access granted",
            "username": payload["sub"],
        }

    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@app.get("/")
def health_check():
    return {"message": "Authentication API is running"}




## Create a new user in the database (for testing purposes)
@app.post("/api/create_user")
def create_user_endpoint(username: str, password: str):
    try:
        password_hasher = PasswordHash.recommended()
        password_hash = password_hasher.hash(password)

        user = create_user(username, password_hash)
        return {"message": "User created successfully", "username": user.user_name}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )



if __name__ == "__main__":
    uvicorn.run(
        "main:app", 
        host=str(os.getenv("APP_HOST")), 
        port=int(os.getenv("APP_PORT")),
        reload=True
    )
