import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WRONG_W9_WORKFLOW_ID = "47e95b24-5d38-4e7a-a5c6-76b7f8e6b667"
REAL_W9_WORKFLOW_ID = "47e95b24-db40-4cd5-b667-5b90e170b667"
SCAN_SUFFIXES = {".py", ".ps1", ".sh"}


def _source_files():
    files = []
    for path in (ROOT / "scripts").rglob("*"):
        if path.is_file() and path.suffix.lower() in SCAN_SUFFIXES:
            files.append(path)
    files.append(ROOT / "service" / "demo_mode.py")
    for path in (ROOT / "pages").glob("*.py"):
        files.append(path)
    return files


class W9WorkflowIdTests(unittest.TestCase):
    def test_no_wrong_w9_workflow_id_in_scripts_or_demo_or_pages(self):
        offenders = []
        for path in _source_files():
            text = path.read_text(encoding="utf-8", errors="ignore")
            if WRONG_W9_WORKFLOW_ID in text:
                offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [], "Wrong W9 workflow_id still present")

    def test_w9_drill_script_uses_real_workflow_id(self):
        text = (ROOT / "scripts" / "run_w9_correlated_drill.ps1").read_text(encoding="utf-8")
        self.assertIn(REAL_W9_WORKFLOW_ID, text)

    def test_demo_mode_w9_default_uses_real_workflow_id(self):
        text = (ROOT / "service" / "demo_mode.py").read_text(encoding="utf-8")
        self.assertIn(REAL_W9_WORKFLOW_ID, text)


if __name__ == "__main__":
    unittest.main()
