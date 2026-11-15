"""사이트 굽기 시험 — Hugo가 박아 둔 판으로 실제로 굽히고, 결과물이 원칙을 지키는지 본다.

Hugo가 없거나 판이 다르면 「확인 못 함」으로 넘기지 않고 빨갛게 멈춘다(통과가 아니다).
"""

import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _pinned_version() -> str:
    conf = tomllib.loads((ROOT / "hugo.toml").read_text(encoding="utf-8"))
    hv = conf["module"]["hugoVersion"]
    assert hv["min"] == hv["max"], "hugo.toml [module.hugoVersion] min · max는 같은 판 하나로 박는다"
    return hv["min"]


def _hugo() -> str:
    exe = shutil.which("hugo")
    assert exe, "hugo가 PATH에 없음 — winget install --id Hugo.Hugo (판은 hugo.toml)"
    return exe


def test_installed_hugo_matches_pin():
    out = subprocess.run([_hugo(), "version"], capture_output=True, text=True, check=True).stdout
    m = re.search(r"v(\d+\.\d+\.\d+)", out)
    assert m, out
    assert m.group(1) == _pinned_version(), (
        f"깔린 Hugo {m.group(1)} ≠ 박아 둔 판 {_pinned_version()} — 판을 올리려면 hugo.toml 한 곳만 고치고 이 시험으로 굽기를 다시 본다"
    )


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("public")
    r = subprocess.run(
        [_hugo(), "--source", str(ROOT), "--destination", str(out), "--quiet", "--panicOnWarning"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    return out


def test_home_page_built(built):
    html = (built / "index.html").read_text(encoding="utf-8")
    assert '<html lang="ko">' in html
    assert "야옹띠의 놀이터" in html


def test_no_external_scripts(built):
    for p in built.rglob("*.html"):
        text = p.read_text(encoding="utf-8")
        srcs = re.findall(r'<script[^>]+src="([^"]+)"', text)
        outside = [s for s in srcs if s.startswith(("http:", "https:", "//"))]
        assert not outside, f"{p.name}: 바깥 스크립트 {outside} — 원칙 2(저장소 안에 복사)"


def test_drafts_not_built(built):
    for md in (ROOT / "content").rglob("*.md"):
        head = md.read_text(encoding="utf-8").split("+++")
        if len(head) >= 3 and tomllib.loads(head[1]).get("draft"):
            title = tomllib.loads(head[1])["title"]
            for p in built.rglob("*.html"):
                assert title not in p.read_text(encoding="utf-8"), f"초안 「{title}」이 {p}에 나옴"


def test_toys_copied_byte_for_byte(built):
    src = ROOT / "static" / "toys"
    if not src.exists():
        pytest.skip("아직 올린 놀이 없음")
    for f in src.rglob("*"):
        if f.is_file():
            rel = f.relative_to(ROOT / "static")
            assert (built / rel).read_bytes() == f.read_bytes(), f"{rel} 이(가) 굽기에서 바뀜"
