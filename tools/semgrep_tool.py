import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def run_semgrep(files_content: dict[str, str]) -> list[dict]:
    """Write files to temp dir, run semgrep, return parsed findings."""
    if not files_content:
        return []

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Write each file preserving relative path structure
        for filepath, content in files_content.items():
            dest = tmp / filepath
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")

        semgrep_bin = shutil.which("semgrep") or "semgrep"
        result = subprocess.run(
            [
                semgrep_bin,
                "--config=auto",
                "--json",
                "--quiet",
                str(tmp),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if not result.stdout.strip():
            return []

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return []

        findings = []
        for r in data.get("results", []):
            # Strip temp dir prefix from path
            raw_path = r.get("path", "")
            relative = raw_path.replace(str(tmp) + "/", "")
            findings.append({
                "file": relative,
                "line": r.get("start", {}).get("line", 0),
                "rule_id": r.get("check_id", ""),
                "severity": r.get("extra", {}).get("severity", "INFO").upper(),
                "message": r.get("extra", {}).get("message", ""),
            })

        return findings
