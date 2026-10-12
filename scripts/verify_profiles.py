"""Exercise the actual installed helper across A→B→A in independent CLI processes."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def verify(helper: Path):
    with tempfile.TemporaryDirectory(prefix="reclaim-profile-isolation-") as temporary:
        a, b = Path(temporary) / "profile-a", Path(temporary) / "profile-b"

        def run(root, command):
            env = dict(os.environ, HERMES_HOME=str(root), PYTHONPATH="", PYTHONIOENCODING="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "inbox_reclaimer",
                    "--workspace-scripts",
                    str(helper),
                    "--demo",
                    "--hermes",
                    *command,
                ],
                env=env,
                capture_output=True,
                encoding="utf-8",
                timeout=60,
            )
            if result.returncode:
                raise RuntimeError(result.stderr)
            return json.loads(result.stdout)

        first = run(a, ["analyze", "--json"])
        second = run(b, ["analyze", "--json"])
        reopened = run(a, ["status"])
        assert first["generation"] != second["generation"]
        assert reopened["inventory"]["generation"] == first["generation"]
        for root in (a, b):
            for filename in ("cache.db", "journal.db", "checkpoints.db"):
                assert (root / "inbox_reclaimer" / filename).is_file()
            assert not (root / "google_token.json").exists()
        return {
            "passed": True,
            "helper": str(helper / "_hermes_home.py"),
            "sequence": "A -> B -> A, separate Python processes",
            "distinct_generations": True,
            "credentials_created_or_changed": False,
            "fixture": "synthetic; no Google access",
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-scripts", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    content = json.dumps(verify(args.workspace_scripts), indent=2)
    print(content)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content + "\n", encoding="utf-8")
