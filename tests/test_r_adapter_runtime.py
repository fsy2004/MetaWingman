from __future__ import annotations

import importlib.util
import os
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "metawingman" / "scripts" / "test_r_adapters.py"
SPEC = importlib.util.spec_from_file_location("test_r_adapters_runtime", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RAdapterRuntimeTests(unittest.TestCase):
    def test_resolve_rscript_discovers_platform_command_when_env_is_absent(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch("shutil.which", return_value="/opt/r/bin/Rscript"):
            self.assertEqual(MODULE.resolve_rscript(), "/opt/r/bin/Rscript")


if __name__ == "__main__":
    unittest.main()
