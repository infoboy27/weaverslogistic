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
