"""Run all tests without pytest (we don't have network to install it).

Mimics the parts of the pytest API we use: fixtures, capsys, tmp_path.
This is for development verification only — production CI uses real pytest.
"""

from __future__ import annotations

import inspect
import sys
import tempfile
import traceback
from io import StringIO
from pathlib import Path

# Make the package importable
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))


# ----- Minimal fixture / capsys / tmp_path infrastructure ----- #
class CapSysCapture:
    def __init__(self):
        self.stdout = StringIO()
        self.stderr = StringIO()

    def readouterr(self):
        out = self.stdout.getvalue()
        err = self.stderr.getvalue()
        self.stdout = StringIO()
        self.stderr = StringIO()
        return type("Cap", (), {"out": out, "err": err})()


def with_capsys(func, *args, **kwargs):
    cap = CapSysCapture()
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = cap.stdout, cap.stderr
    try:
        return func(*args, capsys=cap, **kwargs)
    finally:
        sys.stdout, sys.stderr = old_out, old_err


def make_tmp_path():
    return Path(tempfile.mkdtemp(prefix="picqa_test_"))


# ----- Build fixtures from conftest ----- #
DATA_DIR = Path(__file__).resolve().parent / "tests" / "data"


def fixture_sample_lmzo_path():
    return DATA_DIR / "sample_lmzo.xml"


def fixture_sample_gpdo_path():
    return DATA_DIR / "sample_gpdo.xml"


def fixture_sample_measurement():
    from picqa.io.xml_parser import parse_measurement
    return parse_measurement(fixture_sample_lmzo_path())


def fixture_mini_data_dir(tmp_path):
    import shutil
    session_dir = tmp_path / "D24" / "20190531_151815"
    session_dir.mkdir(parents=True)
    shutil.copy(fixture_sample_lmzo_path(),
                session_dir / "HY202103_D24_(0,0)_LION1_DCM_LMZO.xml")
    shutil.copy(fixture_sample_gpdo_path(),
                session_dir / "HY202103_D24_(0,0)_LION1_DCM_GPDO.xml")
    return tmp_path


FIXTURES = {
    "sample_lmzo_path":   lambda **kw: fixture_sample_lmzo_path(),
    "sample_gpdo_path":   lambda **kw: fixture_sample_gpdo_path(),
    "sample_measurement": lambda **kw: fixture_sample_measurement(),
    "mini_data_dir":      lambda tmp_path, **kw: fixture_mini_data_dir(tmp_path),
    "tmp_path":           lambda **kw: make_tmp_path(),
}


def call_with_fixtures(func):
    sig = inspect.signature(func)
    args = {}
    cap = None
    if "capsys" in sig.parameters:
        cap = CapSysCapture()
        args["capsys"] = cap
    if "tmp_path" in sig.parameters:
        args["tmp_path"] = FIXTURES["tmp_path"]()
    # mini_data_dir needs a tmp_path even if the test itself doesn't ask for one
    needs_tmp_for_mini = "mini_data_dir" in sig.parameters
    for name in sig.parameters:
        if name in args:
            continue
        if name in FIXTURES:
            if name == "mini_data_dir":
                if needs_tmp_for_mini and "tmp_path" not in args:
                    # internal scratch tmp dir, not exposed to test
                    internal_tmp = FIXTURES["tmp_path"]()
                    args[name] = FIXTURES[name](tmp_path=internal_tmp)
                else:
                    args[name] = FIXTURES[name](tmp_path=args["tmp_path"])
            else:
                args[name] = FIXTURES[name]()

    if cap is not None:
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = cap.stdout, cap.stderr
        try:
            return func(**args)
        finally:
            sys.stdout, sys.stderr = old_out, old_err
    return func(**args)


# ----- Discover and run tests ----- #
def find_tests():
    test_dir = Path(__file__).resolve().parent / "tests"
    test_files = sorted(test_dir.glob("test_*.py"))
    sys.path.insert(0, str(test_dir))
    tests = []
    for tf in test_files:
        mod_name = tf.stem
        try:
            mod = __import__(mod_name)
        except Exception as e:
            print(f"  IMPORT FAIL {mod_name}: {e}")
            traceback.print_exc()
            continue
        for name in dir(mod):
            if name.startswith("test_"):
                obj = getattr(mod, name)
                if callable(obj):
                    tests.append((mod_name, name, obj))
    return tests


def run_all():
    tests = find_tests()
    n_pass, n_fail = 0, 0
    failures = []
    for mod, name, fn in tests:
        try:
            call_with_fixtures(fn)
            n_pass += 1
            print(f"  PASS  {mod}::{name}")
        except SystemExit as e:
            # CLI's --version raises SystemExit(0); test_cli_version_flag handles this
            if name == "test_cli_version_flag" and (e.code == 0 or e.code is None):
                n_pass += 1
                print(f"  PASS  {mod}::{name}")
            else:
                n_fail += 1
                failures.append((mod, name, f"SystemExit({e.code})", ""))
                print(f"  FAIL  {mod}::{name}  SystemExit({e.code})")
        except Exception as e:
            n_fail += 1
            tb = traceback.format_exc()
            failures.append((mod, name, repr(e), tb))
            print(f"  FAIL  {mod}::{name}  {e!r}")

    print(f"\n{n_pass} passed, {n_fail} failed (total {n_pass + n_fail})")
    if failures:
        print("\n--- failure tracebacks ---")
        for mod, name, err, tb in failures:
            print(f"\n[{mod}::{name}]\n{tb}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(run_all())
