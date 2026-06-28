# 02. IPC — TUI ↔ Backend (JSON-RPC 2.0)

TUI와 Backend 사이의 유일한 통신 경계다. 모든 데이터 접근이 이 경계를 지난다.

## 통신 모델

- **프로토콜**: JSON-RPC 2.0, **양방향(bidirectional)**. 클라이언트(TUI)뿐 아니라 서버(Backend)도 request를 보낼 수 있어야 한다. (human feedback이 서버 → 클라이언트 request이기 때문)
- **전송 인코딩**: 메시지당 1 JSON 객체. 스트림 경계는 LSP식 `Content-Length` 헤더 또는 줄바꿈 구분(JSON Lines) 중 하나로 고정한다. (개발 시 택1)
- **동시성**: 단일 실행(single-flight)이라 in-flight 파이프라인은 항상 1개. 단, 파이프라인 진행 중에도 notification·feedback request는 흘러야 하므로 채널은 full-duplex여야 한다.

**Transport (확정): TCP(localhost).** Backend를 Docker Compose 서비스로 띄우고, TUI가 클라이언트로 `127.0.0.1:<port>`에 접속한다. 단순 PoC를 넘어 **Backend를 독립 서비스로 재사용**하기 위함이다(다른 클라이언트도 동일 포트로 접속 가능).

- 연결 주소는 secret이 아니다. **Backend 리슨 주소**는 Backend 설정(`.env` 인프라 wiring)으로, **TUI가 접속할 주소**(`SCALA_BACKEND_ADDR`, 기본 `127.0.0.1:<port>`)는 TUI측 설정/플래그로 둔다. (주소는 secret이 아니므로 TUI가 가져도 무방. TUI는 여전히 store/source/LLM secret을 갖지 않는다.)
- 단일 TCP 연결에서 full-duplex로 notification·`feedback.request`가 흐른다. 파이프라인은 여전히 single-flight(`09-run-lifecycle.md`).

## 메서드 (클라이언트 → 서버, request/response)

각 화면이 필요로 하는 호출이다. 읽기 메서드는 LLM을 거치지 않는 deterministic 핸들러가 처리한다.

| 메서드 | 화면 | 설명 |
|---|---|---|
| `settings.get` | 8.settings · 2.source-selection · 4.workflow · 7.monitoring | `scala_settings`의 화면 표시용 값 반환(단일 출처; 단가·system prompt는 백엔드 전용이라 제외). source 목록·agent 모델명도 여기서 온다. |
| `settings.set` | 8.settings | 키 1개 저장(hot-reload). 반환: 저장된 값. |
| `samples.fetch` | 3.data-samples | 선택된 (source,index)들의 field·type·sample 조회. 진행은 notification으로 스트리밍. |
| `pipeline.run` | 4.workflow→5.feedback | 정규화 파이프라인 시작(장기 실행). `run_id` 반환은 즉시, 진행/완료는 notification·feedback로. params: 선택된 sources. |
| `lineage.lookup` | 6.lineage-viewer | OpenSearch `_id` 단건의 lineage 조회(PG 메타 + raw + 정규화). 진행은 notification. |
| `monitoring.query` | 7.agent-monitoring | scope(session/today/all-time)별 agent 토큰·비용·last activity 반환. |

> agent workflow graph(4)의 그래프/역할은 정적이라 TUI가 자체 렌더링하고, **모델명만** `settings.get`에서 채운다. 별도 메서드를 두지 않는다.

> API key는 `.env`에 있어 TUI가 직접 읽지 못하므로, `settings.get` 응답에 **마스킹된 read-only 표시값**(예: `sk-…••••3f9a`)을 Backend가 포함해 준다(`8.settings` 표시용). secret 원문은 전달하지 않는다.

## 서버 → 클라이언트 (notification & request)

| 종류 | 메서드(예) | 용도 |
|---|---|---|
| notification | `progress` | agent 진행/thinking 로그 라인(5.A), source fetch 단계(3.A), lineage 조회 단계(6.D) |
| notification | `output.chunk` | Orchestrator 최종 결과 등 **스트리밍 출력** (PLANS 5 요구) |
| **request** | `feedback.request` | human feedback 요청. params: 원본 필드/타입·샘플·추천 OCSF 필드/이유. **클라이언트가 response로 사용자 선택을 돌려준다.** |
| notification | `run.status` | running → completed/failed 등 상태 전이 |

### human feedback 시퀀스

```text
TUI → Backend : pipeline.run(sources)              (request)
Backend → TUI : (response) run_id                  (즉시 반환)
Backend → TUI : run.status(running) / progress …   (notification)
Backend → TUI : feedback.request(field, recommend) (request, 서버 발신)
TUI → Backend : (response) approve | keep_raw | comment(text)
   … 모든 매핑 끝까지 progress ↔ feedback.request 반복 …
Backend → TUI : output.chunk(결과 요약 스트리밍) + opensearch link
Backend → TUI : run.status(completed)              (run 종료)
```

- `feedback.request`의 추천 내용은 Profiler/Normalization이 생성하고 Orchestrator가 **중계만** 한다(PRD mermaid 8~11, `FRD` Orchestrator). IPC상으로는 Backend가 단일 발신자다.
- 캐시 히트 필드는 feedback 없이 진행되므로 `feedback.request`가 발생하지 않는다(`03-agent-workflow-langgraph.md` 캐시 분기).

## 스트리밍 / 백프레셔

- 출력은 `output.chunk` notification으로 잘게 보낸다(PLANS 5: 대규모 출력 한 번에 금지, 진행 표현 필요).
- TUI는 chunk를 받는 즉시 Content 영역에 append + 스피너 표시(`TUI-DESIGN.md` 로딩 표시).
- 단일 실행이라 다중 run 인터리빙은 없다. chunk에는 `run_id`를 실어 완료 후 도착한 잔여 chunk를 식별한다.

## 입력 게이팅

- 파이프라인 실행 중 TUI 입력창은 비활성(`⌧ agent running`). **`feedback.request` 수신 동안에만** 입력 활성(`5.human-feedback` 규칙).
- 이 게이팅은 TUI가 `run.status`/`feedback.request` 수신 상태로 판단한다.
