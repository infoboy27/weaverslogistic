import base64
import time

from fba_trends import auth


def test_hash_roundtrip():
    h = auth.hash_password("correct horse battery")
    assert h.startswith("scrypt$")
    assert auth.verify_password("correct horse battery", h)
    assert not auth.verify_password("wrong", h)
    assert not auth.verify_password("x", "garbage")


def test_load_users(tmp_path):
    f = tmp_path / "users.txt"
    f.write_text("# comentario\nAna@Example.com scrypt$1$2$3$a$b\n\nmalformed\n", encoding="utf-8")
    assert auth.load_users(f) == {"ana@example.com": "scrypt$1$2$3$a$b"}
    assert auth.load_users(tmp_path / "missing.txt") == {}


def test_token_signed_expiring_and_bound_to_password():
    secret = "s" * 40
    users = {"ana": "hash1"}
    tok = auth.make_token("ana", secret, "hash1", now=1000)
    assert auth.read_token(tok, secret, users, now=1001) == "ana"
    assert auth.read_token(tok, secret, users, now=1000 + auth.SESSION_TTL + 1) is None
    assert auth.read_token(tok, "o" * 40, users, now=1001) is None
    assert auth.read_token(tok, secret, {"ana": "hash2"}, now=1001) is None  # password changed
    assert auth.read_token(tok, secret, {}, now=1001) is None  # user removed
    body, sig = tok.split(".")
    forged = auth.make_token("bob", secret, "hash1", now=1000).split(".")[0]
    assert auth.read_token(f"{forged}.{sig}", secret, {"bob": "hash1"}, now=1001) is None
    assert auth.read_token("not-a-token", secret, users) is None


def test_lockout_after_failures():
    keys = ("u:test-lock", "ip:1.2.3.4")
    auth.clear_failures(*keys)
    for i in range(auth.MAX_FAILURES):
        assert not auth.is_locked(*keys, now=100 + i)
        auth.record_failure(*keys, now=100 + i)
    assert auth.is_locked("u:test-lock", now=110)
    assert auth.is_locked("ip:1.2.3.4", now=110)
    assert not auth.is_locked(*keys, now=100 + auth.LOCK_SECONDS + 10)
    auth.clear_failures(*keys)


def test_password_mode_without_users_denies(monkeypatch, tmp_path):
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("WEAVERS_AUTH_MODE", "password")
    monkeypatch.setenv("WEAVERS_USERS_FILE", str(tmp_path / "none.txt"))
    monkeypatch.setenv("WEAVERS_SESSION_SECRET", "s" * 40)
    at = AppTest.from_file(str(Path(__file__).resolve().parent.parent / "app.py"), default_timeout=60).run()
    assert at.error and "Acceso denegado" in at.error[0].value
    assert not at.metric


def test_password_mode_login(monkeypatch, tmp_path):
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    users = tmp_path / "users.txt"
    users.write_text(f"ana@example.com {auth.hash_password('una-clave-larga')}\n", encoding="utf-8")
    monkeypatch.setenv("WEAVERS_AUTH_MODE", "password")
    monkeypatch.setenv("WEAVERS_USERS_FILE", str(users))
    monkeypatch.setenv("WEAVERS_SESSION_SECRET", "s" * 40)
    at = AppTest.from_file(str(Path(__file__).resolve().parent.parent / "app.py"), default_timeout=180).run()
    assert not at.metric  # login form only
    at.text_input[0].input("ana@example.com")
    at.text_input[1].input("mala")
    at.button[0].click().run()
    assert at.error and "incorrectos" in at.error[0].value
    at.text_input[1].input("una-clave-larga")
    at.button[0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert "Analizados" in [m.label for m in at.metric]


def test_totp_rfc6238_vector():
    # RFC 6238 appendix B, SHA-1 seed "12345678901234567890", T=59 -> 94287082 (last 6 digits)
    secret = base64.b32encode(b"12345678901234567890").decode()
    assert auth.totp_code(secret, 59) == "287082"
    assert auth.verify_totp(secret, "287082", now=59)
    assert auth.verify_totp(secret, "287 082", now=59 + 30)  # one step of clock drift is fine
    assert not auth.verify_totp(secret, "287082", now=59 + 120)
    assert not auth.verify_totp(secret, "12345", now=59)


def test_accounts_with_totp(tmp_path):
    f = tmp_path / "users.txt"
    f.write_text("ana scrypt$a totp:ABCDEF\nbob scrypt$b\nbad scrypt$c extra:1\n", encoding="utf-8")
    acc = auth.load_accounts(f)
    assert acc["ana"] == {"hash": "scrypt$a", "totp": "ABCDEF"}
    assert acc["bob"]["totp"] is None and acc["bad"]["totp"] is None
    assert auth.load_users(f) == {"ana": "scrypt$a", "bob": "scrypt$b", "bad": "scrypt$c"}


def test_token_epoch_revokes_old_sessions():
    secret, users = "s" * 40, {"ana": "h"}
    tok = auth.make_token("ana", secret, "h", now=1000, epoch=2)
    assert auth.read_token(tok, secret, users, now=1001, epoch_of=lambda u: 2) == "ana"
    assert auth.read_token(tok, secret, users, now=1001, epoch_of=lambda u: 3) is None
    assert auth.read_token(tok, secret, users, now=1001) == "ana"  # no epoch source: signature only


def test_totp_login_flow(monkeypatch, tmp_path):
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    secret = base64.b32encode(b"weavers-test-secret!").decode()
    users = tmp_path / "users.txt"
    users.write_text(f"ana {auth.hash_password('una-clave-larga')} totp:{secret}\n", encoding="utf-8")
    monkeypatch.setenv("WEAVERS_AUTH_MODE", "password")
    monkeypatch.setenv("WEAVERS_USERS_FILE", str(users))
    monkeypatch.setenv("WEAVERS_SESSION_SECRET", "s" * 40)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    at = AppTest.from_file(str(Path(__file__).resolve().parent.parent / "app.py"), default_timeout=180).run()
    at.text_input[0].input("ana")
    at.text_input[1].input("una-clave-larga")
    at.button[0].click().run()
    assert not at.metric and "Código de 6 dígitos" in [t.label for t in at.text_input]
    at.text_input[0].input("000000" if auth.totp_code(secret, time.time()) != "000000" else "111111")
    at.button[0].click().run()
    assert at.error and "incorrecto" in at.error[0].value
    at.text_input[0].input(auth.totp_code(secret, time.time()))
    at.button[0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert "Analizados" in [m.label for m in at.metric]
