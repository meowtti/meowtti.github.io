"""새 놀이 저장소 도구 — 놀이 하나 = 저장소 하나(작업 규칙 3)를 명령 셋으로.

  prepare <이름> [--folders img bgm] [--files app.js]   옆 폴더(../<이름>)에 뼈대를 차린다 — 로컬만
  publish <이름> --confirm --audit "감사 결과" [--description 글]
                                                          깃허브 저장소 만들기(없을 때) → push → Pages 켜기
                                                          → 굽기 기다리기 → 실제 주소 확인  ※ 공개로 나간다
  check <이름>                                           실제 주소에서 올린 파일이 다 뜨나만 본다

부르기(이 저장소 폴더에서): uv run --frozen python tools/toy.py <명령> …
계정 이름 · 사이트 주소 · 사이트 이름은 hugo.toml 한 곳에서 읽는다. publish는 주인이 「올려」 한 뒤에만 붙인다.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRECOMMIT = ROOT / ".venv" / "Scripts" / "pre-commit.exe"
NAME_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,62}")

GITATTRIBUTES = """# 줄바꿈을 저장소 안에서는 LF로 맞춘다 (윈도에서 고쳐도 기록이 어지럽지 않게)
* text=auto eol=lf
*.png binary
*.jpg binary
*.jpeg binary
*.webp binary
*.gif binary
*.ico binary
*.mp3 binary
*.ogg binary
*.woff2 binary
"""


def precommit_config(site_dir: str) -> str:
    bs = "\\\\"  # YAML 안 윈도 경로 구분자(역슬래시 둘)
    return f"""# 커밋 직전 검사 — 놀이터 저장소({site_dir})의 검사기를 같이 쓴다(규칙은 그쪽 한 곳).
# 두 저장소를 같은 폴더에 나란히 둔다: ../{site_dir}
# 켜기(한 번, 이 폴더 안에서): ..\\{site_dir}\\.venv\\Scripts\\pre-commit.exe install
repos:
  - repo: local
    hooks:
      - id: guard
        name: guard — 올리면 안 되는 꼴 · 크기 · 사진 EXIF · 내 PC 경로 · 비공개 금지어 (놀이터 검사기)
        entry: ..{bs}{site_dir}{bs}.venv{bs}Scripts{bs}python.exe ../{site_dir}/checks/guard.py
        language: system
      - id: gitleaks
        name: gitleaks — 열쇠 · 비밀번호 무늬 (값은 가림)
        entry: gitleaks git --pre-commit --staged --redact --no-banner --log-level warn -v .
        language: system
        pass_filenames: false
        always_run: true
"""


def site_config() -> tuple[str, str]:
    """(깃허브 계정 이름, 사이트 주소 — 끝 / 포함)."""
    conf = tomllib.loads((ROOT / "hugo.toml").read_text(encoding="utf-8"))
    owner = conf["params"]["github"].rstrip("/").rsplit("/", 1)[-1]
    base = conf["baseURL"].rstrip("/") + "/"
    return owner, base


def site_title() -> str:
    return tomllib.loads((ROOT / "hugo.toml").read_text(encoding="utf-8"))["title"]


def check_name(name: str) -> str:
    if not NAME_RE.fullmatch(name or "") or name == ROOT.name:
        raise SystemExit(
            f"⛔ 저장소 이름 「{name}」 — 영문 소문자 · 숫자 · 붙임표만(주소가 되니 한번 정하면 안 바꿈)"
        )
    return name


def gitignore_text(folders: list[str], files: list[str]) -> str:
    lines = [
        "# 허락 목록 — 아래 ! 줄에 적은 것만 저장소에 들어간다(새 폴더 · 파일은 한 줄 열어야 들어감)",
        "/*",
    ]
    for f in [".gitignore", ".gitattributes", ".nojekyll", ".pre-commit-config.yaml", "README.md", *files]:
        lines.append(f"!/{f}")
    lines += [f"!/{d.strip('/')}/" for d in folders]
    lines += [
        "",
        "# 어디에 있든 막는 것",
        ".DS_Store",
        "Thumbs.db",
        "desktop.ini",
        "*.zip",
        "*.7z",
        "*.rar",
        ".env",
        ".env.*",
    ]
    return "\n".join(lines) + "\n"


def readme_text(name: str) -> str:
    _, base = site_config()
    return f"""# {name}

- 놀러 가기: {base}{name}/
- 다른 놀이: [{site_title()}]({base})

## 쓴 재료

| 무엇 | 출처 · 권리 |
|---|---|

## 라이선스

위 표의 재료를 빼고, 이 놀이의 글 · 그림 · 소리 · 코드는 [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/deed.ko)을 따릅니다. 출처를 밝히면 자유롭게 나누고 고쳐 써도 되지만, 영리 목적으로는 쓸 수 없습니다.
"""


def live_urls(base: str, name: str, tracked: list[str]) -> list[str]:
    urls = [f"{base}{name}/"]
    for f in tracked:
        if f.startswith(".") or "/." in f or f == "README.md":
            continue
        urls.append(f"{base}{name}/" + urllib.parse.quote(f))
    return urls


# ── 바깥 명령 ──────────────────────────────────────────────


def _env() -> dict[str, str]:
    # 놀이터 커밋 중(pre-commit 안)에 불려도 GIT_DIR 같은 값이 새 폴더로 새지 않게
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def _run(args: list, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run(
        [str(a) for a in args],
        cwd=cwd,
        env=_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and r.returncode != 0:
        raise SystemExit(f"⛔ 실패: {' '.join(map(str, args))}\n{(r.stderr or r.stdout).strip()}")
    return r


def _write_if_missing(path: Path, text: str) -> None:
    if path.exists():
        print(f"  · {path.name} 있음 — 그대로 둠")
        return
    path.write_bytes(text.encode("utf-8"))
    print(f"  + {path.name}")


def prepare(
    name: str, folders: list[str] | None = None, files: list[str] | None = None, parent: Path | None = None
) -> Path:
    check_name(name)
    folders, files = folders or [], files or []
    parent = parent or ROOT.parent
    target = parent / name
    target.mkdir(exist_ok=True)
    owner, _ = site_config()
    print(f"준비: {target}")
    _write_if_missing(target / ".gitignore", gitignore_text(folders, ["index.html", *files]))
    _write_if_missing(target / ".gitattributes", GITATTRIBUTES)
    _write_if_missing(target / ".nojekyll", "")
    _write_if_missing(target / ".pre-commit-config.yaml", precommit_config(ROOT.name))
    _write_if_missing(target / "README.md", readme_text(name))
    if not (target / ".git").exists():
        _run(["git", "init", "-q", "-b", "main"], cwd=target)
        print("  + git init (main)")
    # 커밋 작성자 = 놀이터와 같은 noreply(규칙 8)
    for key in ("user.name", "user.email"):
        val = _run(["git", "config", key], cwd=ROOT).stdout.strip()
        _run(["git", "config", key, val], cwd=target)
    want = f"https://github.com/{owner}/{name}.git"
    cur = _run(["git", "remote", "get-url", "origin"], cwd=target, check=False)
    if cur.returncode != 0:
        _run(["git", "remote", "add", "origin", want], cwd=target)
        print(f"  + origin {want}")
    elif cur.stdout.strip() != want:
        print(f"  ⚠ origin이 {cur.stdout.strip()} — 바꾸지 않음(확인할 것)")
    # 커밋 전 검사는 반드시 그 폴더 안에서 켠다(다른 폴더에서 -c로 켜면 그 폴더 훅이 바뀐다 · 2026-11-15 사고)
    if not PRECOMMIT.exists():
        raise SystemExit("⛔ 놀이터 .venv에 pre-commit이 없음 — 놀이터 폴더에서 uv sync --frozen 먼저")
    _run([PRECOMMIT, "install"], cwd=target)
    hook = target / ".git" / "hooks" / "pre-commit"
    if "--config=.pre-commit-config.yaml" not in hook.read_text(encoding="utf-8", errors="ignore"):
        raise SystemExit("⛔ 커밋 전 검사가 이 폴더 설정을 안 가리킴")
    print("  + 커밋 전 검사 켬(이 폴더 안)")
    print(
        "다음: 본체를 넣고 git add · commit(검사가 돈다) → 독립 감사 → 주인 「올려」 뒤 publish --confirm --audit"
    )
    return target


def _gh(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return _run(["gh", *args], check=check)


def check(name: str, parent: Path | None = None, tries: int = 3) -> int:
    check_name(name)
    target = (parent or ROOT.parent) / name
    _, base = site_config()
    tracked = _run(["git", "ls-files"], cwd=target).stdout.split()
    bad: list[str] = []
    for url in live_urls(base, name, tracked):
        for i in range(tries):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=20) as r:
                    ok = r.status == 200
            except urllib.error.URLError:
                ok = False
            if ok:
                break
            time.sleep(10 if i + 1 < tries else 0)  # 막 구운 직후엔 CDN이 늦게 따라온다
        if not ok:
            bad.append(url)
    print(
        f"실제 주소 확인: {len(tracked)}개 파일 중 주소 {len(live_urls(base, name, tracked))}개 · 실패 {len(bad)}"
    )
    for u in bad:
        print(f"  ✕ {u}")
    return 1 if bad else 0


def publish(name: str, description: str = "", parent: Path | None = None, timeout: int = 300) -> int:
    check_name(name)
    target = (parent or ROOT.parent) / name
    if not (target / ".git").exists():
        raise SystemExit("⛔ git 저장소가 아님 — prepare 먼저")
    if _run(["git", "status", "--porcelain"], cwd=target).stdout.strip():
        raise SystemExit("⛔ 커밋 안 된 변경이 있음 — 커밋(검사 통과) 뒤 다시")
    head = _run(["git", "rev-parse", "HEAD"], cwd=target, check=False)
    if head.returncode != 0:
        raise SystemExit("⛔ 커밋이 하나도 없음")
    owner, base = site_config()
    full = f"{owner}/{name}"
    if _gh("repo", "view", full, "--json", "name", check=False).returncode != 0:
        _gh("repo", "create", full, "--public", *(["--description", description] if description else []))
        print(f"+ 깃허브 저장소 만듦: {full} (공개)")
    _run(["git", "push", "-u", "origin", "main"], cwd=target)
    print("+ push")
    if _gh("api", f"repos/{full}/pages", check=False).returncode != 0:
        _gh("api", "-X", "POST", f"repos/{full}/pages", "-f", "source[branch]=main", "-f", "source[path]=/")
        print("+ Pages 켬 (main · /)")
    want = head.stdout.strip()
    end = time.time() + timeout
    while True:
        r = _gh("api", f"repos/{full}/pages/builds/latest", check=False)
        info = json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else {}
        status = info.get("status")
        if status == "built" and info.get("commit") == want:
            print("+ Pages 굽기 끝")
            break
        if status == "errored":
            raise SystemExit(f"⛔ Pages 굽기 실패: {info.get('error', {}).get('message')}")
        if time.time() > end:
            raise SystemExit(f"⛔ {timeout}초 안에 굽기가 안 끝남(지금 {status}) — check로 다시 보기")
        time.sleep(5)
    print(f"주소: {base}{name}/")
    return check(name, parent)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="toy", description="새 놀이 저장소 도구")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("name")
    p.add_argument("--folders", nargs="*", default=[])
    p.add_argument("--files", nargs="*", default=[])
    q = sub.add_parser("publish")
    q.add_argument("name")
    q.add_argument("--description", default="")
    q.add_argument("--confirm", action="store_true")
    q.add_argument(
        "--audit", default="", help="올리기 전 독립 감사 결과 한 줄(예: 「❗0 ⚠️6 → 고친 뒤 반영」)"
    )
    c = sub.add_parser("check")
    c.add_argument("name")
    a = ap.parse_args(argv)
    if a.cmd == "prepare":
        prepare(a.name, a.folders, a.files)
        return 0
    if a.cmd == "publish":
        if not a.confirm:
            print("⛔ 공개로 나가는 단계 — 주인이 「올려」 한 뒤에만 --confirm을 붙인다")
            return 2
        if len(a.audit.strip()) < 5:
            print(
                "⛔ 올리기 전 독립 감사가 한 번 이상 있어야 한다(작업 규칙 3 · 2026-11-16 주인)"
                " — 결론을 안 보여 준 일꾼의 감사 결과 한 줄을 --audit에 적는다"
            )
            return 2
        print(f"감사: {a.audit.strip()}")
        return publish(a.name, a.description)
    return check(a.name)


if __name__ == "__main__":
    sys.exit(main())
