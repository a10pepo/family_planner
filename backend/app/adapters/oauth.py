import jwt
from fastapi import HTTPException
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError


class OAuthVerifier:
    def __init__(
        self,
        issuer: str,
        jwks_url: str,
        audience: str = "family-api",
        provider: str = "keycloak",
        required_group: str = "family-app",
        required_scope: str = "",
    ):
        self.issuer = issuer
        self.audience = audience
        self.provider = provider
        self.required_group = required_group
        self.required_scope = required_scope
        self.keys = PyJWKClient(jwks_url, cache_keys=True, lifespan=300)

    def verify(self, token: str) -> dict:
        try:
            key = self.keys.get_signing_key_from_jwt(token)
            cognito = self.provider == "cognito"
            claims = jwt.decode(
                token,
                key.key,
                algorithms=["RS256"],
                issuer=self.issuer,
                audience=None if cognito else self.audience,
                options={
                    "verify_aud": not cognito,
                    "require": ["exp", "iat", "sub", "iss"] + ([] if cognito else ["aud"]),
                },
            )
        except PyJWKClientConnectionError as exc:
            raise HTTPException(503, "El servicio de acceso no está disponible.") from exc
        except (jwt.PyJWTError, ValueError) as exc:
            raise HTTPException(
                401, "La sesión no es válida.", headers={"WWW-Authenticate": "Bearer"}
            ) from exc
        if self.provider == "cognito":
            if claims.get("token_use") != "access" or claims.get("client_id") != self.audience:
                raise HTTPException(
                    401,
                    "Se requiere un token de acceso válido.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            if self.required_scope and self.required_scope not in claims.get("scope", "").split():
                raise HTTPException(403, "El token no incluye el alcance de acceso familiar.")
            authorized = self.required_group in claims.get("cognito:groups", [])
        else:
            authorized = self.required_group in claims.get("realm_access", {}).get("roles", [])
        if not authorized:
            raise HTTPException(403, "Esta cuenta no tiene acceso a la familia.")
        return claims
