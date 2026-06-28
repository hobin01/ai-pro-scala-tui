# 99. IPC 메시지 스키마 (부록)

TUI ↔ Backend JSON-RPC 2.0 메시지의 **필드 단위 상세 스키마**다. 메서드 목록·설계 근거는 `sw-architecture/02-ipc-json-rpc.md`, 시나리오 맥락 예시는 `01`~`06`.

모든 메시지는 JSON-RPC 2.0 envelope를 따른다.
```
request      : { "jsonrpc":"2.0", "id":<n>, "method":"<m>", "params":{…} }
response     : { "jsonrpc":"2.0", "id":<n>, "result":{…} }   |   { …, "error":{ "code","message" } }
notification : { "jsonrpc":"2.0", "method":"<m>", "params":{…} }   (id 없음)
```
아래는 각 메서드의 `params`/`result`(또는 notification `params`) **본문**만 표기한다.

---

## settings.get  (TUI → Backend)

`params`: `{}`

`result`:
```json
{
  "agents": {
    "orchestrator":    { "model": "gpt-…" },
    "schema_profiler": { "model": "gpt-…-mini" },
    "normalization":   { "model": "gpt-…" },
    "validator":       { "model": "gpt-…-mini" }
  },
  "sources": {
    "elasticsearch": { "url": "https://es-prod:9201", "indices": ["logs-2024","firewall-idx"] },
    "splunk":        { "url": "https://splunk-soc:8089", "indices": ["main","security"] }
  },
  "output":   { "opensearch": { "url": "https://opensearch.local:9201", "index": "scala-normalized" } },
  "consoles": { "kibana": {"url":"…"}, "splunk": {"url":"…"}, "opensearch": {"url":"…"} },
  "openai_api_key_masked": "sk-…••••3f9a"
}
```
- `openai_api_key_masked`: `.env`에서 Backend가 생성한 read-only 표시값(원문 미전달).
- `model.<name>.price`는 백엔드 전용이라 **미포함**(화면 비노출).
- agent system prompt(`agent.<agent>.system_prompt`)는 `scala_settings`에 저장되지만 화면 비노출이라 `settings.get` 응답에 **포함하지 않는다**(단가와 동일 — DB에서만 관리).

## settings.set  (TUI → Backend)

`params`: `{ "key": "<setting_key>", "value": <any> }` — `key`는 `scala_settings` 네임스페이스 키(`RDB-TABLES.md`).
`result`: `{ "key": "<setting_key>", "value": <any>, "applied": "hot-reload" }`

## samples.fetch  (TUI → Backend)

`params`:
```json
{ "sources": [ { "solution": "elasticsearch", "index": "logs-2024" }, … ] }
```
진행 notification `progress`:
```json
{ "target": { "solution":"…", "index":"…" }, "status": "fetching" | "done" | "error", "message": "…(error 시)" }
```
`result`:
```json
{ "indices": [ {
    "solution": "splunk", "index": "main",
    "fields": [ { "name":"clientip", "type":"string", "samples":["10.0.0.5","192.168.1.20"] }, … ]
} ] }
```
- `samples`는 필드당 최대 5개. 결측치는 `null`, 빈 문자열은 `""` 그대로.

## pipeline.run  (TUI → Backend)

`params`: `{ "sources": [ { "solution":"…", "index":"…" }, … ] }`
`result`: `{ "run_id": "<uuid>" }`  ← 즉시 반환. 이후는 아래 notification/request.

### run.status  (Backend → TUI, notification)
```json
{ "run_id":"…", "status": "running" | "completed" | "failed",
  "summary":  { "mapped":13, "kept_raw":2, "loaded":2000, "lineage":2000, "cached":5 },   // completed 시
  "opensearch_link": "https://opensearch.local/_dashboards/…",                            // completed 시
  "error": "…" }                                                                          // failed 시
```

### progress  (Backend → TUI, notification)
```json
{ "run_id":"…", "agent":"schema_profiler", "message":"profiled 13 fields (cache 8 hit · 5 miss)" }
```

### output.chunk  (Backend → TUI, notification)
```json
{ "run_id":"…", "text":"…결과 요약 일부…" }   // 여러 번 잘게 전송(스트리밍)
```

### feedback.request  (Backend → TUI, request — 서버 발신)
`params`:
```json
{ "run_id":"…",
  "field":          { "source_field":"clientip", "type":"string", "samples":["10.0.0.5","192.168.1.20"] },
  "recommendation": { "ocsf_field":"src_endpoint.ip", "ocsf_type":"ip", "action":"map"|"keep_raw",
                      "why":"name+value look like a source IP; cast string→ip" },
  "options": ["approve","keep_raw","comment"] }
```
response (TUI → Backend):
```json
{ "decision": "approve" | "keep_raw" | "comment", "comment": "…(decision=comment 시)" }
```

## lineage.lookup  (TUI → Backend)

`params`: `{ "opensearch_id": "aZ12bQ8…" }`
진행 notification `progress`: `{ "stage": "metadata"|"raw"|"normalized", "status":"fetching"|"done", "target":"splunk·main" }`
`result`:
```json
{ "found": true,
  "metadata": { "source_solution":"splunk", "source_index":"main", "source_doc_id":"_bkt:_cd…",
                "opensearch_index":"scala-normalized", "opensearch_id":"aZ12bQ8…", "run_id":"a1b2c3" },
  "raw_document":        { "clientip":"10.0.0.5", "port":"443", "status":"allow", "_time":"…" },
  "normalized_document": { "src_endpoint.ip":"10.0.0.5", "dst_endpoint.port":443,
                           "activity_name":"allow", "custom_attr":{ "_time":"…" } } }
```
not found: `{ "found": false }`

## monitoring.query  (TUI → Backend)

`params`: `{ "scope": "session" | "today" | "all_time" }`
`result`:
```json
{ "scope":"today", "as_of":"14:05",
  "total": { "tokens":842300, "cost":1.94, "last_run_id":"a1b2c3", "runs":37 },   // runs는 all_time에 의미
  "agents": [
    { "agent":"orchestrator", "model":"gpt-…",      "last_activity":"showed final result", "tokens":120400, "cost":0.61 },
    { "agent":"load",         "model":null,         "last_activity":"loaded 2,000 docs",   "tokens":0,      "cost":0.0 },
    …
  ] }
```
- no-LLM 3종(load/caching/lineage)은 `model:null`, `tokens:0`, `cost:0.0`이되 `last_activity` 포함(7행).

## 에러 코드 (공통)

| code | 의미 |
|---|---|
| `settings_incomplete` | 필수 설정 누락으로 run 시작 불가 |
| `run_in_progress` | 이미 실행 중(단일 실행 위반) |
| `source_unreachable` | source 연결 실패 |
| `not_found` | 대상 없음(예: lineage `_id`) — 또는 `result.found:false`로 표현 |

> 본 스키마는 설계 명세다. 정확한 직렬화·필드명 최종 확정은 백엔드/TUI 연결(step 10)에서 고정한다.
