+++
title = "놀이"

# 놀이 하나 = 목록 파일 하나(content/toys/<이름>.md) + 본체 폴더 하나(static/toys/<이름>/).
# 목록 파일은 제 페이지를 만들지 않고 이 갈래 목록에만 나온다 — 그 주소엔 놀이 본체가 그대로 뜬다.
[[cascade]]
  [cascade.build]
    render = "never"
    list = "local"
    publishResources = false
  [cascade.target]
    kind = "page"
+++
