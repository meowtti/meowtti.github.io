"""커밋 전 검사기 — 공개 저장소에 올라가면 안 되는 것을 막는다.

pre-commit이 이번 커밋에 올린 파일 이름을 넘겨준다. 하나라도 걸리면 종료 1(커밋 멈춤)과 처방전을 찍는다.

막는 것 다섯:
  1. 허락 안 된 확장자 (PDF · zip · 실행 파일 · 원본 그림 · 영상 · 문서 …)
  2. 크기 상한을 넘는 파일 (고해상도 원본 · 큰 묶음 · 긴 녹음) — 소리 파일은 꼬리표 속 경로 · 금지어도 본다
  3. 사진 속 숨은 정보(EXIF — 위치 · 기기 · 시각)
  4. 글 속 내 PC 경로 (사용자 이름 · 폴더 구조가 샘)
  5. 저장소 밖 비공개 금지어 파일에 적은 낱말 (실명 · 회사 이름 등 — 낱말 자체는 저장소에 두지 않는다)
열쇠 · 비밀번호 무늬는 gitleaks가 따로 본다.
"""

import re
import sys
from pathlib import Path

# 올려도 되는 확장자 — 새 꼴이 필요하면 여기 한 곳에 더한다
TEXT_EXT = {
    ".html",
    ".css",
    ".js",
    ".mjs",
    ".json",
    ".md",
    ".txt",
    ".svg",
    ".xml",
    ".toml",
    ".yaml",
    ".yml",
    ".py",
    ".lock",
    ".gitignore",
    ".gitattributes",
    ".python-version",
    ".nojekyll",  # 놀이 저장소를 Pages가 Jekyll 없이 그대로 내보내게 하는 빈 표시 파일
}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico"}
FONT_EXT = {".woff2"}
AUDIO_EXT = {".mp3", ".ogg"}  # 놀이 속 효과음 · 배경 음악(2026-11-15 첫 놀이가 소리 있는 판으로 정해짐)
ALLOWED_EXT = TEXT_EXT | IMAGE_EXT | FONT_EXT | AUDIO_EXT

# 크기 상한(바이트) — 장치 숫자 · 실제 그림을 줄여 보고 다시 정한다
IMAGE_MAX_BYTES = 800_000
TEXT_MAX_BYTES = 300_000
FONT_MAX_BYTES = 500_000
AUDIO_MAX_BYTES = 400_000  # 첫 놀이 가장 큰 곡 317KB(잼) — 긴 원본 녹음이 그대로 섞이는 걸 막는 선

# 비공개 금지어 — 저장소 밖에 두는 파일(한 줄에 한 낱말 · # 줄은 주석)
PRIVATE_WORDS_FILE = Path.home() / ".meowtti" / "private_words.txt"

_BS = re.escape(chr(92))
LOCAL_PATH_PATTERNS = [
    re.compile(r"(?<![A-Za-z])[A-Za-z]:" + _BS + r"+Users" + _BS, re.IGNORECASE),
    re.compile(r"(?<![A-Za-z])[A-Za-z]:/+Users/", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z0-9_])/[a-z]/Users/", re.IGNORECASE),
    # 드라이브 글자로 시작하는 경로 전부(폴더 이름을 여기 적지 않으려고 넓게 막는다 · 웹 주소 https:는 앞 글자 때문에 안 걸림)
    re.compile(r"(?<![A-Za-z])[A-Za-z]:" + _BS + r"+[^" + _BS + r"\s\"'<>]+"),
    re.compile(r"(?<![A-Za-z])[A-Za-z]:/+[^/\s\"'<>]+"),
]
# 소리 파일용 — 압축 바이트엔 우연한 「영문 한 글자 + 콜론 + 빗금」이 생긴다(2026-11-15 첫 놀이 14개 · 잼). 사용자 폴더 꼴 + 「드라이브:\폴더\」 꼴만
AUDIO_PATH_PATTERNS = LOCAL_PATH_PATTERNS[:3] + [
    re.compile(r"(?<![A-Za-z])[A-Za-z]:[" + _BS + r"/]+[\w .-]{2,}[" + _BS + r"/]"),
]


def _suffix(path: Path) -> str:
    name = path.name.lower()
    if name in (".gitignore", ".gitattributes", ".python-version", ".nojekyll"):
        return name
    return path.suffix.lower()


def _has_exif(data: bytes, ext: str) -> bool:
    if ext in (".jpg", ".jpeg"):
        return b"Exif\x00\x00" in data[:131072]
    if ext == ".png":
        return b"eXIf" in data
    if ext == ".webp":
        return b"EXIF" in data[:131072]
    return False


_DRAFT_TRUE = re.compile(r"^\s*draft\s*[=:]\s*true\s*$", re.IGNORECASE | re.MULTILINE)


def _is_draft(text: str) -> bool:
    """글 맨 앞 머리(+++ … +++ 또는 --- … ---) 안에 draft = true가 있나 — 본문 글자는 안 본다."""
    for fence in ("+++", "---"):
        if text.startswith(fence):
            end = text.find("\n" + fence, len(fence))
            if end != -1:
                return bool(_DRAFT_TRUE.search(text[len(fence) : end]))
    return False


def _private_words() -> list[str]:
    try:
        lines = PRIVATE_WORDS_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    return [w.strip().lower() for w in lines if w.strip() and not w.strip().startswith("#")]


def check_file(path: Path) -> list[str]:
    """한 파일의 문제를 처방전 문장 목록으로 돌려준다(없으면 빈 목록)."""
    path = Path(path)
    ext = _suffix(path)
    if ext not in ALLOWED_EXT:
        return [
            f"확장자 {ext or '(없음)'}는 올릴 수 없는 꼴 — 공개해도 되는 파일이면 checks/guard.py ALLOWED_EXT에 더한다"
        ]

    data = path.read_bytes()
    problems: list[str] = []

    limit = (
        IMAGE_MAX_BYTES
        if ext in IMAGE_EXT
        else FONT_MAX_BYTES
        if ext in FONT_EXT
        else AUDIO_MAX_BYTES
        if ext in AUDIO_EXT
        else TEXT_MAX_BYTES
    )
    if len(data) > limit:
        problems.append(f"크기 {len(data):,}바이트 > 상한 {limit:,} — 그림이면 줄여서, 글이면 나눠서 올린다")

    if ext in IMAGE_EXT and _has_exif(data, ext):
        problems.append("사진에 EXIF(위치 · 기기 · 시각 정보)가 남아 있음 — 정보를 지운 사본으로 바꿔 올린다")

    if ext in AUDIO_EXT:
        # 소리 파일 꼬리표(ID3 · Vorbis 주석)에 만든 PC 경로 · 이름이 묻을 수 있다.
        # 경로는 읽을 수 있는 글자가 6자 넘게 이어진 토막에서만 찾는다 — 압축 바이트 속 우연한 드라이브 꼴을 경로로 잡지 않게
        runs = "\n".join(r.decode("ascii") for r in re.findall(rb"[\x20-\x7e]{6,}", data))
        tag_text = data.decode("utf-8", errors="ignore")
        if any(p.search(runs) for p in AUDIO_PATH_PATTERNS):
            problems.append(
                "소리 파일 꼬리표에 내 PC 경로가 들어 있음 — 꼬리표를 지운 사본으로(ffmpeg -map_metadata -1)"
            )
        low = tag_text.lower()
        if any(w in low for w in _private_words()):
            problems.append(
                "소리 파일 꼬리표에 비공개 금지어 파일의 낱말이 들어 있음 — 꼬리표를 지운 사본으로"
            )

    if ext in TEXT_EXT:
        text = data.decode("utf-8", errors="ignore")
        if any(p.search(text) for p in LOCAL_PATH_PATTERNS):
            problems.append("글에 내 PC 경로(드라이브 · 사용자 폴더)가 들어 있음 — 상대 경로로 바꾼다")
        if ext == ".md" and _is_draft(text.lstrip("﻿")):
            problems.append(
                "초안(draft = true) 글 — 공개 저장소라 올리면 누구나 본다. 다 쓰면 draft를 지우고 올린다(그전엔 PC에만)"
            )
        low = text.lower()
        if any(w in low for w in _private_words()):
            problems.append(
                "비공개 금지어 파일의 낱말이 들어 있음 — 그 낱말을 빼거나 바꾼다(낱말은 여기 다시 안 찍음)"
            )

    return problems


def main(argv: list[str]) -> int:
    failed = False
    for name in argv:
        p = Path(name)
        if not p.is_file():
            continue
        problems = check_file(p)
        if problems:
            failed = True
            print(f"⛔ {name}")
            for m in problems:
                print(f"   - {m}")
    if failed:
        print(
            "고치는 법: 위 처방대로 고친 뒤 다시 커밋한다. 올려도 되는 꼴인데 막혔다면 주인에게 묻고 guard.py 한 곳만 고친다."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
