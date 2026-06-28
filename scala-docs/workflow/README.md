## Workflow

SCALA의 **동적 통합 뷰**다. "사용자 입력 → 화면 → IPC → 백엔드/agent → store → 출력"을 하나의 시나리오로 꿰어 추적 가능하게 만든다(PLANS 8).

정적 구조는 다른 문서가 이미 정의했으므로 **다시 쓰지 않고 참조**한다.

| 다루는 곳 | 내용 |
|---|---|
| `tui-pages/` | 화면별 상태·전환 상세 |
| `sw-architecture/` | 컴포넌트·IPC 메서드 카탈로그·agent 그래프·store 접근 |
| `RDB-TABLES.md` | 테이블 스키마 |
| **이 디렉토리** | 위를 **시나리오로 연결**한 흐름 + 단계별 데이터 교환 |

### 표기 규약

각 시나리오 단계는 **3단**으로 기술한다.

1. **화면 행동 → output** — 사용자가 이 화면에서 무엇을 하면 무엇이 나오는가.
2. **IPC** — 그때 TUI↔Backend가 주고받는 JSON-RPC 메시지(시나리오 맥락의 **예시 payload**). 메서드 목록은 `sw-architecture/02-ipc-json-rpc.md`, 필드 단위 상세 스키마는 `99-ipc-schema-appendix.md`.
3. **백엔드/agent + store I/O** — Backend·agent가 한 일과 store 읽기/쓰기.

actor 표기: `User` · `TUI` · `Backend` · agent(`OA`/`PA`/`NA`/`VA`/`LO`/`CA`/`LA`) · store(`PG`/`Redis`/`Chroma`/`OpenSearch`/`ES`/`Splunk`) · `OpenAI`.
메시지 표기: `TUI → Backend : method(params)` (request) · `Backend ⇠ TUI : result` (response) · `Backend ⇢ TUI : notify` (notification).

### 문서 목록

| 파일 | 내용 |
|---|---|
| `01-collect-and-normalize.md` | 메인 end-to-end 시나리오(진입~완료) + 시퀀스 |
| `02-branches.md` | 캐시 hit/miss 분기 · human feedback 루프 |
| `03-data-transformation.md` | 필드 하나의 변환 여정(실제 예시 값) |
| `04-read-flows.md` | lineage 조회 · monitoring · workflow graph 조회 |
| `05-settings-hot-reload.md` | 설정 변경 → hot-reload 반영 흐름 |
| `06-failure-paths.md` | 실패 경로(연결·run·검증) |
| `99-ipc-schema-appendix.md` | IPC 메시지 필드 단위 상세 스키마 |

### 경계 (이 문서가 다루지 않는 것)

- 화면 픽셀/상태 mockup → `tui-pages/`.
- 메서드가 왜 그렇게 설계됐는지·transport → `sw-architecture/`.
- 예시 값은 **설명용**이다. 실제 필드/단가/모델명은 런타임 설정·데이터를 따른다.
