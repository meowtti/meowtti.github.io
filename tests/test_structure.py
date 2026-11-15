"""구조 시험 — 허락 목록 .gitignore가 쓰레기는 막고 올릴 것은 여는지 git에게 직접 묻는다."""

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _ignored(path: str) -> bool:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    r = subprocess.run(
        ["git", "-C", str(ROOT), "check-ignore", "--no-index", "-q", path],
        env=env,
        capture_output=True,
    )
    return r.returncode == 0


@pytest.mark.parametrize(
    "path",
    [
        ".DS_Store",
        "tests/.DS_Store",
        "Thumbs.db",
        "checks/desktop.ini",
        "resume.pdf",
        "random_folder/x.txt",
        ".env",
        "checks/.env.local",
        "checks/build.zip",
        "node_modules/a.js",
        ".venv/Scripts/python.exe",
        "public/index.html",
        "resources/_gen/x.css",
        ".hugo_build.lock",
    ],
)
def test_junk_is_ignored(path):
    assert _ignored(path), f"{path} 이(가) 막히지 않음 — .gitignore 허락 목록을 본다"


@pytest.mark.parametrize(
    "path",
    [
        ".gitignore",
        ".gitattributes",
        ".pre-commit-config.yaml",
        "README.md",
        "CLAUDE.md",
        "pyproject.toml",
        "uv.lock",
        ".python-version",
        "checks/guard.py",
        "tests/test_guard.py",
        "hugo.toml",
        "layouts/baseof.html",
        "content/posts/a.md",
        "static/toys/demo/index.html",
        ".github/workflows/pages.yml",
    ],
)
def test_allowed_files_are_open(path):
    assert not _ignored(path), f"{path} 이(가) 막힘 — 올려야 하는 파일이면 .gitignore에 ! 줄"
