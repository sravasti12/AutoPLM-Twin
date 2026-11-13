"""Separate local credentials and production resource-server authentication."""

import hashlib
import hmac
import json
import logging
import os
from typing import Annotated, Literal

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from pymongo.errors import PyMongoError

from app.oidc_auth import IdentityUnavailable, get_validator
from app.security_store import get_security_store, identity_key

logger = logging.getLogger("autoplm.security")


class ReviewPrincipal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    subject: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    roles: tuple[Literal["investigation_reader", "engineering_reviewer"], ...] = Field(min_length=1)


bearer = HTTPBearer(auto_error=False)


def authenticated_review_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if credentials is None or credentials.scheme.lower() != "bearer":
        logger.warning("security_event=authentication_required")
        raise HTTPException(401, "Reviewer authentication required", headers={"WWW-Authenticate": "Bearer"})
    if os.environ.get("AUTOPLM_ENVIRONMENT", "local") != "local":
        import jwt

        try:
            validator = get_validator()
        except ValueError:
            raise HTTPException(503, "Production identity provider is not configured") from None
        try:
            claims = validator.validate(credentials.credentials)
            store = get_security_store()
            identity = identity_key(validator.config.issuer, claims["sub"])
            store.quota(identity, "requests")
            roles: tuple[Literal["investigation_reader", "engineering_reviewer"], ...] = (
                ("engineering_reviewer",)
                if store.is_reviewer(validator.config.issuer, claims["sub"])
                else ("investigation_reader",)
            )
            return ReviewPrincipal(subject=claims["sub"], roles=roles)
        except jwt.PyJWTError:
            logger.warning("security_event=invalid_access_token")
            raise HTTPException(
                401, "Invalid reviewer credential", headers={"WWW-Authenticate": "Bearer"}
            ) from None
        except (IdentityUnavailable, PyMongoError, ValueError):
            logger.warning("security_event=authorization_unavailable")
            raise HTTPException(503, "Reviewer authorization unavailable") from None
    try:
        raw = json.loads(os.environ.get("AUTOPLM_REVIEW_CREDENTIALS", "{}"))
        if not isinstance(raw, dict) or not raw:
            raise ValueError("Disabled")
        entries = []
        for key, value in raw.items():
            if len(key) != 64 or any(c not in "0123456789abcdef" for c in key):
                raise ValueError("Invalid credential digest")
            entries.append((key, ReviewPrincipal.model_validate(value)))
    except (ValueError, TypeError):
        raise HTTPException(503, "Review authorization is not configured") from None
    token_hash = hashlib.sha256(credentials.credentials.encode()).hexdigest()
    for key, principal in entries:
        if hmac.compare_digest(key, token_hash):
            return principal
    raise HTTPException(401, "Invalid reviewer credential", headers={"WWW-Authenticate": "Bearer"})


def authorized_reviewer(principal: ReviewPrincipal = Depends(authenticated_review_user)) -> ReviewPrincipal:
    if "engineering_reviewer" not in principal.roles:
        logger.warning("security_event=reviewer_role_denied")
        raise HTTPException(403, "Engineering reviewer role required")
    return principal
