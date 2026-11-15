"""배포 워크플로 시험 — 판 고정 · 지문 고정 · 체크섬 · 최소 권한을 지키는지 본다."""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WF = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")


def test_hugo_version_matches_pin():
    pin = tomllib.loads((ROOT / "hugo.toml").read_text(encoding="utf-8"))["module"]["hugoVersion"]["min"]
    m = re.search(r"HUGO_VERSION:\s*([0-9.]+)", WF)
    assert m and m.group(1) == pin, f"워크플로 Hugo 판 ≠ hugo.toml 판 {pin} — 둘을 같이 바꾼다"


def test_hugo_download_is_checksummed():
    assert re.search(r"HUGO_DEB_SHA256:\s*[0-9a-f]{64}\b", WF), "Hugo 받은 파일의 sha256을 박는다"
    assert "sha256sum -c" in WF, "설치 전에 sha256sum -c로 맞댄다"


def test_actions_pinned_by_sha():
    uses = re.findall(r"uses:\s*(\S+)(.*)", WF)
    assert uses, "uses 줄이 없음"
    for ref, rest in uses:
        name, _, ver = ref.partition("@")
        assert re.fullmatch(r"[0-9a-f]{40}", ver), f"{ref} — 태그 대신 커밋 지문 40자로 고정한다"
        assert re.search(r"#\s*v\d", rest), f"{ref} — 뒤에 # v판 이름 주석을 단다(올릴 때 무엇인지 알게)"
        assert name.startswith("actions/"), (
            f"{name} — 깃허브 공식(actions/) 말고 남의 자동 작업은 넣지 않는다"
        )


def test_least_permissions():
    assert "contents: read" in WF
    assert "contents: write" not in WF, "저장소에 쓰는 권한은 주지 않는다"
    assert "persist-credentials: false" in WF, "받은 저장소에 열쇠를 남기지 않는다"
    build_part = WF.split("\n  deploy:")[0]
    assert "pages: write" not in build_part and "id-token: write" not in build_part, (
        "띄우는 권한(pages · id-token)은 deploy 작업에만 준다"
    )
