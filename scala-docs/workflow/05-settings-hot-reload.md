# 05. 설정 변경 → hot-reload 반영

`8.settings`에서 값을 바꾸면 `scala_settings`에 즉시 저장되고, 다른 화면·다음 run이 새 값을 쓴다. 컨테이너 재시작 없음(`sw-architecture/08-config-and-secrets.md`).

---

## 조회 (진입)

**① 화면**: `8.settings` State A — 그룹별 설정 표시. API key는 마스킹·read-only.

**② IPC**:
```
TUI → Backend : settings.get()
Backend ⇠ TUI : { agents:{…model…}, sources:{…url,indices…}, output:{opensearch:{url,index}},
                  consoles:{…}, openai_api_key_masked:"sk-…••••3f9a" }
```
- API key 마스킹값은 `.env`에서 Backend가 만들어 내려준다(TUI는 `.env`를 못 읽음, secret 원문 미전달).
- model 단가는 백엔드 전용이라 응답에 포함하지 않는다(화면 비노출).

## 저장 (편집)

**① 화면**: 필드 위 `enter`로 편집(State B), 하단 입력창을 에디터로. `enter` 저장.

**② IPC**:
```
TUI → Backend : settings.set({ key:"output.opensearch.index", value:"scala-normalized" })
Backend ⇠ TUI : { key:"output.opensearch.index", value:"scala-normalized", applied:"hot-reload" }
```

**③ 백엔드·store**: settings 핸들러가 `PG.scala_settings`의 해당 키를 갱신(`updated_at`). LLM 없음.

## 반영 (hot-reload)

| 변경 | 언제 반영 |
|---|---|
| index 추가 (`source.<solution>.indices`) | **즉시** — `2.source-selection`·`1.main`에서 프로세스 종료 없이 바로 선택 가능 |
| source/OpenSearch **URL**, agent **model** | **다음 run 시작 시** — Backend가 run 시작 때 `scala_settings`를 읽어 연결·모델 구성 |

```
설정 저장(settings.set) → scala_settings 갱신
   index 추가      → source-selection이 settings.get 재호출 시 새 index 노출
   URL/model 변경  → 다음 pipeline.run 시작 시점에 적용
```

- Settings는 idle(main)에서만 진입하므로 run 중 변경 충돌이 없다.
- 인프라 접속(PG/Redis/Chroma)·secret은 `.env`라 이 화면에서 못 바꾼다 → 재시작 유발 없음.
