# models.py
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import ClassVar

from functional import all_of, compose, filter_values, map_values, reduce_values

import streamlit as st
from supabase import create_client, Client


class ValidationError(ValueError):
    pass


class Status(str, Enum):
    PENDING = "Pending Claim"
    CLAIMED = "Claimed"

    @classmethod
    def parse(cls, value):
        try:
            return cls(value)
        except ValueError:
            return cls.PENDING 


# ---------------------------------------------------------------- infrastructure

class SupabaseGateway:
    def __init__(self):
        self._url = st.secrets["SUPABASE_URL"]
        self._anon_key = st.secrets["SUPABASE_KEY"]
        self._reader = create_client(self._url, self._anon_key)
        self._writer = create_client(self._url, st.secrets["SUPABASE_SERVICE_KEY"])

    @property
    def reader(self) -> Client:  # anon, read-only use
        return self._reader

    @property
    def writer(self) -> Client:  # service role, writes only
        return self._writer

    def new_auth_client(self) -> Client:  # throwaway, one per login
        return create_client(self._url, self._anon_key)


@st.cache_resource
def get_gateway() -> SupabaseGateway:
    return SupabaseGateway()


# ---------------------------------------------------------------- domain entities

@dataclass(frozen=True)
class Institution:
    name: str
    city: str
    campuses: tuple[str, ...]

    def __init__(self, name, city, campuses):
        campuses = tuple(campuses)
        if not campuses:
            raise ValueError("An institution must have at least one campus.")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "city", city)
        object.__setattr__(self, "campuses", campuses)

    @property
    def default_campus(self):
        return self.campuses[0]

    def get_details(self):
        return f"{self.name} - {self.city}"


@dataclass(frozen=True)
class Category:
    name: str
    code: str


@dataclass(frozen=True)
class CategoryCatalog:
    _categories: tuple[Category, ...]
    _fallback_name: str

    def __init__(self, categories, fallback_name):
        object.__setattr__(self, "_categories", tuple(categories))
        object.__setattr__(self, "_fallback_name", fallback_name)

    @classmethod
    def default(cls):
        return cls([
            Category("Electronics", "CAT-01"),
            Category("Tumblers/Bottles", "CAT-02"),
            Category("IDs/Cards", "CAT-03"),
            Category("Others", "CAT-04"),
        ], fallback_name="Others")

    def all(self):
        return self._categories

    def names(self):
        return map_values(lambda category: category.name, self._categories)

    def find(self, name):
        by_name = {category.name: category for category in self._categories}
        return by_name.get(name) or by_name[self._fallback_name]


@dataclass(frozen=True)
class Tracking:
    status: Status = Status.PENDING
    date_claimed: str | None = None

    def __post_init__(self):
        # Accept either Status values or their stored string representation.
        object.__setattr__(self, "status", Status.parse(self.status))

    @property
    def is_claimed(self):
        return self.status is Status.CLAIMED

    def with_status(self, new_status, claimed_at=None):
        """Return a new Tracking object; leave this instance unchanged."""
        status = Status(new_status)  # invalid values raise ValueError
        date_claimed = (
            claimed_at or datetime.now(timezone.utc).isoformat()
            if status is Status.CLAIMED else None
        )
        return replace(self, status=status, date_claimed=date_claimed)

    def update(self, new_status):
        """Compatibility method that now returns a replacement Tracking object."""
        return self.with_status(new_status)

    def days_left(self, retention_days):
        try:
            claimed_at = datetime.fromisoformat(str(self.date_claimed).replace("Z", "+00:00"))
            if claimed_at.tzinfo is None:
                claimed_at = claimed_at.replace(tzinfo=timezone.utc)
            remaining = claimed_at + timedelta(days=retention_days) - datetime.now(timezone.utc)
            return max(remaining.days, 0)
        except (TypeError, ValueError):
            return None


_NORMALIZE_TEXT = compose(str.lower, str.strip, lambda value: value or "")


@dataclass(frozen=True)
class Item:
    name: str
    description: str
    category: Category
    campus_location: str
    image_url: str | None = None
    tracking: Tracking = field(default_factory=Tracking)

    def __post_init__(self):
        object.__setattr__(self, "description", self.description or "")
        if self.tracking is None:
            object.__setattr__(self, "tracking", Tracking())

    def with_image(self, url):
        """Return a new Item containing the uploaded image URL."""
        return replace(self, image_url=url)

    def with_tracking(self, tracking):
        """Return a new Item with replacement tracking information."""
        return replace(self, tracking=tracking)

    def matches(self, query):
        normalized_query = _NORMALIZE_TEXT(query)
        if not normalized_query:
            return True
        searchable_fields = map_values(
            _NORMALIZE_TEXT,
            (self.name, self.category.name, self.description),
        )
        return any(normalized_query in value for value in searchable_fields)


# ---------------------------------------------------------------- users

@dataclass(frozen=True)
class User(ABC):
    username: str
    institutional_id: str
    BASE_SECTIONS: ClassVar[tuple[str, ...]] = ("Feed", "Claimed")

    @property
    def avatar_initial(self):
        return self.username[:1].upper()

    @property
    @abstractmethod
    def role_label(self):
        ...

    @abstractmethod
    def can_manage_items(self):
        ...

    @abstractmethod
    def sections(self):
        ...


class StandardUser(User):
    @property
    def role_label(self):
        return "Student/Faculty"

    def can_manage_items(self):
        return False

    def sections(self):
        return list(self.BASE_SECTIONS)


class Administrator(User):
    @property
    def role_label(self):
        return "Administrator"

    def can_manage_items(self):
        return True

    def sections(self):
        return list(self.BASE_SECTIONS) + ["Report", "Update status"]


class UserFactory:
    @staticmethod
    def admin_emails():
        raw = st.secrets.get("ADMIN_EMAILS", "")
        return {e.strip().lower() for e in raw.split(",") if e.strip()}

    @classmethod
    def create(cls, email, username=None):
        username = username or (email or "").split("@")[0]
        if email and email.strip().lower() in cls.admin_emails():
            return Administrator(username, email)
        return StandardUser(username, email)


@dataclass(frozen=True)
class Post:
    post_id: str
    date_posted: str
    user: User
    item: Item

    @classmethod
    def create(cls, user, item):
        post_id = f"POST-{int(datetime.now().timestamp())}-{uuid.uuid4().hex[:6]}"
        return cls(post_id, datetime.now().strftime("%Y-%m-%d"), user, item)

    @classmethod
    def from_record(cls, record, catalog, default_campus):
        item = Item(
            record["item_name"],
            record.get("description"),
            catalog.find(record.get("category_name")),
            record.get("campus_location") or default_campus,
            record.get("image_url"),
            Tracking(record.get("status", Status.PENDING), record.get("date_claimed")),
        )
        user = UserFactory.create(record["institutional_id"], record.get("username"))
        return cls(record["post_id"], record["date_posted"], user, item)

    @property
    def tracking_id(self):
        return f"TRK-{self.post_id}"

    def with_item(self, item):
        """Return a new Post containing the supplied immutable Item."""
        return replace(self, item=item)

    def with_tracking(self, tracking):
        """Return a new Post with new tracking data, without mutating old objects."""
        return self.with_item(self.item.with_tracking(tracking))

    def matches(self, query):
        return self.item.matches(query)

    def to_record(self):
        return {
            "post_id": self.post_id,
            "date_posted": self.date_posted,
            "username": self.user.username,
            "institutional_id": self.user.institutional_id,
            "item_name": self.item.name,
            "description": self.item.description,
            "category_name": self.item.category.name,
            "campus_location": self.item.campus_location,
            "image_url": self.item.image_url,
            "status": self.item.tracking.status.value,
            "date_claimed": self.item.tracking.date_claimed,
        }


# ---------------------------------------------------------------- authentication

class AuthResult:
    def __init__(self, user=None, refresh_token=None, error=None):
        self.user = user
        self.refresh_token = refresh_token
        self.error = error

    @property
    def success(self):
        return self.user is not None


class AuthService:
    def __init__(self, gateway):
        self._gateway = gateway

    def login(self, email, password):
        try:
            client = self._gateway.new_auth_client()
            response = client.auth.sign_in_with_password({"email": email, "password": password})
            return AuthResult(UserFactory.create(response.user.email), response.session.refresh_token)
        except Exception as e:
            return AuthResult(error=str(e))

    def restore(self, refresh_token):
        try:
            client = self._gateway.new_auth_client()
            response = client.auth.refresh_session(refresh_token)
            if not response.user or not response.session:
                return AuthResult(error="No user/session returned")
            return AuthResult(UserFactory.create(response.user.email), response.session.refresh_token)
        except Exception as e:
            return AuthResult(error=str(e))


# ---------------------------------------------------------------- persistence

class ImageStorage(ABC):
    @abstractmethod
    def upload(self, post_id, image):
        ...

    @abstractmethod
    def delete(self, url):
        ...


class SupabaseImageStorage(ImageStorage):
    BUCKET = "item-images"

    def __init__(self, gateway):
        self._gateway = gateway

    def _bucket(self):
        return self._gateway.writer.storage.from_(self.BUCKET)

    def upload(self, post_id, image):
        path = f"{post_id}.{image.name.split('.')[-1]}"
        self._bucket().upload(
            path=path,
            file=image.getvalue(),
            file_options={"content-type": image.type, "upsert": "true"},
        )
        return self._bucket().get_public_url(path)

    def delete(self, url):
        try:
            self._bucket().remove([url.split("?")[0].split("/")[-1]])
        except Exception as e:
            print(f"Error deleting image from storage: {e}")


class PostRepository(ABC):
    @abstractmethod
    def all(self):
        ...

    @abstractmethod
    def add(self, post, image=None):
        ...

    @abstractmethod
    def save_status(self, post):
        ...

    @abstractmethod
    def purge_expired(self, retention_days):
        ...


class SupabasePostRepository(PostRepository):
    TABLE = "posts"

    def __init__(self, gateway, catalog, storage, default_campus):
        self._gateway = gateway
        self._catalog = catalog
        self._storage = storage
        self._default_campus = default_campus

    def all(self):
        rows = self._gateway.reader.table(self.TABLE).select("*").execute().data or []
        posts = map_values(
            lambda row: Post.from_record(row, self._catalog, self._default_campus),
            rows,
        )
        return tuple(sorted(posts, key=lambda post: post.post_id))  # oldest first

    def add(self, post, image=None):
        stored_post = post
        if image is not None:
            image_url = self._storage.upload(post.post_id, image)
            stored_post = post.with_item(post.item.with_image(image_url))
        self._gateway.writer.table(self.TABLE).insert(stored_post.to_record()).execute()
        return stored_post

    def save_status(self, post):
        tracking = post.item.tracking
        self._gateway.writer.table(self.TABLE).update({
            "status": tracking.status.value,
            "date_claimed": tracking.date_claimed,
        }).eq("post_id", post.post_id).execute()

    def purge_expired(self, retention_days):
        threshold = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
        expired = self._gateway.writer.table(self.TABLE) \
            .select("post_id, image_url") \
            .eq("status", Status.CLAIMED.value) \
            .lt("date_claimed", threshold) \
            .execute().data or []
        for row in expired:
            if row.get("image_url"):
                self._storage.delete(row["image_url"])
            self._gateway.writer.table(self.TABLE).delete().eq("post_id", row["post_id"]).execute()
        return len(expired)


# ---------------------------------------------------------------- application service

@dataclass(frozen=True)
class PostSummary:
    active: int
    claimed: int

    @property
    def total(self):
        return self.active + self.claimed


class LostAndFoundService:
    RETENTION_DAYS = 7
    STALE_AFTER = 30  # seconds before the feed reloads from the database

    def __init__(self, repository, catalog, institution, matcher=None):
        self._repo = repository
        self._catalog = catalog
        self._institution = institution
        self._matcher = matcher  # optional logic engine (Prolog rules)
        self._posts = ()
        self._loaded_at = 0.0
        self.refresh()

    @property
    def catalog(self):
        return self._catalog

    @property
    def institution(self):
        return self._institution

    @property
    def posts(self):
        # Tuples prevent callers from changing the service's collection.
        return self._posts

    def refresh(self):
        self._repo.purge_expired(self.RETENTION_DAYS)
        self._posts = tuple(sorted(self._repo.all(), key=lambda post: post.post_id))
        self._loaded_at = time.monotonic()

    def refresh_if_stale(self):
        if time.monotonic() - self._loaded_at > self.STALE_AFTER:
            self.refresh()

    def find(self, post_id):
        return next(filter(lambda post: post.post_id == post_id, self._posts))

    def _filter_posts(self, status_predicate, campus, query):
        predicate = all_of(
            status_predicate,
            lambda post: campus is None or post.item.campus_location == campus,
            lambda post: post.matches(query),
        )
        return filter_values(predicate, reversed(self._posts))

    def active(self, campus=None, query=""):
        return self._filter_posts(lambda post: not post.item.tracking.is_claimed, campus, query)

    def claimed(self, campus=None, query=""):
        return self._filter_posts(lambda post: post.item.tracking.is_claimed, campus, query)

    def possible_matches(self, query, campus=None, category=None):
        """Posts the logic engine considers possible matches; empty when it is unavailable."""
        if self._matcher is None or not (query or "").strip():
            return ()
        records = map_values(lambda post: post.to_record(), self._posts)
        try:
            results = self._matcher.find_possible_matches(
                query, records, category=category, campus=campus
            )
        except Exception as e:  # keep the feed usable if the Prolog engine fails
            print(f"Logic engine error: {e}")
            return ()
        by_id = {post.post_id: post for post in self._posts}
        return tuple(by_id[r["post_id"]] for r in results if r["post_id"] in by_id)

    def summary(self):
        """Aggregate post statuses with reduce into an immutable result."""
        active_count, claimed_count = reduce_values(
            lambda counts, post: (
                counts[0] + int(not post.item.tracking.is_claimed),
                counts[1] + int(post.item.tracking.is_claimed),
            ),
            self._posts,
            (0, 0),
        )
        return PostSummary(active_count, claimed_count)

    @staticmethod
    def _require_admin(user):
        if not user.can_manage_items():
            raise PermissionError("Only administrators can do this.")

    def report(self, user, name, description, category_name, campus, image=None):
        self._require_admin(user)
        if not (name or "").strip():
            raise ValidationError("Please provide an item name.")
        item = Item(name, description, self._catalog.find(category_name), campus)
        post = Post.create(user, item)
        self._repo.add(post, image)
        self.refresh()
        return self.find(post.post_id)

    def set_status(self, user, post_id, new_status):
        self._require_admin(user)
        post = self.find(post_id)
        updated_tracking = post.item.tracking.update(new_status)
        updated_post = post.with_tracking(updated_tracking)

        # Persist first. Only replace the in-memory value after the save succeeds.
        self._repo.save_status(updated_post)
        self._posts = map_values(
            lambda current: updated_post if current.post_id == post_id else current,
            self._posts,
        )
        self._loaded_at = time.monotonic()
        return updated_post
