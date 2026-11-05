"""
This module keeps Supabase infrastructure behind a small service layer so the
Streamlit UI, Functional module, and Prolog module do not need
to make direct database calls.

Every Supabase operation (authentication, the posts table, photo storage) goes
through the three APIs exposed by FoundItBackend.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Mapping

from supabase import Client, create_client

logger = logging.getLogger(__name__)


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

    The anonymous client is used for reads and sign-in. The service client is
    optional and is only used by trusted server-side code for writes.
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

    def new_auth_client(self) -> Client:  # throwaway, one per login
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
            raise BackendError(f"Login failed: {exc}") from exc

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
            raise BackendError(f"Session restoration failed: {exc}") from exc


class PostsAPI:
    """Backend-facing API for FoundIt's posts table.

    Record keys deliberately match the FoundIt schema so records can be
    consumed by models.Post.from_record() and the Prolog logic engine.
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
            raise BackendError(f"Could not load posts: {exc}") from exc

    def create_post(self, record: Mapping[str, Any]) -> dict[str, Any]:
        clean = self._validate_post(record)
        try:
            result = self._gateway.privileged().table(self.TABLE).insert(clean).execute()
            rows = result.data or []
            return dict(rows[0]) if rows else clean
        except Exception as exc:
            raise BackendError(f"Could not create post: {exc}") from exc

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
            raise BackendError(f"Could not update post status: {exc}") from exc

    def delete_post(self, post_id: str) -> None:
        post_id = (post_id or "").strip()
        if not post_id:
            raise BackendValidationError("post_id is required.")
        try:
            self._gateway.privileged().table(self.TABLE).delete().eq(
                "post_id", post_id
            ).execute()
        except Exception as exc:
            raise BackendError(f"Could not delete post: {exc}") from exc


class StorageAPI:
    """Backend-facing API for the public `item-images` bucket."""

    BUCKET = "item-images"
    ALLOWED_TYPES = {"image/jpeg", "image/png"}

    def __init__(self, gateway: SupabaseGateway):
        self._gateway = gateway

    def _bucket(self):
        return self._gateway.privileged().storage.from_(self.BUCKET)

    def upload(self, path: str, data: bytes, content_type: str) -> str:
        """Store the file and return its public URL."""
        if not (path or "").strip() or not data:
            raise BackendValidationError("A file name and file contents are required.")
        if content_type not in self.ALLOWED_TYPES:
            raise BackendValidationError("Only JPEG and PNG images are allowed.")
        try:
            bucket = self._bucket()
            bucket.upload(
                path=path,
                file=data,
                file_options={"content-type": content_type, "upsert": "true"},
            )
            result = bucket.get_public_url(path)
        except Exception as exc:
            raise BackendError(f"Could not upload photo: {exc}") from exc
        if isinstance(result, dict):
            result = result.get("publicUrl") or result.get("public_url")
        return str(result)

    def delete(self, url: str) -> bool:
        """Remove the file behind a public URL. Returns False instead of raising."""
        name = (url or "").split("?")[0].rstrip("/").split("/")[-1]
        if not name:
            return False
        try:
            self._bucket().remove([name])
            return True
        except Exception as exc:
            logger.warning("Could not delete image %s: %s", name, exc)
            return False


@dataclass(frozen=True)
class FoundItBackend:
    """Facade exposed to the rest of FoundIt."""

    auth: AuthAPI
    posts: PostsAPI
    storage: StorageAPI

    @classmethod
    def create(cls, secrets: Mapping[str, Any]) -> "FoundItBackend":
        gateway = SupabaseGateway(BackendConfig.from_mapping(secrets))
        return cls(auth=AuthAPI(gateway), posts=PostsAPI(gateway), storage=StorageAPI(gateway))
