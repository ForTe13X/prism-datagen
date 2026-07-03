"""The CLI wires the library correctly: list/gen/sweep exit 0, gen --out writes files, unknown domain fails."""
from datagen.cli import main


def test_list_ok(capsys):
    assert main(["list"]) == 0
    assert "logistics_demo" in capsys.readouterr().out


def test_gen_preview_and_eval(capsys):
    assert main(["gen", "-d", "0.6", "-l", "4", "-s", "ho-0", "--eval"]) == 0
    out = capsys.readouterr().out
    assert "跨源真值" in out and "判别力" in out


def test_gen_writes_all_formats(tmp_path):
    rc = main(["gen", "-d", "0.3", "-s", "ho-0", "-o", str(tmp_path), "--format", "all"])
    assert rc == 0
    got = {p.suffix for p in tmp_path.iterdir()}
    assert ".json" in got and ".db" in got
    assert any(p.is_dir() and p.name.endswith("_csv") for p in tmp_path.iterdir())


def test_sweep_ok(capsys):
    assert main(["sweep", "--over", "link"]) == 0
    assert "naive_f1" in capsys.readouterr().out


def test_unknown_domain_exits_nonzero():
    assert main(["gen", "-D", "nope"]) == 2
