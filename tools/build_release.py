# Copyright (C) 2026 Connor Baird
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software under GNU GPL version 3 or later.
# It comes WITHOUT ANY WARRANTY; see LICENSE and NOTICE.
"""Build and verify a source + sdist + wheel release. Never publishes."""

import argparse
import ast
from datetime import date
from email.parser import BytesParser
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
    "NOTICE",
    "THIRD_PARTY_NOTICES.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "MANIFEST.in",
    "pyproject.toml",
    "launch.py",
    "install.py",
    "requirements-tested.txt",
    ".gitignore",
    "Install-and-Run.bat",
    "Run.bat",
    "Run-Terminal.bat",
    "install-and-run.sh",
    "run.sh",
    "run-terminal.sh",
}
DIRECTORIES = {
    "statbridge",
    "docs",
    "examples",
    "tests",
    "tools",
    "benchmarks",
    ".github",
}
EXTENSIONS = {".py", ".md", ".txt", ".json", ".csv", ".do", ".yml"}
SKIP = {"__pycache__", ".pytest_cache", ".venv", "build", "dist", ".git"}


def version_assignment(path, variable):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == variable for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise ValueError(f"Missing {variable} in {path.name}")


def check_versions(root):
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    version = project["version"]
    if version_assignment(root / "statbridge/__init__.py", "__version__") != version:
        raise ValueError("Package and project versions differ")
    if version_assignment(root / "launch.py", "RELEASE_VERSION") != version:
        raise ValueError("Launcher and project versions differ")
    if (
        project["license"] != "GPL-3.0-or-later"
        or {"name": "Connor Baird"} not in project["authors"]
    ):
        raise ValueError("Review author and GPL metadata before building")
    return version


def validate_wheel(wheel, root, version):
    with zipfile.ZipFile(wheel) as z:
        metadata_name = next(
            n for n in z.namelist() if n.endswith(".dist-info/METADATA")
        )
        metadata = BytesParser().parsebytes(z.read(metadata_name))
        if metadata["Version"] != version or metadata["Author"] != "Connor Baird":
            raise ValueError("Wheel version/author mismatch")
        if metadata["License-Expression"] != "GPL-3.0-or-later":
            raise ValueError("Wheel GPL metadata missing")
        for name in ("LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md"):
            if z.read("statbridge/legal/" + name) != (root / name).read_bytes():
                raise ValueError("Missing or stale wheel legal notice: " + name)
        asset_name = "statbridge/assets/statbridge.svg"
        if z.read(asset_name) != (root / asset_name).read_bytes():
            raise ValueError("Wheel application icon missing or stale")
        for path in (root / "statbridge").rglob("*.py"):
            if (
                "__pycache__" not in path.parts
                and z.read(path.relative_to(root).as_posix()) != path.read_bytes()
            ):
                raise ValueError("Wheel source mismatch: " + path.name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    version = check_versions(ROOT)
    # Only reviewed binary assets can enter a release, not arbitrary downloaded data.
    assets = set(json.loads((ROOT / "tools/approved_assets.json").read_text()))
    for name in ("LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md"):
        target = ROOT / "statbridge/legal" / name
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    environment = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    print(result.stdout)
    if result.returncode:
        raise SystemExit("Tests failed; no release built.")
    with tempfile.TemporaryDirectory(prefix="statbridge-build-") as temp:
        stage = Path(temp) / f"StatBridge-Qt-{version}"
        stage.mkdir()
        for path in sorted(ROOT.rglob("*")):
            relative = path.relative_to(ROOT)
            if any(p in SKIP or p.endswith(".egg-info") for p in relative.parts):
                continue
            if not path.is_file():
                continue
            if len(relative.parts) == 1:
                if relative.as_posix() not in ROOT_FILES:
                    continue
            elif relative.parts[0] not in DIRECTORIES:
                continue
            elif path.suffix not in EXTENSIONS and relative.as_posix() not in assets:
                # Legal resources and retained fixture licence are text without suffix.
                if relative.as_posix() not in {
                    "statbridge/legal/LICENSE",
                    "statbridge/legal/NOTICE",
                    "tests/fixtures/PYREADSTAT_LICENSE",
                }:
                    raise ValueError("Unreviewed release asset: " + relative.as_posix())
            if path.is_symlink():
                raise ValueError("Release source must not contain symlinks")
            dest = stage / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
        (stage / "docs/test-results.txt").write_text(result.stdout, encoding="utf-8")
        summary = next(
            (line for line in reversed(result.stdout.splitlines()) if "passed" in line),
            "See docs/test-results.txt",
        )
        manifest = {
            "version": version,
            "channel": "public beta",
            "date": date.today().isoformat(),
            "author": "Connor Baird",
            "license": "GPL-3.0-or-later",
            "tests": summary,
            "tested_platform": sys.platform,
            "python": sys.version.split()[0],
            "native_windows_macos_verified": False,
            "stata_parity_verified": False,
            "dtabnk_commit": "a1af2b0cfc87cedef12b416d2fa2ae6ff341ff63",
        }
        manifest["sha256"] = {
            p.relative_to(stage).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(stage.rglob("*"))
            if p.is_file() and p.name != "RELEASE.json"
        }
        (stage / "RELEASE.json").write_text(json.dumps(manifest, indent=2) + "\n")
        subprocess.run(
            [sys.executable, "-m", "build", "--no-isolation"], cwd=stage, check=True
        )
        wheels = list((stage / "dist").glob("*.whl"))
        if len(wheels) != 1:
            raise ValueError("Expected exactly one wheel")
        validate_wheel(wheels[0], stage, version)
        installed = Path(temp) / "installed"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--target",
                str(installed),
                str(wheels[0]),
            ],
            check=True,
        )
        smoke = subprocess.run(
            [sys.executable, str(stage / "tools/smoke_installed.py"), str(installed)],
            cwd=temp,
            env=dict(environment, PYTHONPATH=str(installed)),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if smoke.returncode:
            print(smoke.stdout)
            raise SystemExit("Installed-wheel checks failed; no release built.")
        (stage / "docs/installed-test-results.txt").write_text(
            smoke.stdout, encoding="utf-8"
        )
        manifest["installed_wheel_checks"] = (
            "30 lessons and 3 example do-files; see docs/installed-test-results.txt"
        )
        members = [
            p
            for p in stage.rglob("*")
            if p.is_file()
            and not any(
                x in SKIP - {"dist"} or x.endswith(".egg-info")
                for x in p.relative_to(stage).parts
            )
            and p.name != "RELEASE.json"
        ]
        manifest["sha256"] = {
            p.relative_to(stage).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(members)
        }
        manifest_path = stage / "RELEASE.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        args.output.mkdir(parents=True, exist_ok=True)
        output = args.output.resolve() / (stage.name + ".zip")
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
            for path in sorted(members + [manifest_path]):
                info = zipfile.ZipInfo(
                    stage.name + "/" + path.relative_to(stage).as_posix(),
                    (2026, 1, 1, 0, 0, 0),
                )
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (
                    0o100755 if path.suffix == ".sh" else 0o100644
                ) << 16
                z.writestr(info, path.read_bytes())
        with zipfile.ZipFile(output) as z:
            if z.testzip() is not None:
                raise ValueError("ZIP integrity failed")
        checksum = hashlib.sha256(output.read_bytes()).hexdigest()
        (args.output / "SHA256SUMS").write_text(checksum + "  " + output.name + "\n")
        print(f"Built {output}\nSHA256 {checksum}")


if __name__ == "__main__":
    main()
