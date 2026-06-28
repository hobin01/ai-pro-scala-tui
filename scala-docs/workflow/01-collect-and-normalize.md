# 01. 메인 시나리오 — Collect & Normalize

사용자가 데이터 정규화를 한 번 수행하는 **end-to-end** 흐름이다. 화면은 `1.main → 2.source-selection → 3.data-samples → 4.agent-workflow-graph → 5.human-feedback(완료)` 순으로 전환된다.

표기·actor는 `README.md` 참고. 단계별로 **① 화면 행동→output / ② IPC / ③ 백엔드·agent + store** 3단으로 기술한다.

---

## 단계 1 — 진입 (1.main → 2.source-selection)

**① 화면**: `1.main` State A에서 `▸ Collect & Normalize` 선택 후 `enter` → `2.source-selection`으로 전환.

**② IPC**: source 목록을 그리기 위해 TUI가 현재 설정을 읽는다.
```
TUI → Backend : settings.get()
Backend ⇠ TUI : { sources:{ elasticsearch:{url, indices:[...]}, splunk:{url, indices:[...]} }, ... }
```

**③ 백엔드·store**: settings 핸들러가 `PG.scala_settings`에서 `source.*.url`·`source.*.indices`를 읽어 반환(LLM 없음). → `05-settings-hot-reload.md`.

## 단계 2 — source 선택 (2.source-selection)

**① 화면**: `space`로 index 토글, **2개 이상** 선택 후 `enter` → `3.data-samples`. output: 선택된 `(solution, index)` 목록. (2개 미만 `enter`는 에러 라인, 0개면 State D로 Settings 안내 → `06-failure-paths.md`)

**② IPC**: 없음. 선택 목록은 단계 1의 `settings.get` 결과를 TUI가 들고 토글만 한다(정적 목록, 실제 연결 없음).

**③ 백엔드·store**: 없음.

## 단계 3 — 샘플 조회 (3.data-samples)

**① 화면**: 진입 시 소스별 로딩(State A) → index별 `Field · Type · Sample values` 표(State B). `←→`로 index 이동, `enter` → `4.agent-workflow-graph`. **실제 소스 연결이 처음 일어나는 지점**이다.

**② IPC**:
```
TUI → Backend : samples.fetch({ sources:[{solution,index}, …] })
Backend ⇢ TUI : progress({ target:{solution,index}, status:"fetching" })   ← 소스별 진행
Backend ⇢ TUI : progress({ target:{solution,index}, status:"done" })
Backend ⇠ TUI : { indices:[ { solution, index, fields:[{name,type,samples:[≤5]}] } ] }
```

**③ 백엔드·source**: Connector가 선택된 index마다 `fetch_schema_samples(index, ≤5)`로 `ES`/`Splunk` SDK 조회 → 필드·타입·샘플 반환(가공 없음). 연결 실패는 여기서 표면화(→ `06-failure-paths.md`). LLM 없음. Connector 상세 `sw-architecture/04-siem-connector.md`.

## 단계 4 — 워크플로우 확인 & 실행 (4.agent-workflow-graph)

**① 화면**: agent 흐름도 + 역할 + **모델**(설정값) 표시. 게이트 모드라 하단에 "Run the pipeline on N selected sources?" → `▸ Start pipeline` 선택 → `5.human-feedback`. output: 파이프라인 시작.

**② IPC**: 모델명은 단계 1 `settings.get` 결과로 이미 채운다(그래프/역할은 정적, TUI 렌더). `Start pipeline` 시:
```
TUI → Backend : pipeline.run({ sources:[{solution,index}, …] })
Backend ⇠ TUI : { run_id }                               ← 즉시 반환
```

**③ 백엔드·store**: `pipeline.run`이 `PG.scala_runs`에 1행 생성(`status=running`, `started_at`, `selected_sources`), `run_id` 반환. 이후 동작은 notification·feedback로(단계 5). 단일 실행이라 진행 중 또 다른 `pipeline.run`은 거부(→ `06-…`).

## 단계 5 — 파이프라인 실행 & human feedback (5.human-feedback)

**① 화면**: State A(동작 중) — agent 진행을 thinking 로그로 스트리밍, 입력 비활성. 필요 시 State B(feedback 요청) — 입력 활성. 모든 매핑·적재 완료 시 State D(결과 + OpenSearch 링크). `enter` → `1.main`.

**② IPC** (run_id 기준 비동기):
```
Backend ⇢ TUI : run.status({ run_id, status:"running" })
Backend ⇢ TUI : progress({ run_id, agent:"schema_profiler", message:"profiled 13 fields (cache 8 hit · 5 miss)" })
Backend ⇢ TUI : feedback.request({ run_id, field:{…}, recommendation:{…} })   ← 필요할 때만(서버 발신 request)
TUI → Backend : (response) { decision:"approve" | "keep_raw" | "comment", comment? }
   … 매핑 끝까지 progress ↔ feedback.request 반복 …
Backend ⇢ TUI : output.chunk({ run_id, text:"…결과 요약…" })                 ← 스트리밍 출력
Backend ⇢ TUI : run.status({ run_id, status:"completed", summary:{…}, opensearch_link })
```

**③ 백엔드·agent·store**: LangGraph 그래프 실행(`sw-architecture/03-agent-workflow-langgraph.md`).
- `OA` 시작 → `PA`가 필드별 cache 조회(`Redis`), 미스 시 OCSF 후보 조회(`Chroma`) → `NA` 매핑 Rule 생성/적용 → `VA` 검증, 미달 시 interrupt(→ `feedback.request`).
- per-field 캐시 hit/miss·feedback 분기는 `02-branches.md`.
- finalize 후 `LO`가 `OpenSearch` 적재(+`_id`를 `LA`로) · `CA`가 확정 매핑을 `Redis` 저장 · `LA`가 `PG.scala_data_lineage_metadata`에 문서 단위 저장.
- 각 agent 노드가 `PG.scala_agent_usage`에 토큰/비용 기록(no-LLM 3종은 0 + last_activity).
- `OA`가 결과 종합 → `output.chunk`로 스트리밍 + OpenSearch 링크.

## 단계 6 — 복귀

**① 화면**: State D에서 `enter` → `1.main` State A.
**②③**: 없음(다음 작업 대기). run은 `completed` 상태로 `PG.scala_runs`에 남아 monitoring/lineage의 근거가 된다.

---

## 시퀀스 (요약 타임라인)

```text
User → TUI   : Collect & Normalize
TUI  → BE    : settings.get()                         ⇠ sources
User → TUI   : (space×N, enter) 2+ sources
TUI  → BE    : samples.fetch(sources)
BE   → ES/SP : fetch_schema_samples ×N                ⇢ progress ⇠ fields/samples
User → TUI   : enter (samples ok)
User → TUI   : Start pipeline
TUI  → BE    : pipeline.run(sources)                  ⇠ run_id ; scala_runs=running
BE           : OA→PA(Redis,Chroma)→NA→VA …            ⇢ progress
BE   ⇢ TUI   : feedback.request   ↔   TUI → BE response   (필요 시 반복)
BE           : finalize → LO(OpenSearch)+CA(Redis)+LA(PG)
BE           : scala_agent_usage 기록(7 agent)
BE   ⇢ TUI   : output.chunk(결과) ; run.status(completed) ; scala_runs=completed
User → TUI   : enter → 1.main
```

상세 payload 스키마는 `99-ipc-schema-appendix.md`.
