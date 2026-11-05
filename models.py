# models.py
from __future__ import annotations

import logging
import mimetypes
import re
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
from typing import Callable, ClassVar, Iterable, Optional

from backend import BackendError, BackendValidationError, FoundItBackend
from functional import all_of, compose, filter_values, map_values, reduce_values

logger = logging.getLogger(__name__)


class ValidationError(ValueError):
    pass


# ---------------------------------------------------------------- time helpers

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_timestamp(value) -> Optional[datetime]:
    """Parse a Supabase date or timestamptz string into an aware UTC datetime."""
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    # Postgres trims trailing zeros, so the fraction can have 1-6 digits; Python < 3.11 wants 3 or 6.
    text = re.sub(r"\.(\d+)", lambda m: "." + m.group(1)[:6].ljust(6, "0"), text, count=1)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------- value objects (immutable)

class Status:
    PENDING = "Pending Claim"
    CLAIMED = "Claimed"
    ALL = (PENDING, CLAIMED)

    @classmethod
    def parse(cls, value) -> str:
        """Lenient: an unknown status coming from the database is read as Pending Claim."""
        text = (value or "").strip()
        return text if text in cls.ALL else cls.PENDING

    @classmethod
    def validate(cls, value) -> str:
        """Strict: used for status changes requested by an administrator."""
        text = (value or "").strip()
        if text not in cls.ALL:
            raise ValueError(f"Invalid status: {value!r}")
        return text


@dataclass(frozen=True)
class Institution:
    name: str
    city: str
    campuses: tuple = ()

    def __post_init__(self):
        object.__setattr__(self, "campuses", tuple(self.campuses))

    @property
    def default_campus(self) -> str:
        return self.campuses[0] if self.campuses else ""

    def get_details(self) -> str:
        return f"{self.name} - {self.city}"


@dataclass(frozen=True)
class Category:
    name: str


class CategoryCatalog:
    FALLBACK = "Others"
    # Names used by older posts, mapped onto the current categories.
    ALIASES = {"ids/cards": "IDs & Cards", "tumblers/bottles": "Accessories"}

    def __init__(self, categories: Iterable[str]):
        self._categories = tuple(Category(name) for name in categories)

    @classmethod
    def default(cls) -> "CategoryCatalog":
        return cls(["Electronics", "IDs & Cards", "Clothing", "Books & Notes", "Accessories", cls.FALLBACK])

    def names(self) -> list:
        return [c.name for c in self._categories]

    def find(self, name) -> Optional[Category]:
        """Strict lookup (case-insensitive, old names accepted); None when unknown."""
        key = (name or "").strip().lower()
        key = self.ALIASES.get(key, key).lower()
        return next((c for c in self._categories if c.name.lower() == key), None)

    def resolve(self, name) -> Category:
        """Lenient lookup used when reading rows: unknown names become 'Others'."""
        return self.find(name) or Category(self.FALLBACK)


@dataclass(frozen=True)
class Tracking:
    status: str = Status.PENDING
    date_claimed: Optional[str] = None

    def __post_init__(self):
        object.__setattr__(self, "status", Status.parse(self.status))

    @property
    def is_claimed(self) -> bool:
        return self.status == Status.CLAIMED

    def with_status(self, new_status) -> "Tracking":
        """Return a NEW Tracking; the claim timestamp is created once and kept."""
        status = Status.validate(new_status)  # raises ValueError if invalid
        claimed_at = (self.date_claimed or utc_now_iso()) if status == Status.CLAIMED else None
        return Tracking(status, claimed_at)

    def _claimed_at(self) -> Optional[datetime]:
        return parse_timestamp(self.date_claimed) if self.is_claimed else None

    def days_left(self, retention_days: int, now: Optional[datetime] = None) -> Optional[int]:
        claimed_at = self._claimed_at()
        if claimed_at is None:
            return None
        remaining = claimed_at + timedelta(days=retention_days) - (now or datetime.now(timezone.utc))
        return max(remaining.days, 0)

    def is_expired(self, retention_days: int, now: Optional[datetime] = None) -> bool:
        claimed_at = self._claimed_at()
        if claimed_at is None:
            return False
        return (now or datetime.now(timezone.utc)) - claimed_at >= timedelta(days=retention_days)


@dataclass(frozen=True)
class Item:
    name: str
    description: str
    category: Category
    campus_location: str
    image_url: Optional[str] = None
    tracking: Tracking = field(default_factory=Tracking)

    def with_image(self, url: Optional[str]) -> "Item":
        return replace(self, image_url=url)

    def with_tracking(self, tracking: Tracking) -> "Item":
        return replace(self, tracking=tracking)


# ---------------------------------------------------------------- users (inheritance + polymorphism)

@dataclass(frozen=True)
class User(ABC):
    email: str
    username: str

    BASE_SECTIONS: ClassVar[tuple] = ("Feed", "Claimed")

    @property
    def institutional_id(self) -> str:
        return self.email

    @property
    def avatar_initial(self) -> str:
        return (self.username or "U")[:1].upper()

    @property
    @abstractmethod
    def role_label(self) -> str:
        ...

    @abstractmethod
    def can_manage_items(self) -> bool:
        ...

    @abstractmethod
    def sections(self) -> list:
        ...


class StandardUser(User):
    @property
    def role_label(self) -> str:
        return "Student/Faculty"

    def can_manage_items(self) -> bool:
        return False

    def sections(self) -> list:
        return list(self.BASE_SECTIONS)


class Administrator(User):
    @property
    def role_label(self) -> str:
        return "Administrator"

    def can_manage_items(self) -> bool:
        return True

    def sections(self) -> list:
        return list(self.BASE_SECTIONS) + ["Report", "Update status"]


class UserFactory:
    """Builds the right User subclass. Only the configured admin list grants admin rights."""

    def __init__(self, admin_emails: Iterable[str] = ()):
        self._admins = frozenset(e.strip().lower() for e in admin_emails if e and e.strip())

    @classmethod
    def from_setting(cls, raw) -> "UserFactory":
        """Accepts the ADMIN_EMAILS secret: a comma-separated string or a list."""
        items = raw.split(",") if isinstance(raw, str) else (raw or ())
        return cls(items)

    def create(self, email, username: Optional[str] = None) -> User:
        clean = (email or "").strip().lower()
        name = username or clean.split("@")[0] or "user"
        kind = Administrator if clean in self._admins else StandardUser
        return kind(email=clean, username=name)


# ---------------------------------------------------------------- posts

def _poster_identity(record: dict):
    """Old rows keep the email in institutional_id and a plain name in username; newer rows may be swapped."""
    candidates = [str(record.get("institutional_id") or ""), str(record.get("username") or "")]
    email = next((c for c in candidates if "@" in c), "")
    plain = next((c for c in candidates if c and "@" not in c), None)
    return email, plain


@dataclass(frozen=True)
class Post:
    post_id: str
    date_posted: str
    user: User
    item: Item

    @classmethod
    def create(cls, user: User, item: Item) -> "Post":
        # second-resolution time keeps IDs sortable; the random suffix prevents collisions
        post_id = f"POST-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
        return cls(post_id, date.today().isoformat(), user, item)

    @classmethod
    def from_record(cls, record: dict, catalog: CategoryCatalog, users: UserFactory, default_campus: str) -> "Post":
        email, plain = _poster_identity(record)
        item = Item(
            name=record.get("item_name") or "Untitled",
            description=record.get("description") or "",
            category=catalog.resolve(record.get("category_name")),
            campus_location=record.get("campus_location") or default_campus,
            image_url=record.get("image_url"),
            tracking=Tracking(record.get("status"), record.get("date_claimed")),
        )
        return cls(record.get("post_id", ""), str(record.get("date_posted") or ""), users.create(email, plain), item)

    @property
    def tracking_id(self) -> str:
        return f"TRK-{self.post_id}"

    @property
    def is_claimed(self) -> bool:
        return self.item.tracking.is_claimed

    def with_item(self, item: Item) -> "Post":
        return replace(self, item=item)

    def to_record(self) -> dict:
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
            "status": self.item.tracking.status,
            "date_claimed": self.item.tracking.date_claimed,
        }


# ---------------------------------------------------------------- functional helpers: predicates are first-class values

normalize_text = compose(str.lower, str.strip, lambda value: value or "")


def has_status(status: str) -> Callable[[Post], bool]:
    return lambda post: post.item.tracking.status == status


def in_campus(campus: Optional[str]) -> Callable[[Post], bool]:
    if not campus:
        return lambda post: True
    wanted = normalize_text(campus)
    return lambda post: normalize_text(post.item.campus_location) == wanted


def matches_query(query: Optional[str]) -> Callable[[Post], bool]:
    q = normalize_text(query)
    if not q:
        return lambda post: True
    return lambda post: any(
        q in normalize_text(field_value)
        for field_value in (post.item.name, post.item.category.name, post.item.description)
    )


def newest_first(posts: Iterable[Post]) -> tuple:
    return tuple(sorted(posts, key=lambda post: post.post_id, reverse=True))


# ---------------------------------------------------------------- authentication

@dataclass(frozen=True)
class AuthResult:
    success: bool
    user: Optional[User] = None
    refresh_token: Optional[str] = None
    error: Optional[str] = None


class AuthService:
    def __init__(self, backend: FoundItBackend, users: UserFactory):
        self._backend = backend
        self._users = users

    def _to_result(self, data: dict) -> AuthResult:
        return AuthResult(True, self._users.create(data["email"]), data.get("refresh_token"))

    def login(self, email: str, password: str) -> AuthResult:
        try:
            return self._to_result(self._backend.auth.login(email, password))
        except (BackendError, BackendValidationError) as exc:
            return AuthResult(False, error=str(exc))

    def restore(self, refresh_token: str) -> AuthResult:
        try:
            return self._to_result(self._backend.auth.restore_session(refresh_token))
        except (BackendError, BackendValidationError) as exc:
            return AuthResult(False, error=str(exc))


# ---------------------------------------------------------------- persistence (abstract interfaces + Supabase implementations)

@dataclass(frozen=True)
class ImageUpload:
    filename: str
    content_type: str
    data: bytes

    @classmethod
    def from_file(cls, file) -> "ImageUpload":
        """Adapts an uploaded file object (name, type, getvalue())."""
        return cls(file.name, getattr(file, "type", "") or "", file.getvalue())


class ImageStorage(ABC):
    @abstractmethod
    def upload(self, post_id: str, image: ImageUpload) -> str:
        ...

    @abstractmethod
    def delete(self, url: str) -> None:
        ...


class SupabaseImageStorage(ImageStorage):
    MAX_BYTES = 5 * 1024 * 1024
    EXTENSIONS = {"image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png"}
    CANONICAL_TYPES = {"jpg": "image/jpeg", "png": "image/png"}

    def __init__(self, backend: FoundItBackend):
        self._backend = backend

    def upload(self, post_id: str, image: ImageUpload) -> str:
        declared = (image.content_type or mimetypes.guess_type(image.filename)[0] or "").lower()
        extension = self.EXTENSIONS.get(declared)
        if extension is None:
            raise ValidationError("Only JPG and PNG photos are supported.")
        if not image.data:
            raise ValidationError("The selected photo is empty.")
        if len(image.data) > self.MAX_BYTES:
            raise ValidationError("The photo is too large (maximum 5 MB).")
        # the file is named after the post, so spaces or odd characters in the original name never matter
        return self._backend.storage.upload(f"{post_id}.{extension}", image.data, self.CANONICAL_TYPES[extension])

    def delete(self, url: str) -> None:
        self._backend.storage.delete(url)


class PostRepository(ABC):
    @abstractmethod
    def list_posts(self) -> tuple:
        ...

    @abstractmethod
    def add(self, post: Post) -> None:
        ...

    @abstractmethod
    def update_status(self, post_id: str, tracking: Tracking) -> None:
        ...

    @abstractmethod
    def delete(self, post_id: str) -> None:
        ...


class SupabasePostRepository(PostRepository):
    def __init__(self, backend: FoundItBackend, catalog: CategoryCatalog, users: UserFactory, default_campus: str):
        self._backend = backend
        self._catalog = catalog
        self._users = users
        self._default_campus = default_campus

    def list_posts(self) -> tuple:
        """Raises BackendError on failure, so the app can show the problem instead of an empty feed."""
        records = self._backend.posts.list_posts()
        return map_values(lambda row: Post.from_record(row, self._catalog, self._users, self._default_campus), records)

    def add(self, post: Post) -> None:
        self._backend.posts.create_post(post.to_record())

    def update_status(self, post_id: str, tracking: Tracking) -> None:
        self._backend.posts.update_status(post_id, tracking.status, tracking.date_claimed)

    def delete(self, post_id: str) -> None:
        self._backend.posts.delete_post(post_id)


# ---------------------------------------------------------------- application service

@dataclass(frozen=True)
class FeedSummary:
    active: int
    claimed: int


class LostAndFoundService:
    RETENTION_DAYS = 7
    STALE_AFTER = 30  # seconds before the feed reloads from the database

    def __init__(self, repository: PostRepository, storage: ImageStorage, catalog: CategoryCatalog,
                 institution: Institution, matcher=None, clock: Callable[[], float] = time.monotonic):
        self._repo = repository
        self._storage = storage
        self._catalog = catalog
        self._institution = institution
        self._matcher = matcher  # optional Prolog logic engine
        self._clock = clock
        self._posts: tuple = ()  # newest first
        self._loaded_at = 0.0
        self.refresh()

    @property
    def catalog(self) -> CategoryCatalog:
        return self._catalog

    @property
    def institution(self) -> Institution:
        return self._institution

    @property
    def posts(self) -> tuple:
        return self._posts

    # --- loading ---
    def refresh(self) -> None:
        posts = newest_first(self._repo.list_posts())
        removed = {post.post_id for post in self._purge_expired(posts)}
        self._posts = filter_values(lambda post: post.post_id not in removed, posts)
        self._loaded_at = self._clock()

    def refresh_if_stale(self) -> None:
        if self._clock() - self._loaded_at > self.STALE_AFTER:
            self.refresh()

    def _purge_expired(self, posts: Iterable[Post]) -> tuple:
        """Delete expired claimed posts (and their photos); returns the ones actually removed."""
        removed = []
        for post in filter_values(lambda p: p.item.tracking.is_expired(self.RETENTION_DAYS), posts):
            try:
                self._repo.delete(post.post_id)
            except BackendError as exc:
                logger.warning("Could not purge %s: %s", post.post_id, exc)
                continue
            if post.item.image_url:
                self._storage.delete(post.item.image_url)
            removed.append(post)
        return tuple(removed)

    # --- queries ---
    def find(self, post_id: str) -> Post:
        post = next((p for p in self._posts if p.post_id == post_id), None)
        if post is None:
            raise ValidationError("That item no longer exists. Please refresh the page.")
        return post

    def _select(self, status: str, campus: Optional[str], query: str) -> tuple:
        return filter_values(all_of(has_status(status), in_campus(campus), matches_query(query)), self._posts)

    def active(self, campus: Optional[str] = None, query: str = "") -> tuple:
        return self._select(Status.PENDING, campus, query)

    def claimed(self, campus: Optional[str] = None, query: str = "") -> tuple:
        return self._select(Status.CLAIMED, campus, query)

    def summary(self) -> FeedSummary:
        def count(total: FeedSummary, post: Post) -> FeedSummary:
            return FeedSummary(total.active + int(not post.is_claimed), total.claimed + int(post.is_claimed))
        return reduce_values(count, self._posts, FeedSummary(0, 0))

    def possible_matches(self, query: str, campus: Optional[str] = None) -> tuple:
        """Pending posts the Prolog rules consider related to the search; empty if Prolog is unavailable."""
        if self._matcher is None or not (query or "").strip():
            return ()
        candidates = self._select(Status.PENDING, None, "")
        try:
            results = self._matcher.find_possible_matches(query, map_values(Post.to_record, candidates), campus=campus)
        except Exception:  # keep the feed usable if the Prolog engine fails
            logger.warning("Prolog matching failed", exc_info=True)
            return ()
        by_id = {post.post_id: post for post in candidates}
        return tuple(by_id[r["post_id"]] for r in results if r["post_id"] in by_id)

    # --- commands (administrators only) ---
    @staticmethod
    def _require_admin(user: User) -> None:
        if not user.can_manage_items():
            raise PermissionError("Only administrators can do this.")

    def report(self, user: User, name: str, description: str, category_name: str, campus: str, image=None) -> Post:
        self._require_admin(user)
        name = (name or "").strip()
        if not name:
            raise ValidationError("Please provide an item name.")
        category = self._catalog.find(category_name)
        if category is None:
            raise ValidationError("Please choose a valid category.")
        if campus not in self._institution.campuses:
            raise ValidationError("Please choose a valid campus.")

        post = Post.create(user, Item(name, (description or "").strip(), category, campus))
        uploaded_url = None
        if image is not None:
            uploaded_url = self._storage.upload(post.post_id, ImageUpload.from_file(image))  # fails loudly
            post = post.with_item(post.item.with_image(uploaded_url))
        try:
            self._repo.add(post)
        except Exception:
            if uploaded_url:
                self._storage.delete(uploaded_url)  # do not leave an orphaned photo behind
            raise
        self._posts = newest_first((post,) + self._posts)
        return post

    def set_status(self, user: User, post_id: str, new_status: str) -> Post:
        self._require_admin(user)
        post = self.find(post_id)
        try:
            tracking = post.item.tracking.with_status(new_status)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        self._repo.update_status(post_id, tracking)
        updated = post.with_item(post.item.with_tracking(tracking))
        self._posts = tuple(updated if p.post_id == post_id else p for p in self._posts)
        return updated
