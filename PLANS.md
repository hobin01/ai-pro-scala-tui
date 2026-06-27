## PLANS.md

`너`의 작업을 위한 Plan 목록이다. 현재 프로젝트 마무리를 위해 ruff한 계획만 작성하였으며, 추후 계획 변동이 발생할 수 있다.

구체화 문서 작업 등 문서 작업이 주요 작업인 경우, `사용자`와 interactive하게 합의점을 찾은 뒤 작업을 수행한다.

### 1. 구성된 문서 목록 파악
- 전체적인 문서 목록 및 프로젝트 목표 파악

### 2. PRD 구체화 
- `scala-docs/PRD.md`에서 논리적 오류 검사 

### 3. FRD 작업 
- `scala-docs/FRD.md` 작성 및 구체화를 통해 상세한 프로그램 기능 명세 도출

### 4. TUI 디자인 `사용자`와 함께 구성 
- `scala-docs/tui-pages` 하위 문서 작업을 통해 상세한 page 별 mockup 구성

### 5. TUI 개발
- Go Bubbletea 이용하여 TUI 개발
- 백엔드 없는 더미 데이터로 개발 
- `scala-docs/tui-pages`의 모든 페이지 구현
- `사용자` 출력은 스트리밍으로 출력 필요 (현재 출력이 진행되고 있음을 표현하며, 대규모 출력을 한 번에 처리하기에 버퍼에 무리 있음)
- Unit Test 기반 TDD 수행

### 6. RDB 설계 
- `scala-docs/RDB-TABLES.md` 파일 작성
- Postgresql docker container 기반으로 db 관리 구성 

### 7. SW Architecture 구성
- `scala-docs/SW-ARCHITECTURE.md` 파일 작성
- 구체적인 SW 기술 스택 구체화
- SW 구성 요소 간 IO, 요청/응답 결과 등을 구체화
- TUI, 백엔드 간 IPC 포맷 구체화

### 8. WORKFLOW 구성 
- `scala-docs/WORKFLOW.md` 파일 작성 
- 사용자 입력부터 SCALA 최종 출력 결과까지 모든 과정에 대한 워크플로우 구체화 

### 9. 백엔드 개발 
- 필요한 RDB 설정 및 table 생성, 필요한 초기 데이터 추가 
- python 백엔드 app 개발 
- langgraph 기반 agent workflow 구성
- elasticsearch / splunk sdk 통한 데이터 Source 연결 (추후 다른 보안솔루션 연동을 위해 추상화된 개발 필수)
- OCSF 최신 버전을 이용한 RAG Vector DB 구성 (Chroma DB)
- opensearch sdk 통한 정규화된 데이터 적재 
- Data Lineage Metadata 저장을 위한 Postgresql RDB 설계 및 설정 
- Redis 이용한 캐싱 처리 구성 
- `scala-agent` 구성하는 AI Agent 구성 (`scala-docs/PRD.md`의 `## 6. Scala-Agents` 목록)
- 기타 `scala-docs/PRD.md`의 모든 요구사항을 충족하도록 개발
- Unit Test 기반 TDD 수행

### 10. TUI, 백엔드 연결 
- 개발된 TUI, 백엔드 간의 연결 수행
- JSON-RPC 2.0 기반 통신 시, TUI, 백엔드 간 IPC 포맷에 맞도록 데이터 통신 수행 
- 요구사항 충족하는 지 최종 테스트 수행 

### 11. 최종 SCALA 개발 
- Docker Compose 기반 설정 및 필요한 SW 인프라, 솔루션 간 연결
- Docker Compose 기반 빌드 및 정상 실행, 동작 유무 테스트 

### 12. 수동 테스트 데이터 구성 
- `scala-docs/PRD.md`의 `## 9. 수동 확인용 랜덤 데이터 정책`에 대한 수동 테스트용 데이터 생성
- 해당 데이터를 이용하여 `사용자`가 수동 테스트를 할 수 있도록 가이드 문서 작성
- 선행 작업이 있는 경우, 반드시 가이드에 포함하여야 함 (ex. docker compose 명령어로 깔끔한 상태를 만든다.)
- 수동 테스트용 데이터 구성 시, 이상한 필드 이름, 결측치, 인덱스 별 서로 다른 필드 이름 / 데이터 타입 구성 등이 반드시 필요
- 수동 테스트 시, 캐싱 처리가 되지 않은 가장 처음 상태부터 테스트할 수 있어야 함

### 13. 성능 지표 측정용 데이터 구성 
- `scala-docs/PRD.md`의 `## 10. 평가 지표 측정`에 대한 성능 지표 측정용 데이터 구성 
- 해당 데이터를 이용하여 지표를 측정하는 방법 `사용자`를 위한 가이드 문서 작성
- 성능 지표 측정용 데이터 구성 시, 이상한 필드 이름, 결측치, 인덱스 별 서로 다른 필드 이름 / 데이터 타입 구성 등이 반드시 필요
- 성능 지표 측정용 데이터 구성 시, 캐싱 처리가 되지 않은 가장 처음 상태부터 테스트할 수 있어야 함

### 14. 최종 점검
- 요구사항을 모두 충족하였는지 최종 점검 
- 프로그램 실행을 위한 `README.md` 작성 
- 추후 유지보수를 위해 코드에 주석 올바른지 확인 및 전반적인 코드 리뷰 
- 문서 중 잘못된 부분이 있는 지 전체적으로 확인
- 불필요한 파일 삭제
