# 01. 컴포넌트 토폴로지 & 기술 스택

SCALA를 구성하는 프로세스/컨테이너와 그 연결 관계, 그리고 확정 기술 스택을 정의한다.

## 프로세스 모델

SCALA는 **2개의 1급 실행 단위**로 구성된다.

| 단위 | 구현 | 역할 |
|---|---|---|
| **TUI (frontend)** | Go + Bubbletea | 사용자 터미널 앱. 화면 렌더링·입력 처리. **store/source/LLM에 직접 붙지 않으며 secret을 갖지 않는다.** |
| **Backend** | Python (단일 프로세스) | 모든 store·source·LLM 연결 독점. LangGraph agent 파이프라인 + 읽기용 deterministic 핸들러. |

TUI ↔ Backend는 **JSON-RPC 2.0**으로만 통신한다(상세 `02-ipc-json-rpc.md`). 그 외 모든 데이터는 Backend가 중계한다.

나머지는 모두 Backend가 클라이언트로 접속하는 **인프라/외부 시스템**이다.

| 시스템 | 용도 | 접속 정보 위치 |
|---|---|---|
| PostgreSQL | `scala_settings` · `scala_runs` · `scala_agent_usage` · `scala_data_lineage_metadata` | `.env` |
| Redis | source field → OCSF 매핑 cache | `.env` |
| ChromaDB | OCSF 표준 임베딩(RAG) | `.env` |
| OpenSearch | 정규화 결과 저장 | url/index는 `scala_settings`, auth는 `.env` |
| Elasticsearch / Splunk | source SIEM | url/index는 `scala_settings`, auth는 `.env` |
| OpenAI | LLM provider | API key는 `.env` |

> 인프라 접속(PostgreSQL/Redis/Chroma)은 `.env`로만 관리하므로 Settings 변경으로 재시작이 유발되지 않는다. source/OpenSearch는 url·index가 `scala_settings`에 있고 auth만 `.env`에 있다(상세 `08-config-and-secrets.md`).

## 토폴로지

```text
        ┌──────────────────────────┐
        │  TUI (Go · Bubbletea)    │   ← 사용자 터미널, secret 없음
        └────────────┬─────────────┘
                     │ JSON-RPC 2.0 (양방향, 스트리밍)
        ┌────────────┴─────────────┐
        │  Backend (Python)        │
        │  · LangGraph 파이프라인   │
        │  · 읽기용 핸들러          │
        │  · Connector / Provider  │
        └─┬───┬───┬───┬───┬───┬────┘
          │   │   │   │   │   │
   PostgreSQL │ ChromaDB │ Elasticsearch
            Redis    OpenSearch    Splunk        OpenAI(API)
```

- 읽기 화면(`6.lineage-viewer`·`7.agent-monitoring`·`8.settings`·`2.source-selection`·`3.data-samples`)은 Backend의 **deterministic 핸들러**가 처리한다. LLM Orchestrator를 거치지 않는다.
- 파이프라인 실행(`5.human-feedback`)만 LangGraph agent 그래프를 거친다.

## 기술 스택 (확정)

| 영역 | 스택 | 비고 |
|---|---|---|
| TUI | Go, Bubbletea, Lipgloss | mockup·색상은 `TUI-DESIGN.md` |
| Backend 언어 | Python | 단일 프로세스 |
| Agent orchestration | LangGraph | human feedback = interrupt/checkpoint (`03-…`) |
| LLM | OpenAI (provider 추상화) | 모델·단가는 `scala_settings` (`07-…`) |
| RDB | PostgreSQL | 스키마는 `RDB-TABLES.md` |
| Cache | Redis | key = `source_type+index+field+type` |
| Vector DB | ChromaDB | OCSF RAG (`06-…`) |
| 결과 저장 | OpenSearch | 정규화 문서 |
| Source SDK | Elasticsearch / Splunk SDK | Connector 추상화 뒤 (`04-…`) |
| 패키징 | Docker Compose | 인프라 + Backend (PLANS 11) |

> 라이브러리 정확한 버전 핀은 백엔드 개발(step 9)에서 `requirements`/`go.mod`로 확정한다. 본 문서는 스택 선택까지만 고정한다.

## 배치 (Docker Compose)

PLANS 11에서 Docker Compose로 묶는 대상은 **인프라(PostgreSQL/Redis/ChromaDB/OpenSearch/ES/Splunk)와 Backend**다. TUI는 사용자가 터미널에서 실행하는 클라이언트 바이너리다.

> ⚖️ 판단 필요 — **IPC transport 및 Backend 실행 형태.** Backend를 (a) Compose 서비스로 띄우고 TUI가 소켓(TCP localhost 또는 Unix domain socket)으로 접속할지, (b) TUI가 Backend를 자식 프로세스로 띄워 stdio로 통신할지. 토폴로지·Compose 구성이 갈린다. 상세 트레이드오프는 `02-ipc-json-rpc.md`.
