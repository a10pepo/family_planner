import jwt
from fastapi import HTTPException
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError


class OAuthVerifier:
    def __init__(self, issuer: str, jwks_url: str, audience: str = "family-api"):
        self.issuer = issuer
        self.audience = audience
        self.keys = PyJWKClient(jwks_url, cache_keys=True, lifespan=300)

    def verify(self, token: str) -> dict:
        try:
            key = self.keys.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                key.key,
                algorithms=["RS256"],
                issuer=self.issuer,
                audience=self.audience,
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
            )
        except PyJWKClientConnectionError as exc:
            raise HTTPException(503, "El servicio de acceso no está disponible.") from exc
        except (jwt.PyJWTError, ValueError) as exc:
            raise HTTPException(
                401, "La sesión no es válida.", headers={"WWW-Authenticate": "Bearer"}
            ) from exc
        if "family-app" not in claims.get("realm_access", {}).get("roles", []):
            raise HTTPException(403, "Esta cuenta no tiene acceso a la familia.")
        return claims
