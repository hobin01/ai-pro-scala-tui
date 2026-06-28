# 08. 설정 & 시크릿 로딩

3-tier 설정 모델(`.env` / `scala_settings`)의 로딩 순서·반영 방식·경계 동작을 정의한다.

## 두 출처

| 출처 | 담는 것 | 로딩 |
|---|---|---|
| **`.env`** | secret + 인프라 wiring: API key, PostgreSQL/Redis/Chroma 접속, ES/Splunk/OpenSearch/Kibana auth token | Backend **기동 시 1회** 로드. TUI는 읽지 않음. |
| **`scala_settings`** (PostgreSQL) | 가변 앱 설정: agent 모델·프롬프트, 모델 단가, source url·index, OpenSearch url·index, 웹 콘솔 URL | **run 시작 시점에 read**(hot-reload). `settings.set`으로 갱신. |

소유 매트릭스 전체는 `FRD`의 "SCALA 데이터 관리 요구사항", 스키마는 `RDB-TABLES.md`.

## 로딩 순서

1. Backend 기동 → `.env` 로드. 인프라 접속(PostgreSQL 등) 자격이 없으면 **fail-fast**(여기 없으면 아무것도 못 함).
2. PostgreSQL 연결 후 `scala_settings` 사용 가능.
3. 각 파이프라인 run 시작 시 현재 `scala_settings`를 읽어 source/OpenSearch 연결·agent 모델/프롬프트를 구성 → URL·model·prompt 변경이 다음 run부터 자동 반영(재시작 불필요).

## url(settings) + auth(.env) 결합

source/OpenSearch는 **url·index가 `scala_settings`**, **auth가 `.env`**로 나뉜다. 둘을 `solution`(또는 대상) 키로 결합한다.

```text
연결(elasticsearch) = scala_settings.source.elasticsearch.url
                    + .env 의 elasticsearch auth(token/계정)
```

- 즉 Settings에서 URL만 바꿔도 auth는 `.env`가 제공한다. auth 교체는 `.env`에서 한다.
- `.env`의 자격 키는 `solution`과 1:1로 대응하도록 명명 규약을 둔다(정확한 변수명은 step 9에서 `.env.example`로 고정).

## 빈 `scala_settings` (신규 설치)

신규 설치 시 `scala_settings`는 **빈 테이블**이다(시드 없음, `RDB-TABLES.md`). 사용자가 `8.settings`에서 채운다.

- source가 없으면 `2.source-selection`은 "No data sources configured → Open Settings"(State D)를 띄운다.
- 필수 설정 누락 시 `pipeline.run`은 시작 전에 **검증 실패를 반환**하고 TUI가 에러로 표면화한다.
- **필수 설정**(최소 실행 요건): source url·연결 가능 index(2개 이상 선택 가능하도록), agent 모델 4종, OpenSearch url·result index. (`8.settings.md` 필수 설정값 중 **`scala_settings`에 속하는 run-critical 항목**. API key는 `.env`, 웹 콘솔 URL은 실행 비필수라 이 목록에서 제외)

> API key는 `scala_settings`가 아닌 `.env`에 있으므로, 빈 settings 상태와 무관하게 `.env`에 있어야 한다. TUI는 read-only 마스킹 표시만 한다(`8.settings.md`).

## 반영 방식 (hot-reload, 확정)

- 모든 `scala_settings` 변경은 hot-reload. 컨테이너 재시작·프로세스 종료 불필요(step 6~7 확정).
- 근거: 인프라 접속은 `.env`(설정 변경 대상 아님), source/OpenSearch 연결은 run마다 재구성, Settings는 idle에서만 진입해 run 중 변경 충돌이 없음.
