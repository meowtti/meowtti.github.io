# 야옹띠의 놀이터

작은 놀이 · 그림 · 주간 일지를 모아 두는 정적 사이트입니다. 주소: https://meowtti.github.io (준비 중)

## 원칙

- 정적 파일만 — 서버 · 데이터베이스 · 로그인 · 비밀 열쇠 없음
- 바깥 스크립트는 방문 통계 하나만 (지문(SRI)으로 고정 · 시험이 지킴) — 그 밖엔 꼭 필요하면 판을 고정해 저장소 안에 복사
- 놀이 하나 = 본체 폴더 하나(`static/toys/<이름>/`) + 목록 파일 하나(`content/toys/<이름>.md`)
- 올리면 안 되는 것은 커밋 전에 기계로 막는다 (`checks/guard.py` · gitleaks · 허락 목록 `.gitignore`)

## 검사

```
uv sync --frozen
uv run --frozen pre-commit install
uv run --frozen pytest
```

## 라이선스

| 무엇 | 조건 |
|---|---|
| 콘텐츠 — `content/`의 글, `static/`의 놀이 · 그림 | [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/deed.ko) — 출처(야옹띠의 놀이터 · 링크)를 밝히면 나누고 고쳐 쓸 수 있습니다. 영리 목적으로는 쓸 수 없습니다. |
| 그 밖의 코드 — 틀(`layouts/`) · 검사기(`checks/`) · 시험 · 설정 | 별도 라이선스를 주지 않습니다(모든 권리 보유). 보고 배우는 것은 자유입니다. |

팬아트에 나오는 원작 캐릭터 · 이름 · 로고의 권리는 원작자에게 있습니다. 위 라이선스는 그 부분에 적용되지 않습니다.
