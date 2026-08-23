"""Low-cost guard for the Streamlit curriculum import contract."""

import ast
import os
from pathlib import Path
import subprocess
import sys
import unittest

from services import curriculum_catalog


class CurriculumApiContractTests(unittest.TestCase):
    def test_contract_runs_on_project_venv(self):
        expected = Path(__file__).resolve().parents[1] / ".venv" / "Scripts" / "python.exe"
        self.assertTrue(expected.exists(), expected)
        self.assertEqual(Path(sys.executable).resolve(), expected.resolve())

    def test_app_curriculum_imports_are_public_symbols(self):
        app_source = Path(__file__).resolve().parents[1] / "app.py"
        tree = ast.parse(app_source.read_text(encoding="utf-8"))
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module in {"services.curriculum_catalog", "app.services.curriculum_catalog"}
            for alias in node.names
            if alias.name != "*"
        }
        self.assertTrue(imported)
        missing = sorted(name for name in imported if not hasattr(curriculum_catalog, name))
        self.assertEqual(missing, [])

    def test_both_runtime_import_paths_export_every_symbol(self):
        app_root = str(Path(__file__).resolve().parents[1])
        code = (
            "import importlib; names = " + repr(sorted({
                alias.name
                for node in ast.walk(ast.parse((Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")))
                if isinstance(node, ast.ImportFrom)
                and node.module in {"services.curriculum_catalog", "app.services.curriculum_catalog"}
                for alias in node.names if alias.name != "*"
            })) + "; m=importlib.import_module('services.curriculum_catalog'); assert all(hasattr(m,n) for n in names)"
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = app_root
        result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_app_module_loads_with_streamlit_import_context(self):
        root = Path(__file__).resolve().parents[1]
        app_file = root / "app.py"
        code = (
            "import importlib.util,sys; sys.path.insert(0, r'" + str(root) + "'); "
            "s=importlib.util.spec_from_file_location('mathai_app', r'" + str(app_file) + "'); "
            "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print('APP MODULE IMPORT OK')"
        )
        result = subprocess.run([str(root / ".venv" / "Scripts" / "python.exe"), "-c", code],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        self.assertIn("APP MODULE IMPORT OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
