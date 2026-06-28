# 04. SIEM Connector 추상화

이기종 source SIEM(현재 Elasticsearch·Splunk, 미래 QRadar/ArcSight 등)을 단일 인터페이스 뒤에 둔다. `AGENTS.md`·`PRD` 5.2의 "확장 가능한 Interface" 요구의 핵심이다.

## 인터페이스

Backend는 source를 직접 다루지 않고 `SiemConnector` 인터페이스로만 접근한다.

| 메서드 | 입력 | 출력 | 사용처 |
|---|---|---|---|
| `fetch_schema_samples(index, n≤5)` | index | 필드·타입·샘플 값(필드별 ≤5) | `3.data-samples` |
| `iter_documents(index)` | index | 원본 raw 문서 스트림(+doc id) | 파이프라인(정규화·적재 대상 읽기) |
| `fetch_raw_document(index, doc_id)` | index, 원본 doc id | 원본 raw 문서 1건 | `6.lineage-viewer` 역추적 |

- `fetch_schema_samples`는 결측치·빈 값·이기종 타입을 **가공 없이** 반환한다(`3.data-samples` 정책).
- `iter_documents`는 전량 누락 없이 읽어야 한다(`PRD` 4: 누락 없는 적재). 대량(예: 1000건/index)이므로 스트리밍/배치로 제공.
- `fetch_raw_document`의 `doc_id`는 `scala_data_lineage_metadata.source_doc_id`로 저장한 값과 동일 식별자를 쓴다(`05-…`, `RDB-TABLES.md`).

## 구현체 & 팩토리

| 구현체 | solution |
|---|---|
| `ElasticsearchConnector` | elasticsearch |
| `SplunkConnector` | splunk |

- `make_connector(solution, url, auth)` 팩토리가 `solution` 문자열로 구현체를 선택한다.
- 미래 SIEM은 인터페이스 구현 + 팩토리 등록만으로 확장한다(코드 변경 최소화).

## 접속 정보 결합

연결에는 **url·index(= `scala_settings`)** 와 **auth(= `.env`)** 가 둘 다 필요하다(상세 `08-config-and-secrets.md`).

- url/index: `scala_settings`의 `source.<solution>.url` · `source.<solution>.indices`.
- auth: `.env`의 solution별 자격(예: token/계정). `solution`을 키로 url(settings)과 auth(.env)를 결합한다.

> ⚖️ 판단 필요 — **`fetch_raw_document`의 Splunk 식별자 안정성.** Splunk의 원본 식별자(예: `_bkt=…::host::1234`)로 사후 단건 재조회가 가능한지 SDK 차원에서 확인 필요. 불가하면 lineage 저장 시점에 재조회 가능한 키(예: 검색 가능한 unique 필드)를 함께 저장하도록 `RDB-TABLES.md`에 컬럼 보강이 필요할 수 있다. (Elasticsearch는 `_id`로 단건 GET 가능)

## 캐시 key의 source_type

Schema Profiler/Caching의 cache key는 `source_type+index_name+field_name+field_type`다(`FRD`). 여기서 `source_type`의 정의가 `04`/캐시 정확도에 직접 영향을 준다.

> ⚖️ 판단 필요 — **`source_type` 입도.** `FRD`는 "elasticsearch, splunk **또는 해당하는 url**"로 적어 모호하다. 
> ① solution 이름(`elasticsearch`)으로 두면 같은 solution의 서로 다른 연결이 캐시를 공유 — 같은 index명이 다른 인스턴스에서 의미가 다르면 오적용 위험. 
> ② `url`(또는 url+index)까지 포함하면 인스턴스별로 분리 — 안전하지만 캐시 재사용률↓. 
> 현재 단일 인스턴스 PoC면 ①로 충분하나, 정의를 명시 확정해야 한다.
