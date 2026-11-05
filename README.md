# FoundIt: Campus Lost & Found Hub

A modern, tiered-architecture web application where students and faculty can browse found items on campus, and administrators can post items, manage photos, and track items through their lifecycle. Built with **Python**, **Streamlit**, **Supabase**, and **SWI-Prolog** for Mapúa Malayan Colleges Mindanao (Davao City).

## Features

* **Feed & Search:** Photo cards of unclaimed items with keyword search, campus filters (e.g., *RSY Building*, *RG Birrey*), and Prolog-based semantic matching.
* **Claimed Page:** Items that were picked up, featuring an automated "removed in N days" retention countdown.
* **Role-Based Access:**
  * *Students & Faculty:* Access to view the active feed and claimed items page.
  * *Administrators:* Full access to report new items (with photo uploads), update statuses, and purge items.
* **Status Flow & Auto-Purge:** `Pending Claim` → `Claimed`. Claimed items and associated storage objects are cleaned up automatically after 7 days.
* **Institutional Authentication:** Supabase Auth enforced for institutional `@mcm.edu.ph` email addresses with persistent cookie session restoration.

## Tech Stack

| Component | Technology |
| --- | --- |
| Language | Python 3.10+ |
| Interface | Streamlit (Custom HTML/CSS card views & pills navigation) |
| Auth & DB | Supabase (PostgreSQL `posts` table) |
| Media Storage | Supabase Storage (`item-images` bucket) |
| Match Engine | SWI-Prolog via `pyswip` (`logic_engine.py` & `matching_rules.pl`) |
| Session Handling | `extra-streamlit-components` |

## Project Structure

```text
.
├── .devcontainer/         # Dev container settings
├── .streamlit/
│   ├── config.toml        # Dark theme configuration
│   └── secrets.toml       # Environment keys & credentials (GIT-IGNORED)
├── assets/                # Static UI assets and branding
├── app.py                 # Streamlit UI layer & page views
├── backend.py             # API Gateway & Supabase SDK interface
├── functional.py          # Functional utilities & query helpers
├── logic_engine.py        # Prolog integration wrapper for item matching
├── matching_rules.pl      # Prolog knowledge base & inference rules
├── models.py              # Domain entities, repositories, & storage adapters
├── packages.txt           # Linux system dependencies (swi-prolog-nox)
├── requirements.txt       # Python package dependencies
└── README.md              # Documentation
```

## Getting Started

### 1. Prerequisites

* Python 3.10 or newer
* [SWI-Prolog](https://www.swi-prolog.org/) installed locally (`swipl`)
* A free [Supabase](https://supabase.com) project
* Streamlit **1.40 or newer**

### 2. Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/Made0fB1naries/FoundIt-Prototype-redesigned-.git
cd FoundIt-Prototype-redesigned-

python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Supabase Configuration

**a) Database Table Setup:**
Run the following query in your Supabase SQL Editor:

```sql
create table public.posts (
  post_id          text primary key,
  date_posted      date not null,
  username         text not null,
  institutional_id text not null,
  item_name        text not null,
  description      text,
  category_name    text,
  campus_location  text,
  image_url        text,
  status           text not null default 'Pending Claim',
  date_claimed     timestamptz
);

alter table public.posts enable row level security;

create policy "Public read posts" on public.posts
  for select to anon, authenticated using (true);
```

**b) Storage Bucket:**
Create a bucket named **`item-images`** under **Storage** and switch **Public Bucket** to **ON**.

### 4. Configure Secrets

Create `.streamlit/secrets.toml`:

```toml
SUPABASE_URL = "https://YOUR-PROJECT.supabase.co"
SUPABASE_KEY = "your_supabase_anon_key"
SUPABASE_SERVICE_KEY = "your_supabase_service_role_key"
ADMIN_EMAILS = "admin1@mcm.edu.ph, admin2@mcm.edu.ph"
```

> **Note:** Ensure `.streamlit/secrets.toml` remains inside your `.gitignore` to protect API keys.

### 5. Running the App

```bash
streamlit run app.py
```

## Deploying on Streamlit Community Cloud

1. Push your changes to GitHub (ensure `packages.txt` with `swi-prolog-nox` is present in the repository root).
2. Connect your repo on [Streamlit Cloud](https://share.streamlit.io).
3. Paste the four config lines into **Advanced Settings → Secrets**.
4. Deploy the application.

## Troubleshooting

| Issue | Resolution |
| --- | --- |
| `PyswipError` or missing Prolog | Ensure `swi-prolog-nox` is included in `packages.txt` on Streamlit Cloud or installed on your host OS. |
| `KeyError: 'SUPABASE_SERVICE_KEY'` | Verify secret configuration in `.streamlit/secrets.toml`. |
| "Unauthorized" on Admin Pages | Check that your logged-in email is added to `ADMIN_EMAILS` using the `@mcm.edu.ph` domain. |
| Image upload fails (`NULL` in DB) | Verify that `item-images` exists as a **Public** bucket in Supabase Storage. |

## About

Developed as an object-oriented Python software project for Mapúa Malayan Colleges Mindanao.
