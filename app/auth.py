"""Read the owner id from a Firebase sign-in token. The studio does not store the teacher."""

import jwt
from jwt import PyJWKClient

from app.config import get_settings

_CERTS_URL = "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com"
_jwks: PyJWKClient | None = None


class AuthError(Exception):
    def __init__(self, message: str, status_code: int) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def bearer_token(authorization: str) -> str:
    parts = authorization.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        return ""
    return parts[1].strip()


def owner_id_from_authorization(authorization: str) -> str:
    token = bearer_token(authorization)
    if not token:
        raise AuthError("Sign in is required", 401)
    project_id = get_settings().firebase_project_id.strip()
    if not project_id:
        raise AuthError("FIREBASE_PROJECT_ID is not set", 500)
    return owner_id_from_token(token, project_id)


def owner_id_from_token(token: str, project_id: str, jwks_client: PyJWKClient | None = None) -> str:
    try:
        jwt.get_unverified_header(token)
        signing_key = (jwks_client or _cert_client()).get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=project_id,
            issuer=f"https://securetoken.google.com/{project_id}",
            leeway=10,
        )
    except jwt.InvalidTokenError as exc:
        raise AuthError("Invalid authentication token", 401) from exc
    except AuthError:
        raise
    except Exception as exc:
        raise AuthError("Could not check the sign-in token", 502) from exc
    owner_id = str(payload.get("user_id") or payload.get("sub") or "").strip()
    if not owner_id:
        raise AuthError("Invalid authentication token", 401)
    return owner_id


def _cert_client() -> PyJWKClient:
    global _jwks
    if _jwks is None:
        _jwks = PyJWKClient(_CERTS_URL)
    return _jwks
