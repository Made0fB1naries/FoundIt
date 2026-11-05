"""
This module keeps Supabase infrastructure behind a small service layer so the
Streamlit UI, Functional module, and Prolog module do not need
to make direct database calls.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping

from supabase import Client, create_client


class BackendError(RuntimeError):
    """Raised when a backend operation cannot be completed safely."""


class BackendValidationError(ValueError):
    """Raised when an API request contains invalid data."""


@dataclass(frozen=True)
class BackendConfig:
    url: str
    anon_key: str
    service_key: str | None = None

    @classmethod
    def from_mapping(cls, secrets: Mapping[str, Any]) -> "BackendConfig":
        url = str(secrets.get("SUPABASE_URL") or "").strip()
        anon_key = str(secrets.get("SUPABASE_KEY") or "").strip()
        service_key = str(secrets.get("SUPABASE_SERVICE_KEY") or "").strip() or None
        if not url or not anon_key:
            raise BackendValidationError("SUPABASE_URL and SUPABASE_KEY are required.")
        return cls(url=url, anon_key=anon_key, service_key=service_key)

    @classmethod
    def from_environment(cls) -> "BackendConfig":
        return cls.from_mapping(os.environ)


class SupabaseGateway:
    """Centralized creation of Supabase clients.

    The anonymous client is used for normal/authenticated access. The service
    client is optional and should only be used by trusted server-side code.
    """

    def __init__(self, config: BackendConfig):
        self._config = config
        self._public = create_client(config.url, config.anon_key)
        self._service = (
            create_client(config.url, config.service_key)
            if config.service_key else None
        )

    @property
    def public(self) -> Client:
        return self._public

    def new_auth_client(self) -> Client:
        return create_client(self._config.url, self._config.anon_key)

    def privileged(self) -> Client:
        if self._service is None:
            raise BackendError(
                "A server-side SUPABASE_SERVICE_KEY is required for this privileged operation."
            )
        return self._service


class AuthAPI:
    def __init__(self, gateway: SupabaseGateway):
        self._gateway = gateway

    def login(self, email: str, password: str) -> dict[str, Any]:
        email = (email or "").strip().lower()
        if not email or not password:
            raise BackendValidationError("Email and password are required.")
        try:
            response = self._gateway.new_auth_client().auth.sign_in_with_password(
                {"email": email, "password": password}
            )
            if not response.user or not response.session:
                raise BackendError("Supabase did not return a valid user session.")
            return {
                "email": response.user.email,
                "refresh_token": response.session.refresh_token,
            }
        except BackendError:
            raise
        except Exception as exc:
            raise BackendError("Login failed.") from exc

    def restore_session(self, refresh_token: str) -> dict[str, Any]:
        if not (refresh_token or "").strip():
            raise BackendValidationError("Refresh token is required.")
        try:
            response = self._gateway.new_auth_client().auth.refresh_session(refresh_token)
            if not response.user or not response.session:
                raise BackendError("Supabase did not return a valid restored session.")
            return {
                "email": response.user.email,
                "refresh_token": response.session.refresh_token,
            }
        except BackendError:
            raise
        except Exception as exc:
            raise BackendError("Session restoration failed.") from exc


class PostsAPI:
    """Backend-facing API for FoundIt's existing posts table.

    Record keys deliberately match the existing FoundIt schema so records can
    still be consumed by models.Post.from_record() and Claire's logic engine.
    """

    TABLE = "posts"
    ALLOWED_STATUSES = {"Pending Claim", "Claimed"}
    REQUIRED_FIELDS = {
        "post_id", "date_posted", "username", "institutional_id",
        "item_name", "category_name", "campus_location", "status",
    }

    def __init__(self, gateway: SupabaseGateway):
        self._gateway = gateway

    @classmethod
    def _validate_post(cls, record: Mapping[str, Any]) -> dict[str, Any]:
        clean = dict(record)
        missing = [key for key in cls.REQUIRED_FIELDS if not str(clean.get(key) or "").strip()]
        if missing:
            raise BackendValidationError(
                "Missing required post fields: " + ", ".join(sorted(missing))
            )
        if clean["status"] not in cls.ALLOWED_STATUSES:
            raise BackendValidationError("Invalid post status.")
        return clean

    def list_posts(self) -> tuple[dict[str, Any], ...]:
        try:
            rows = self._gateway.public.table(self.TABLE).select("*").execute().data or []
            return tuple(dict(row) for row in rows)
        except Exception as exc:
            raise BackendError("Could not load posts.") from exc

    def create_post(self, record: Mapping[str, Any]) -> dict[str, Any]:
        clean = self._validate_post(record)
        try:
            result = self._gateway.privileged().table(self.TABLE).insert(clean).execute()
            rows = result.data or []
            return dict(rows[0]) if rows else clean
        except Exception as exc:
            raise BackendError("Could not create post.") from exc

    def update_status(self, post_id: str, status: str, date_claimed: str | None) -> None:
        post_id = (post_id or "").strip()
        if not post_id:
            raise BackendValidationError("post_id is required.")
        if status not in self.ALLOWED_STATUSES:
            raise BackendValidationError("Invalid post status.")
        payload = {"status": status, "date_claimed": date_claimed}
        try:
            self._gateway.privileged().table(self.TABLE).update(payload).eq(
                "post_id", post_id
            ).execute()
        except Exception as exc:
            raise BackendError("Could not update post status.") from exc

    def delete_post(self, post_id: str) -> None:
        post_id = (post_id or "").strip()
        if not post_id:
            raise BackendValidationError("post_id is required.")
        try:
            self._gateway.privileged().table(self.TABLE).delete().eq(
                "post_id", post_id
            ).execute()
        except Exception as exc:
            raise BackendError("Could not delete post.") from exc


@dataclass(frozen=True)
class FoundItBackend:
    """Facade exposed to the rest of FoundIt."""
    auth: AuthAPI
    posts: PostsAPI

    @classmethod
    def create(cls, secrets: Mapping[str, Any]) -> "FoundItBackend":
        gateway = SupabaseGateway(BackendConfig.from_mapping(secrets))
        return cls(auth=AuthAPI(gateway), posts=PostsAPI(gateway))
