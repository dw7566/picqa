"""End-to-end tests for the CLI."""

from __future__ import annotations

import pandas as pd

from picqa.cli import main


def test_cli_inventory(mini_data_dir, capsys):
    rc = main(["inventory", str(mini_data_dir)])
    assert rc == 0
    captured = capsys.readouterr()
    assert "Total files: 2" in captured.out
    assert "D24" in captured.out


def test_cli_extract_mzm_writes_csv(mini_data_dir, tmp_path, capsys):
    out = tmp_path / "features.csv"
    rc = main(["extract", "mzm", str(mini_data_dir), "-o", str(out)])
    assert rc == 0
    assert out.exists()
    df = pd.read_csv(out)
    assert "FSR_nm" in df.columns
    assert len(df) == 1


def test_cli_extract_pd_writes_csv(mini_data_dir, tmp_path):
    out = tmp_path / "pd.csv"
    rc = main(["extract", "pd", str(mini_data_dir), "-o", str(out)])
    assert rc == 0
    df = pd.read_csv(out)
    assert "I_dark_at_-1V_pA" in df.columns


def test_cli_plot_iv(mini_data_dir, tmp_path):
    out = tmp_path / "iv.png"
    rc = main(["plot", "iv", str(mini_data_dir), "-o", str(out)])
    assert rc == 0
    assert out.exists()
    assert out.stat().st_size > 0


def test_cli_yield_with_spec(mini_data_dir, tmp_path):
    # Extract first
    feat_csv = tmp_path / "features.csv"
    main(["extract", "mzm", str(mini_data_dir), "-o", str(feat_csv)])

    spec_yaml = tmp_path / "spec.yaml"
    spec_yaml.write_text(
        "mzm:\n"
        "  PeakIL_near_1310_dB:\n"
        "    min: -50\n"
    )

    out_csv = tmp_path / "yield.csv"
    rc = main(["yield", str(feat_csv), "--spec", str(spec_yaml),
               "--family", "mzm", "-o", str(out_csv)])
    assert rc == 0
    assert out_csv.exists()


def test_cli_report_generates_markdown(mini_data_dir, tmp_path):
    out_dir = tmp_path / "report"
    rc = main(["report", str(mini_data_dir), "-o", str(out_dir)])
    assert rc == 0
    md = out_dir / "report.md"
    assert md.exists()
    content = md.read_text(encoding="utf-8")
    assert "PICQA Analysis Report" in content
    assert "Inventory" in content


def test_cli_version_flag(capsys):
    try:
        main(["--version"])
    except SystemExit as e:
        assert e.code == 0
    captured = capsys.readouterr()
    assert "picqa" in captured.out
