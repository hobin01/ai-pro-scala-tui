# 03. 데이터 변환 추적

필드/문서 하나가 **원본 → 정규화 → 적재 → 리니지**로 변하는 여정을 실제 예시 값으로 따라간다. (`6.lineage-viewer`가 보여주는 양끝의 *중간 단계*를 채운다)

예시 원본: **Splunk · main** 인덱스의 한 이벤트.

---

## 0. 원본 raw (Splunk)

```
clientip : "10.0.0.5"     port   : "443"
status   : allow          _time  : 2026-06-25 01:02:03
```

- 이름·타입이 OCSF와 불일치(`clientip` string, `port` string `"443"`). 정규화 대상.
- 이벤트 식별자: Splunk `(_bkt, _cd)` 합성(단건 GET 없음, `sw-architecture/04-siem-connector.md`).

## 1. 프로파일 (PA)

필드별 cache key 계산 후 `Redis` 조회.

| 필드 | cache key (요약) | 결과 |
|---|---|---|
| `clientip` | `<splunk-url>+main+clientip+string` | miss → RAG로 |
| `port` | `…+port+string` | (예) hit → 캐시 매핑 적용 |

## 2. OCSF 후보 (PA → Chroma, miss 필드만)

`clientip`(string, samples `10.0.0.5`…)를 질의 → OCSF 1.8.0 후보:

```
src_endpoint.ip (ip)   ← top 후보
```

## 3. 매핑 Rule (NA) + 검증 (VA)

```
clientip (string) ──rename──▶ src_endpoint.ip
                  ──cast────▶ string → ip
```

- 애매하면 human feedback(`02-branches.md`). 확정되면 `VA` 자가 검증 후 반영.
- OCSF로 매핑 안 되는 필드(`_time` 등)는 **누락 없이** `custom_attr`로 보존(`PRD` 4).

## 4. 정규화 문서 (OCSF)

```json
{
  "src_endpoint.ip":   "10.0.0.5",
  "dst_endpoint.port": 443,
  "activity_name":     "allow",
  "custom_attr":       { "_time": "2026-06-25 01:02:03" }
}
```

- `port "443"`(string) → `dst_endpoint.port 443`(number), `status allow` → `activity_name`. 매핑 못한 `_time`은 `custom_attr`로 보존.

## 5. 적재 (LO → OpenSearch)

`LO`가 정규화 문서를 `OpenSearch`(`scala-normalized`)에 적재 → `_id` 발급(예: `aZ12bQ8…`). `_id`를 `LA`로 전달.

## 6. 확정 매핑 캐시 (CA → Redis)

확정된 `clientip → src_endpoint.ip` 매핑을 cache key로 `Redis`에 저장 → 다음 run의 같은 필드는 캐시 hit.

## 7. 리니지 메타데이터 (LA → PostgreSQL)

`scala_data_lineage_metadata`에 **문서 1행**:

| 컬럼 | 값 |
|---|---|
| `source_solution` | splunk |
| `source_index` | main |
| `source_doc_id` | `_bkt:_cd` 합성(opaque) |
| `opensearch_index` | scala-normalized |
| `opensearch_id` | aZ12bQ8… |
| `run_id` | (이번 run) |

---

## 역방향 (lineage 조회)

`6.lineage-viewer`에서 `opensearch_id`로 위 메타를 찾아, 원본 위치로 raw를 다시 가져와 **원본 ↔ 정규화**를 나란히 보여준다. 흐름은 `04-read-flows.md`.

```
opensearch_id aZ12bQ8…  ─(PG 메타)→  splunk·main·(_bkt:_cd)
   ├─ raw(Splunk)        : clientip "10.0.0.5" · port "443" · _time …
   └─ normalized(OS)     : src_endpoint.ip 10.0.0.5 · dst_endpoint.port 443 · custom_attr{_time}
```
