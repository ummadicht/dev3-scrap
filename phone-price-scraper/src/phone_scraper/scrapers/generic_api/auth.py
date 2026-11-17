from __future__ import annotations

import base64
import logging
from typing import Any

import httpx

from phone_scraper.core.auth import resolve_env_secret

logger = logging.getLogger(__name__)


class ApiAuthProvider:
    """
    Handles authentication injection and 401 token refresh for generic_api sources.
    Supports: none, api_key (header|query), bearer, basic, oauth2_client_credentials, cookie.
    """

    def __init__(
        self,
        auth_config: dict[str, Any] | None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.config = auth_config or {"type": "none"}
        self.auth_type = str(self.config.get("type", "none")).lower()
        self._cached_token: str | None = None
        self._transport = transport

    def _fetch_oauth2_token(self) -> str:
        token_url = str(self.config.get("token_url") or "")
        client_id = resolve_env_secret(self.config.get("client_id_env"))
        client_secret = resolve_env_secret(self.config.get("client_secret_env"))
        scope = str(self.config.get("scope") or "").strip()

        if not token_url or not client_id or not client_secret:
            raise ValueError(
                "oauth2_client_credentials requires token_url, client_id_env, and client_secret_env"
            )

        data: dict[str, str] = {"grant_type": "client_credentials"}
        if scope:
            data["scope"] = scope

        logger.info("Requesting OAuth2 client_credentials token from %s", token_url)
        client_kwargs: dict[str, Any] = {"timeout": 15.0}
        if self._transport is not None:
            client_kwargs["transport"] = self._transport

        with httpx.Client(**client_kwargs) as client:
            resp = client.post(token_url, auth=(client_id, client_secret), data=data)
            resp.raise_for_status()
            payload = resp.json()
            token = str(payload.get("access_token") or "")
            if not token:
                raise RuntimeError("OAuth2 token endpoint response missing access_token")
            self._cached_token = token
            return token

    def refresh(self) -> bool:
        """Refresh token after a 401 response if refresh credentials are configured."""
        if self.auth_type == "oauth2_client_credentials" or self.config.get("token_url"):
            self._cached_token = None
            self._fetch_oauth2_token()
            return True
        if self.auth_type == "bearer":
            # Re-read env var or optional refresh_token_env in case token rotated externally
            refresh_env = self.config.get("refresh_token_env")
            if refresh_env:
                rotated = resolve_env_secret(str(refresh_env))
                if rotated:
                    self._cached_token = rotated
                    return True
        return False

    def apply(
        self,
        headers: dict[str, str],
        params: dict[str, Any],
    ) -> tuple[dict[str, str], dict[str, Any]]:
        out_headers = dict(headers)
        out_params = dict(params)

        if self.auth_type == "none":
            return out_headers, out_params

        if self.auth_type == "api_key":
            secret = resolve_env_secret(self.config.get("key_env"))
            location = str(self.config.get("in", "header")).lower()
            name = str(self.config.get("name", "X-API-Key"))
            if location == "query":
                out_params[name] = secret
            else:
                out_headers[name] = secret
            return out_headers, out_params

        if self.auth_type == "bearer":
            token = self._cached_token or resolve_env_secret(self.config.get("token_env"))
            if token:
                out_headers["Authorization"] = f"Bearer {token}"
            return out_headers, out_params

        if self.auth_type == "basic":
            user = resolve_env_secret(self.config.get("username_env"))
            password = resolve_env_secret(self.config.get("password_env"))
            raw = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
            out_headers["Authorization"] = f"Basic {raw}"
            return out_headers, out_params

        if self.auth_type == "oauth2_client_credentials":
            token = self._cached_token or self._fetch_oauth2_token()
            out_headers["Authorization"] = f"Bearer {token}"
            return out_headers, out_params

        if self.auth_type == "cookie":
            cookie_val = resolve_env_secret(self.config.get("cookie_env"))
            cookie_name = str(self.config.get("cookie_name", "session"))
            if cookie_val:
                out_headers["Cookie"] = f"{cookie_name}={cookie_val}"
            return out_headers, out_params

        raise ValueError(f"Unsupported auth type: {self.auth_type}")
