## SW Architecture

SCALA의 소프트웨어 아키텍처 문서다. 항목이 많아 단일 파일 대신 주제별로 분리한다.

각 문서는 `PRD.md` / `FRD.md` / `RDB-TABLES.md` / `TUI-DESIGN.md` / `tui-pages/`를 근거로 하며, 내용이 충돌하면 **PRD·FRD가 상위**다.

### 확정된 전제 (전 문서 공통)

이 전제들은 step 6~7 논의에서 확정되었으며, 모든 아키텍처 문서가 따른다.

- **모든 데이터 접근은 백엔드 IPC 경유다.** TUI는 store/source에 직접 붙지 않고, secret을 갖지 않는다. (PRD mermaid: User는 Orchestrator하고만 연결)
- **백엔드는 단일 Python 프로세스**로, 모든 store·source·LLM 연결을 독점한다.
- **파이프라인은 단일 실행(single-flight)** — 큐 시스템이 없다. 실행 중 사용자 입력은 human feedback 요청 때만 일시 활성.
- **설정은 hot-reload** — 백엔드가 run 시작 시점에 `scala_settings`를 읽어 연결을 구성한다. 컨테이너 재시작 불필요.

### 문서 목록

| # | 문서 | 내용 |
|---|---|---|
| 01 | `01-component-topology-and-stack.md` | 프로세스·컨테이너 토폴로지, 기술 스택 |
| 02 | `02-ipc-json-rpc.md` | TUI ↔ 백엔드 JSON-RPC 2.0 (메서드·notification·스트리밍) |
| 03 | `03-agent-workflow-langgraph.md` | LangGraph agent 그래프·state·인터럽트·캐시 분기 |
| 04 | `04-siem-connector.md` | SIEM Connector 추상화 인터페이스 |
| 05 | `05-data-store-access.md` | store별 접근 주체·시점 |
| 06 | `06-ocsf-rag-ingestion.md` | OCSF 임베딩·ChromaDB 적재 |
| 07 | `07-llm-provider-and-usage.md` | LLM provider 추상화·토큰/비용 회계 |
| 08 | `08-config-and-secrets.md` | `.env` / `scala_settings` 로딩·반영 |
| 09 | `09-run-lifecycle.md` | run 생명주기·동시성·에러 경계 |
