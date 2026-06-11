# Auth + News Email — Design Spec

**Date:** 2026-06-11
**Status:** Approved
**Branch target:** new feature branch off current work

## Goal

Add two features to the Colombus FX Risk Alert Dashboard:

1. **Authentication** — open self-signup with email + password, JWT-based, gating the
   platform (frontend pages and backend data routes).
2. **News email** — email the AI news digest to a logged-in user, both on demand (button)
   and as an opt-in scheduled daily digest, sent via Gmail SMTP.

Both run on the existing single-machine stack (FastAPI + SQLAlchemy + SQLite + React),
with no new external infrastructure.

## Decisions (locked)

- User model: **open self-signup**, anyone can register. No email verification in v1.
- Auth: **email + password**, bcrypt hashing, **PyJWT** access token, **7-day** expiry,
  no refresh tokens (re-login on expiry).
- Backend data routes (`rates`, `alerts`, `analysis`, `ai`, `news`, `hedge`) are **gated**
  behind `get_current_user`. `auth` routes and health are public. Tests get a shared
  auth fixture.
- Email delivery: **Gmail SMTP** (`smtplib`, STARTTLS on 587) using an app password.
- Digest content: **all 4 pairs** (EUR/USD, GBP/USD, USD/TND, EUR/TND) for the target date.
- Schedule: **APScheduler** in-process, daily at `DIGEST_HOUR` (default 08:00),
  timezone **Africa/Tunis**, to every user with `digest_enabled = true`.

---

## Component 1 — Authentication

### Data model (`models.py`)

```
User
  id              INTEGER PK
  email           TEXT UNIQUE NOT NULL
  hashed_password TEXT NOT NULL
  is_active       BOOLEAN NOT NULL DEFAULT 1
  digest_enabled  BOOLEAN NOT NULL DEFAULT 0
  created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

### Config additions (`config.py`)

```
jwt_secret: str = ""            # required in prod; generated/dev default tolerated
jwt_expire_minutes: int = 10080 # 7 days
```

### Security helpers (`services/security.py`)

- `hash_password(plain) -> str` and `verify_password(plain, hashed) -> bool` (passlib bcrypt).
- `create_access_token(sub: str) -> str` and `decode_token(token) -> dict` (PyJWT, HS256).

### Auth router (`routers/auth.py`, prefix `/api/v1/auth`)

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/register` | `{email, password}` | `{id, email}` (201); 409 if email exists |
| POST | `/login` | `{email, password}` | `{access_token, token_type:"bearer"}`; 401 on bad creds |
| GET | `/me` | — (Bearer) | `{id, email, digest_enabled}` |
| PATCH | `/me` | `{digest_enabled}` (Bearer) | updated `{id, email, digest_enabled}` |

Password rules: min length 8 (validated in Pydantic schema). Email validated by Pydantic
`EmailStr`.

### Dependency (`services/deps.py` or in `auth.py`)

`get_current_user(authorization header) -> User`:
decode Bearer token → load user by `sub` (user id/email) → 401 on missing/invalid/expired.

Applied as a router-level dependency to: `rates`, `alerts`, `analysis`, `ai`, `news`,
`hedge`, and the `/currencies` route. `auth` router stays public.

### Frontend

- `api/client.ts`: read JWT from `localStorage`, attach `Authorization: Bearer`; on 401,
  clear token and redirect to `/login`.
- `auth/AuthContext.tsx`: `{user, token, login(), logout(), register()}`.
- Pages: `LoginPage`, `SignupPage`.
- `ProtectedRoute` wrapper around the dashboard; unauthenticated → `/login`.
- Header: show user email + Logout button.

---

## Component 2 — News Email

### Email service (`services/email_service.py`)

- `send_email(to: str, subject: str, html: str) -> None` via `smtplib.SMTP` + STARTTLS.
- Reads SMTP config from settings. Raises a typed error on failure; callers degrade
  gracefully (manual endpoint returns 502; scheduler logs and continues to next user).

### Config additions (`config.py`)

```
smtp_host: str = "smtp.gmail.com"
smtp_port: int = 587
smtp_user: str = ""
smtp_password: str = ""        # Gmail app password
smtp_from: str = ""            # defaults to smtp_user if empty
digest_hour: int = 8
digest_timezone: str = "Africa/Tunis"
```

### Digest builder (`services/digest_builder.py`)

- `build_digest_html(db, on_date, pairs) -> tuple[str subject, str html]`.
- For each pair, call `news_section.get_pair_news(db, base, quote, on_date)` and render the
  `top` (with explanation) + `more` headlines into a simple, inline-styled HTML email
  (dark header, per-pair sections, source links). Reuses the existing news pipeline — no
  new data sources.
- Subject e.g. `Colombus FX — News digest for {date}`.

### News email endpoint (`routers/news.py`, auth required)

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/news/email` | `{date?}` (Bearer) | `{sent: true, to: email}`; 502 if SMTP fails |

Sends the all-4-pairs digest for the given date (default today) to `current_user.email`.

### Scheduler (`services/scheduler.py` + `main.py` lifespan)

- `AsyncIOScheduler` (or `BackgroundScheduler`) started in the FastAPI lifespan; shut down
  on app stop.
- One cron job at `digest_hour` in `digest_timezone`.
- Job: open a DB session → query `User` where `digest_enabled = true` → build today's
  digest once (shared across users) → `send_email` per user; wrap each send in try/except
  so one failure doesn't abort the batch.

### Frontend

- News section: **"Email me this"** button → `POST /news/email`; toast on success/failure.
- Daily-digest **opt-in toggle** (header menu or small settings panel) → `PATCH /auth/me`
  with `{digest_enabled}`.

---

## Error handling

| Scenario | Status / behavior |
|---|---|
| Register existing email | 409 `{detail}` |
| Bad login credentials | 401 |
| Missing/invalid/expired token on gated route | 401 |
| Password too short | 422 (Pydantic) |
| SMTP send fails (manual) | 502 `{detail: "Email delivery failed"}` |
| SMTP send fails (scheduled) | logged, batch continues |

## Testing

- **Auth:** password hash round-trip; register success + duplicate 409; login success +
  bad-creds 401; `/me` requires token; a gated data route returns 401 without token and
  200 with token. Shared pytest fixture issues a valid token + auth headers.
- **Email:** `digest_builder` renders mocked news into HTML containing the headlines;
  `email_service.send_email` with a **mocked `smtplib.SMTP`** (no real network); manual
  endpoint sends to current user (sender mocked); scheduler per-user job continues past a
  failing send (sender mocked to raise once).

## New dependencies (`requirements.txt`)

```
pyjwt>=2.8
passlib[bcrypt]>=1.7
apscheduler>=3.10
email-validator>=2.0   # for Pydantic EmailStr
```

## Out of scope (v1)

Email verification, password reset, refresh tokens, roles/permissions, per-pair digest
selection, multiple transactional providers, rate limiting.
