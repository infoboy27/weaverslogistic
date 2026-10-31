import pandas as pd

from fba_trends import safe_io


def test_write_csv_atomic_and_readable(tmp_path):
    target = tmp_path / "sub" / "x.csv"
    safe_io.write_csv(pd.DataFrame({"a": [1, 2]}), target)
    assert pd.read_csv(target)["a"].tolist() == [1, 2]
    safe_io.write_csv(pd.DataFrame({"a": [3]}), target)
    assert pd.read_csv(target)["a"].tolist() == [3]
    assert [p.name for p in target.parent.iterdir() if p.suffix == ".tmp"] == []  # no temp files left


def test_failed_write_keeps_previous_file(tmp_path):
    target = tmp_path / "x.txt"
    safe_io.write_text(target, "old")

    class Boom:
        def to_csv(self, **kw):
            raise RuntimeError("boom")
    try:
        safe_io.write_csv(Boom(), target)
    except RuntimeError:
        pass
    assert target.read_text() == "old"
