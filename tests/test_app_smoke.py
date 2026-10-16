"""Smoke test: the whole dashboard script runs and the home page renders without exceptions."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parent.parent / "app.py"


def test_home_page_renders():
    at = AppTest.from_file(str(APP), default_timeout=180).run()
    assert not at.exception, [e.value for e in at.exception]
    labels = [m.label for m in at.metric]
    assert "Analizados" in labels and "Candidatos" in labels
