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
- `fetch_raw_document`의 `doc_id`는 `scala_data_lineage_metadata.source_doc_id`로 저장한 값과 동일 식별자를 쓴다(`05-data-store-access.md`, `RDB-TABLES.md`).

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

## 단건 재조회 (`fetch_raw_document`)

source별로 단건 재조회 방식이 다르다. Connector가 그 차이를 흡수하므로, lineage는 **Connector가 돌려준 식별자를 그대로 저장**했다가(`source_doc_id`) 같은 Connector에 되돌려 주기만 하면 된다.

- **Elasticsearch**: `_id`로 단건 GET 가능. `source_doc_id = _id`.
- **Splunk**: 단건 GET API가 없다(이벤트는 search로만 회수). 이벤트는 **`_cd`(이벤트 주소 `bucket:offset`)** + **`_bkt`(버킷 GUID, 클러스터에서도 안정)** 튜플로 유일 식별된다. 재조회는 **index/시간으로 범위를 좁힌 search 후 `_bkt`·`_cd`로 필터**한다. (`_cd`는 base search에 직접 박기보다 `rename _cd as x | search x="bucket:offset"` 또는 `| where`로 거른다.) 최신 `splunk-sdk-python`(splunklib) 기준 재조회는 search job + `splunklib.results` 리더로 수행한다.
  - 따라서 Splunk의 `source_doc_id`는 **opaque 합성 키**다(`_bkt`+`_cd`, 범위 한정용 `index`/`_time` 동반).

즉 `source_doc_id`는 **Connector가 정의하는 불투명 식별자**이며, `RDB-TABLES.md`의 `source_doc_id TEXT`가 그대로 수용한다(스키마 변경 불필요).

## 캐시 key의 source_type

Schema Profiler/Caching의 cache key는 `source_type+index_name+field_name+field_type`다(`FRD`).

**확정**: `source_type`은 **인스턴스 단위(= 연결 URL)** 로 분리한다. solution 이름만으로 구분하면, 서로 다른 인스턴스에 **같은 index 이름**이 있을 때 실제 데이터 구성이 달라도 캐시를 공유해 **오적용**될 수 있기 때문이다.

- `source_type` = source 연결 **URL**(인스턴스 식별; solution은 URL로 유도). 같은 index 이름이라도 다른 인스턴스면 키가 분리된다.
- 캐시 재사용률은 다소 낮아질 수 있으나 **정확성을 우선**한다.
