# 06. 실패 경로

PoC 범위의 실패 표면화만 다룬다. 복구·재시도·롤백 같은 resilience는 범위 밖(`sw-architecture/09-run-lifecycle.md`).

---

## 설정 없음 (빈 scala_settings)

신규 설치 시 `scala_settings`가 비어 있다.

- **source 0개**: `2.source-selection` State D — "No data sources configured → Open Settings". `settings.get`이 빈 sources를 반환한 결과.
- **필수 설정 누락 상태로 실행 시**: `pipeline.run`이 시작 전 검증 실패를 반환.
```
TUI → Backend : pipeline.run({ sources:[…] })
Backend ⇠ TUI : error({ code:"settings_incomplete", message:"OpenSearch URL is not configured" })
```
필수 설정 정의는 `sw-architecture/08-config-and-secrets.md`.

## 소스 연결/조회 실패 (samples.fetch)

실제 연결이 처음 일어나는 `3.data-samples`에서 표면화.

```
TUI → Backend : samples.fetch({ sources:[…] })
Backend ⇢ TUI : progress({ target:{solution:"elasticsearch",index:"firewall-idx"}, status:"error",
                           message:"Connection refused (https://es-prod:9201)" })
```
**① 화면**: State D — `✗ Could not fetch…` + `Retry · Back to sources · Open Settings`. `Retry`는 해당 소스만 재조회, `Open Settings`는 URL 수정(→ `05-settings-hot-reload.md`).

## run 도중 실패 (all-or-nothing)

LLM 호출·OpenSearch 적재 등 실행 중 오류.

```
Backend ⇢ TUI : run.status({ run_id, status:"failed", error:"OpenSearch bulk load failed: …" })
```
**① 화면**: `5.human-feedback`에 에러 라인(`✗`). **② 처리**: run을 `failed`로 두고 멈춘다. 롤백/정리 코드 없음 — 사용자가 원인 고쳐 **재실행**(새 `run_id`). 깨끗한 상태가 필요하면 `docker compose`로 초기화(`PLANS` 12).
- 영속화(Load/Cache/Lineage)는 끝단에 모이므로, 그 전 단계(매핑·검증·feedback) 실패는 OpenSearch/PG에 **아무것도 안 남긴다**. Load 도중 실패만 부분 문서를 남길 수 있고, 이는 정리하지 않는다.

## lineage 조회 실패 (lineage.lookup)

```
TUI → Backend : lineage.lookup({ opensearch_id:"zzz9" })
Backend ⇠ TUI : { found:false }
```
**① 화면**: `6.lineage-viewer` State C — `✗ No lineage found`. 잘못된 `_id`이거나 SCALA가 만들지 않은 문서.

## 단일 실행 위반

run 진행 중 또 다른 `pipeline.run` 요청(정상 경로에선 입력 비활성이라 발생 안 함).
```
Backend ⇠ TUI : error({ code:"run_in_progress", message:"a pipeline is already running" })
```
