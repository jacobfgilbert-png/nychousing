from __future__ import annotations

import importlib.util
import inspect
import sys
import traceback
from pathlib import Path


def main() -> int:
    tests_dir = Path("tests")
    failures = 0
    total = 0
    for path in sorted(tests_dir.glob("test_*.py")):
        module = _load_module(path)
        for name, func in inspect.getmembers(module, inspect.isfunction):
            if not name.startswith("test_"):
                continue
            total += 1
            try:
                func()
                print(f"{path.name}::{name} PASSED")
            except Exception:
                failures += 1
                print(f"{path.name}::{name} FAILED")
                traceback.print_exc()
    print(f"{total - failures} passed, {failures} failed")
    return 1 if failures else 0


def console_main() -> int:
    return main()


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    raise SystemExit(main())
