from __future__ import annotations

import re
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Optional

from pyswip import Prolog


class FoundItLogicEngine:

    def __init__(self, rules_file: Optional[str] = None):
        self.prolog = Prolog()
        self._lock = threading.Lock()  # Prolog facts are global, so one query at a time
        path = Path(rules_file) if rules_file else Path(__file__).with_name("matching_rules.pl")
        if not path.is_file():
            raise FileNotFoundError(f"Prolog rules file not found: {path}")
        self.prolog.consult(str(path.resolve()))

    @staticmethod
    def _atom(value: object) -> str:
        """Safely format a Python value as a quoted Prolog atom."""
        value = str(value).replace("\\", "\\\\").replace("'", "\\'")
        return f"'{value}'"

    @staticmethod
    def _tokens(value: str) -> set[str]:
        # Ignore very short words because they usually add little matching value.
        return {word for word in re.findall(r"[a-z0-9]+", (value or "").lower()) if len(word) > 2}

    @staticmethod
    def _clear_facts(prolog: Prolog) -> None:
        for predicate in (
            "item_category(_, _)",
            "item_status(_, _)",
            "item_campus(_, _)",
            "item_word(_, _)",
            "query_category(_)",
            "query_campus(_)",
            "query_word(_)",
        ):
            list(prolog.query(f"retractall({predicate})"))

    def _find_possible_matches(
        self,
        search_text: str,
        posts: Iterable[dict],
        category: Optional[str] = None,
        campus: Optional[str] = None,
        limit: int = 10,
    ) -> list[dict]:
        words = self._tokens(search_text)
        if not words:
            return []

        self._clear_facts(self.prolog)

        if category and category.strip():
            self.prolog.assertz(f"query_category({self._atom(category.strip().lower())})")
        if campus and campus.strip():
            self.prolog.assertz(f"query_campus({self._atom(campus.strip().lower())})")

        for word in words:
            self.prolog.assertz(f"query_word({self._atom(word)})")

        for post in posts:
            post_id = post.get("post_id")
            if not post_id:
                continue

            status = str(post.get("status", "")).strip().lower()
            if status != "pending claim":
                continue

            pid = self._atom(post_id)
            item_category = str(post.get("category_name") or "").strip().lower()
            item_campus = str(post.get("campus_location") or "").strip().lower()
            item_text = f"{post.get('item_name', '')} {post.get('description', '')}"

            self.prolog.assertz(f"item_status({pid}, pending)")
            if item_category:
                self.prolog.assertz(f"item_category({pid}, {self._atom(item_category)})")
            if item_campus:
                self.prolog.assertz(f"item_campus({pid}, {self._atom(item_campus)})")

            for word in self._tokens(item_text):
                self.prolog.assertz(f"item_word({pid}, {self._atom(word)})")

        matches = {}
        for result in self.prolog.query("possible_match(PostId, Word)"):
            post_id = str(result["PostId"])
            word = str(result["Word"])
            matches.setdefault(post_id, set()).add(word)

        same_campus = {
            str(result["PostId"])
            for result in self.prolog.query("same_campus_match(PostId)")
        }

        ranked = [
            {
                "post_id": post_id,
                "matched_words": sorted(matched_words),
                "same_campus": post_id in same_campus,
            }
            for post_id, matched_words in matches.items()
        ]
        ranked.sort(
            key=lambda item: (item["same_campus"], len(item["matched_words"])),
            reverse=True,
        )
        return ranked[:max(1, int(limit))]

    def _is_claim_expired(
        self,
        date_claimed: str,
        retention_days: int = 7,
        today: Optional[date] = None,
    ) -> bool:
        if not date_claimed:
            return False

        try:
            claimed_date = datetime.fromisoformat(
                str(date_claimed).replace("Z", "+00:00")
            ).date()
        except ValueError:
            try:
                claimed_date = date.fromisoformat(str(date_claimed)[:10])
            except ValueError:
                return False

        current_date = today or date.today()
        query = (
            f"claim_expired({claimed_date.toordinal()}, "
            f"{current_date.toordinal()}, {int(retention_days)})"
        )
        return bool(list(self.prolog.query(query)))

    def find_possible_matches(self, search_text, posts, category=None, campus=None, limit=10):
        """Thread-safe entry point: Streamlit runs each user session in its own thread."""
        with self._lock:
            return self._find_possible_matches(search_text, posts, category, campus, limit)

    def is_claim_expired(self, date_claimed, retention_days=7, today=None):
        with self._lock:
            return self._is_claim_expired(date_claimed, retention_days, today)
