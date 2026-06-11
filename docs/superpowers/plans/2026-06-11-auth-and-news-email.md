# Auth + News Email Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add open self-signup JWT auth (gating the platform) and a news-digest email feature (on-demand button + opt-in daily schedule via Gmail SMTP) to the Colombus FX dashboard.

**Architecture:** Backend adds a `User` model, bcrypt/PyJWT security helpers, an `/auth` router, and a `get_current_user` dependency applied at `app.include_router(...)` to gate all data routers. Email reuses the existing news pipeline: an `email_service` (stdlib `smtplib`) sends HTML built by a `digest_builder`, triggered either by `POST /news/email` or an in-process APScheduler cron job. Frontend (single-page, no router) gates the dashboard behind an `AuthContext`, attaches the JWT to every `fetch`, and adds an "Email me this" button + a daily-digest toggle.

**Tech Stack:** FastAPI, SQLAlchemy, SQLite, Pydantic, PyJWT, bcrypt, APScheduler, smtplib · React 19 + TypeScript + Vite (plain fetch).

---

## File Structure

**Backend — create:**
- `Backend/app/services/security.py` — password hashing + JWT encode/decode
- `Backend/app/services/deps.py` — `get_current_user` dependency
- `Backend/app/routers/auth.py` — register / login / me / patch-me
- `Backend/app/services/email_service.py` — SMTP sender
- `Backend/app/services/digest_builder.py` — news → HTML email
- `Backend/app/services/scheduler.py` — APScheduler job + start/stop
- `Backend/tests/test_security.py`, `test_auth.py`, `test_auth_gating.py`, `test_email_service.py`, `test_digest_builder.py`, `test_news_email.py`, `test_scheduler.py`

**Backend — modify:**
- `requirements.txt` — add pyjwt, bcrypt, apscheduler, email-validator
- `app/config.py` — JWT + SMTP + digest settings
- `app/models.py` — `User` model
- `app/schemas.py` — auth + email schemas
- `app/main.py` — gate routers, register auth router, start/stop scheduler
- `app/routers/news.py` — `POST /news/email`
- `tests/conftest.py` — override `get_current_user`; add unauthenticated client + auth helpers

**Frontend — create:**
- `src/auth/AuthContext.tsx`, `src/auth/api.ts`
- `src/components/auth/LoginPage.tsx`, `src/components/auth/SignupPage.tsx`

**Frontend — modify:**
- `src/api/endpoints.ts` — auth + news-email endpoints
- `src/api/client.ts` — attach Bearer token, 401 handling, `emailNews()`
- `src/main.tsx` — wrap `<App/>` in `AuthProvider`
- `src/App.tsx` — gate behind auth; pass digest toggle to header
- `src/components/layout/Header.tsx` — email, logout, digest toggle
- `src/components/News.tsx` — "Email me this" button

---

## Task 1: Dependencies + config

**Files:**
- Modify: `Backend/requirements.txt`
- Modify: `Backend/app/config.py`

- [ ] **Step 1: Add dependencies to `requirements.txt`**

Append these lines after `pytest-mock>=3.14`:

```
pyjwt>=2.8
bcrypt>=4.0
apscheduler>=3.10
email-validator>=2.0
```

- [ ] **Step 2: Install them**

Run: `cd Backend && pip install -r requirements.txt`
Expected: installs pyjwt, bcrypt, apscheduler, email-validator without errors.

- [ ] **Step 3: Add config fields**

Replace the body of `Backend/app/config.py` with:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "sqlite:///./fx_dashboard.db"
    groq_api_key: str = ""

    # Auth
    jwt_secret: str = "dev-insecure-change-me"   # MUST be overridden in prod via .env
    jwt_expire_minutes: int = 10080              # 7 days

    # Email / SMTP (Gmail app password)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""                          # falls back to smtp_user when empty

    # Daily digest schedule
    digest_hour: int = 8
    digest_timezone: str = "Africa/Tunis"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8-sig",
        "extra": "ignore",
    }

settings = Settings()
```

- [ ] **Step 4: Verify import works**

Run: `cd Backend && python -c "from app.config import settings; print(settings.jwt_expire_minutes, settings.smtp_host)"`
Expected: `10080 smtp.gmail.com`

- [ ] **Step 5: Commit**

```bash
git add Backend/requirements.txt Backend/app/config.py
git commit -m "feat: add auth + email dependencies and config"
```

---

## Task 2: Security helpers (hashing + JWT)

**Files:**
- Create: `Backend/app/services/security.py`
- Test: `Backend/tests/test_security.py`

- [ ] **Step 1: Write the failing test**

Create `Backend/tests/test_security.py`:

```python
import pytest
from app.services import security


def test_password_hash_roundtrip():
    h = security.hash_password("hunter2pass")
    assert h != "hunter2pass"
    assert security.verify_password("hunter2pass", h) is True
    assert security.verify_password("wrong", h) is False


def test_token_roundtrip():
    token = security.create_access_token("user-42")
    payload = security.decode_token(token)
    assert payload["sub"] == "user-42"


def test_decode_invalid_token_raises():
    with pytest.raises(Exception):
        security.decode_token("not.a.real.token")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Backend && pytest tests/test_security.py -v`
Expected: FAIL — `ModuleNotFoundError: app.services.security`.

- [ ] **Step 3: Write minimal implementation**

Create `Backend/app/services/security.py`:

```python
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from app.config import settings

ALGORITHM = "HS256"


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(sub: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode({"sub": sub, "exp": expire}, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd Backend && pytest tests/test_security.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add Backend/app/services/security.py Backend/tests/test_security.py
git commit -m "feat: bcrypt password hashing and JWT helpers"
```

---

## Task 3: User model + auth schemas

**Files:**
- Modify: `Backend/app/models.py`
- Modify: `Backend/app/schemas.py`
- Test: `Backend/tests/test_user_model.py`

- [ ] **Step 1: Write the failing test**

Create `Backend/tests/test_user_model.py`:

```python
from app import models


def test_user_row_persists(db_session):
    u = models.User(email="a@b.com", hashed_password="x", digest_enabled=False)
    db_session.add(u)
    db_session.commit()
    got = db_session.query(models.User).filter_by(email="a@b.com").one()
    assert got.id is not None
    assert got.is_active is True
    assert got.digest_enabled is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Backend && pytest tests/test_user_model.py -v`
Expected: FAIL — `AttributeError: module 'app.models' has no attribute 'User'`.

- [ ] **Step 3: Add the User model**

In `Backend/app/models.py`, add `Boolean` to the sqlalchemy import line so it reads:

```python
from sqlalchemy import Column, Integer, Text, Float, Date, DateTime, Boolean, UniqueConstraint
```

Then append at the end of the file:

```python
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(Text, unique=True, nullable=False)
    hashed_password = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    digest_enabled = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, server_default=func.now())
```

- [ ] **Step 4: Add auth schemas**

Append to `Backend/app/schemas.py` (keep existing imports; if `BaseModel`/`EmailStr` aren't imported, add `from pydantic import BaseModel, EmailStr, Field`):

```python
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: EmailStr
    digest_enabled: bool


class DigestPrefIn(BaseModel):
    digest_enabled: bool


class EmailNewsIn(BaseModel):
    date: str | None = None


class EmailNewsOut(BaseModel):
    sent: bool
    to: EmailStr
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd Backend && pytest tests/test_user_model.py -v`
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add Backend/app/models.py Backend/app/schemas.py Backend/tests/test_user_model.py
git commit -m "feat: User model and auth/email schemas"
```

---

## Task 4: get_current_user dependency

**Files:**
- Create: `Backend/app/services/deps.py`
- Test: `Backend/tests/test_deps.py`

- [ ] **Step 1: Write the failing test**

Create `Backend/tests/test_deps.py`:

```python
import pytest
from fastapi import HTTPException
from app import models
from app.services import deps, security


def test_get_current_user_valid(db_session):
    u = models.User(email="x@y.com", hashed_password="h")
    db_session.add(u)
    db_session.commit()
    token = security.create_access_token(str(u.id))
    got = deps.get_current_user(authorization=f"Bearer {token}", db=db_session)
    assert got.id == u.id


def test_get_current_user_missing_header(db_session):
    with pytest.raises(HTTPException) as e:
        deps.get_current_user(authorization=None, db=db_session)
    assert e.value.status_code == 401


def test_get_current_user_bad_token(db_session):
    with pytest.raises(HTTPException) as e:
        deps.get_current_user(authorization="Bearer garbage", db=db_session)
    assert e.value.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Backend && pytest tests/test_deps.py -v`
Expected: FAIL — `ModuleNotFoundError: app.services.deps`.

- [ ] **Step 3: Write the dependency**

Create `Backend/app/services/deps.py`:

```python
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from app.services import security


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> models.User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ", 1)[1]
    try:
        payload = security.decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.query(models.User).filter_by(id=int(payload.get("sub", 0))).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")
    return user
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd Backend && pytest tests/test_deps.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add Backend/app/services/deps.py Backend/tests/test_deps.py
git commit -m "feat: get_current_user auth dependency"
```

---

## Task 5: Auth router

**Files:**
- Create: `Backend/app/routers/auth.py`
- Test: `Backend/tests/test_auth.py`

- [ ] **Step 1: Write the failing test**

Create `Backend/tests/test_auth.py` (uses the `noauth_client` fixture added in Task 7):

```python
def test_register_and_login_flow(noauth_client):
    r = noauth_client.post("/api/v1/auth/register",
                           json={"email": "t@e.com", "password": "secret12"})
    assert r.status_code == 201
    assert r.json()["email"] == "t@e.com"

    dup = noauth_client.post("/api/v1/auth/register",
                             json={"email": "t@e.com", "password": "secret12"})
    assert dup.status_code == 409

    ok = noauth_client.post("/api/v1/auth/login",
                            json={"email": "t@e.com", "password": "secret12"})
    assert ok.status_code == 200
    token = ok.json()["access_token"]
    assert token

    bad = noauth_client.post("/api/v1/auth/login",
                             json={"email": "t@e.com", "password": "wrong"})
    assert bad.status_code == 401

    me = noauth_client.get("/api/v1/auth/me",
                           headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["digest_enabled"] is False

    patched = noauth_client.patch("/api/v1/auth/me",
                                  headers={"Authorization": f"Bearer {token}"},
                                  json={"digest_enabled": True})
    assert patched.status_code == 200
    assert patched.json()["digest_enabled"] is True


def test_short_password_rejected(noauth_client):
    r = noauth_client.post("/api/v1/auth/register",
                           json={"email": "s@e.com", "password": "short"})
    assert r.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Backend && pytest tests/test_auth.py -v`
Expected: FAIL — fixture `noauth_client` not found (added in Task 7) OR route 404. Either failure is expected at this point.

- [ ] **Step 3: Write the auth router**

Create `Backend/app/routers/auth.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from app.services import security
from app.services.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=schemas.UserOut, status_code=201)
def register(body: schemas.RegisterIn, db: Session = Depends(get_db)):
    if db.query(models.User).filter_by(email=body.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    user = models.User(email=body.email, hashed_password=security.hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=schemas.TokenOut)
def login(body: schemas.LoginIn, db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(email=body.email).first()
    if user is None or not security.verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return schemas.TokenOut(access_token=security.create_access_token(str(user.id)))


@router.get("/me", response_model=schemas.UserOut)
def me(current: models.User = Depends(get_current_user)):
    return current


@router.patch("/me", response_model=schemas.UserOut)
def update_me(body: schemas.DigestPrefIn,
              current: models.User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    current.digest_enabled = body.digest_enabled
    db.commit()
    db.refresh(current)
    return current
```

- [ ] **Step 4: Register the router (public, ungated)**

In `Backend/app/main.py`, add `auth` to the routers import:

```python
from app.routers import currencies, rates, alerts, analysis, ai, news, hedge, auth
```

and register it WITHOUT the auth dependency (place this line before the others):

```python
app.include_router(auth.router, prefix="/api/v1")
```

- [ ] **Step 5: Run test to verify it passes (after Task 7 fixtures exist)**

Run: `cd Backend && pytest tests/test_auth.py -v`
Expected: after Task 7 adds `noauth_client`, 2 passed. (If running now, it fails only on the missing fixture — proceed to Task 7, then re-run.)

- [ ] **Step 6: Commit**

```bash
git add Backend/app/routers/auth.py Backend/app/main.py Backend/tests/test_auth.py
git commit -m "feat: auth router (register/login/me) registered public"
```

---

## Task 6: Gate the data routers

**Files:**
- Modify: `Backend/app/main.py`

- [ ] **Step 1: Apply the dependency at registration**

In `Backend/app/main.py`, add the import near the top:

```python
from fastapi import Depends
from app.services.deps import get_current_user
```

Replace the data-router registration block (currencies/rates/alerts/analysis/ai/news/hedge) with a gated version:

```python
_auth = [Depends(get_current_user)]
app.include_router(auth.router, prefix="/api/v1")
app.include_router(currencies.router, prefix="/api/v1", dependencies=_auth)
app.include_router(rates.router, prefix="/api/v1", dependencies=_auth)
app.include_router(alerts.router, prefix="/api/v1", dependencies=_auth)
app.include_router(analysis.router, prefix="/api/v1", dependencies=_auth)
app.include_router(ai.router, prefix="/api/v1", dependencies=_auth)
app.include_router(news.router, prefix="/api/v1", dependencies=_auth)
app.include_router(hedge.router, prefix="/api/v1", dependencies=_auth)
```

- [ ] **Step 2: Verify the app imports**

Run: `cd Backend && python -c "from app.main import app; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add Backend/app/main.py
git commit -m "feat: gate data routers behind get_current_user"
```

---

## Task 7: Test fixtures (keep existing tests green)

**Files:**
- Modify: `Backend/tests/conftest.py`
- Test: `Backend/tests/test_auth_gating.py`

- [ ] **Step 1: Write the failing gating test**

Create `Backend/tests/test_auth_gating.py`:

```python
def test_gated_route_rejects_without_token(noauth_client):
    r = noauth_client.get("/api/v1/currencies")
    assert r.status_code == 401


def test_gated_route_allows_with_override(client):
    # `client` overrides get_current_user, so no token needed.
    r = client.get("/api/v1/currencies")
    assert r.status_code == 200
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd Backend && pytest tests/test_auth_gating.py -v`
Expected: FAIL — `noauth_client` fixture missing.

- [ ] **Step 3: Update conftest**

In `Backend/tests/conftest.py`, add an import of the dependency at the top:

```python
from app.services.deps import get_current_user
from app import models
```

Modify the `client` fixture so it ALSO overrides `get_current_user` with a seeded test user (this keeps all pre-existing data-route tests passing without tokens). Add a second fixture `noauth_client` that does NOT override auth. Replace the existing `client` fixture with:

```python
@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    test_user = models.User(id=1, email="test@fixture.com", hashed_password="x")
    db_session.add(test_user)
    db_session.commit()

    main.app.dependency_overrides[get_db] = override_get_db
    main.app.dependency_overrides[get_current_user] = lambda: test_user
    client = TestClient(main.app)
    yield client
    main.app.dependency_overrides.clear()


@pytest.fixture
def noauth_client(db_session):
    """Client with the real auth dependency active (only get_db overridden).
    Use for auth + gating tests that exercise tokens."""
    def override_get_db():
        yield db_session

    main.app.dependency_overrides[get_db] = override_get_db
    client = TestClient(main.app)
    yield client
    main.app.dependency_overrides.clear()
```

- [ ] **Step 4: Run the auth, gating, and full suite**

Run: `cd Backend && pytest tests/test_auth.py tests/test_auth_gating.py -v`
Expected: all passed.

Run: `cd Backend && pytest`
Expected: entire suite green (existing data-route tests still pass via the override).

- [ ] **Step 5: Commit**

```bash
git add Backend/tests/conftest.py Backend/tests/test_auth_gating.py
git commit -m "test: auth-aware fixtures, keep existing route tests green"
```

---

## Task 8: Email service (SMTP)

**Files:**
- Create: `Backend/app/services/email_service.py`
- Test: `Backend/tests/test_email_service.py`

- [ ] **Step 1: Write the failing test**

Create `Backend/tests/test_email_service.py`:

```python
from unittest.mock import MagicMock, patch
from app.services import email_service


def test_send_email_uses_smtp(monkeypatch):
    monkeypatch.setattr(email_service.settings, "smtp_user", "me@gmail.com")
    monkeypatch.setattr(email_service.settings, "smtp_password", "app-pw")
    fake = MagicMock()
    with patch("app.services.email_service.smtplib.SMTP") as smtp_cls:
        smtp_cls.return_value.__enter__.return_value = fake
        email_service.send_email("to@x.com", "Subject", "<b>hi</b>")
    fake.starttls.assert_called_once()
    fake.login.assert_called_once_with("me@gmail.com", "app-pw")
    fake.send_message.assert_called_once()


def test_send_email_raises_when_unconfigured(monkeypatch):
    monkeypatch.setattr(email_service.settings, "smtp_user", "")
    monkeypatch.setattr(email_service.settings, "smtp_password", "")
    try:
        email_service.send_email("to@x.com", "S", "<b>h</b>")
        assert False, "expected EmailError"
    except email_service.EmailError:
        pass
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd Backend && pytest tests/test_email_service.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the sender**

Create `Backend/app/services/email_service.py`:

```python
import smtplib
from email.message import EmailMessage
from app.config import settings


class EmailError(Exception):
    """Raised when an email cannot be sent."""


def send_email(to: str, subject: str, html: str) -> None:
    if not settings.smtp_user or not settings.smtp_password:
        raise EmailError("SMTP credentials not configured")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to
    msg.set_content("This email requires an HTML-capable client.")
    msg.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
    except Exception as exc:  # network, auth, etc.
        raise EmailError(str(exc)) from exc
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd Backend && pytest tests/test_email_service.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add Backend/app/services/email_service.py Backend/tests/test_email_service.py
git commit -m "feat: SMTP email_service with EmailError"
```

---

## Task 9: Digest builder

**Files:**
- Create: `Backend/app/services/digest_builder.py`
- Test: `Backend/tests/test_digest_builder.py`

- [ ] **Step 1: Write the failing test**

Create `Backend/tests/test_digest_builder.py`:

```python
from datetime import date
from types import SimpleNamespace
from app.services import digest_builder


def _item(headline, explanation=None):
    return SimpleNamespace(headline=headline, source="Reuters",
                           url="http://x", explanation=explanation)


def test_build_digest_html_contains_headlines(monkeypatch):
    def fake_news(db, base, quote, on_date):
        return [_item(f"{base}{quote} top", "because reasons")], [_item(f"{base}{quote} more")]
    monkeypatch.setattr(digest_builder.news_section, "get_pair_news", fake_news)

    subject, html = digest_builder.build_digest_html(db=None, on_date=date(2026, 6, 11))
    assert "2026-06-11" in subject
    assert "EURUSD top" in html
    assert "because reasons" in html
    assert "USDTND top" in html
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd Backend && pytest tests/test_digest_builder.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the builder**

Create `Backend/app/services/digest_builder.py`:

```python
from datetime import date
from app.services import news_section

PAIRS = [("EUR", "USD"), ("GBP", "USD"), ("USD", "TND"), ("EUR", "TND")]


def _section_html(base: str, quote: str, top, more) -> str:
    rows = []
    for it in top:
        expl = f'<p style="margin:4px 0;color:#cbd5e1">{it.explanation}</p>' if it.explanation else ""
        rows.append(
            f'<li style="margin-bottom:10px">'
            f'<a href="{it.url}" style="color:#2DD4BF;text-decoration:none">{it.headline}</a>'
            f'<span style="color:#64748b"> — {it.source}</span>{expl}</li>'
        )
    for it in more:
        rows.append(
            f'<li style="margin-bottom:6px">'
            f'<a href="{it.url}" style="color:#94a3b8;text-decoration:none">{it.headline}</a>'
            f'<span style="color:#64748b"> — {it.source}</span></li>'
        )
    body = "".join(rows) or '<li style="color:#64748b">No headlines.</li>'
    return (
        f'<h2 style="color:#2DD4BF;font-size:16px;margin:24px 0 8px">{base}/{quote}</h2>'
        f'<ul style="list-style:none;padding:0;margin:0">{body}</ul>'
    )


def build_digest_html(db, on_date: date) -> tuple[str, str]:
    subject = f"Colombus FX — News digest for {on_date.isoformat()}"
    sections = []
    for base, quote in PAIRS:
        try:
            top, more = news_section.get_pair_news(db, base, quote, on_date)
        except Exception:
            top, more = [], []
        sections.append(_section_html(base, quote, top, more))

    html = (
        '<div style="background:#0F172A;color:#e2e8f0;font-family:Arial,sans-serif;'
        'padding:24px;max-width:640px;margin:0 auto">'
        f'<h1 style="color:#fff;font-size:20px;margin:0">Colombus FX News Digest</h1>'
        f'<p style="color:#94a3b8;margin:4px 0 0">{on_date.isoformat()}</p>'
        + "".join(sections)
        + '<p style="color:#64748b;font-size:12px;margin-top:32px">'
        'You are receiving this because you enabled the daily digest in Colombus. '
        'Educational use only — not financial advice.</p></div>'
    )
    return subject, html
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd Backend && pytest tests/test_digest_builder.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add Backend/app/services/digest_builder.py Backend/tests/test_digest_builder.py
git commit -m "feat: HTML news digest builder"
```

---

## Task 10: POST /news/email endpoint

**Files:**
- Modify: `Backend/app/routers/news.py`
- Test: `Backend/tests/test_news_email.py`

- [ ] **Step 1: Write the failing test**

Create `Backend/tests/test_news_email.py`:

```python
from unittest.mock import patch


def test_email_news_sends_to_current_user(client):
    # `client` fixture's test user is test@fixture.com
    with patch("app.routers.news.email_service.send_email") as send, \
         patch("app.routers.news.digest_builder.build_digest_html",
               return_value=("Subj", "<b>body</b>")):
        r = client.post("/api/v1/news/email", json={"date": "2026-06-11"})
    assert r.status_code == 200
    assert r.json() == {"sent": True, "to": "test@fixture.com"}
    send.assert_called_once_with("test@fixture.com", "Subj", "<b>body</b>")


def test_email_news_returns_502_on_smtp_failure(client):
    from app.services.email_service import EmailError
    with patch("app.routers.news.email_service.send_email", side_effect=EmailError("nope")), \
         patch("app.routers.news.digest_builder.build_digest_html",
               return_value=("S", "<b>b</b>")):
        r = client.post("/api/v1/news/email", json={})
    assert r.status_code == 502
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd Backend && pytest tests/test_news_email.py -v`
Expected: FAIL — route 404 / 405.

- [ ] **Step 3: Add the endpoint**

In `Backend/app/routers/news.py`, extend the imports:

```python
from datetime import date
from fastapi import APIRouter, Depends, Query, HTTPException
from app.services import news_section, digest_builder, email_service
from app.services.deps import get_current_user
from app import models
```

Append the endpoint at the end of the file:

```python
@router.post("/email", response_model=schemas.EmailNewsOut)
def email_news(
    body: schemas.EmailNewsIn,
    current: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    on_date = date.fromisoformat(body.date) if body.date else date.today()
    subject, html = digest_builder.build_digest_html(db, on_date)
    try:
        email_service.send_email(current.email, subject, html)
    except email_service.EmailError:
        raise HTTPException(status_code=502, detail="Email delivery failed")
    return schemas.EmailNewsOut(sent=True, to=current.email)
```

Note: `current` is injected by the route's own `Depends(get_current_user)`, which the `client` fixture overrides — so the test user flows through.

- [ ] **Step 4: Run to verify it passes**

Run: `cd Backend && pytest tests/test_news_email.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add Backend/app/routers/news.py Backend/tests/test_news_email.py
git commit -m "feat: POST /news/email sends digest to current user"
```

---

## Task 11: Daily digest scheduler

**Files:**
- Create: `Backend/app/services/scheduler.py`
- Modify: `Backend/app/main.py`
- Test: `Backend/tests/test_scheduler.py`

- [ ] **Step 1: Write the failing test**

Create `Backend/tests/test_scheduler.py`:

```python
from unittest.mock import patch
from datetime import date
from app import models
from app.services import scheduler


def test_run_digest_job_sends_only_to_opted_in(db_session):
    db_session.add_all([
        models.User(email="on@x.com", hashed_password="h", digest_enabled=True),
        models.User(email="off@x.com", hashed_password="h", digest_enabled=False),
    ])
    db_session.commit()

    with patch("app.services.scheduler.SessionLocal", return_value=db_session), \
         patch("app.services.scheduler.digest_builder.build_digest_html",
               return_value=("S", "<b>b</b>")), \
         patch("app.services.scheduler.email_service.send_email") as send:
        scheduler.run_digest_job()

    sent_to = {c.args[0] for c in send.call_args_list}
    assert sent_to == {"on@x.com"}


def test_run_digest_job_continues_past_failure(db_session):
    db_session.add_all([
        models.User(email="a@x.com", hashed_password="h", digest_enabled=True),
        models.User(email="b@x.com", hashed_password="h", digest_enabled=True),
    ])
    db_session.commit()
    from app.services.email_service import EmailError

    with patch("app.services.scheduler.SessionLocal", return_value=db_session), \
         patch("app.services.scheduler.digest_builder.build_digest_html",
               return_value=("S", "<b>b</b>")), \
         patch("app.services.scheduler.email_service.send_email",
               side_effect=[EmailError("x"), None]) as send:
        scheduler.run_digest_job()  # must not raise

    assert send.call_count == 2
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd Backend && pytest tests/test_scheduler.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the scheduler**

Create `Backend/app/services/scheduler.py`:

```python
import logging
from datetime import date
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.database import SessionLocal
from app.config import settings
from app import models
from app.services import digest_builder, email_service

logger = logging.getLogger("colombus.scheduler")
_scheduler: BackgroundScheduler | None = None


def run_digest_job() -> None:
    """Build today's digest once and email every opted-in user.
    Per-user failures are logged and skipped so the batch always completes."""
    db = SessionLocal()
    try:
        users = db.query(models.User).filter_by(digest_enabled=True, is_active=True).all()
        if not users:
            return
        subject, html = digest_builder.build_digest_html(db, date.today())
        for user in users:
            try:
                email_service.send_email(user.email, subject, html)
            except Exception as exc:
                logger.warning("digest send failed for %s: %s", user.email, exc)
    finally:
        db.close()


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(timezone=settings.digest_timezone)
    _scheduler.add_job(
        run_digest_job,
        CronTrigger(hour=settings.digest_hour, minute=0, timezone=settings.digest_timezone),
        id="daily_news_digest",
        replace_existing=True,
    )
    _scheduler.start()


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
```

- [ ] **Step 4: Wire into the app lifespan**

In `Backend/app/main.py`, import and start/stop the scheduler in `lifespan`:

```python
from app.services import scheduler
```

Update the `lifespan` function body to:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    models.Base.metadata.create_all(bind=engine)
    _heal_schema()
    scheduler.start_scheduler()
    try:
        yield
    finally:
        scheduler.stop_scheduler()
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd Backend && pytest tests/test_scheduler.py -v`
Expected: 2 passed.

- [ ] **Step 6: Run the full backend suite**

Run: `cd Backend && pytest`
Expected: entire suite green.

- [ ] **Step 7: Commit**

```bash
git add Backend/app/services/scheduler.py Backend/app/main.py Backend/tests/test_scheduler.py
git commit -m "feat: APScheduler daily news digest job"
```

---

## Task 12: Frontend — auth API + token-aware client

**Files:**
- Modify: `frontend/src/api/endpoints.ts`
- Create: `frontend/src/auth/api.ts`
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add endpoints**

In `frontend/src/api/endpoints.ts`, add inside the `endpoints` object:

```typescript
  register: () => `${BASE}/auth/register`,
  login: () => `${BASE}/auth/login`,
  me: () => `${BASE}/auth/me`,
  emailNews: () => `${BASE}/news/email`,
```

- [ ] **Step 2: Token storage + auth API**

Create `frontend/src/auth/api.ts`:

```typescript
import { endpoints } from '../api/endpoints';

const TOKEN_KEY = 'colombus_token';

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

export interface Me { id: number; email: string; digest_enabled: boolean; }

export async function apiRegister(email: string, password: string): Promise<void> {
  const r = await fetch(endpoints.register(), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? 'Registration failed');
}

export async function apiLogin(email: string, password: string): Promise<string> {
  const r = await fetch(endpoints.login(), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? 'Login failed');
  return (await r.json()).access_token as string;
}

export async function apiMe(): Promise<Me> {
  const r = await fetch(endpoints.me(), { headers: authHeaders() });
  if (!r.ok) throw new Error('Not authenticated');
  return (await r.json()) as Me;
}

export async function apiSetDigest(enabled: boolean): Promise<Me> {
  const r = await fetch(endpoints.me(), {
    method: 'PATCH',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ digest_enabled: enabled }),
  });
  if (!r.ok) throw new Error('Failed to update preference');
  return (await r.json()) as Me;
}

export function authHeaders(): Record<string, string> {
  const t = tokenStore.get();
  return t ? { Authorization: `Bearer ${t}` } : {};
}
```

- [ ] **Step 3: Make the data client send the token + handle 401**

In `frontend/src/api/client.ts`, add the import at the top:

```typescript
import { authHeaders, tokenStore } from '../auth/api';
```

Replace the `jget` helper with a token-aware version that clears the token and reloads on 401:

```typescript
async function jget<T>(url: string): Promise<T> {
  const r = await fetch(url, { headers: authHeaders() });
  if (r.status === 401) { tokenStore.clear(); location.reload(); throw new Error('Unauthorized'); }
  if (!r.ok) throw new Error(`GET ${url} -> ${r.status}`);
  return (await r.json()) as T;
}
```

In `fetchCommentary`, add the auth header to the POST call by replacing its `headers` line:

```typescript
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
```

Append an `emailNews` helper at the end of the file:

```typescript
/** Email the current user the 4-pair news digest for today. */
export async function emailNews(): Promise<{ sent: boolean; to: string }> {
  const r = await fetch(endpoints.emailNews(), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({}),
  });
  if (!r.ok) throw new Error(`POST email -> ${r.status}`);
  return (await r.json()) as { sent: boolean; to: string };
}
```

(Ensure `endpoints` is already imported in `client.ts` — it is, at the top of the file.)

- [ ] **Step 4: Verify the build compiles**

Run: `cd frontend && npm run build`
Expected: build succeeds (TypeScript compiles with no errors).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/endpoints.ts frontend/src/auth/api.ts frontend/src/api/client.ts
git commit -m "feat: token-aware frontend client + auth API"
```

---

## Task 13: Frontend — AuthContext, login/signup pages, gating

**Files:**
- Create: `frontend/src/auth/AuthContext.tsx`
- Create: `frontend/src/components/auth/LoginPage.tsx`
- Create: `frontend/src/components/auth/SignupPage.tsx`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: AuthContext**

Create `frontend/src/auth/AuthContext.tsx`:

```typescript
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { apiLogin, apiMe, apiRegister, apiSetDigest, tokenStore, type Me } from './api';

interface AuthState {
  user: Me | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
  setDigest: (enabled: boolean) => Promise<void>;
}

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!tokenStore.get()) { setReady(true); return; }
    apiMe().then(setUser).catch(() => tokenStore.clear()).finally(() => setReady(true));
  }, []);

  const login = async (email: string, password: string) => {
    tokenStore.set(await apiLogin(email, password));
    setUser(await apiMe());
  };
  const register = async (email: string, password: string) => {
    await apiRegister(email, password);
    await login(email, password);
  };
  const logout = () => { tokenStore.clear(); setUser(null); };
  const setDigest = async (enabled: boolean) => setUser(await apiSetDigest(enabled));

  return <Ctx.Provider value={{ user, ready, login, register, logout, setDigest }}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error('useAuth must be used within AuthProvider');
  return v;
}
```

- [ ] **Step 2: Login page**

Create `frontend/src/components/auth/LoginPage.tsx`:

```typescript
import { useState } from 'react';
import { useAuth } from '../../auth/AuthContext';

export function LoginPage({ onSwitch }: { onSwitch: () => void }) {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null); setBusy(true);
    try { await login(email, password); }
    catch (e) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  return (
    <div className="auth-shell">
      <form className="auth-card" onSubmit={submit}>
        <h1>Colombus FX</h1>
        <p className="auth-sub">Sign in to your dashboard</p>
        <input type="email" placeholder="Email" value={email}
               onChange={(e) => setEmail(e.target.value)} required />
        <input type="password" placeholder="Password" value={password}
               onChange={(e) => setPassword(e.target.value)} required />
        {err && <p className="auth-err">{err}</p>}
        <button type="submit" disabled={busy}>{busy ? '…' : 'Sign in'}</button>
        <p className="auth-switch">No account?{' '}
          <button type="button" onClick={onSwitch}>Create one</button></p>
      </form>
    </div>
  );
}
```

- [ ] **Step 3: Signup page**

Create `frontend/src/components/auth/SignupPage.tsx`:

```typescript
import { useState } from 'react';
import { useAuth } from '../../auth/AuthContext';

export function SignupPage({ onSwitch }: { onSwitch: () => void }) {
  const { register } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    if (password.length < 8) { setErr('Password must be at least 8 characters'); return; }
    setBusy(true);
    try { await register(email, password); }
    catch (e) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  return (
    <div className="auth-shell">
      <form className="auth-card" onSubmit={submit}>
        <h1>Colombus FX</h1>
        <p className="auth-sub">Create your account</p>
        <input type="email" placeholder="Email" value={email}
               onChange={(e) => setEmail(e.target.value)} required />
        <input type="password" placeholder="Password (min 8 chars)" value={password}
               onChange={(e) => setPassword(e.target.value)} required />
        {err && <p className="auth-err">{err}</p>}
        <button type="submit" disabled={busy}>{busy ? '…' : 'Create account'}</button>
        <p className="auth-switch">Have an account?{' '}
          <button type="button" onClick={onSwitch}>Sign in</button></p>
      </form>
    </div>
  );
}
```

- [ ] **Step 4: Wrap the app in AuthProvider**

In `frontend/src/main.tsx`, wrap the rendered `<App />` with `<AuthProvider>`. Add the import:

```typescript
import { AuthProvider } from './auth/AuthContext';
```

and wrap the existing `<App />` render so App is a child of `<AuthProvider>` (keep any existing providers like QueryClientProvider outermost or as-is).

- [ ] **Step 5: Gate the dashboard in App.tsx**

In `frontend/src/App.tsx`, add imports:

```typescript
import { useAuth } from './auth/AuthContext';
import { LoginPage } from './components/auth/LoginPage';
import { SignupPage } from './components/auth/SignupPage';
```

At the very top of the `App()` function body (before the existing hooks that fetch data is fine — these auth hooks must be unconditional), add:

```typescript
  const { user, ready } = useAuth();
  const [authView, setAuthView] = useState<'login' | 'signup'>('login');
```

Immediately before the `return (`, add the gate:

```typescript
  if (!ready) return null;
  if (!user) {
    return authView === 'login'
      ? <LoginPage onSwitch={() => setAuthView('signup')} />
      : <SignupPage onSwitch={() => setAuthView('login')} />;
  }
```

- [ ] **Step 6: Minimal auth styles**

Append to the global stylesheet (the file imported by `main.tsx`, e.g. `src/index.css` or equivalent — check the import in `main.tsx`):

```css
.auth-shell { min-height: 100vh; display: grid; place-items: center; background: #0F172A; }
.auth-card { display: flex; flex-direction: column; gap: 12px; width: 320px;
  padding: 32px; background: #111c33; border: 1px solid #1e293b; border-radius: 12px; }
.auth-card h1 { color: #fff; margin: 0; font-size: 22px; }
.auth-sub { color: #94a3b8; margin: 0 0 8px; font-size: 14px; }
.auth-card input { padding: 10px 12px; border-radius: 8px; border: 1px solid #334155;
  background: #0b1322; color: #e2e8f0; }
.auth-card button[type=submit] { padding: 10px; border: 0; border-radius: 8px;
  background: #2DD4BF; color: #042f2a; font-weight: 600; cursor: pointer; }
.auth-err { color: #f87171; font-size: 13px; margin: 0; }
.auth-switch { color: #94a3b8; font-size: 13px; text-align: center; margin: 4px 0 0; }
.auth-switch button { background: none; border: 0; color: #2DD4BF; cursor: pointer; }
```

- [ ] **Step 7: Verify build + manual smoke**

Run: `cd frontend && npm run build`
Expected: build succeeds.

Manual: with the backend running and `VITE_USE_MOCKS` unset, `npm run dev` → app shows the login page; create an account → dashboard loads.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/auth frontend/src/components/auth frontend/src/main.tsx frontend/src/App.tsx frontend/src/index.css
git commit -m "feat: auth context, login/signup pages, dashboard gating"
```

---

## Task 14: Frontend — header logout + digest toggle + email button

**Files:**
- Modify: `frontend/src/components/layout/Header.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/News.tsx`

- [ ] **Step 1: Add account controls to the Header**

In `frontend/src/components/layout/Header.tsx`, import the auth hook:

```typescript
import { useAuth } from '../../auth/AuthContext';
```

Inside the component, read auth state and render account controls (email, digest toggle, logout) next to the existing theme toggle:

```typescript
  const { user, logout, setDigest } = useAuth();
```

Add this markup within the header's controls area:

```tsx
  {user && (
    <div className="acct">
      <span className="acct-email">{user.email}</span>
      <label className="acct-digest">
        <input type="checkbox" checked={user.digest_enabled}
               onChange={(e) => setDigest(e.target.checked)} />
        Daily digest
      </label>
      <button className="acct-logout" onClick={logout}>Log out</button>
    </div>
  )}
```

If `Header` does not already accept the data it needs, no new props are required — it reads everything from `useAuth()`.

- [ ] **Step 2: "Email me this" button in News**

In `frontend/src/components/News.tsx`, import the helper:

```typescript
import { emailNews } from '../api/client';
import { useState } from 'react';
```

Add local state and a handler inside the component:

```typescript
  const [emailing, setEmailing] = useState(false);
  const [emailMsg, setEmailMsg] = useState<string | null>(null);

  const onEmail = async () => {
    setEmailing(true); setEmailMsg(null);
    try { const r = await emailNews(); setEmailMsg(`Sent to ${r.to}`); }
    catch { setEmailMsg('Failed to send'); }
    finally { setEmailing(false); }
  };
```

Render a button in the News section header:

```tsx
  <button className="news-email-btn" onClick={onEmail} disabled={emailing}>
    {emailing ? 'Sending…' : 'Email me this'}
  </button>
  {emailMsg && <span className="news-email-msg">{emailMsg}</span>}
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/layout/Header.tsx frontend/src/components/News.tsx
git commit -m "feat: header logout + digest toggle + email-me-this button"
```

---

## Task 15: Docs + env example

**Files:**
- Modify: `Backend/.env.example` (create if absent)
- Modify: `README.md`

- [ ] **Step 1: Update `.env.example`**

Ensure `Backend/.env.example` includes (create the file if it does not exist):

```
DATABASE_URL=sqlite:///./fx_dashboard.db
GROQ_API_KEY=your_key_here

# Auth — set a long random string in production
JWT_SECRET=change-me-to-a-long-random-string
JWT_EXPIRE_MINUTES=10080

# Email (Gmail app password)
SMTP_USER=youraddress@gmail.com
SMTP_PASSWORD=your_16_char_app_password
SMTP_FROM=youraddress@gmail.com
DIGEST_HOUR=8
DIGEST_TIMEZONE=Africa/Tunis
```

- [ ] **Step 2: Document the new features in README**

In `README.md`, add `users` to the schema/feature list, document the auth flow (register → login → Bearer token gates all `/api/v1` data routes) and the news email (`POST /api/v1/news/email` + opt-in daily digest), and list the new env vars.

- [ ] **Step 3: Commit**

```bash
git add Backend/.env.example README.md
git commit -m "docs: document auth + news email setup and env vars"
```

---

## Self-Review Notes

- **Spec coverage:** User model (T3) · bcrypt+JWT (T2) · register/login/me/patch (T5) · gating (T6) + green tests (T7) · SMTP (T8) · digest HTML (T9) · manual email endpoint (T10) · scheduler (T11) · frontend client/auth/gating/controls (T12–T14) · env+docs (T15). All spec sections mapped.
- **Type consistency:** `get_current_user(authorization, db)` signature identical in deps, tests, and routes. `build_digest_html(db, on_date)` identical in builder, endpoint, scheduler, and tests. `send_email(to, subject, html)` identical everywhere. `EmailNewsOut{sent,to}` matches endpoint return and test assertion. `Me{id,email,digest_enabled}` matches `UserOut`.
- **Gotcha:** Gating is applied at `include_router(..., dependencies=_auth)` in main.py; the `client` test fixture overrides `get_current_user` so the ~10 existing data-route test files keep passing untouched. `noauth_client` exercises the real token path.
- **bcrypt:** used directly (not via passlib) to avoid passlib/bcrypt 4.x version-probe warnings.
```
