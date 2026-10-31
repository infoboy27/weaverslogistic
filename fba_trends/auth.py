"""Fail-closed authentication for the Streamlit dashboard.

Modes (WEAVERS_AUTH_MODE):
- password (default): username + password from a users file (WEAVERS_USERS_FILE), one user per line:
  ``usuario scrypt$16384$8$1$<salt_b64>$<hash_b64>``. Create lines with ``python -m scripts.add_user``.
  The session survives a browser refresh through an HMAC-signed cookie (WEAVERS_SESSION_SECRET).
- oidc: Streamlit st.login + allowlist WEAVERS_ALLOWED_EMAILS ([auth] in .streamlit/secrets.toml).
- disabled: only with WEAVERS_ALLOW_INSECURE_LOCAL=1, for local tests.
Anything else (or missing users/secret) denies access.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from pathlib import Path

import streamlit as st

COOKIE = "weavers_session"
SESSION_TTL = 12 * 3600
MAX_FAILURES = 5          # per user or per IP ...
LOCK_SECONDS = 15 * 60    # ... within this window, then locked for the same time
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 1

_failures: dict[str, list[float]] = {}  # shared by every session of this process
_lock = threading.Lock()


# ---------------------------------------------------------------- password hashing
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    b64 = lambda b: base64.b64encode(b).decode()  # noqa: E731
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${b64(salt)}${b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, digest = stored.split("$")
        if algo != "scrypt":
            return False
        expected = base64.b64decode(digest)
        got = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p),
                             dklen=len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(got, expected)


_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))  # equal timing for unknown users


def load_users(path: str | os.PathLike | None = None) -> dict[str, str]:
    path = Path(path or os.getenv("WEAVERS_USERS_FILE", "/run/secrets/weavers_users"))
    users = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#") and len(line.split()) == 2:
            name, stored = line.split()
            users[name.casefold()] = stored
    return users


# ---------------------------------------------------------------- brute-force throttle
def _recent(key: str, now: float) -> list[float]:
    return [t for t in _failures.get(key, []) if now - t < LOCK_SECONDS]


def is_locked(*keys: str, now: float | None = None) -> bool:
    now = time.time() if now is None else now
    with _lock:
        return any(len(_recent(k, now)) >= MAX_FAILURES for k in keys)


def record_failure(*keys: str, now: float | None = None) -> None:
    now = time.time() if now is None else now
    with _lock:
        for k in keys:
            _failures[k] = [*_recent(k, now), now]


def clear_failures(*keys: str) -> None:
    with _lock:
        for k in keys:
            _failures.pop(k, None)


# ---------------------------------------------------------------- signed session cookie
def _key(secret: str, stored_hash: str) -> bytes:
    # Bound to the password hash: changing a password invalidates that user's sessions.
    return hashlib.sha256(f"{secret}\x00{stored_hash}".encode()).digest()


def make_token(user: str, secret: str, stored_hash: str, now: float | None = None) -> str:
    now = time.time() if now is None else now
    body = base64.urlsafe_b64encode(json.dumps({"u": user, "e": int(now + SESSION_TTL)}).encode()).decode()
    sig = hmac.new(_key(secret, stored_hash), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def read_token(token: str, secret: str, users: dict[str, str], now: float | None = None) -> str | None:
    now = time.time() if now is None else now
    try:
        body, sig = token.split(".")
        data = json.loads(base64.urlsafe_b64decode(body))
        user = str(data["u"])
        stored = users.get(user)
        if not stored or now > float(data["e"]):
            return None
        expected = hmac.new(_key(secret, stored), body.encode(), hashlib.sha256).hexdigest()
        return user if hmac.compare_digest(sig, expected) else None
    except (ValueError, KeyError, TypeError):
        return None


def _set_cookie(value: str, max_age: int) -> None:
    import streamlit.components.v1 as components
    cookie = f"{COOKIE}={value}; Path=/; Max-Age={max_age}; SameSite=Strict; Secure"
    components.html(f"<script>(window.parent||window).document.cookie = {json.dumps(cookie)};</script>", height=0)


def _client_ip() -> str:
    h = st.context.headers
    return (h.get("Cf-Connecting-Ip") or (h.get("X-Forwarded-For") or "").split(",")[0].strip()
            or str(getattr(st.context, "ip_address", "") or "?"))


# ---------------------------------------------------------------- entry point
def require_login() -> None:
    mode = os.getenv("WEAVERS_AUTH_MODE", "password").lower()
    if mode == "disabled" and os.getenv("WEAVERS_ALLOW_INSECURE_LOCAL") == "1":
        st.sidebar.warning("AUTH DESACTIVADA — no publicar esta configuración.")
        return
    if mode == "password":
        return _require_password()
    if mode in ("oidc", "required"):
        return _require_oidc()
    st.error("Configuración de autenticación inválida. Acceso denegado.")
    st.stop()


def _require_password() -> None:
    users = load_users()
    secret = os.getenv("WEAVERS_SESSION_SECRET", "")
    if not users or len(secret) < 32:
        st.error("Autenticación sin configurar (usuarios o secreto de sesión). Acceso denegado.")
        st.stop()
    ss = st.session_state

    user = ss.get("auth_user")
    if user and user not in users:  # removed from the users file while logged in
        user = ss["auth_user"] = None
    if not user and not ss.get("auth_logged_out"):
        token = st.context.cookies.get(COOKIE)
        user = read_token(token, secret, users) if token else None
        ss["auth_user"] = user

    if user:
        if ss.pop("auth_set_cookie", False):
            _set_cookie(make_token(user, secret, users[user]), SESSION_TTL)
        with st.sidebar:
            st.caption(f"Sesión: {user}")
            if st.button("Cerrar sesión", key="weavers_logout"):
                ss["auth_user"], ss["auth_logged_out"] = None, True
                st.rerun()
        return

    if ss.get("auth_logged_out"):
        _set_cookie("", 0)
    _login_form(users, secret)
    st.stop()


def _login_form(users: dict[str, str], secret: str) -> None:
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.title("Weavers Logistic")
        st.caption("Acceso privado")
        with st.form("login"):
            name = st.text_input("Usuario", autocomplete="username")
            pwd = st.text_input("Contraseña", type="password", autocomplete="current-password")
            sent = st.form_submit_button("Entrar", type="primary", width="stretch")
        if not sent:
            return
        name = name.strip().casefold()
        keys = (f"u:{name}", f"ip:{_client_ip()}")
        if is_locked(*keys):
            st.error("Demasiados intentos. Espera 15 minutos.")
            return
        stored = users.get(name)
        ok = verify_password(pwd, stored or _DUMMY_HASH) and stored is not None
        if not ok:
            record_failure(*keys)
            st.error("Usuario o contraseña incorrectos.")
            return
        clear_failures(*keys)
        st.session_state.update(auth_user=name, auth_logged_out=False, auth_set_cookie=True)
        st.rerun()


def _require_oidc() -> None:
    if not st.user.is_logged_in:
        st.title("Weavers Logistic")
        st.write("Accede con tu proveedor de identidad para consultar datos comerciales.")
        if st.button("Iniciar sesión", type="primary"):
            st.login()
        st.stop()

    allowed = {x.strip().casefold() for x in os.getenv("WEAVERS_ALLOWED_EMAILS", "").split(",") if x.strip()}
    email = str(getattr(st.user, "email", "") or "").strip().casefold()
    # Identity-provider authentication alone is insufficient for an internal console.
    if not allowed or not email or email not in allowed:
        st.error("Usuario sin autorización para acceder a esta consola.")
        if st.button("Cerrar sesión"):
            st.logout()
        st.stop()
    with st.sidebar:
        st.caption(f"Sesión: {email}")
        if st.button("Cerrar sesión", key="weavers_logout"):
            st.logout()
