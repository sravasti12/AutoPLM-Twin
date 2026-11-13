"""Auth0-compatible resource-server validation; never trusts a token's key URLs or roles."""

import json
import os
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlsplit

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

from app.startup_diagnostics import startup_stage


class IdentityUnavailable(Exception):
    pass


@dataclass(frozen=True)
class OIDCConfig:
    issuer: str
    audience: str
    client_id: str

    @classmethod
    def from_environment(cls):
        return cls.from_values(
            os.environ.get("AUTOPLM_OIDC_ISSUER", ""),
            os.environ.get("AUTOPLM_OIDC_AUDIENCE", ""),
            os.environ.get("AUTOPLM_OIDC_CLIENT_ID", ""),
        )

    @classmethod
    def from_values(cls, issuer: str, audience: str, client_id: str):
        """Apply the same validation to backend environment or protected frontend settings."""
        parsed = urlsplit(issuer)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.port is not None
            or parsed.path != "/"
            or parsed.query
            or parsed.fragment
            or not audience.startswith("https://")
            or len(audience) > 256
            or not client_id
            or len(client_id) > 120
            or audience == client_id
            or audience == issuer + "userinfo"
        ):
            raise ValueError("Invalid OIDC configuration")
        return cls(issuer, audience, client_id)


def fetch_document(url: str) -> dict:
    """Only called with operator-configured HTTPS URLs; bounded size/time, no redirects."""
    try:
        with httpx.Client(timeout=5, follow_redirects=False, trust_env=False) as client:
            with client.stream("GET", url) as response:
                if response.status_code != 200:
                    raise ValueError("Unavailable")
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > 65536:
                        raise ValueError("Oversized identity document")
        value = json.loads(body)
        if not isinstance(value, dict):
            raise ValueError("Invalid identity document")
        return value
    except (httpx.HTTPError, ValueError, TypeError):
        raise IdentityUnavailable() from None


class OIDCValidator:
    ttl = 300
    refresh_interval = 30

    def __init__(self, config: OIDCConfig):
        self.config = config
        self.keys: dict[str, RSAPublicKey] = {}
        self.loaded_at = float("-inf")
        self.attempted_at = float("-inf")
        self.lock = threading.Lock()

    def _refresh(self) -> None:
        self.attempted_at = time.monotonic()
        document = fetch_document(self.config.issuer + ".well-known/jwks.json")
        try:
            entries = document["keys"]
            if not isinstance(entries, list) or not 1 <= len(entries) <= 16:
                raise ValueError("Invalid keys")
            keys = {}
            for entry in entries:
                if entry.get("kty") != "RSA" or entry.get("use", "sig") != "sig":
                    continue
                kid = entry.get("kid")
                if (
                    not isinstance(kid, str)
                    or not 1 <= len(kid) <= 128
                    or kid in keys
                    or entry.get("alg", "RS256") != "RS256"
                    or entry.get("key_ops", ["verify"]) != ["verify"]
                    or "d" in entry
                ):
                    raise ValueError("Invalid signing key")
                key = jwt.PyJWK.from_dict({k: entry[k] for k in ("kty", "n", "e")}, algorithm="RS256").key
                if not isinstance(key, RSAPublicKey) or not 2048 <= key.key_size <= 8192:
                    raise ValueError("Invalid signing key size")
                keys[kid] = key
            if not keys:
                raise ValueError("No signing keys")
        except (KeyError, ValueError, TypeError, AttributeError, jwt.PyJWTError):
            raise IdentityUnavailable() from None
        self.keys = keys
        self.loaded_at = time.monotonic()

    def startup(self) -> None:
        with startup_stage("oidc_discovery_jwks_initialization"):
            document = fetch_document(self.config.issuer + ".well-known/openid-configuration")
            if (
                document.get("issuer") != self.config.issuer
                or document.get("jwks_uri") != self.config.issuer + ".well-known/jwks.json"
            ):
                raise IdentityUnavailable()
            with self.lock:
                self._refresh()

    def validate(self, token: str) -> dict:
        if not isinstance(token, str) or len(token) > 16384:
            raise jwt.InvalidTokenError()
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if (
            header.get("alg") != "RS256"
            or header.get("typ") not in ("JWT", "at+jwt")
            or not isinstance(kid, str)
            or not 1 <= len(kid) <= 128
            or any(k in header for k in ("jku", "jwk", "x5u", "crit"))
        ):
            raise jwt.InvalidTokenError()
        with self.lock:
            now = time.monotonic()
            if kid not in self.keys or now - self.loaded_at >= self.ttl:
                if now - self.attempted_at >= self.refresh_interval:
                    self._refresh()
                elif now - self.loaded_at >= self.ttl:
                    raise IdentityUnavailable()
            key = self.keys.get(kid)
            if key is None:
                raise jwt.InvalidTokenError()
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=self.config.issuer,
            audience=self.config.audience,
            options={"require": ["iss", "aud", "sub", "iat", "exp", "azp", "scope"]},
            leeway=5,
        )
        if (
            claims.get("azp") != self.config.client_id
            or not isinstance(claims.get("sub"), str)
            or not 1 <= len(claims["sub"]) <= 120
            or claims["sub"] != claims["sub"].strip()
            or claims["sub"].endswith("@clients")
            or ("nbf" in claims and type(claims["nbf"]) is not int)
            or claims.get("gty") == "client-credentials"
            or "nonce" in claims
            or type(claims["iat"]) is not int
            or type(claims["exp"]) is not int
            or not 0 < claims["exp"] - claims["iat"] <= 3600
            or not isinstance(claims["scope"], str)
            or len(claims["scope"]) > 4096
            or "autoplm:access" not in claims["scope"].split()
        ):
            raise jwt.InvalidTokenError()
        return claims


@lru_cache(maxsize=1)
def get_validator() -> OIDCValidator:
    return OIDCValidator(OIDCConfig.from_environment())
