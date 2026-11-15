"""새 놀이 저장소 도구(tools/toy.py) 시험 — 네트워크 없이 본다.

핵심: prepare가 놀이 폴더 안에서만 커밋 전 검사를 켜고, 놀이터 자기 검사 장치는 건드리지 않는다
(2026-11-15 다른 저장소 설정으로 install해서 놀이터 훅이 바뀐 사고).
"""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("toy", ROOT / "tools" / "toy.py")
toy = importlib.util.module_from_spec(_spec)
sys.modules["toy"] = toy
_spec.loader.exec_module(toy)

PRECOMMIT = ROOT / ".venv" / "Scripts" / "pre-commit.exe"


def _git(*args, cwd):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True)


def test_site_config_comes_from_hugo_toml():
    owner, base = toy.site_config()
    assert owner == "meowtti"
    assert base == "https://meowtti.github.io/"


def test_gitignore_is_allowlist():
    text = toy.gitignore_text(["img", "bgm"], ["index.html", "anscene.js"])
    lines = text.splitlines()
    assert "/*" in lines
    for want in ["!/index.html", "!/anscene.js", "!/img/", "!/bgm/", "!/.nojekyll", "!/README.md"]:
        assert want in lines, want
    assert ".env" in lines and "*.zip" in lines


def test_live_urls_skip_dotfiles_and_quote():
    urls = toy.live_urls(
        "https://meowtti.github.io/", "demo", [".gitignore", "README.md", "img/한 칸.png", "index.html"]
    )
    assert urls[0] == "https://meowtti.github.io/demo/"
    assert "https://meowtti.github.io/demo/index.html" in urls
    assert any(u.endswith("/img/%ED%95%9C%20%EC%B9%B8.png") for u in urls)
    assert not any(".gitignore" in u or u.endswith("README.md") for u in urls)


@pytest.mark.skipif(not (ROOT.parent / "akjil-cat").exists(), reason="본보기 놀이 저장소가 옆에 없음")
def test_skeleton_matches_published_example():
    # 2026-11-16 실전으로 올라간 놀이 저장소와 글자까지 같아야 한다
    ex = ROOT.parent / "akjil-cat"
    assert toy.precommit_config(ROOT.name) == ex.joinpath(".pre-commit-config.yaml").read_text(
        encoding="utf-8"
    )
    assert toy.GITATTRIBUTES == ex.joinpath(".gitattributes").read_text(encoding="utf-8")


def test_publish_needs_confirm(capsys):
    assert toy.main(["publish", "demo"]) != 0
    assert "--confirm" in capsys.readouterr().out


@pytest.mark.parametrize("bad", ["", "../x", "a/b", "Demo", "-x", "meowtti.github.io"])
def test_bad_names_refused(bad):
    with pytest.raises(SystemExit):
        toy.check_name(bad)


@pytest.mark.skipif(not PRECOMMIT.exists(), reason="이 PC 밖(검사 도구 없음)")
def test_prepare_sets_up_sibling_without_touching_playground(tmp_path):
    own_hook = ROOT / ".git" / "hooks" / "pre-commit"
    before = own_hook.read_bytes() if own_hook.exists() else None
    target = tmp_path / "demo"
    target.mkdir()
    (target / "README.md").write_bytes("# 내 글\n".encode("utf-8"))
    (target / "index.html").write_bytes(b"<!doctype html>")

    toy.prepare("demo", folders=["img"], parent=tmp_path)

    # 놀이 폴더 안에 검사 장치가 걸리고, 그 설정을 가리킨다
    hook = target / ".git" / "hooks" / "pre-commit"
    assert hook.exists(), "놀이 폴더에 커밋 전 검사가 안 켜짐"
    assert "--config=.pre-commit-config.yaml" in hook.read_text(encoding="utf-8", errors="ignore")
    # 놀이터 자기 장치는 그대로
    after = own_hook.read_bytes() if own_hook.exists() else None
    assert before == after, "놀이터 저장소 커밋 전 검사가 바뀜"
    # 이미 있던 README는 덮어쓰지 않는다
    assert (target / "README.md").read_bytes() == "# 내 글\n".encode("utf-8")
    # 뼈대 파일
    for name in [".gitignore", ".gitattributes", ".nojekyll", ".pre-commit-config.yaml"]:
        assert (target / name).exists(), name
    # 작성자 = 놀이터와 같은 noreply · 원격 = 계정/이름
    mail = _git("config", "user.email", cwd=target).stdout.strip()
    assert mail == _git("config", "user.email", cwd=ROOT).stdout.strip()
    assert (
        _git("remote", "get-url", "origin", cwd=target).stdout.strip()
        == "https://github.com/meowtti/demo.git"
    )
    # 허락 목록이 실제로 먹는다
    assert _git("check-ignore", "-q", "notes.txt", cwd=target).returncode == 0
    assert _git("check-ignore", "-q", "img/a.png", cwd=target).returncode != 0
    assert _git("check-ignore", "-q", "index.html", cwd=target).returncode != 0

    # 두 번 돌려도 그대로(덮어쓰기 · 원격 중복 없음)
    toy.prepare("demo", folders=["img"], parent=tmp_path)
    assert (target / "README.md").read_bytes() == "# 내 글\n".encode("utf-8")
