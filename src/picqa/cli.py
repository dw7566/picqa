"""Command-line interface for picqa (week-2 subset)."""
from __future__ import annotations
import argparse, logging, pickle, sys
from pathlib import Path
from picqa import __version__
from picqa.extract.mzm import extract_mzm_features
from picqa.extract.photodetector import extract_pd_features
from picqa.io.xml_parser import inventory, parse_directory


def cmd_inventory(args):
    inv = inventory(args.data_dir)
    print(f"Total files: {inv['n_files']}, {inv['total_size_bytes']/1e6:.1f} MB")
    for k, v in inv["by_wafer"].items():
        print(f"  {k}: {v} files")
    return 0


def cmd_parse(args):
    measurements = parse_directory(args.data_dir, test_site=args.test_site)
    print(f"Parsed {len(measurements)} measurements")
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("wb") as f:
            pickle.dump(measurements, f)
    return 0


def cmd_extract(args):
    test_site_map = {"mzm": "DCM_LMZO", "pd": "DCM_GPDO"}
    measurements = parse_directory(args.data_dir, test_site=test_site_map[args.device])
    if args.device == "mzm":
        df = extract_mzm_features(measurements)
    else:
        df = extract_pd_features(measurements)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out, index=False)
        print(f"Saved → {out}")
    else:
        print(df.head())
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="picqa")
    p.add_argument("-V", "--version", action="version", version=f"picqa {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("inventory"); sp.add_argument("data_dir"); sp.set_defaults(func=cmd_inventory)
    sp = sub.add_parser("parse")
    sp.add_argument("data_dir"); sp.add_argument("--test-site"); sp.add_argument("-o", "--output")
    sp.set_defaults(func=cmd_parse)
    sp = sub.add_parser("extract")
    sp.add_argument("device", choices=["mzm", "pd"])
    sp.add_argument("data_dir"); sp.add_argument("-o", "--output")
    sp.set_defaults(func=cmd_extract)

    args = p.parse_args(argv)
    logging.basicConfig(level=logging.WARNING)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
