"""커밋 전 검사기(checks/guard.py) 시험 — 올라가면 안 되는 것을 실제로 막는지 본다.

경로 · 비밀 무늬는 글자 그대로 적으면 이 파일 자체가 검사에 걸리므로 조각을 이어 만든다.
"""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("guard", ROOT / "checks" / "guard.py")
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)

BS = chr(92)  # 역슬래시


def _write(tmp_path, name, data):
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        p.write_bytes(data.encode("utf-8"))
    else:
        p.write_bytes(data)
    return p


# ── 확장자: 허락 안 된 꼴은 막는다 ─────────────────────────────


@pytest.mark.parametrize(
    "name", ["resume.pdf", "build.zip", "a.exe", "draft.psd", "clip.mp4", "memo.docx", "x.hwp"]
)
def test_blocks_disallowed_extension(tmp_path, name):
    p = _write(tmp_path, name, b"x")
    problems = guard.check_file(p)
    assert any("확장자" in m for m in problems), problems


@pytest.mark.parametrize(
    "name", ["index.html", "style.css", "app.js", "works.json", "post.md", "logo.svg", ".nojekyll"]
)
def test_allows_site_files(tmp_path, name):
    p = _write(tmp_path, name, "hello")
    assert guard.check_file(p) == []


# ── 크기: 상한을 넘으면 막는다 ─────────────────────────────


def test_blocks_big_image(tmp_path):
    p = _write(tmp_path, "big.png", b"\x89PNG\r\n\x1a\n" + b"0" * (guard.IMAGE_MAX_BYTES + 1))
    assert any("크기" in m for m in guard.check_file(p))


def test_blocks_big_text(tmp_path):
    p = _write(tmp_path, "big.js", "a" * (guard.TEXT_MAX_BYTES + 1))
    assert any("크기" in m for m in guard.check_file(p))


# ── 사진 숨은 정보(EXIF) ─────────────────────────────


def test_blocks_jpeg_with_exif(tmp_path):
    data = b"\xff\xd8\xff\xe1\x00\x10Exif\x00\x00" + b"0" * 32 + b"\xff\xd9"
    p = _write(tmp_path, "photo.jpg", data)
    assert any("EXIF" in m for m in guard.check_file(p))


def test_blocks_png_with_exif_chunk(tmp_path):
    data = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x04eXIf" + b"0000" + b"\x00\x00\x00\x00IEND"
    p = _write(tmp_path, "pic.png", data)
    assert any("EXIF" in m for m in guard.check_file(p))


def test_allows_clean_jpeg(tmp_path):
    data = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"0" * 32 + b"\xff\xd9"
    p = _write(tmp_path, "clean.jpg", data)
    assert guard.check_file(p) == []


# ── 내 PC 경로가 글에 박힘 ─────────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        "C:" + BS + "Users" + BS + "someone" + BS + "a.txt",
        "Q:" + BS + "folder" + BS + "x",
        "q:" + "/folder/x",
        "c:" + "/users/someone/x",
        "/c" + "/Users/someone/x",
    ],
)
def test_blocks_local_paths(tmp_path, text):
    p = _write(tmp_path, "page.html", "<p>" + text + "</p>")
    assert any("PC 경로" in m for m in guard.check_file(p))


def test_web_urls_and_css_are_not_paths(tmp_path):
    text = '<a href="https://meowtti.github.io/toys/">x</a> http://localhost:1313/ <style>a:hover{color:red}</style>'
    p = _write(tmp_path, "ok.html", text)
    assert guard.check_file(p) == []


# ── 초안 글은 공개 저장소에 안 올림 ─────────────────────────────


@pytest.mark.parametrize(
    "head",
    [
        '+++\ntitle = "쓰는 중"\ndraft = true\n+++\n본문',
        "---\ntitle: 쓰는 중\ndraft: true\n---\n본문",
    ],
)
def test_blocks_draft_posts(tmp_path, head):
    p = _write(tmp_path, "content/posts/wip.md", head)
    assert any("초안" in m for m in guard.check_file(p))


def test_allows_finished_post(tmp_path):
    p = _write(
        tmp_path,
        "content/posts/done.md",
        '+++\ntitle = "다 씀"\ndraft = false\n+++\n본문에 draft = true 라는 글자가 있어도 머리 밖이면 괜찮다',
    )
    assert guard.check_file(p) == []


# ── 저장소 밖 비공개 금지어 파일 ─────────────────────────────


def test_private_words_from_outside_file(tmp_path, monkeypatch):
    words = tmp_path / "private_words.txt"
    words.write_text("# 주석은 무시\nsecretname\n", encoding="utf-8")
    monkeypatch.setattr(guard, "PRIVATE_WORDS_FILE", words)
    p = _write(tmp_path / "site", "post.md", "hello SecretName here")
    problems = guard.check_file(p)
    assert any("금지어" in m for m in problems)
    # 처방전에 금지어 자체를 다시 찍지 않는다(화면 · 기록으로 새지 않게)
    assert not any("secretname" in m.lower() for m in problems)


def test_no_private_words_file_is_fine(tmp_path, monkeypatch):
    monkeypatch.setattr(guard, "PRIVATE_WORDS_FILE", tmp_path / "없음.txt")
    p = _write(tmp_path, "post.md", "hello")
    assert guard.check_file(p) == []


# ── main: 하나라도 걸리면 종료 1 + 처방전 ─────────────────────────────


def test_main_exit_codes(tmp_path, capsys):
    good = _write(tmp_path, "ok.html", "hi")
    bad = _write(tmp_path, "cv.pdf", b"x")
    assert guard.main([str(good)]) == 0
    assert guard.main([str(good), str(bad)]) == 1
    out = capsys.readouterr().out
    assert "cv.pdf" in out and "고치는 법" in out


# ── 소리: 놀이 속 효과음 · 배경 음악은 올리되, 크기와 꼬리표(태그) 속 경로를 본다 ──────


@pytest.mark.parametrize("name", ["bgm/a.mp3", "sfx/b.ogg"])
def test_allows_small_clean_audio(tmp_path, name):
    p = _write(tmp_path, name, b"ID3\x04\x00" + b"\x00" * 2000 + b"TSSE Lavf61")
    assert guard.check_file(p) == []


def test_blocks_big_audio(tmp_path):
    p = _write(tmp_path, "bgm/long.mp3", b"\x00" * (guard.AUDIO_MAX_BYTES + 1))
    assert any("크기" in m for m in guard.check_file(p))


def test_blocks_local_path_inside_audio_tag(tmp_path):
    tag = ("Q:" + BS + "Users" + BS + "someone" + BS + "song.wav").encode("utf-8")
    p = _write(tmp_path, "sfx/c.mp3", b"ID3\x04\x00" + tag + b"\x00" * 100)
    assert any("경로" in m for m in guard.check_file(p))


def test_blocks_private_word_inside_audio_tag(tmp_path, monkeypatch):
    words = tmp_path / "words.txt"
    words.write_text("비밀낱말\n", encoding="utf-8")
    monkeypatch.setattr(guard, "PRIVATE_WORDS_FILE", words)
    p = _write(tmp_path, "sfx/d.ogg", b"OggS" + "ARTIST=비밀낱말".encode("utf-8") + b"\x00" * 100)
    assert any("금지어" in m for m in guard.check_file(p))


def test_random_audio_bytes_are_not_paths(tmp_path):
    # 실제로 걸렸던 꼴(2026-11-15 첫 놀이 소리 14개): 압축 바이트 속 우연한 「글자:/」 + 제어 문자
    noise = (
        b"\xff\xfb\x90"
        + b"C"
        + b":/[\x17Qybqp@_Y\x15q"
        + b"\x00\x81"
        + b"v"
        + b":/sdtYej`?4(\xdb\x91-\x1a"
        + b"\x00" * 50
    )
    p = _write(tmp_path, "bgm/e.mp3", noise)
    assert guard.check_file(p) == []
