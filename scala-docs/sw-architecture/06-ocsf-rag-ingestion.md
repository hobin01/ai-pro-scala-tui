# 06. OCSF RAG 적재 (ChromaDB)

Schema Profiler가 캐시 미스 필드에 대해 OCSF 후보를 찾을 때 쓰는 벡터 검색 인덱스를 구성한다.

## 데이터 소스

- **OCSF 표준 스키마**(필드 정의)를 임베딩 대상으로 한다.
- 출처는 **공식 OCSF 배포본만** 사용한다(`AGENTS.md` 규칙 2: 검증된 공식 자료만 다운로드).

**버전 (확정)**: OCSF **1.8.0** 으로 핀한다. (`ocsf/ocsf-schema` v1.8.0, 2026-03 릴리스 — 현 시점 최신 stable.) 공식 태그 1.8.0 배포본만 다운로드해 사용하며, RAG 임베딩·평가 지표(`PRD` 10)는 이 버전을 기준으로 한다. 버전 업그레이드 시 재임베딩(또는 새 컬렉션)한다.

## 임베딩 & 컬렉션

- OCSF 필드(이름/설명/타입/카테고리 등)를 문서 단위로 임베딩한다.
- 임베딩 모델은 **OpenAI 임베딩**을 사용한다(provider는 `07-llm-provider-and-usage.md`).
- ChromaDB 컬렉션 1개에 적재한다. 메타데이터로 OCSF 필드 식별자(예: `src_endpoint.ip`)·타입·카테고리를 함께 저장해, 검색 결과를 매핑 후보로 바로 쓸 수 있게 한다.

## 적재 시점

- **최초 1회 부트스트랩**으로 적재한다(파이프라인 run마다 적재하지 않는다).
- **idempotent**: 컬렉션이 이미 채워져 있으면 건너뛴다. OCSF 버전이 바뀌면 재적재(또는 새 컬렉션).

**부트스트랩 트리거 (확정 · 하이브리드)**: 평소엔 **빈 컬렉션 자동 감지 시 적재**한다(Backend 기동 시 컬렉션이 비어 있으면 OCSF 1.8.0을 임베딩해 채움). 더불어 **명시적 재적재 명령**(예: `python -m scala.ingest_ocsf`)을 제공해, OCSF 버전 업그레이드나 평가용 환경 초기화(`PRD` 10: 서비스 독립 환경) 시 강제로 다시 채울 수 있게 한다.

## 조회 (Schema Profiler)

- 캐시 **미스** 필드에 한해(`03-agent-workflow-langgraph.md`/`05-data-store-access.md`), 원본 필드명·타입·샘플을 질의로 OCSF 후보 top-k를 가져온다.
- 후보가 없거나 모호하면 Normalization/Validator를 거쳐 최종적으로 human feedback 또는 `custom_attr`/`unmapped_field` 처리로 귀결된다(`PRD` 4: 모든 필드 누락 금지).
