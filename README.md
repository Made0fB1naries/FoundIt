# FoundIt: Campus Lost & Found Hub

A web app where students and faculty can browse found items on campus, and administrators can post items and track them until they are claimed. Built with **Python OOP**, **Streamlit** and **Supabase** for Mapúa Malayan Colleges Mindanao (Davao City).

## Features

- **Feed:** photo cards of unclaimed items, with search and a campus filter (RSY Building, RG Birrey).
- **Claimed page:** items that were picked up, with a "removed in N days" countdown.
- **Roles:**
  - *Student/Faculty* can view the feed and the claimed page.
  - *Administrators* can also **report** items (photo, name, description, campus, category) and **update status**.
- **Status flow:** `Pending Claim` → `Claimed`. Claimed items are deleted automatically (row and photo) after 7 days.
- **Login:** Supabase Auth with email and password, and a cookie so a page refresh keeps you signed in.
- **Fresh data:** the feed reloads from the database when it is more than 30 seconds old.

## Tech stack

| Part | Technology |
|---|---|
| Language | Python 3.10+ |
| Interface | Streamlit, with custom HTML and CSS for the dark card UI |
| Login | Supabase Auth |
| Database | Supabase (PostgreSQL) `posts` table |
| Photos | Supabase Storage `item-images` bucket |
| Cookie session | `extra-streamlit-components` |

## Project structure

```
.
├── app.py                  # Streamlit UI: pages, cards, login, navigation
├── models.py               # Domain classes, Supabase access, business rules
├── requirements.txt
└── .streamlit/
    ├── config.toml         # dark theme (committed)
    └── secrets.toml        # your keys (NOT committed, see below)
```

## Getting started

### 1. Prerequisites

- Python 3.10 or newer
- A free [Supabase](https://supabase.com) account
- Streamlit **1.40 or newer** (the app uses `st.pills`, which older versions do not have)

### 2. Clone and install

```bash
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>

python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate

pip install -r requirements.txt
```

`requirements.txt` should contain:

```
streamlit
supabase
extra-streamlit-components
```

### 3. Set up Supabase

Create a new project, then do the following.

**a) Create the `posts` table** (SQL Editor → New query → Run):

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
```

**b) Make the table read-only for the public key.** The app writes with the secret key, which bypasses these rules, so the public key only needs to read:

```sql
alter table public.posts enable row level security;

create policy "Public read posts" on public.posts
  for select to anon, authenticated using (true);
```

**c) Create the photo bucket.** Storage → New bucket → name it exactly `item-images` and turn on **Public bucket**. No storage policies are needed, because uploads and deletes use the secret key.

**d) Create user accounts.** Authentication → Users → Add user → Create new user (tick *Auto Confirm User*). Create one account for each student, faculty member or admin. To stop strangers from registering, turn off **Allow new users to sign up** in the Authentication settings.

**e) Copy your keys.** Project Settings → API Keys:

- Project URL
- **Publishable key** (`sb_publishable_...`)
- **Secret key** (`sb_secret_...`)

### 4. Add your secrets

Create the file `.streamlit/secrets.toml`:

```toml
SUPABASE_URL = "https://YOUR-PROJECT.supabase.co"
SUPABASE_KEY = "sb_publishable_..."
SUPABASE_SERVICE_KEY = "sb_secret_..."
ADMIN_EMAILS = "admin1@school.edu, admin2@school.edu"
```

- Each value must stay on **one line**.
- `ADMIN_EMAILS` is a comma-separated list. Only these exact emails (not case sensitive) become administrators; everyone else is a standard user.
- **Never commit this file.** Add it to `.gitignore`:

```
.streamlit/secrets.toml
__pycache__/
.venv/
```

### 5. Theme (recommended)

Create `.streamlit/config.toml` so the built-in widgets match the black UI:

```toml
[theme]
base = "dark"
primaryColor = "#A8C7FA"
backgroundColor = "#000000"
secondaryBackgroundColor = "#121212"
textColor = "#E3E3E3"
font = "sans serif"
```

### 6. Run

```bash
streamlit run app.py
```

Open the link it prints (usually http://localhost:8501) and sign in with a Supabase user.

## Deploy on Streamlit Community Cloud

1. Push the project to GitHub (without `secrets.toml`).
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**, pick the repo and set the main file to `app.py`.
3. Open **Advanced settings → Secrets** and paste the same four lines from step 4.
4. Deploy. If you change the secrets later, reboot the app from **Manage app**.

## How it works

- **Roles:** after login, the email is checked against `ADMIN_EMAILS`. Admins get the Report and Update status pages. The service layer checks admin rights again on every write, so hiding a page is not the only protection.
- **Reading and writing:** the public key only reads posts. Every insert, status change, photo upload and delete uses the secret key on the server side.
- **Reporting an item:** the admin uploads a photo (JPG or PNG) and fills in the details. The photo is stored unchanged, and cards show it in a 4:3 frame. The post gets a unique ID.
- **Claiming:** when an admin sets an item to `Claimed`, the time is saved. After 7 days the row and its photo are removed automatically.
- **Older data:** rows saved earlier with a status the app no longer uses (for example `Lost`) are shown as `Pending Claim`.

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: extra_streamlit_components` | Install the requirements: `pip install -r requirements.txt`. On Streamlit Cloud, make sure `requirements.txt` is in the repo root. |
| `KeyError: 'SUPABASE_SERVICE_KEY'` (or another key) | That secret is missing. Check the spelling in `secrets.toml` or the Cloud Secrets box. |
| `AttributeError: ... has no attribute 'pills'` | Upgrade Streamlit: `pip install -U streamlit`. |
| "Authentication failed" | Check the email and password in Supabase → Authentication → Users, and that the user is confirmed. |
| No Report / Update status pages | The email is not in `ADMIN_EMAILS`. Add it exactly, then sign out and in again. |
| Photos do not show | The `item-images` bucket must be **Public**. |
| Posting works but nothing saves | The secret key is wrong, or is not the `sb_secret_...` key. |

## Security notes

- Keep `SUPABASE_SERVICE_KEY` only in secrets. It bypasses all database rules.
- Do not paste real keys in screenshots, issues or commits. If one leaks, rotate it in Supabase → Project Settings → API Keys.

## About

Built as a Python OOP course project.
