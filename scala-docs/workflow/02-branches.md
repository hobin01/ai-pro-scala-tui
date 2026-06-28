# 02. 분기 흐름 — 캐시 hit/miss · Human feedback

단계 5(파이프라인 실행) 내부의 두 결정 지점이다. 둘 다 **필드 단위**로 일어난다.

---

## 캐시 hit / miss (토큰 이코노미)

`PA`(Schema Profiler)가 필드마다 cache key로 `Redis`를 조회한다.

- **cache key** = `source_type + index_name + field_name + field_type`
  (`source_type` = 연결 URL = 인스턴스 식별. `sw-architecture/04-siem-connector.md`)

### hit — LLM·검증·feedback 생략

매핑 결정이 이미 확정돼 있으므로 그대로 적용한다. RAG·`NA`·`VA`·human feedback을 **건너뛴다**.

```
PA → Redis : GET key(src_ip@logs-2024…)        ⇠ { ocsf_field:"src_endpoint.ip", action:"map", cast:"string→ip" }
PA         : 캐시된 매핑 적용 → 확정             (NA/VA/feedback 없음)
```

### miss — 전체 경로

```
PA → Redis  : GET key(clientip@main…)           ⇠ (miss)
PA → Chroma : OCSF 후보 조회(field name+type+samples)   ⇠ top-k 후보
NA          : 매핑 Rule 생성·적용
VA          : 정합성 검증
   정합성 OK  → 확정
   정합성 미달 → feedback 요청(아래)
확정 후 CA → Redis : SET key = 확정 매핑          ← 정규화 확정 시에만 저장
```

> 캐시 분기는 그래프에 별도 엣지로 그리지 않는다(per-field 조건 분기). 흐름·근거는 `sw-architecture/03-agent-workflow-langgraph.md`, PRD 7 주석.

---

## Human feedback 루프

`VA`가 정합성 미달로 판단한 필드는 그래프를 **interrupt**하고, Backend가 `feedback.request`로 사용자에게 묻는다. 채널은 `OA`가 중계한다(추천 내용은 `PA`/`NA`가 생성, `OA`는 전달만 — PRD mermaid 8~11).

### 요청 (서버 → 클라이언트 request)

**① 화면**: `5.human-feedback` State B — 원본 필드/타입·샘플·추천 OCSF 필드/이유 + 3선택. 입력 활성.

**② IPC**:
```
Backend ⇢ TUI : feedback.request({
  run_id,
  field:          { source_field:"clientip", type:"string", samples:["10.0.0.5","192.168.1.20"] },
  recommendation: { ocsf_field:"src_endpoint.ip", ocsf_type:"ip", action:"map",
                    why:"name+value look like a source IP; cast string→ip" },
  options: ["approve","keep_raw","comment"]
})
```

### 응답 3종

| 선택 | response | 처리 |
|---|---|---|
| 추천 승인 | `{ decision:"approve" }` | 추천 매핑 적용 |
| raw 유지 | `{ decision:"keep_raw" }` | 원본 유지 → `custom_attr`/`unmapped_field` |
| 의견 후 재검토 | `{ decision:"comment", comment:"this is proxy client ip…" }` | `NA` 재검토 → 갱신된 추천으로 `feedback.request` 재발신 |

```
TUI → Backend : (response) { decision:"comment", comment:"prefer x_forwarded_for" }
Backend       : NA 재검토 → 갱신 추천
Backend ⇢ TUI : feedback.request({ … recommendation:{ ocsf_field:"…", why:"…(updated)" } })   ← State B 재진입
```

### 수용 전 자가 검증

`approve`·`comment` 결과는 `VA`가 **수용 전 한 번 더 자가 검증**한 뒤 반영한다(`FRD` Validator). 모든 필드가 확정될 때까지 State A ↔ State B 반복.

> 동작 중에는 feedback 요청 때만 입력이 활성된다(큐 없음). 입력 게이팅은 `sw-architecture/02-ipc-json-rpc.md`.
