# app.py
import html
import datetime
import base64
from pathlib import Path
from abc import ABC, abstractmethod
from urllib.parse import quote

import streamlit as st
import extra_streamlit_components as stx

from backend import BackendError, BackendValidationError, FoundItBackend
from models import (AuthService, CategoryCatalog, Institution, LostAndFoundService, Status,
                    SupabaseImageStorage, SupabasePostRepository, UserFactory, ValidationError)

try:  # the app still runs without SWI-Prolog; the "Possible matches" panel is then hidden
    from logic_engine import FoundItLogicEngine
except ImportError:
    FoundItLogicEngine = None


# ---------------------------------------------------------------- shared resources

@st.cache_resource
def get_backend() -> FoundItBackend:
    return FoundItBackend.create(st.secrets)


@st.cache_resource
def get_matcher():
    if FoundItLogicEngine is None:
        return None
    try:
        return FoundItLogicEngine()
    except Exception as exc:
        print(f"Logic engine unavailable: {exc}")
        return None


# ---------------------------------------------------------------- UI Theme Engine (Light & Dark Mode)

class Theme:
    LIGHT_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
    --mapua-red: #B30000;
    --mapua-red-dark: #8C0000;
    --ink: #202124;
    --muted: #5F6368;
    --line: #E0E2E6;
    --surface: #FFFFFF;
    --input-bg: #F1F3F5;
    --page: #F8F9FA;
}

html, body, .stApp {
    background-color: var(--page) !important;
    color: var(--ink) !important;
    font-family: 'Inter', sans-serif !important;
}

[data-testid="stHeader"] {
    height: 0 !important;
    min-height: 0 !important;
    background: transparent !important;
}
[data-testid="stToolbar"] { right: 1rem; }
[data-testid="stAppViewContainer"] > .main,
[data-testid="stAppViewBlockContainer"],
.block-container {
    max-width: 100% !important;
    padding: 0 !important;
    margin: 0 !important;
}
footer { visibility: hidden; }

/* Login split layout */
.st-key-login_shell { min-height: 100vh; padding: 0 !important; }
.st-key-login_visual {
    min-height: 100vh;
    height: 100vh;
    box-sizing: border-box;
    display: flex; flex-direction: column; justify-content: flex-end;
    padding: 7vh 5vw !important;
    background: #1A1C1E;
    border-right: 1px solid #E9E9EB;
}
.hero-text-container { padding: 1rem 0; }
.hero-title {
    font-size: clamp(2.6rem, 3.8vw, 3.6rem) !important;
    font-weight: 800 !important;
    color: #FFFFFF !important;
    line-height: 1.15 !important;
    margin-bottom: 1rem !important;
    text-shadow: 0 2px 14px rgba(0, 0, 0, 0.42);
}
.hero-subtitle {
    font-size: 1.2rem !important;
    color: #E2E8F0 !important;
    line-height: 1.6 !important;
    max-width: 460px;
    text-shadow: 0 1px 10px rgba(0, 0, 0, 0.42);
}

.st-key-login_panel {
    min-height: 100vh; display: flex; flex-direction: column; justify-content: center;
    padding: 6vh clamp(28px, 6vw, 96px) !important;
    background: #FFFFFF;
}
.fi-login-brand { display: flex; align-items: center; gap: 11px; margin-bottom: 48px; }
.fi-login-mark {
    width: 42px; height: 42px; display: grid; place-items: center; border-radius: 10px;
    background: var(--mapua-red); color: #FFFFFF; font-size: 1.35rem; font-weight: 700;
}
.fi-login-brand-name { color: #202124; font-size: 1.2rem; font-weight: 700; line-height: 1.1; }
.fi-login-brand-sub { color: #777D87; font-size: 0.76rem; margin-top: 4px; }
.fi-login-heading { margin-bottom: 28px; }
.fi-login-heading h2 { color: #202124; font-size: clamp(1.7rem, 2.2vw, 2.15rem); font-weight: 700; margin: 0 0 8px; }
.fi-login-heading p { color: #6B7280; font-size: 0.94rem; margin: 0; }

/* Fixed Form Inputs */
.st-key-login_panel [data-baseweb="input"],
.st-key-main_shell [data-baseweb="input"],
.st-key-main_shell [data-baseweb="base-input"],
.st-key-main_shell [data-baseweb="textarea"],
.st-key-main_shell [data-baseweb="select"] > div {
    background: var(--input-bg) !important;
    border: 1px solid var(--line) !important;
    border-radius: 8px !important;
}
.st-key-main_shell input,
.st-key-main_shell textarea,
.st-key-main_shell [data-baseweb="select"] span,
.st-key-main_shell [data-baseweb="select"] div,
.st-key-login_panel input {
    color: #202124 !important;
    -webkit-text-fill-color: #202124 !important;
    font-weight: 500 !important;
}
.st-key-main_shell input::placeholder,
.st-key-main_shell textarea::placeholder,
.st-key-login_panel input::placeholder {
    color: #6C757D !important;
    -webkit-text-fill-color: #6C757D !important;
    opacity: 1 !important;
}
.st-key-main_shell [data-baseweb="select"] svg { fill: #202124 !important; }
.st-key-main_shell [data-testid="stWidgetLabel"] p { color: #202124 !important; font-weight: 600; }

/* Main app layout */
.st-key-main_shell {
    width: 100%; max-width: 1180px; margin: 0 auto !important; padding: 2rem 2.25rem 3rem !important; box-sizing: border-box;
}
.fi-brand { display: flex; align-items: center; gap: 12px; }
.fi-logo {
    width: 44px; height: 44px; border-radius: 12px; background: var(--mapua-red); color: #FFFFFF;
    font-weight: 700; font-size: 1.4rem; display: flex; align-items: center; justify-content: center;
}
.fi-name { font-size: 1.4rem; font-weight: 700; line-height: 1.1; color: #202124; }
.fi-sub { color: #777D87; font-size: 0.8rem; }
.fi-user { display: flex; align-items: center; gap: 10px; justify-content: flex-end; }
.fi-avatar {
    width: 36px; height: 36px; border-radius: 50%; background: #FCE8EC; color: var(--mapua-red);
    display: flex; align-items: center; justify-content: center; font-weight: 600;
}
.fi-uname { font-weight: 600; font-size: 0.9rem; color: #202124; line-height: 1.1; }
.fi-role { color: #80868B; font-size: 0.75rem; }

/* Theme switch button styling */
.st-key-main_shell .st-key-theme_btn button {
    background: #FFFFFF !important;
    border: 1px solid #D5D8DE !important;
    border-radius: 8px !important;
    min-height: 38px !important;
    width: 42px !important;
    padding: 0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}
.st-key-main_shell .st-key-theme_btn button p { display: none !important; }

/* Grid Cards & Images (Preserves Image Visibility) */
[class*="st-key-card_"] {
    background: #FFFFFF; border: 1px solid var(--line); border-radius: 16px; padding: 14px; gap: 0.6rem;
}
.fi-img { 
    width: 100%; aspect-ratio: 4 / 3; background-size: cover; background-position: center; border-radius: 12px; 
}
.fi-noimg { background: #EAECEF; color: #6C757D; display: flex; align-items: center; justify-content: center; }
.fi-title { font-size: 1.15rem; font-weight: 600; margin: 8px 0 6px; color: #202124; }
.fi-chip { padding: 3px 10px; border-radius: 6px; font-size: 0.75rem; font-weight: 500; background: #FCE8EC; color: #9F1028; }
.fi-pending { background: #FFF4D6; color: #805B00; }
.fi-claimed { background: #E8F5EC; color: #21683A; }
.fi-desc { color: #495057; margin: 0 0 8px; font-size: 0.9rem; }
.fi-meta { color: #6C757D; font-size: 0.75rem; }
.fi-empty { text-align: center; color: #6C757D; padding: 48px 16px; border: 1px dashed var(--line); border-radius: 16px; background: #FFFFFF; }

/* File Uploader Fix */
.st-key-main_shell [data-testid="stFileUploader"] section {
    background: #F8F9FA !important; border: 1px dashed #CED4DA !important; border-radius: 12px !important;
}
.st-key-main_shell [data-testid="stFileUploader"] button {
    background: #FFFFFF !important; border: 1px solid #CED4DA !important; border-radius: 8px !important;
}
"""

    DARK_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
    --mapua-red: #D32F2F;
    --mapua-red-dark: #B71C1C;
    --ink: #E2E8F0;
    --muted: #94A3B8;
    --line: #2D3748;
    --surface: #1E293B;
    --input-bg: #0F172A;
    --page: #0B0F17;
}

html, body, .stApp {
    background-color: var(--page) !important;
    color: var(--ink) !important;
    font-family: 'Inter', sans-serif !important;
}

[data-testid="stHeader"] { height: 0 !important; background: transparent !important; }
footer { visibility: hidden; }

.st-key-login_shell { min-height: 100vh; padding: 0 !important; }
.st-key-login_visual {
    min-height: 100vh; height: 100vh; box-sizing: border-box;
    display: flex; flex-direction: column; justify-content: flex-end;
    padding: 7vh 5vw !important; background: #0F172A; border-right: 1px solid #1E293B;
}
.hero-title {
    font-size: clamp(2.6rem, 3.8vw, 3.6rem) !important; font-weight: 800 !important;
    color: #F8FAFC !important; line-height: 1.15 !important; margin-bottom: 1rem !important;
}
.hero-subtitle { font-size: 1.2rem !important; color: #94A3B8 !important; line-height: 1.6 !important; max-width: 460px; }

.st-key-login_panel {
    min-height: 100vh; display: flex; flex-direction: column; justify-content: center;
    padding: 6vh clamp(28px, 6vw, 96px) !important; background: #1E293B;
}
.fi-login-mark {
    width: 42px; height: 42px; display: grid; place-items: center; border-radius: 10px;
    background: var(--mapua-red); color: #FFFFFF; font-size: 1.35rem; font-weight: 700;
}
.fi-login-brand-name { color: #F8FAFC; font-size: 1.2rem; font-weight: 700; }
.fi-login-brand-sub { color: #94A3B8; font-size: 0.76rem; }
.fi-login-heading h2 { color: #F8FAFC; font-size: clamp(1.7rem, 2.2vw, 2.15rem); font-weight: 700; }
.fi-login-heading p { color: #94A3B8; font-size: 0.94rem; }

/* Dark Mode Form Inputs */
.st-key-login_panel [data-baseweb="input"],
.st-key-main_shell [data-baseweb="input"],
.st-key-main_shell [data-baseweb="base-input"],
.st-key-main_shell [data-baseweb="textarea"],
.st-key-main_shell [data-baseweb="select"] > div {
    background: var(--input-bg) !important;
    border: 1px solid var(--line) !important;
    border-radius: 8px !important;
}
.st-key-main_shell input,
.st-key-main_shell textarea,
.st-key-main_shell [data-baseweb="select"] span,
.st-key-main_shell [data-baseweb="select"] div,
.st-key-login_panel input {
    color: #F8FAFC !important;
    -webkit-text-fill-color: #F8FAFC !important;
}
.st-key-main_shell input::placeholder,
.st-key-main_shell textarea::placeholder,
.st-key-login_panel input::placeholder {
    color: #64748B !important;
    -webkit-text-fill-color: #64748B !important;
}
.st-key-main_shell [data-baseweb="select"] svg { fill: #F8FAFC !important; }
.st-key-main_shell [data-testid="stWidgetLabel"] p { color: #F8FAFC !important; font-weight: 600; }

/* Main Shell */
.st-key-main_shell { width: 100%; max-width: 1180px; margin: 0 auto !important; padding: 2rem 2.25rem 3rem !important; }
.fi-brand { display: flex; align-items: center; gap: 12px; }
.fi-logo { width: 44px; height: 44px; border-radius: 12px; background: var(--mapua-red); color: #FFFFFF; font-weight: 700; font-size: 1.4rem; display: flex; align-items: center; justify-content: center; }
.fi-name { font-size: 1.4rem; font-weight: 700; color: #F8FAFC; }
.fi-sub { color: #94A3B8; font-size: 0.8rem; }
.fi-user { display: flex; align-items: center; gap: 10px; justify-content: flex-end; }
.fi-avatar { width: 36px; height: 36px; border-radius: 50%; background: #331017; color: #FF8A8A; display: flex; align-items: center; justify-content: center; font-weight: 600; }
.fi-uname { font-weight: 600; font-size: 0.9rem; color: #F8FAFC; line-height: 1.1; }
.fi-role { color: #94A3B8; font-size: 0.75rem; }

/* Dark Mode Theme switch button styling */
.st-key-main_shell .st-key-theme_btn button {
    background: #1E293B !important;
    border: 1px solid #334155 !important;
    border-radius: 8px !important;
    min-height: 38px !important;
    width: 42px !important;
    padding: 0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}
.st-key-main_shell .st-key-theme_btn button p { display: none !important; }

/* Dark Mode Cards & Images (Ensures Photo Display) */
[class*="st-key-card_"] {
    background: var(--surface); border: 1px solid var(--line); border-radius: 16px; padding: 14px; gap: 0.6rem;
}
.fi-img { 
    width: 100%; aspect-ratio: 4 / 3; background-size: cover; background-position: center; border-radius: 12px; 
}
.fi-noimg { background: #0F172A; color: #64748B; display: flex; align-items: center; justify-content: center; }
.fi-title { font-size: 1.15rem; font-weight: 600; margin: 8px 0 6px; color: #F8FAFC; }
.fi-chip { padding: 3px 10px; border-radius: 6px; font-size: 0.75rem; font-weight: 500; background: #331017; color: #FF8A8A; }
.fi-pending { background: #3A2E00; color: #FFD54F; }
.fi-claimed { background: #0B3818; color: #81C784; }
.fi-desc { color: #CBD5E1; margin: 0 0 8px; font-size: 0.9rem; }
.fi-meta { color: #94A3B8; font-size: 0.75rem; }
.fi-empty { text-align: center; color: #94A3B8; padding: 48px 16px; border: 1px dashed var(--line); border-radius: 16px; background: var(--surface); }

/* File Uploader Dark */
.st-key-main_shell [data-testid="stFileUploader"] section {
    background: #0F172A !important; border: 1px dashed #334155 !important; border-radius: 12px !important;
}
.st-key-main_shell [data-testid="stFileUploader"] button {
    background: #1E293B !important; border: 1px solid #334155 !important; border-radius: 8px !important;
}
"""

    @classmethod
    def apply(cls, is_dark=False):
        selected_css = cls.DARK_CSS if is_dark else cls.LIGHT_CSS
        image_path = Path(__file__).parent / "assets" / "mapua_background.png"
        image_css = ""
        if image_path.is_file():
            image_data = base64.b64encode(image_path.read_bytes()).decode("utf-8")
            suffix = image_path.suffix.lower()
            mime_type = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
            image_css = f"""
.st-key-login_visual {{
    background-image: url("data:{mime_type};base64,{image_data}");
    background-size: cover; background-position: center center; background-repeat: no-repeat;
}}
"""
        st.markdown(f"<style>{selected_css}{image_css}</style>", unsafe_allow_html=True)


class Html:
    @staticmethod
    def esc(value):
        return html.escape(str(value or ""))


class EmptyState:
    @staticmethod
    def show(message):
        st.markdown(f'<div class="fi-empty">{Html.esc(message)}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------- session + cookies

class SessionField:
    def __init__(self, default=None):
        self._default = default

    def __set_name__(self, owner, name):
        self._key = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return st.session_state.setdefault(self._key, self._default)

    def __set__(self, obj, value):
        st.session_state[self._key] = value


class AppState:
    current_user = SessionField()
    logged_out = SessionField(False)
    pending_token = SessionField()
    pending_delete = SessionField(False)
    status_msg = SessionField()
    report_n = SessionField(0)
    report_msg = SessionField()
    service = SessionField()
    dark_mode = SessionField(False)

    def reset_navigation(self):
        st.session_state.pop("nav", None)


class CookieSession:
    NAME = "foundit_refresh_token"
    DAYS = 7

    def __init__(self, state, auth):
        self._state = state
        self._auth = auth
        self._cookies = stx.CookieManager()

    def restore(self):
        state = self._state
        if state.current_user or state.logged_out:
            return
        token = self._cookies.get(self.NAME)
        if token:
            result = self._auth.restore(token)
            if result.success:
                state.current_user = result.user
                state.pending_token = result.refresh_token
                st.rerun()

    def sync(self):
        state = self._state
        if state.pending_token and state.current_user:
            self._cookies.set(
                self.NAME,
                state.pending_token,
                expires_at=datetime.datetime.now() + datetime.timedelta(days=self.DAYS),
            )
            state.pending_token = None
        if state.pending_delete and not state.current_user:
            self._cookies.delete(self.NAME)
            state.pending_delete = False


# ---------------------------------------------------------------- views

class PostCardView:
    STATUS_CLASS = {Status.PENDING: "fi-pending", Status.CLAIMED: "fi-claimed"}

    def __init__(self, post, claimed=False, retention_days=7):
        self._post = post
        self._claimed = claimed
        self._retention_days = retention_days

    def _media(self):
        item = self._post.item
        if item.image_url:
            style = f"background-image:url('{quote(item.image_url, safe=':/?=&%#')}')"
            return f'<div class="fi-img" style="{style}"></div>'
        return '<div class="fi-img fi-noimg">No photo</div>'

    def _chips(self):
        item = self._post.item
        status = item.tracking.status
        css_class = self.STATUS_CLASS.get(status, "fi-pending")
        chips = "" if self._claimed else f'<span class="fi-chip {css_class}">{Html.esc(status)}</span>'
        chips += f'<span class="fi-chip">{Html.esc(item.campus_location)}</span><span class="fi-chip">{Html.esc(item.category.name)}</span>'
        return chips

    def _footer(self):
        if self._claimed:
            remaining = self._post.item.tracking.days_left(self._retention_days)
            return f"Removed in {remaining} day(s)" if remaining is not None else ""
        return f"Posted by {Html.esc(self._post.user.username)} on {Html.esc(self._post.date_posted)}"

    def html(self):
        item = self._post.item
        desc = f'<p class="fi-desc">{Html.esc(item.description).replace(chr(10), "<br>")}</p>' if item.description else ""
        return (
            f'{self._media()}<div class="fi-body"><div class="fi-title">{Html.esc(item.name)}</div>'
            f'<div class="fi-chips">{self._chips()}</div>{desc}<div class="fi-meta">{self._footer()}</div></div>'
        )

    def render(self, key=None):
        with st.container(key=key or f"card_{self._post.post_id}"):
            st.markdown(self.html(), unsafe_allow_html=True)


class PostGrid:
    def __init__(self, posts, claimed=False, retention_days=7, key="grid"):
        self._posts = posts
        self._claimed = claimed
        self._retention_days = retention_days
        self._key = key

    def render(self):
        cols = st.columns(2, gap="small")
        for idx, col in enumerate(cols):
            with col:
                with st.container(key=f"{self._key}_col_{idx}"):
                    for post in self._posts[idx::2]:
                        PostCardView(post, self._claimed, self._retention_days).render()


class LoginView:
    def __init__(self, auth, state, institution):
        self._auth = auth
        self._state = state
        self._institution = institution

    def render(self):
        with st.container(key="login_shell"):
            visual, panel = st.columns([1.45, 1], gap=None)

            with visual:
                with st.container(key="login_visual"):
                    st.markdown(
                        '<div class="hero-text-container">'
                        '<div class="hero-title">Lost something?<br>Find it here.</div>'
                        '<div class="hero-subtitle">A campus lost-and-found space for the Mapúa MCM community. '
                        'Sign in to report, browse, and keep track of items.</div>'
                        '</div>',
                        unsafe_allow_html=True,
                    )

            with panel:
                with st.container(key="login_panel"):
                    st.markdown(
                        '<div class="fi-login-brand">'
                        '<div class="fi-login-mark">F</div>'
                        '<div><div class="fi-login-brand-name">FoundIt</div>'
                        '<div class="fi-login-brand-sub">Mapúa Malayan Colleges Mindanao</div></div>'
                        '</div>'
                        '<div class="fi-login-heading"><h2>Welcome back</h2>'
                        '<p>Sign in using your institutional account.</p></div>',
                        unsafe_allow_html=True,
                    )

                    with st.form("login_form"):
                        email = st.text_input("Institutional Email", placeholder="name@mcm.edu.ph")
                        password = st.text_input("Password", type="password", placeholder="Enter your password")
                        submitted = st.form_submit_button("Sign in")

                    st.markdown(
                        '<div class="fi-login-footnote">For Mapúa MCM students and authorized personnel.</div>',
                        unsafe_allow_html=True,
                    )

                    if submitted:
                        result = self._auth.login(email, password)
                        if result.success:
                            self._state.current_user = result.user
                            self._state.logged_out = False
                            self._state.pending_token = result.refresh_token
                            st.rerun()
                        else:
                            st.error(f"Authentication failed: {result.error}")


class AppBar:
    MOON_SVG = """<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#202124" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>"""
    SUN_SVG = """<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>"""

    def __init__(self, institution, user, state):
        self._institution = institution
        self._user = user
        self._state = state

    def render(self):
        c_brand, c_controls = st.columns([5, 5], vertical_alignment="center")
        with c_brand:
            st.markdown(
                f'<div class="fi-brand"><div class="fi-logo">F</div><div><div class="fi-name">FoundIt</div>'
                f'<div class="fi-sub">{Html.esc(self._institution.get_details())}</div></div></div>',
                unsafe_allow_html=True,
            )
        with c_controls:
            c_btn, c_user, c_out = st.columns([0.6, 2.8, 1.2], vertical_alignment="center")
            with c_btn:
                with st.container(key="theme_btn"):
                    icon_svg = self.SUN_SVG if self._state.dark_mode else self.MOON_SVG
                    st.markdown(f'<div style="position: absolute; pointer-events: none; margin-top: 8px; margin-left: 11px;">{icon_svg}</div>', unsafe_allow_html=True)
                    if st.button("", key="theme_toggle_click", help="Toggle Theme"):
                        self._state.dark_mode = not self._state.dark_mode
                        st.rerun()
            with c_user:
                st.markdown(
                    f'<div class="fi-user"><div class="fi-avatar">{Html.esc(self._user.avatar_initial)}</div>'
                    f'<div><div class="fi-uname">{Html.esc(self._user.username)}</div>'
                    f'<div class="fi-role">{Html.esc(self._user.role_label)}</div></div></div>',
                    unsafe_allow_html=True,
                )
            with c_out:
                return st.button("Logout", key="logout")


# ---------------------------------------------------------------- pages

class Page(ABC):
    title = ""
    ALL_CAMPUSES = "All Campuses"

    def __init__(self, service, state):
        self._service = service
        self._state = state

    def _campus_filter(self, key):
        options = [self.ALL_CAMPUSES, *self._service.institution.campuses]
        choice = st.selectbox("Campus", options, key=key, label_visibility="collapsed")
        return None if choice == self.ALL_CAMPUSES else choice

    @abstractmethod
    def render(self, user):
        ...


class AdminPage(Page):
    def render(self, user):
        if not user.can_manage_items():
            st.error("Only administrators can open this page.")
            return
        self._render(user)

    @abstractmethod
    def _render(self, user):
        ...


class FeedPage(Page):
    title = "Feed"

    def _render_possible_matches(self, query, campus, shown):
        shown_ids = {post.post_id for post in shown}
        matches = tuple(
            post for post in self._service.possible_matches(query, campus)
            if post.post_id not in shown_ids
        )
        if not matches:
            return
        st.markdown("#### Possible matches")
        st.caption("is this what you were looking for? try searching the items from the selected campus first.")
        PostGrid(matches, retention_days=self._service.RETENTION_DAYS, key="match_grid").render()

    def render(self, user):
        summary = self._service.summary()
        st.caption(f"{summary.active} unclaimed items · {summary.claimed} claimed items")

        col_search, col_campus = st.columns([3, 1])
        with col_search:
            query = st.text_input(
                "Search", "", key="feed_search", placeholder="Search by name, category or description", label_visibility="collapsed"
            )
        with col_campus:
            campus = self._campus_filter("feed_campus")

        posts = self._service.active(campus, query)
        if not posts:
            EmptyState.show("No items match your search or filter.")
        else:
            PostGrid(posts, retention_days=self._service.RETENTION_DAYS).render()

        self._render_possible_matches(query, campus, posts)


class ClaimedPage(Page):
    title = "Claimed"

    def render(self, user):
        st.caption(f"Claimed items stay here for {self._service.RETENTION_DAYS} days, then are removed automatically.")
        col_search, col_campus = st.columns([3, 1])
        with col_search:
            query = st.text_input(
                "Search", "", key="claimed_search", placeholder="Search by name, category or description", label_visibility="collapsed"
            )
        with col_campus:
            campus = self._campus_filter("claimed_campus")

        posts = self._service.claimed(campus, query)
        if not posts:
            EmptyState.show("No claimed items match your search or filter.")
        else:
            PostGrid(posts, claimed=True, retention_days=self._service.RETENTION_DAYS).render()


class ReportPage(AdminPage):
    title = "Report"

    def _photo_section(self, rk):
        photo = st.file_uploader("Item Photo", type=["jpg", "jpeg", "png"], key=f"r_photo_{rk}")
        if photo is not None:
            st.image(photo, caption=photo.name)
        return photo

    def _details_section(self, user, rk, photo):
        name = st.text_input("Item Name", key=f"r_name_{rk}")
        description = st.text_area("Description / Distinguishing Features", key=f"r_desc_{rk}")
        campus = st.selectbox("Campus Holding Office", self._service.institution.campuses, key=f"r_campus_{rk}")
        category = st.selectbox("Category", self._service.catalog.names(), key=f"r_cat_{rk}")

        if st.button("Post Item", key="post_item"):
            try:
                self._service.report(user, name, description, category, campus, photo)
            except ValidationError as e:
                st.warning(str(e))
            except BackendError as e:
                st.error(str(e))
            else:
                self._state.report_n += 1
                self._state.report_msg = "Item posted successfully and saved to Supabase!"
                st.rerun()

    def _render(self, user):
        rk = self._state.report_n
        if self._state.report_msg:
            st.success(self._state.report_msg)
            self._state.report_msg = None

        left, right = st.columns(2, gap="large")
        with left:
            photo = self._photo_section(rk)
        with right:
            self._details_section(user, rk, photo)


class UpdateStatusPage(AdminPage):
    title = "Update status"

    @staticmethod
    def _label(post):
        return f"{post.item.name} ({post.item.tracking.status}) - {post.user.username}"

    def _render(self, user):
        if self._state.status_msg:
            st.success(self._state.status_msg)
            self._state.status_msg = None

        posts = self._service.posts
        if not posts:
            EmptyState.show("No items available to update.")
            return

        by_id = {p.post_id: p for p in posts}
        left, right = st.columns(2, gap="large")
        with left:
            selected_id = st.selectbox("Select Item to Update", list(by_id.keys()), format_func=lambda pid: self._label(by_id[pid]))
            new_status = st.radio("Select New Status", list(Status.ALL), horizontal=True)
            apply_update = st.button("Apply Status Update")
        with right:
            PostCardView(by_id[selected_id], retention_days=self._service.RETENTION_DAYS).render(key="card_preview")

        if apply_update:
            try:
                self._service.set_status(user, selected_id, new_status)
            except ValidationError as e:
                st.warning(str(e))
            except BackendError as e:
                st.error(str(e))
            else:
                self._state.status_msg = f"Status updated to **{new_status}** in Supabase!"
                st.rerun()


# ---------------------------------------------------------------- application

class FoundItApp:
    PAGES = (FeedPage, ClaimedPage, ReportPage, UpdateStatusPage)

    def __init__(self):
        self._backend = get_backend()
        self._users = UserFactory.from_setting(st.secrets.get("ADMIN_EMAILS", ""))
        self._state = AppState()
        self._auth = AuthService(self._backend, self._users)
        self._cookies = CookieSession(self._state, self._auth)
        self._institution = Institution("Mapúa Malayan Colleges Mindanao", "Davao City", ["RSY Building", "RG Birrey"])

    def _service(self):
        if self._state.service is None:
            catalog = CategoryCatalog.default()
            repository = SupabasePostRepository(self._backend, catalog, self._users, self._institution.default_campus)
            self._state.service = LostAndFoundService(repository, SupabaseImageStorage(self._backend), catalog, self._institution, matcher=get_matcher())
        return self._state.service

    def _logout(self):
        self._state.current_user = None
        self._state.logged_out = True
        self._state.pending_delete = True
        self._state.service = None
        self._state.reset_navigation()
        st.rerun()

    def _render_main(self, user):
        with st.container(key="main_shell"):
            if AppBar(self._institution, user, self._state).render():
                self._logout()

            try:
                service = self._service()
                service.refresh_if_stale()
            except BackendError as exc:
                st.error(f"Could not load items from the database. {exc}")
                return

            if not user.can_manage_items():
                st.caption("Standard account: only administrators can report or update items.")

            navigation = st.pills("Section", user.sections(), default="Feed", key="nav", label_visibility="collapsed") or "Feed"
            pages = {cls.title: cls(service, self._state) for cls in self.PAGES}
            pages.get(navigation, pages["Feed"]).render(user)

    def run(self):
        Theme.apply(is_dark=self._state.dark_mode)
        self._cookies.restore()
        self._cookies.sync()
        user = self._state.current_user
        if user is None:
            LoginView(self._auth, self._state, self._institution).render()
        else:
            self._render_main(user)


def main():
    st.set_page_config(page_title="FoundIt - Campus Lost & Found", page_icon="F", layout="wide")
    try:
        app = FoundItApp()
    except (BackendError, BackendValidationError) as exc:
        st.error(f"FoundIt is not configured correctly: {exc}")
        return
    app.run()


main()
