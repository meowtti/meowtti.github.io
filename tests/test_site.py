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


def _site_pages(built: Path) -> list[Path]:
    """Hugo가 틀로 만든 페이지만 — static/에서 그대로 복사된 놀이 본체는 뺀다(바이트 그대로가 원칙)."""
    static = ROOT / "static"
    return [p for p in built.rglob("*.html") if not (static / p.relative_to(built)).exists()]


def _analytics() -> dict:
    return tomllib.loads((ROOT / "hugo.toml").read_text(encoding="utf-8"))["params"]["analytics"]


def test_only_pinned_analytics_script_outside(built):
    allowed = _analytics()["src"]
    for p in built.rglob("*.html"):
        text = p.read_text(encoding="utf-8")
        for tag in re.findall(r"<script\b[^>]*>", text):
            m = re.search(r'src="?([^"\s>]+)', tag)
            if not m or not m.group(1).startswith(("http:", "https:", "//")):
                continue
            assert m.group(1) == allowed, f"{p.name}: 허락 안 된 바깥 스크립트 {m.group(1)} — 원칙 2"
            assert "integrity=" in tag and "sha384-" in tag, f"{p.name}: 통계 스크립트에 지문(SRI)이 없음"
            assert "crossorigin=" in tag, f"{p.name}: 지문 검사엔 crossorigin이 있어야 함"


def test_analytics_on_every_page_in_production(built):
    site = _analytics()["site"]
    pages = _site_pages(built)
    assert pages
    for p in pages:
        assert site in p.read_text(encoding="utf-8"), f"{p.name}: 통계 줄이 빠짐"


def test_no_analytics_in_local_preview(tmp_path):
    r = subprocess.run(
        [
            _hugo(),
            "--source",
            str(ROOT),
            "--destination",
            str(tmp_path),
            "--quiet",
            "--environment",
            "development",
        ],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    for p in tmp_path.rglob("*.html"):
        assert "cloudflareinsights" not in p.read_text(encoding="utf-8"), f"{p.name}: 미리 보기에 통계가 붙음"


def test_drafts_not_built(built):
    for md in (ROOT / "content").rglob("*.md"):
        head = md.read_text(encoding="utf-8").split("+++")
        if len(head) >= 3 and tomllib.loads(head[1]).get("draft"):
            title = tomllib.loads(head[1])["title"]
            for p in built.rglob("*.html"):
                assert title not in p.read_text(encoding="utf-8"), f"초안 「{title}」이 {p}에 나옴"


def test_home_title_not_doubled(built):
    html = (built / "index.html").read_text(encoding="utf-8")
    m = re.search(r"<title>(.*?)</title>", html)
    assert m, "첫 화면에 <title>이 없음"
    assert m.group(1) == "야옹띠의 놀이터", f"첫 화면 탭 제목 = {m.group(1)!r} — 사이트 이름 한 번만"


def test_license_line_on_every_page(built):
    for p in _site_pages(built):
        text = p.read_text(encoding="utf-8")
        assert "creativecommons.org/licenses/by-nc/4.0" in text, f"{p}: 바닥글 라이선스 줄이 빠짐(README 표)"
        assert "따로 밝힌 것을 빼고" in text, (
            f"{p}: 남의 소재(놀이 속 사진 · 소리 등)를 라이선스에서 빼는 말이 빠짐"
        )


def _front(md: Path) -> dict:
    parts = md.read_text(encoding="utf-8").split("+++")
    return tomllib.loads(parts[1]) if len(parts) >= 3 else {}


def _toy_entries() -> list[Path]:
    d = ROOT / "content" / "toys"
    return [p for p in d.glob("*.md") if p.name != "_index.md"] if d.exists() else []


TOY_REPO_LINK = re.compile(r"^https://meowtti\.github\.io/[a-z0-9-]+/$")


def _toy_href(md: Path) -> str:
    """놀이 주소 — 틀(_partials/toy-href.html)과 같은 규칙: link가 있으면 따로 올린 저장소, 없으면 /toys/<이름>/."""
    return _front(md).get("link") or f"/toys/{md.stem}/"


def test_every_toy_entry_points_at_real_files():
    for md in _toy_entries():
        slug = md.stem
        front = _front(md)
        link = front.get("link")
        if link:
            assert TOY_REPO_LINK.match(link), (
                f"content/toys/{md.name}: link {link!r} — 같은 계정 놀이 저장소 주소(https://meowtti.github.io/<저장소>/)만"
            )
            assert not (ROOT / "static" / "toys" / slug).exists(), (
                f"{md.name}: 따로 올린 놀이인데 static/toys/{slug}/ 사본이 남아 있음 — 한 곳에만"
            )
        else:
            assert (ROOT / "static" / "toys" / slug / "index.html").is_file(), (
                f"content/toys/{md.name} 이(가) 가리키는 static/toys/{slug}/index.html 이 없음 — 놀이 폴더 이름 = 목록 파일 이름"
            )
        for key in ("title", "date", "description"):
            assert front.get(key), f"content/toys/{md.name}: {key} 칸이 비었음"
        thumb = front.get("thumb")
        if thumb:
            assert (ROOT / "static" / thumb.lstrip("/")).is_file(), (
                f"content/toys/{md.name}: 그림 {thumb} 이 static에 없음"
            )


def test_toy_links_open_in_new_window(built):
    hrefs = {_toy_href(md) for md in _toy_entries()}
    found = set()
    for p in built.rglob("*.html"):
        for tag in re.findall(r"<a\b[^>]*>", p.read_text(encoding="utf-8")):
            m = re.search(r'href="?([^"\s>]+)', tag)
            if not m or m.group(1) not in hrefs:
                continue
            found.add(m.group(1))
            assert 'target="_blank"' in tag or "target=_blank" in tag, f"{p}: 놀이 링크가 새 창이 아님 {tag}"
            assert "noopener" in tag, f"{p}: 새 창 링크에 noopener가 없음 {tag}"
    assert found == hrefs, f"목록에 있는데 화면에 링크가 없는 놀이: {hrefs - found}"


def test_toy_entries_have_no_page_of_their_own(built):
    for md in _toy_entries():
        if _front(md).get("link"):
            continue
        page = built / "toys" / md.stem / "index.html"
        src = ROOT / "static" / "toys" / md.stem / "index.html"
        assert page.read_bytes() == src.read_bytes(), f"{md.name}: 목록 항목이 놀이 자리에 페이지를 덮어씀"


def test_no_hugo_default_english_or_empty_dates(built):
    for p in _site_pages(built):
        text = p.read_text(encoding="utf-8")
        assert "0001" not in re.sub(r"<script.*?</script>", "", text, flags=re.S), (
            f"{p}: 빈 날짜(0001년)가 보임"
        )
        assert "<h1>Tags</h1>" not in text, f"{p}: Hugo 기본 영어 제목"
        assert 'name="generator"' not in text, f"{p}: 생성기 판 표시 — hugo.toml disableHugoGeneratorInject"


def test_korean_404_page(built):
    page = built / "404.html"
    assert page.is_file(), "404.html 이 없음 — GitHub Pages가 영어 기본 404를 띄운다"
    text = page.read_text(encoding="utf-8")
    assert 'href="/"' in text, "404에 첫 화면으로 가는 링크가 없음"
    assert "Page not found" not in text, "404 탭 제목 · og 제목이 Hugo 기본 영어"


def test_github_profile_links_open_new_tab(built):
    github = tomllib.loads((ROOT / "hugo.toml").read_text(encoding="utf-8"))["params"]["github"]
    html = (built / "index.html").read_text(encoding="utf-8")
    tags = [t for t in re.findall(r"<a\b[^>]*>", html) if github in t]
    assert len(tags) >= 2, "첫 화면에 깃허브 링크가 둘(소개 · 바닥글) 있어야 함"
    for t in tags:
        assert "_blank" in t and "noopener" in t, f"깃허브 링크가 새 탭 · noopener가 아님 {t}"


def test_icons_linked_and_present(built):
    html = (built / "index.html").read_text(encoding="utf-8")
    for name in ("favicon-32.png", "apple-touch-icon.png"):
        assert name in html, f"첫 화면 머리에 {name} 링크가 없음"
        assert (built / name).is_file(), f"{name} 파일이 굽기에 없음(static/)"


def test_home_link_preview_has_image(built):
    html = (built / "index.html").read_text(encoding="utf-8")
    if _toy_entries() or tomllib.loads((ROOT / "hugo.toml").read_text(encoding="utf-8"))["params"].get(
        "image"
    ):
        assert 'property="og:image"' in html, (
            "첫 화면 링크 미리 보기에 그림이 없음(대표 그림 또는 최근 놀이 썸네일)"
        )


def test_feeds_have_links_and_korean(built):
    feeds = list(built.rglob("index.xml"))
    assert feeds
    for f in feeds:
        text = f.read_text(encoding="utf-8")
        assert "Recent content" not in text and " on " not in text, f"{f}: Hugo 기본 영어 피드 문구"
        assert "<language>ko</language>" in text, f"{f}: 피드 언어가 ko가 아님"
        for item in re.findall(r"<item>.*?</item>", text, flags=re.S):
            link = re.search(r"<link>(.*?)</link>", item, flags=re.S)
            assert link and link.group(1).strip().startswith("http"), f"{f}: 링크 빈 피드 항목 {item[:120]}"


def test_toys_copied_byte_for_byte(built):
    src = ROOT / "static" / "toys"
    if not src.exists():
        pytest.skip("아직 올린 놀이 없음")
    for f in src.rglob("*"):
        if f.is_file():
            rel = f.relative_to(ROOT / "static")
            assert (built / rel).read_bytes() == f.read_bytes(), f"{rel} 이(가) 굽기에서 바뀜"
