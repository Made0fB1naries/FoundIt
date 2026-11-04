# app.py
import html
import datetime
import base64
from pathlib import Path
from abc import ABC, abstractmethod
from urllib.parse import quote

import streamlit as st
import extra_streamlit_components as stx

from models import (AuthService, CategoryCatalog, Institution, LostAndFoundService,
                    Status, SupabaseImageStorage, SupabasePostRepository, ValidationError, get_gateway)


# ---------------------------------------------------------------- UI redesign

class Theme:
    CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
    --mapua-red: #C8102E;
    --mapua-red-dark: #A80D26;
    --ink: #202124;
    --muted: #6B7280;
    --line: #E5E7EB;
    --surface: #FFFFFF;
    --page: #F7F7F8;
}

html, body {
    margin: 0 !important;
    padding: 0 !important;
}
html, body, .stApp, button, input, textarea, label, p, h1, h2, h3 {
    font-family: 'Inter', sans-serif;
}
.stApp {
    background: var(--page);
    color: var(--ink);
}
[data-testid="stHeader"] {
    height: 0 !important;
    min-height: 0 !important;
    background: transparent !important;
}
[data-testid="stToolbar"] { right: 1rem; }
[data-testid="stAppViewContainer"] > .main,
[data-testid="stAppViewContainer"] > .main > div,
[data-testid="stAppViewBlockContainer"],
[data-testid="stMainBlockContainer"],
.block-container {
    max-width: 100% !important;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
    margin-top: 0 !important;
}
footer { visibility: hidden; }

/* Login split layout */
.st-key-login_shell {
    min-height: 100vh;
    padding: 0 !important;
}
.st-key-login_visual {
    min-height: 100vh;
    height: 100vh;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    padding: 7vh 5vw !important;
    background: #F1F1F2;
    border-right: 1px solid #E9E9EB;
}
.st-key-login_visual h1 {
    color: #FFFFFF !important;
    text-shadow: 0 2px 14px rgba(0, 0, 0, 0.42);
    font-size: clamp(2rem, 3.2vw, 3.3rem);
    line-height: 1.08;
    letter-spacing: -0.045em;
    font-weight: 700;
    margin: 0 0 14px;
}
.st-key-login_visual p {
    color: #FFFFFF !important;
    text-shadow: 0 1px 10px rgba(0, 0, 0, 0.42);
    font-size: 1rem;
    line-height: 1.65;
    max-width: 430px;
}
.st-key-login_panel {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 6vh clamp(28px, 6vw, 96px) !important;
    background: #FFFFFF;
}
.fi-login-brand {
    display: flex;
    align-items: center;
    gap: 11px;
    margin-bottom: 48px;
}
.fi-login-mark {
    width: 42px;
    height: 42px;
    display: grid;
    place-items: center;
    border-radius: 10px;
    background: var(--mapua-red);
    color: #FFFFFF;
    font-size: 1.35rem;
    font-weight: 700;
}
.fi-login-brand-name {
    color: #202124;
    font-size: 1.2rem;
    font-weight: 700;
    line-height: 1.1;
}
.fi-login-brand-sub {
    color: #777D87;
    font-size: 0.76rem;
    margin-top: 4px;
}
.fi-login-heading {
    margin-bottom: 28px;
}
.fi-login-heading h2 {
    color: #202124;
    font-size: clamp(1.7rem, 2.2vw, 2.15rem);
    font-weight: 700;
    letter-spacing: -0.035em;
    margin: 0 0 8px;
}
.fi-login-heading p {
    color: #6B7280;
    font-size: 0.94rem;
    margin: 0;
}
.st-key-login_panel [data-testid="stForm"] {
    background: transparent;
    border: 0;
    border-radius: 0;
    padding: 0;
}
.st-key-login_panel [data-testid="stTextInput"] label {
    color: #343A40;
    font-size: 0.86rem;
    font-weight: 600;
    margin-bottom: 7px;
}
.st-key-login_panel [data-baseweb="input"] {
    min-height: 46px;
    border: 1px solid #D9DDE3 !important;
    border-radius: 8px;
    background: #F3F4F6 !important;
    box-shadow: none !important;
}
.st-key-login_panel [data-baseweb="input"] > div {
    background: #F3F4F6 !important;
}
.st-key-login_panel [data-baseweb="input"]:focus-within {
    border-color: var(--mapua-red);
    box-shadow: 0 0 0 1px var(--mapua-red);
}
.st-key-login_panel input {
    color: #202124 !important;
    background: #F3F4F6 !important;
    font-size: 0.93rem;
}
.st-key-login_panel input::placeholder {
    color: #8A9099 !important;
    opacity: 1;
}
.st-key-login_panel .stFormSubmitButton > button {
    width: 100%;
    min-height: 46px;
    margin-top: 12px;
    border: 1px solid var(--mapua-red);
    border-radius: 8px;
    background: var(--mapua-red);
    transition: background 0.15s ease, border-color 0.15s ease;
}
.st-key-login_panel .stFormSubmitButton > button:hover {
    background: var(--mapua-red-dark);
    border-color: var(--mapua-red-dark);
}
.st-key-login_panel .stFormSubmitButton > button p {
    color: #FFFFFF;
    font-weight: 600;
}
.fi-login-footnote {
    color: #8A9099;
    font-size: 0.76rem;
    margin-top: 26px;
    line-height: 1.5;
}
@media (max-width: 800px) {
    .st-key-login_visual {
        min-height: 34vh;
        height: auto;
        padding: 38px 28px 24px !important;
        border-right: 0;
    }
    .st-key-login_visual h1 { font-size: 1.8rem; }
    .st-key-login_visual p { font-size: 0.9rem; }
    .st-key-login_panel {
        min-height: 66vh;
        padding: 38px 28px !important;
    }
    .fi-login-brand { margin-bottom: 32px; }
}

/* Main application */
.st-key-main_shell {
    width: 100%;
    max-width: 1180px;
    margin-left: auto !important;
    margin-right: auto !important;
    padding: 2rem 2.25rem 3rem !important;
    box-sizing: border-box;
}
@media (max-width: 800px) {
    .st-key-main_shell {
        padding: 1.25rem 1rem 2rem !important;
    }
}
.fi-brand { display: flex; align-items: center; gap: 12px; }
.fi-logo {
    width: 44px; height: 44px; border-radius: 12px;
    background: var(--mapua-red); color: #FFFFFF;
    font-weight: 700; font-size: 1.4rem;
    display: flex; align-items: center; justify-content: center;
}
.fi-name { font-size: 1.4rem; font-weight: 700; line-height: 1.1; }
.fi-sub { color: #777D87; font-size: 0.8rem; }
.fi-user { display: flex; align-items: center; gap: 10px; justify-content: flex-end; }
.fi-avatar {
    width: 36px; height: 36px; border-radius: 50%;
    background: #FCE8EC; color: var(--mapua-red);
    display: flex; align-items: center; justify-content: center; font-weight: 600;
}
.fi-uname { font-weight: 600; font-size: 0.9rem; line-height: 1.1; }
.fi-role { color: #80868B; font-size: 0.75rem; }
.fi-welcome { text-align: center; margin: 2rem 0 1rem; }
.fi-welcome .fi-logo { margin: 0 auto 16px; width: 56px; height: 56px; font-size: 1.8rem; }
.fi-welcome h2 { margin: 0; font-weight: 700; }
.fi-welcome p { color: #80868B; margin: 4px 0 0; }
[data-testid="stBaseButton-pills"], [data-testid="stBaseButton-pillsActive"] {
    border-radius: 8px !important; padding: 6px 18px !important;
}
[data-testid="stBaseButton-pillsActive"] {
    background: #FCE8EC !important; border-color: #F2B8C4 !important;
}
[data-testid="stBaseButton-pillsActive"] p { color: var(--mapua-red) !important; font-weight: 600; }
.st-key-grid_col_0, .st-key-grid_col_1 { gap: 1rem !important; }
[class*="st-key-card_"] {
    background: #FFFFFF; border: 1px solid #E7E8EB;
    border-radius: 16px; padding: 12px; gap: 0.6rem;
}
[class*="st-key-card_"]:hover { border-color: #D8A0AA; }
.fi-img {
    width: 100%; aspect-ratio: 4 / 3; background-size: cover;
    background-position: center; border-radius: 12px;
}
.fi-noimg { background: #F1F2F4; color: #777D87; display: flex; align-items: center; justify-content: center; }
.fi-body { padding: 8px 6px 4px; }
.fi-title { font-size: 1.15rem; font-weight: 600; margin: 0 0 8px; }
.fi-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
.fi-chip { padding: 3px 10px; border-radius: 6px; font-size: 0.75rem; font-weight: 500; background: #FCE8EC; color: #9F1028; }
.fi-pending { background: #FFF4D6; color: #805B00; }
.fi-claimed { background: #E8F5EC; color: #21683A; }
.fi-desc { color: #555B65; margin: 0 0 8px; font-size: 0.9rem; }
.fi-meta { color: #80868B; font-size: 0.75rem; }
.fi-empty { text-align: center; color: #80868B; padding: 48px 16px; border: 1px dashed #D5D8DE; border-radius: 16px; }
.stButton > button, .stFormSubmitButton > button {
    width: 100%; background: var(--mapua-red); border: 1px solid var(--mapua-red);
    border-radius: 8px; padding: 0.5rem 1.5rem;
}
.stButton > button:hover, .stFormSubmitButton > button:hover { background: var(--mapua-red-dark); }
.stButton > button p, .stFormSubmitButton > button p { color: #FFFFFF; font-weight: 600; }
.st-key-logout button { background: transparent !important; border: 1px solid #D5D8DE !important; }
.st-key-logout button p { color: #444B55 !important; }
[data-testid="stForm"] { background: #FFFFFF; border: 1px solid #E7E8EB; border-radius: 16px; padding: 20px; }
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"], [data-baseweb="select"] > div { border-radius: 8px !important; }
.st-key-feed_search [data-baseweb="input"], .st-key-feed_search [data-baseweb="base-input"], .st-key-feed_search input,
.st-key-claimed_search [data-baseweb="input"], .st-key-claimed_search [data-baseweb="base-input"], .st-key-claimed_search input { border-radius: 999px !important; }
.st-key-feed_search input, .st-key-claimed_search input { padding-left: 18px !important; }
.st-key-feed_campus [data-baseweb="select"] > div, .st-key-claimed_campus [data-baseweb="select"] > div { border-radius: 999px !important; }
[data-testid="stImage"] img { border-radius: 12px; }

/* MCM light palette: improve contrast throughout the signed-in app */
:root {
    --fi-text: #24232B;
    --fi-secondary: #55515D;
    --fi-muted: #706B78;
    --fi-red: #B5122B;
    --fi-red-hover: #940E23;
    --fi-border: #DEDDE3;
    --fi-input: #F4F3F6;
    --fi-soft-red: #FBE9ED;
}

/* Streamlit text, headings, captions and widget labels */
.st-key-main_shell,
.st-key-main_shell [data-testid="stMarkdown"],
.st-key-main_shell [data-testid="stMarkdown"] p,
.st-key-main_shell [data-testid="stMarkdown"] li,
.st-key-main_shell [data-testid="stMarkdown"] span,
.st-key-main_shell [data-testid="stCaptionContainer"],
.st-key-main_shell [data-testid="stCaptionContainer"] p,
.st-key-main_shell label,
.st-key-main_shell legend,
.st-key-main_shell [data-testid="stWidgetLabel"] p {
    color: var(--fi-text) !important;
}
.st-key-main_shell h1,
.st-key-main_shell h2,
.st-key-main_shell h3,
.st-key-main_shell h4 {
    color: #211F27 !important;
    font-weight: 700;
}
.st-key-main_shell [data-testid="stCaptionContainer"] p,
.st-key-main_shell .fi-sub,
.st-key-main_shell .fi-role,
.st-key-main_shell .fi-meta {
    color: var(--fi-muted) !important;
}
.st-key-main_shell .fi-title {
    color: #211F27 !important;
}
.st-key-main_shell .fi-desc {
    color: #514D58 !important;
}
.st-key-main_shell .fi-empty {
    color: #625D69 !important;
    background: #FFFFFF;
}

/* Inputs, text areas and dropdowns */
.st-key-main_shell [data-baseweb="input"],
.st-key-main_shell [data-baseweb="base-input"],
.st-key-main_shell [data-baseweb="textarea"],
.st-key-main_shell [data-baseweb="select"] > div {
    background: var(--fi-input) !important;
    border: 1px solid var(--fi-border) !important;
    color: var(--fi-text) !important;
    box-shadow: none !important;
}
.st-key-main_shell input,
.st-key-main_shell textarea {
    color: var(--fi-text) !important;
    background: transparent !important;
    -webkit-text-fill-color: var(--fi-text) !important;
}
.st-key-main_shell input::placeholder,
.st-key-main_shell textarea::placeholder {
    color: #817B88 !important;
    -webkit-text-fill-color: #817B88 !important;
    opacity: 1 !important;
}
.st-key-main_shell [data-baseweb="select"] *,
.st-key-main_shell [data-baseweb="popover"] *,
[data-baseweb="menu"] * {
    color: var(--fi-text) !important;
}
.st-key-main_shell [data-baseweb="select"] svg {
    fill: #625D69 !important;
}

/* Consistent MCM-red primary buttons and readable neutral buttons */
.st-key-main_shell .stButton > button,
.st-key-main_shell .stFormSubmitButton > button,
.st-key-main_shell [data-testid^="stBaseButton-"] {
    background: var(--fi-red) !important;
    color: #FFFFFF !important;
    border: 1px solid var(--fi-red) !important;
    border-radius: 8px !important;
    box-shadow: none !important;
}
.st-key-main_shell .stButton > button:hover,
.st-key-main_shell .stFormSubmitButton > button:hover,
.st-key-main_shell [data-testid^="stBaseButton-"]:hover {
    background: var(--fi-red-hover) !important;
    border-color: var(--fi-red-hover) !important;
}
.st-key-main_shell .stButton > button *,
.st-key-main_shell .stFormSubmitButton > button *,
.st-key-main_shell [data-testid^="stBaseButton-"] * {
    color: #FFFFFF !important;
    fill: #FFFFFF !important;
}

/* Logout remains a quiet outlined button */
.st-key-main_shell .st-key-logout button {
    background: #FFFFFF !important;
    color: #514D58 !important;
    border: 1px solid #D5D2DA !important;
}
.st-key-main_shell .st-key-logout button *,
.st-key-main_shell .st-key-logout button svg {
    color: #514D58 !important;
    fill: #514D58 !important;
}
.st-key-main_shell .st-key-logout button:hover {
    background: #FBE9ED !important;
    border-color: #E7AAB6 !important;
}

/* Selected navigation pills use a soft red surface; inactive pills stay white */
.st-key-main_shell [data-testid="stBaseButton-pillsActive"] {
    background: #FBE9ED !important;
    border: 1px solid #E7AAB6 !important;
}
.st-key-main_shell [data-testid="stBaseButton-pillsActive"] *,
.st-key-main_shell [data-testid="stBaseButton-pillsActive"] p {
    color: #9F1028 !important;
}
.st-key-main_shell [data-testid="stBaseButton-pills"] {
    background: #FFFFFF !important;
    border: 1px solid #DEDDE3 !important;
}
.st-key-main_shell [data-testid="stBaseButton-pills"] *,
.st-key-main_shell [data-testid="stBaseButton-pills"] p {
    color: #514D58 !important;
}

/* Radio buttons, checkboxes and switches */
.st-key-main_shell [data-testid="stRadio"] label,
.st-key-main_shell [data-testid="stCheckbox"] label,
.st-key-main_shell [data-testid="stToggle"] label {
    color: var(--fi-text) !important;
}
.st-key-main_shell [data-testid="stRadio"] [aria-checked="true"],
.st-key-main_shell [data-testid="stCheckbox"] [aria-checked="true"] {
    color: var(--fi-red) !important;
}

/* Soft grey controls across Feed, Claimed, and Report */
.st-key-main_shell [data-baseweb="input"],
.st-key-main_shell [data-baseweb="base-input"],
.st-key-main_shell [data-baseweb="textarea"],
.st-key-main_shell [data-baseweb="select"] > div,
.st-key-main_shell [data-testid="stDateInput"] input,
.st-key-main_shell [data-testid="stNumberInput"] input {
    background: #F3F4F6 !important;
    border: 1px solid #D8DADF !important;
    border-radius: 8px !important;
    box-shadow: none !important;
}
.st-key-main_shell [data-baseweb="input"] > div,
.st-key-main_shell [data-baseweb="base-input"] > div,
.st-key-main_shell [data-baseweb="textarea"] > div,
.st-key-main_shell [data-baseweb="select"] > div {
    background: #F3F4F6 !important;
}
.st-key-main_shell input,
.st-key-main_shell textarea,
.st-key-main_shell [data-baseweb="select"] *,
.st-key-main_shell [data-testid="stNumberInput"] input {
    color: #292730 !important;
    -webkit-text-fill-color: #292730 !important;
}
.st-key-main_shell input::placeholder,
.st-key-main_shell textarea::placeholder {
    color: #77737D !important;
    -webkit-text-fill-color: #77737D !important;
    opacity: 1 !important;
}
.st-key-main_shell [data-baseweb="input"]:focus-within,
.st-key-main_shell [data-baseweb="textarea"]:focus-within,
.st-key-main_shell [data-baseweb="select"]:focus-within {
    border-color: #B8B5BE !important;
    box-shadow: 0 0 0 1px #B8B5BE !important;
}

/* Buttons use the same quiet grey surface as the login input fields */
.st-key-main_shell .stButton > button,
.st-key-main_shell .stFormSubmitButton > button,
.st-key-main_shell [data-testid^="stBaseButton-"] {
    background: #F3F4F6 !important;
    color: #34313B !important;
    border: 1px solid #D8DADF !important;
    border-radius: 8px !important;
    box-shadow: none !important;
}
.st-key-main_shell .stButton > button:hover,
.st-key-main_shell .stFormSubmitButton > button:hover,
.st-key-main_shell [data-testid^="stBaseButton-"]:hover {
    background: #E7E8EB !important;
    border-color: #C9CBD1 !important;
}
.st-key-main_shell .stButton > button *,
.st-key-main_shell .stFormSubmitButton > button *,
.st-key-main_shell [data-testid^="stBaseButton-"] * {
    color: #34313B !important;
    fill: #34313B !important;
}

/* Search and campus filters have a soft grey pill appearance */
.st-key-main_shell .st-key-feed_search [data-baseweb="input"],
.st-key-main_shell .st-key-claimed_search [data-baseweb="input"],
.st-key-main_shell .st-key-feed_campus [data-baseweb="select"] > div,
.st-key-main_shell .st-key-claimed_campus [data-baseweb="select"] > div {
    background: #F3F4F6 !important;
    border: 1px solid #D8DADF !important;
}
.st-key-main_shell .st-key-feed_search input,
.st-key-main_shell .st-key-claimed_search input {
    background: transparent !important;
    color: #292730 !important;
}

/* Report tab uploader/drop area */
.st-key-main_shell [data-testid="stFileUploader"] section,
.st-key-main_shell [data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"] {
    background: #F3F4F6 !important;
    border: 1px dashed #C9CBD1 !important;
    border-radius: 10px !important;
}
.st-key-main_shell [data-testid="stFileUploader"] *,
.st-key-main_shell [data-testid="stFileUploader"] small {
    color: #514D58 !important;
}
.st-key-main_shell [data-testid="stFileUploader"] button {
    background: #E7E8EB !important;
    color: #34313B !important;
    border: 1px solid #D0D2D8 !important;
}
.st-key-main_shell [data-testid="stFileUploader"] button * {
    color: #34313B !important;
}

/* Radio controls and labels in the report/status forms */
.st-key-main_shell [data-testid="stRadio"] label,
.st-key-main_shell [data-testid="stCheckbox"] label,
.st-key-main_shell [data-testid="stWidgetLabel"] p {
    color: #34313B !important;
}
.st-key-main_shell [data-testid="stRadio"] [data-baseweb="radio"] div:first-child {
    border-color: #77737D !important;
}

/* Form surfaces and feedback blocks */
.st-key-main_shell [data-testid="stForm"] {
    background: #FFFFFF !important;
    border: 1px solid #E5E2E8 !important;
}
.st-key-main_shell [data-testid="stAlert"] {
    color: #302D35 !important;
    border-radius: 10px;
}
.st-key-main_shell [data-testid="stAlert"] p {
    color: inherit !important;
}

/* High-contrast grey controls requested for the signed-in pages.
   Login fields are intentionally excluded. */
:root {
    --fi-control-grey: #666B75;
    --fi-control-grey-hover: #555A64;
    --fi-control-border: #555A64;
    --fi-control-white: #FFFFFF;
    --fi-control-placeholder: #F0F1F3;
}

/* Main navigation: Feed, Claimed, Report, Update status */
.st-key-main_shell [data-testid="stBaseButton-pills"],
.st-key-main_shell [data-testid="stBaseButton-pillsActive"] {
    background: var(--fi-control-grey) !important;
    border: 1px solid var(--fi-control-border) !important;
    color: var(--fi-control-white) !important;
    border-radius: 8px !important;
}
.st-key-main_shell [data-testid="stBaseButton-pills"] *,
.st-key-main_shell [data-testid="stBaseButton-pillsActive"] *,
.st-key-main_shell [data-testid="stBaseButton-pills"] p,
.st-key-main_shell [data-testid="stBaseButton-pillsActive"] p {
    color: var(--fi-control-white) !important;
    fill: var(--fi-control-white) !important;
    opacity: 1 !important;
}
.st-key-main_shell [data-testid="stBaseButton-pills"]:hover,
.st-key-main_shell [data-testid="stBaseButton-pillsActive"]:hover {
    background: var(--fi-control-grey-hover) !important;
    border-color: var(--fi-control-grey-hover) !important;
}

/* Feed and Claimed search fields, plus all Report and Update Status fields */
.st-key-main_shell .st-key-feed_search [data-baseweb="input"],
.st-key-main_shell .st-key-claimed_search [data-baseweb="input"],
.st-key-main_shell [data-testid="stTextInput"] [data-baseweb="input"],
.st-key-main_shell [data-testid="stTextArea"] [data-baseweb="textarea"],
.st-key-main_shell [data-testid="stSelectbox"] [data-baseweb="select"] > div {
    background: var(--fi-control-grey) !important;
    border: 1px solid var(--fi-control-border) !important;
    border-radius: 8px !important;
    box-shadow: none !important;
}
.st-key-main_shell .st-key-feed_search input,
.st-key-main_shell .st-key-claimed_search input,
.st-key-main_shell [data-testid="stTextInput"] input,
.st-key-main_shell [data-testid="stTextArea"] textarea {
    background: transparent !important;
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
    caret-color: #FFFFFF !important;
}
.st-key-main_shell .st-key-feed_search input::placeholder,
.st-key-main_shell .st-key-claimed_search input::placeholder,
.st-key-main_shell [data-testid="stTextInput"] input::placeholder,
.st-key-main_shell [data-testid="stTextArea"] textarea::placeholder {
    color: var(--fi-control-placeholder) !important;
    -webkit-text-fill-color: var(--fi-control-placeholder) !important;
    opacity: 1 !important;
}

/* Campus filters and the item/campus/category selectors */
.st-key-main_shell [data-testid="stSelectbox"] [data-baseweb="select"] > div,
.st-key-main_shell [data-testid="stSelectbox"] [data-baseweb="select"] > div *,
.st-key-main_shell [data-testid="stSelectbox"] [data-baseweb="select"] svg {
    color: #FFFFFF !important;
    fill: #FFFFFF !important;
}
.st-key-main_shell [data-testid="stSelectbox"] [data-baseweb="select"] [data-testid="stSelectboxVirtualDropdown"] {
    color: #24232B !important;
}
/* The opened dropdown menu remains white with dark text for readability. */
.st-key-main_shell [data-baseweb="popover"] [role="option"],
.st-key-main_shell [data-baseweb="popover"] [role="option"] *,
[data-baseweb="menu"] [role="option"],
[data-baseweb="menu"] [role="option"] * {
    background: #FFFFFF !important;
    color: #24232B !important;
}

/* Update Status: Pending Claim and Claimed radio choices */
.st-key-main_shell [data-testid="stRadio"] [role="radiogroup"] label {
    background: var(--fi-control-grey) !important;
    border: 1px solid var(--fi-control-border) !important;
    border-radius: 8px !important;
    padding: 8px 14px !important;
    margin-right: 8px !important;
}
.st-key-main_shell [data-testid="stRadio"] [role="radiogroup"] label *,
.st-key-main_shell [data-testid="stRadio"] [role="radiogroup"] label p,
.st-key-main_shell [data-testid="stRadio"] [role="radiogroup"] label span {
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
}
.st-key-main_shell [data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) {
    background: var(--fi-control-grey-hover) !important;
    border-color: #3F444D !important;
}

/* Keep field labels dark on the white page, not white on grey. */
.st-key-main_shell [data-testid="stWidgetLabel"] p,
.st-key-main_shell [data-testid="stTextInput"] label,
.st-key-main_shell [data-testid="stTextArea"] label,
.st-key-main_shell [data-testid="stSelectbox"] label,
.st-key-main_shell [data-testid="stRadio"] > label {
    color: #292730 !important;
}

"""

    @classmethod
    def apply(cls):
        image_path = Path(__file__).parent / "assets" / "mapua_background.png"
        image_css = ""
        if image_path.is_file():
            image_data = base64.b64encode(image_path.read_bytes()).decode("utf-8")
            suffix = image_path.suffix.lower()
            mime_type = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
            image_css = f"""
.st-key-login_visual {{
    background-image: url("data:{mime_type};base64,{image_data}");
    background-size: cover;
    background-position: center center;
    background-repeat: no-repeat;
}}
"""
        st.markdown(f"<style>{cls.CSS}{image_css}</style>", unsafe_allow_html=True)


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
    """Descriptor: an attribute stored in st.session_state."""

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

    def reset_navigation(self):
        st.session_state.pop("nav", None)


class CookieSession:
    NAME = "foundit_refresh_token"
    DAYS = 7

    def __init__(self, state, auth):
        self._state = state
        self._auth = auth
        self._cookies = stx.CookieManager()

    def restore(self):  # auto-login, survives page refresh
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

    def sync(self):  # write / clear the cookie safely
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
        chips = "" if self._claimed else f'<span class="fi-chip {self.STATUS_CLASS[status]}">{Html.esc(status.value)}</span>'
        chips += f'<span class="fi-chip">{Html.esc(item.campus_location)}</span><span class="fi-chip">{Html.esc(item.category.name)}</span>'
        return chips

    def _footer(self):
        if self._claimed:
            remaining = self._post.item.tracking.days_left(self._retention_days)
            return f"Removed in {remaining} day(s)" if remaining is not None else ""
        return f"Posted by {Html.esc(self._post.user.username)} on {Html.esc(self._post.date_posted)}"

    def html(self):
        item = self._post.item
        desc = "" if self._claimed else f'<p class="fi-desc">{Html.esc(item.description).replace(chr(10), "<br>")}</p>'
        return (
            f'{self._media()}<div class="fi-body"><div class="fi-title">{Html.esc(item.name)}</div>'
            f'<div class="fi-chips">{self._chips()}</div>{desc}<div class="fi-meta">{self._footer()}</div></div>'
        )

    def render(self, key=None):
        with st.container(key=key or f"card_{self._post.post_id}"):
            st.markdown(self.html(), unsafe_allow_html=True)


class PostGrid:
    def __init__(self, posts, claimed=False, retention_days=7):
        self._posts = posts
        self._claimed = claimed
        self._retention_days = retention_days

    def render(self):
        cols = st.columns(2, gap="small")
        for idx, col in enumerate(cols):
            with col:
                with st.container(key=f"grid_col_{idx}"):
                    for post in self._posts[idx::2]:
                        PostCardView(post, self._claimed, self._retention_days).render()


class LoginView:
    def __init__(self, auth, state, institution):
        self._auth = auth
        self._state = state
        self._institution = institution

    def render(self):
        # The left panel is intentionally image-free. Add your own background
        # image to .st-key-login_visual in your preferred design workflow.
        with st.container(key="login_shell"):
            visual, panel = st.columns([1.45, 1], gap=None)

            with visual:
                with st.container(key="login_visual"):
                    st.markdown(
                        '<div><h1>Lost something?<br>Find it here.</h1>'
                        '<p>A campus lost-and-found space for the Mapúa MCM community. '
                        'Sign in to report, browse, and keep track of items.</p></div>',
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
                        email = st.text_input(
                            "Institutional Email",
                            placeholder="name@mapua.edu.ph",
                        )
                        password = st.text_input(
                            "Password",
                            type="password",
                            placeholder="Enter your password",
                        )
                        submitted = st.form_submit_button("Sign in")

                    st.markdown(
                        '<div class="fi-login-footnote">'
                        'For Mapúa MCM students and authorized personnel.</div>',
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
    def __init__(self, institution, user):
        self._institution = institution
        self._user = user

    def render(self):  # returns True when Logout was clicked
        c_brand, c_user, c_out = st.columns([5, 3, 1.5], vertical_alignment="center")
        with c_brand:
            st.markdown(
                f'<div class="fi-brand"><div class="fi-logo">F</div><div><div class="fi-name">FoundIt</div>'
                f'<div class="fi-sub">{Html.esc(self._institution.get_details())}</div></div></div>',
                unsafe_allow_html=True,
            )
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
        options = [self.ALL_CAMPUSES] + self._service.institution.campuses
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

    def render(self, user):
        col_search, col_campus = st.columns([3, 1])
        with col_search:
            query = st.text_input(
                "Search", "", key="feed_search", placeholder="Search by name, category or description",
                label_visibility="collapsed",
            )
        with col_campus:
            campus = self._campus_filter("feed_campus")

        posts = self._service.active(campus, query)
        if not posts:
            EmptyState.show("No items match your search or filter.")
        else:
            PostGrid(posts, retention_days=self._service.RETENTION_DAYS).render()


class ClaimedPage(Page):
    title = "Claimed"

    def render(self, user):
        st.caption(f"Claimed items stay here for {self._service.RETENTION_DAYS} days, then are removed automatically.")
        col_search, col_campus = st.columns([3, 1])
        with col_search:
            query = st.text_input(
                "Search", "", key="claimed_search", placeholder="Search by name, category or description",
                label_visibility="collapsed",
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
            st.image(photo, caption=photo.name, use_container_width=True)
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
        return f"{post.item.name} ({post.item.tracking.status.value}) - {post.user.username}"

    def _render(self, user):
        if self._state.status_msg:  # message saved before the rerun
            st.success(self._state.status_msg)
            self._state.status_msg = None

        posts = list(reversed(self._service.posts))
        if not posts:
            EmptyState.show("No items available to update.")
            return

        by_id = {p.post_id: p for p in posts}
        left, right = st.columns(2, gap="large")
        with left:
            selected_id = st.selectbox(
                "Select Item to Update", list(by_id.keys()), format_func=lambda pid: self._label(by_id[pid])
            )
            new_status = st.radio("Select New Status", [s.value for s in Status], horizontal=True)
            apply_update = st.button("Apply Status Update")
        with right:
            PostCardView(by_id[selected_id], retention_days=self._service.RETENTION_DAYS).render(key="card_preview")

        if apply_update:
            self._service.set_status(user, selected_id, new_status)
            self._state.status_msg = f"Status updated to **{new_status}** in Supabase!"
            st.rerun()


# ---------------------------------------------------------------- application

class FoundItApp:
    PAGES = (FeedPage, ClaimedPage, ReportPage, UpdateStatusPage)

    def __init__(self):
        self._gateway = get_gateway()
        self._state = AppState()
        self._auth = AuthService(self._gateway)
        self._cookies = CookieSession(self._state, self._auth)
        self._institution = Institution("Mapúa Malayan Colleges Mindanao", "Davao City", ["RSY Building", "RG Birrey"])

    def _service(self):
        if self._state.service is None:
            catalog = CategoryCatalog.default()
            repository = SupabasePostRepository(
                self._gateway, catalog, SupabaseImageStorage(self._gateway), self._institution.default_campus
            )
            self._state.service = LostAndFoundService(repository, catalog, self._institution)
        return self._state.service

    def _logout(self):
        self._state.current_user = None
        self._state.logged_out = True
        self._state.pending_delete = True
        self._state.service = None
        self._state.reset_navigation()
        st.rerun()

    def _render_main(self, user):
        # Keep the authenticated app centered and comfortably sized on wide screens.
        with st.container(key="main_shell"):
            service = self._service()
            service.refresh_if_stale()
            if AppBar(self._institution, user).render():
                self._logout()

            if not user.can_manage_items():
                st.caption("Standard account: only administrators can report or update items.")

            navigation = st.pills(
                "Section", user.sections(), default="Feed", key="nav", label_visibility="collapsed"
            ) or "Feed"
            pages = {cls.title: cls(service, self._state) for cls in self.PAGES}
            pages.get(navigation, pages["Feed"]).render(user)

    def run(self):
        Theme.apply()
        self._cookies.restore()
        self._cookies.sync()
        user = self._state.current_user
        if user is None:
            LoginView(self._auth, self._state, self._institution).render()
        else:
            self._render_main(user)


def main():
    st.set_page_config(page_title="FoundIt - Campus Lost & Found", page_icon="F", layout="wide")
    FoundItApp().run()


main()
