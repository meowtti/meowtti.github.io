# 야옹띠의 놀이터

작은 놀이 · 그림 · 주간 일지를 모아 두는 정적 사이트입니다. 주소: https://meowtti.github.io (준비 중)

## 원칙

- 정적 파일만 — 서버 · 데이터베이스 · 로그인 · 비밀 열쇠 없음
- 바깥 스크립트 없음 (꼭 필요하면 판을 고정해 저장소 안에 복사)
- 놀이 하나 = 폴더 하나 · 목록은 데이터 파일 한 곳에서
- 올리면 안 되는 것은 커밋 전에 기계로 막는다 (`checks/guard.py` · gitleaks · 허락 목록 `.gitignore`)

## 검사

```
uv sync --frozen
uv run --frozen pre-commit install
uv run --frozen pytest
```

## 라이선스

아직 정하지 않았습니다.
