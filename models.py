# models.py
from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any, List, Optional

import streamlit as st
from backend import FoundItBackend, BackendError, BackendValidationError

# ---------------------------------------------------------------- Backend Gateway Factory

def get_backend() -> FoundItBackend:
    """Initializes the backend facade using Streamlit secrets."""
    try:
        return FoundItBackend.create(st.secrets)
    except Exception as exc:
        raise RuntimeError("Failed to initialize FoundIt backend from secrets.") from exc


# ---------------------------------------------------------------- Domain Entities & Enums

class Status:
    PENDING = "Pending Claim"
    CLAIMED = "Claimed"

    @classmethod
    def parse(cls, value: str) -> str:
        v = (value or "").strip()
        if v in (cls.PENDING, cls.CLAIMED):
            return v
        return cls.PENDING


@dataclass(frozen=True)
class Category:
    name: str


class CategoryCatalog:
    def __init__(self, categories: List[str]):
        self._categories = [Category(c) for c in categories]

    @classmethod
    def default(cls) -> "CategoryCatalog":
        return cls.default_instance()

    @classmethod
    def default_instance(cls) -> "CategoryCatalog":
        return cls(["Electronics", "IDs & Cards", "Clothing", "Books & Notes", "Accessories", "Others"])

    def names(self) -> List[str]:
        return [c.name for c in self._categories]

    def find(self, name: str) -> Optional[Category]:
        for c in self._categories:
            if c.name.lower() == (name or "").strip().lower():
                return c
        return None


@dataclass(frozen=True)
class Institution:
    name: str
    city: str
    campuses: List[str]

    @property
    def default_campus(self) -> str:
        return self.campuses[0] if self.campuses else ""

    def get_details(self) -> str:
        return f"{self.name} - {self.city}"


@dataclass(frozen=True)
class User:
    email: str
    username: str
    institutional_id: str
    role: str

    @property
    def avatar_initial(self) -> str:
        return self.username[0].upper() if self.username else "U"

    @property
    def role_label(self) -> str:
        return "Administrator" if self.can_manage_items() else "Student"

    def can_manage_items(self) -> bool:
        return self.role.lower() == "admin"


class UserFactory:
    @staticmethod
    def create(email: str) -> User:
        clean_email = (email or "").strip().lower()
        admin_emails = [
            e.strip().lower()
            for e in st.secrets.get("ADMIN_EMAILS", "").split(",")
            if e.strip()
        ]
        is_admin = clean_email in admin_emails or (clean_email.endswith("@mcm.edu.ph") and "admin" in clean_email)
        
        username = clean_email.split("@")[0] if "@" in clean_email else "user"
        institutional_id = username
        role = "admin" if is_admin else "student"
        return User(email=clean_email, username=username, institutional_id=institutional_id, role=role)


@dataclass(frozen=True)
class Tracking:
    status: str
    date_claimed: Optional[str] = None

    def days_left(self, retention_days: int) -> Optional[int]:
        if self.status != Status.CLAIMED or not self.date_claimed:
            return None
        try:
            claimed_date = datetime.date.fromisoformat(self.date_claimed)
            expiry_date = claimed_date + datetime.timedelta(days=retention_days)
            delta = (expiry_date - datetime.date.today()).days
            return max(0, delta)
        except Exception:
            return None


@dataclass(frozen=True)
class Item:
    name: str
    description: str
    category: Category
    campus_location: str
    image_url: Optional[str]
    tracking: Tracking


@dataclass(frozen=True)
class Post:
    post_id: str
    date_posted: str
    user: User
    item: Item

    @classmethod
    def from_record(cls, record: dict, catalog: CategoryCatalog) -> "Post":
        cat = catalog.find(record.get("category_name", "")) or Category("Others")
        user = UserFactory.create(record.get("username", "user@mapua.edu.ph"))
        tracking = Tracking(
            status=Status.parse(record.get("status", Status.PENDING)),
            date_claimed=record.get("date_claimed")
        )
        item = Item(
            name=record.get("item_name", "Untitled"),
            description=record.get("description", ""),
            category=cat,
            campus_location=record.get("campus_location", ""),
            image_url=record.get("image_url"),
            tracking=tracking
        )
        return cls(
            post_id=record.get("post_id", ""),
            date_posted=record.get("date_posted", ""),
            user=user,
            item=item
        )

    def to_record(self) -> dict:
        return {
            "post_id": self.post_id,
            "date_posted": self.date_posted,
            "username": self.user.email,
            "institutional_id": self.user.institutional_id,
            "item_name": self.item.name,
            "description": self.item.description,
            "category_name": self.item.category.name,
            "campus_location": self.item.campus_location,
            "image_url": self.item.image_url,
            "status": self.item.tracking.status,
            "date_claimed": self.item.tracking.date_claimed,
        }


# ---------------------------------------------------------------- Services & Storage

class AuthService:
    def __init__(self, backend: FoundItBackend):
        self._backend = backend

    def login(self, email: str, password: str) -> AuthResult:
        try:
            data = self._backend.auth.login(email, password)
            user = UserFactory.create(data["email"])
            return AuthResult(success=True, user=user, refresh_token=data.get("refresh_token"))
        except (BackendError, BackendValidationError) as e:
            return AuthResult(success=False, error=str(e))

    def restore(self, refresh_token: str) -> AuthResult:
        try:
            data = self._backend.auth.restore_session(refresh_token)
            user = UserFactory.create(data["email"])
            return AuthResult(success=True, user=user, refresh_token=data.get("refresh_token"))
        except (BackendError, BackendValidationError) as e:
            return AuthResult(success=False, error=str(e))


@dataclass(frozen=True)
class AuthResult:
    success: bool
    user: Optional[User] = None
    refresh_token: Optional[str] = None
    error: Optional[str] = None


class SupabaseImageStorage:
    BUCKET = "item-images"

    def __init__(self, backend: FoundItBackend):
        self._backend = backend

    def upload(self, file_bytes: bytes, filename: str) -> Optional[str]:
        if not file_bytes:
            return None
        try:
            path = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
            client = self._backend._gateway.privileged()
            client.storage.from_(self.BUCKET).upload(path, file_bytes, {"file-options": {"contentType": "image/jpeg"}})
            res = client.storage.from_(self.BUCKET).get_public_url(path)
            return res
        except Exception:
            return None


class SupabasePostRepository:
    def __init__(self, backend: FoundItBackend, catalog: CategoryCatalog, storage: SupabaseImageStorage, default_campus: str):
        self._backend = backend
        self._catalog = catalog
        self._storage = storage
        self._default_campus = default_campus

    def list_posts(self) -> List[Post]:
        try:
            records = self._backend.posts.list_posts()
            return [Post.from_record(r, self._catalog) for r in records]
        except Exception:
            return []

    def save(self, post: Post):
        try:
            self._backend.posts.create_post(post.to_record())
        except Exception as e:
            raise ValidationError(f"Failed to save post: {e}")

    def update_status(self, post_id: str, status: str, date_claimed: Optional[str]):
        try:
            self._backend.posts.update_status(post_id, status, date_claimed)
        except Exception as e:
            raise ValidationError(f"Failed to update post status: {e}")

    def delete(self, post_id: str):
        try:
            self._backend.posts.delete_post(post_id)
        except Exception as e:
            raise ValidationError(f"Failed to delete post: {e}")


class ValidationError(Exception):
    pass


@dataclass(frozen=True)
class FeedSummary:
    active: int
    claimed: int


class LostAndFoundService:
    RETENTION_DAYS = 7

    def __init__(self, repository: SupabasePostRepository, catalog: CategoryCatalog, institution: Institution, matcher=None):
        self._repository = repository
        self.catalog = catalog
        self.institution = institution
        self._matcher = matcher
        self._posts: List[Post] = []
        self.refresh()

    def refresh(self):
        self._posts = self._repository.list_posts()
        self.purge_expired()

    def refresh_if_stale(self):
        self.refresh()

    @property
    def posts(self) -> List[Post]:
        return self._posts

    def summary(self) -> FeedSummary:
        active = sum(1 for p in self._posts if p.item.tracking.status == Status.PENDING)
        claimed = sum(1 for p in self._posts if p.item.tracking.status == Status.CLAIMED)
        return FeedSummary(active=active, claimed=claimed)

    def active(self, campus: Optional[str] = None, query: str = "") -> List[Post]:
        filtered = [p for p in self._posts if p.item.tracking.status == Status.PENDING]
        if campus:
            filtered = [p for p in filtered if p.item.campus_location.lower() == campus.lower()]
        if query.strip():
            q = query.lower()
            filtered = [
                p for p in filtered
                if q in p.item.name.lower() or q in p.item.description.lower() or q in p.item.category.name.lower()
            ]
        return filtered

    def claimed(self, campus: Optional[str] = None, query: str = "") -> List[Post]:
        filtered = [p for p in self._posts if p.item.tracking.status == Status.CLAIMED]
        if campus:
            filtered = [p for p in filtered if p.item.campus_location.lower() == campus.lower()]
        if query.strip():
            q = query.lower()
            filtered = [
                p for p in filtered
                if q in p.item.name.lower() or q in p.item.description.lower() or q in p.item.category.name.lower()
            ]
        return filtered

    def possible_matches(self, query: str, campus: Optional[str] = None) -> List[Post]:
        base = self.active(campus=campus, query="")
        if not self._matcher or not query.strip():
            return self.active(campus=campus, query=query)
        try:
            matched_ids = self._matcher.find_matches(base, query)
            by_id = {p.post_id: p for p in base}
            return [by_id[pid] for pid in matched_ids if pid in by_id]
        except Exception:
            return self.active(campus=campus, query=query)

    def report(self, user: User, name: str, description: str, category_name: str, campus: str, photo_file: Any) -> Post:
        if not name.strip():
            raise ValidationError("Item name is required.")
        cat = self.catalog.find(category_name)
        if not cat:
            raise ValidationError("Invalid category.")
        
        image_url = None
        if photo_file is not None:
            storage = SupabaseImageStorage(self._repository._backend)
            image_url = storage.upload(photo_file.getvalue(), photo_file.name)

        post_id = f"POST-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        date_posted = datetime.date.today().isoformat()
        
        item = Item(
            name=name.strip(),
            description=description.strip(),
            category=cat,
            campus_location=campus,
            image_url=image_url,
            tracking=Tracking(status=Status.PENDING)
        )
        post = Post(post_id=post_id, date_posted=date_posted, user=user, item=item)
        self._repository.save(post)
        self.refresh()
        return post

    def set_status(self, user: User, post_id: str, new_status_value: str):
        if not user.can_manage_items():
            raise ValidationError("Unauthorized: only administrators can change item status.")
        new_status = Status.parse(new_status_value)
        date_claimed = datetime.date.today().isoformat() if new_status == Status.CLAIMED else None
        self._repository.update_status(post_id, new_status, date_claimed)
        self.refresh()

    def purge_expired(self):
        today = datetime.date.today()
        for p in list(self._posts):
            if p.item.tracking.status == Status.CLAIMED and p.item.tracking.date_claimed:
                try:
                    c_date = datetime.date.fromisoformat(p.item.tracking.date_claimed)
                    if (today - c_date).days >= self.RETENTION_DAYS:
                        self._repository.delete(p.post_id)
                except Exception:
                    pass
