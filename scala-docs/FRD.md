## FRD 

기능 요구사항은 페이지 별로 정리한다. 페이지는 `tui-pages/`를 기준으로 한다. 

### 1.main.md

#### `scala-agent`가 동작하는 것이 없는 초기 화면 - 공통

`scala-agent` 동작을 위해 `사용자`가 처리해야 할 과정을 step 별로 가이드한다. 기본 가이드는 템플릿화된 정적인 메시지로 구성한다.

step 별 가이드 하단에는 SCALA 데이터 취합을 원하는지, 결과 확인을 원하는지, 환경 설정을 할 것인지 사용자가 처음 선택하도록 한다.

`/help` 커맨드로 SCALA 실행에 대한 도움말을 확인할 수 있도록 한다.

#### `scala-agent`가 동작하는 것이 없는 초기 화면 - SCALA 데이터 취합을 요청하는 경우

데이터 취합을 선택한 경우, 가이드에 대한 `사용자`의 입력 내용은 `Orchestrator Agent`가 확인 후, `scala-agent`에게 동작을 요청한다.

1. Data Source 선택
  - settings에 미리 설정된 값 중 2개 이상을 선택. Elasticsearch index 2개, Elasticsearch index 1개, Splunk index 1개, Splunk index 2개 등을 고를 수 있음
  - 상세 기능은 하단의 `2.source-selection.md` 섹션에서 설명한다.
2. Data Sample 확인 
  - 선택된 index에 포함된 데이터 필드, 타입, 값에 대한 샘플을 확인
  - 상세 기능은 하단의 `3.data-samples.md` 섹션에서 설명한다. 
3. Agent Workflow Graph 확인
  - `2.` Data Sample 확인 후 `enter` 입력 시 `4.agent-workflow-graph.md` 화면으로 전환된다.
  - 현재 구성된 agent workflow graph(에이전트 구성도, 각 에이전트의 역할, 사용 모델)를 확인한다.
  - 상세 기능은 하단의 `4.agent-workflow-graph.md` 섹션에서 설명한다.
4. 파이프라인 동작 실행 여부 확인
  - `4.agent-workflow-graph.md` 화면에서 사용자에게 최종 실행 여부를 확인한다.
  - 사용자가 Y, Yes 등을 선택 시, 동작 완료 때까지 추가 입력을 받지 않음 (현재 프로젝트 범위에서 큐잉 시스템 없음)


#### `scala-agent`가 동작하는 것이 없는 초기 화면 - 결과 확인을 원하는 경우

결과 확인을 선택한 경우, 다음의 기능을 수행할 수 있다. 

1. Lineage Viewer 기능
  - `/lineage-viewer` 커맨드로 데이터 lineage를 확인할 수 있는 화면으로 전환된다. 
  - 해당 화면의 상세 기능은 하단의 `6.lineage-viewer.md` 섹션에서 설명한다. 

2. Agent Workflow Graph 기능 
  - `/agent-workflow` 커맨드로 현재 `scala-agent`에 구성된 에이전트들의 구성을 시각화하여 볼 수 있는 화면으로 전환된다. 
  - 즉, langgraph로 동작되는 전체적인 에이전트 구성도와 각 에이전트 역할에 대한 설명이 시각화된다.
  - 현재 프로젝트 범위에서는 거의 정적인 화면 구성이다.
  - 해당 화면의 상세 구성은 하단의 `4.agent-workflow-graph.md` 섹션에서 설명한다.

3. Agent Monitoring 기능 
  - `/agent-monitoring` 커맨드로 현재 `scala-agent` 동작에 사용되는 에이전트들의 모니터링을 표시한다. 
  - 각 에이전트 별로 현재 세션, 전체 프로그램에서 최종 작업을 수행한 이력은 무엇인지, 에이전트 별로 현재 세션, 전체 프로그램에서 토큰은 얼마나 썼는지, 오늘 사용, 전체 기간 동안 사용한 총 토큰은 얼마인지 등 전체적인 에이전트 시스템의 비용과 이력 관련 모니터링을 위주로 한다.
  - 실시간 조회는 현재 프로젝트에서는 하지 않고, 커맨드 실행 시점을 기준으로 계산한다.
  - 해당 화면의 상세 구성은 하단의 `7.agent-monitoring.md` 섹션에서 설명한다.


#### `scala-agent`가 동작하는 것이 없는 초기 화면 - 환경 설정을 하는 경우

환경 설정을 하고자 하는 경우, 다음의 기능을 수행할 수 있다. 

1. settings 기능
  - settings 설정값을 확인하고, TUI에서 직접 수정할 수 있다. (source url, index 등)
  - 수정된 내용은 db의 `settings` table에 즉각 반영되어, 다른 화면에서도 바로 적용되어야 한다. (index 추가 : main 화면에서 추가된 index를 프로세스 종료 없이 바로 선택 가능)
  - 상세 기능은 하단의 `8.settings.md` 섹션에서 설명한다.


#### `scala-agent`가 동작 중인 경우 

`scala-agent`가 동작 중인 경우, 동작 종료 시까지 `사용자`로부터 입력을 받지 않는다. 현재 프로젝트 범위에서는 큐잉 시스템이 없다. 즉, 모든 `사용자`의 요청 (프롬프트, / 커맨드 등) 은 한 건 씩 처리가 된다. 

단, 예외적으로 `human feedback`이 필요한 경우, `human feedback`를 `사용자`에게 요청한다. 이 경우에만 `사용자` 입력을 일시적으로 허용한다. `human feedback` 수행 시 필요한 상세 기능은 하단의 `5.human-feedback.md` 섹션에서 설명한다.


#### `scala-agent`가 동작 완료한 경우

`scala-agent`가 동작을 완료한 경우, `Orchestrator Agent`가 최종 결과를 사용자에게 스트리밍으로 알려준다. 동시에 실제 취합된 결과가 저장된 opensearch 웹 화면 링크를 함께 제공한다. 

`사용자`가 결과 확인을 마친 경우, `enter` 키를 입력받아 "#### `scala-agent`가 동작하는 것이 없는 초기 화면 - 공통" 섹션에 해당하는 main 화면으로 이동한다. 

완료 화면의 상세 기능은 하단의 `5.human-feedback.md` 섹션에서 설명한다.


### 2.source-selection.md

elasticsearch index 2개, Elasticsearch index 1개, Splunk index 1개, Splunk index 2개 등을 고를 수 있다. 단, 2개 이상 선택이 가능해야 하므로 주의하여 개발한다. 

선택은 `space`로 선택을 하며, 선택 가능한 source는 `8.settings.md`에 설정된 source를 선택하는 것이다.

사용자가 선택 완료 후 `enter`를 입력하면, 선택된 2개 이상의 index들을 대상으로 `scala-agent`를 동작시킨다. 

올바른 선택인 경우, `3.data-samples.md` 화면으로 전환되며, 

올바르지 않은 선택인 경우, 올바른 선택을 하라는 메시지를 화면에 표시한다. 이후 사용자는 올바른 선택을 다시 시도한다.


### 3.data-samples.md

선택된 index에 포함된 데이터 필드, 타입, 값에 대한 샘플을 확인한다.

source solution의 sdk를 이용해 선택된 index에 대한 데이터 필드와 샘플을 일부 가져오고, 사용자에게 보여준다. 

샘플은 최대 5개만 보여주되, 필드는 기본 설정된 필드 외에 실데이터에 대한 모든 필드를 보여줘야 한다. 

단, 보여줄 항목이 너무 많은 경우 페이지네이션이 필요하다. 페이지 이동은 `← →` 키보드 버튼으로 이동한다.

`사용자`에게 `enter`를 누르면 다음 화면으로 전환됨을 알리고, `enter` 입력 시, `4.agent-workflow-graph.md` 화면으로 전환된다. 


### 4.agent-workflow-graph.md

`사용자`는 현재 구성된 agent workflow graph 구성을 확인한다. 

agent workflow graph에는 다음을 표현한다. 

1. 현재 구성된 agent 간 구성도 및 아키텍처 (PRD 문서의 mermaid 그림 참고)
2. 각 agent의 역할 설명
3. 각 agent의 실제 모델 (ex. chatgpt-5.4-mini 등)

`사용자`가 구성 확인을 완료하면 `enter`를 입력한다. 

main 화면에서 단순 조회로 해당 페이지에 접근한 경우, main 페이지로 돌아간다. 

source 선택 후 해당 페이지에 접근한 경우, `사용자`에게 `scala` 동작 시작 유무를 확인한다.

사용자가 시작 선택 시, `5.human-feedback.md` 화면으로 이동한다. 


### 5.human-feedback.md

`scala` 동작 중인 상태에서 화면이 시작된다. 화면에는 현재 어떤 agent가 어떤 동작을 수행 중인지 표시한다. (codex, claude code의 thinking 과정과 같이 표시.) (만약 표시하는 것의 구현 난이도가 높다면 단순히 동작 중임을 의미하는 표현만 화면에 표시한다.)

만약 `scala-agent`에서 human feedback을 요청하는 경우, 사용자 입력이 활성화된다. 그 외에는 사용자 입력은 비활성화된다. 

human feedback을 `scala-agent`가 요청한 경우, 화면에는 현재 어떤 어려움을 겪고 있는 것인지, 매칭을 위한 필드의 원본 이름과 `scala-agent`가 생각한 적합한 OCSF 필드명 또는 원본 필드 유지하는 것이 좋을 지 등 추천하는 필드와 타입을 표시한다. 

`사용자`가 human feedback 요청 내용에 대해 `scala-agent`의 추천 내용을 받아들인다면 `추천 승인` 선택, 원본 유지를 원한다면 `raw 유지`, 특별한 의견을 제시할테니 다시 의견을 요청하는 경우 `의견 작성 후 재검토`를 선택할 수 있게 한다.

 `scala-agent`는 `사용자`가 `추천 승인` 선택 시, 자신의 추천 매핑을 수용하고, `raw 유지` 선택 시, 원본 유지를 하고, `의견 작성 후 재검토` 선택 시, `사용자`의 입력 내용에 따라 재검토 후 다시 추천 매핑을 제시한다. 

 human feedback이 없고 모든 매핑이 완료될 때까지 해당 화면에 머물고 위 내용을 반복한다. 

 만약 human feedback이 남은 것이 없고, 모든 매핑이 끝나고 opensearch에 모든 적재가 완료된 경우, `orchestrator agent`는 `사용자`에게 `scala-agent`의 수행 결과 내용을 보여준다. 동시에 적재된 내용을 확인할 수 있는 opensearch 링크를 제공한다.

 `사용자`가 결과 확인을 마친 경우, `enter` 키를 입력받아 main 화면으로 이동하도록 한다.


### 6.lineage-viewer.md

data lineage를 확인하는 화면으로, opensearch에 저장된 document의 원본 데이터를 찾아 보여준다. 

원본 데이터 추적은 Postgresql에 저장된 메타데이터를 이용하여 현재 opensearch에 저장된 document의 원본이 elasticsearch, splunk에 있는 raw 데이터 중 무엇인지를 보여주는 것이다. 

모든 opensearch 데이터에 대해 보여주는 것은 불가능하니 (화면에 보여줄 데이터 너무 많고, 검색 느림) 사용자가 opensearch document id를 입력하면 그에 대한 data lineage를 추적하여 보여준다. 

opensearch document와 postgresql에 저장된 metadata 정보가 있으므로 별도 agent 동작은 하지 않는다.

`사용자`가 결과 확인을 마친 경우, `enter` 키를 입력받아 main 화면으로 이동하도록 한다.


### 7.agent-monitoring.md

각 에이전트 별로 최종 작업을 수행한 이력은 무엇인지, 에이전트 별로 토큰은 얼마나 썼는지, 현재 프로세스에서 사용한 총 토큰은 얼마인지, 오늘 사용한 총 토큰은 얼마인지 등 전체적인 에이전트 시스템의 비용과 이력 관련 모니터링을 한다. 

이때 현재 세션을 넘어서는 집계(오늘 사용량, 전체 기간 누적 사용량 등)는 PostgreSQL에 저장된 에이전트 토큰/비용 사용 이력을 기반으로 계산한다. (구체적인 테이블 설계는 별도 디자인 작업에서 진행한다.)

`scala-agent`를 구성한 agent에서 사용하는 자세한 모델명(chatgpt-5.4-mini 등), 각 모델의 마지막 작업 이력 (orchestrator agent의 경우, 최종 취합 결과를 사용자에게 보여줬음에 대한 이력), 각 agent들이 토큰을 얼마나 사용하고 현재 비용이 얼마가 사용되었는지 등을 상세히 표현한다.

`사용자`가 확인 환료한 경우, `enter` 키를 입력받아 main 화면으로 이동하도록 한다.


### 8.settings.md

환경설정과 관련된 값들을 확인, 수정을 한다. 즉, settings 설정값을 확인하고, TUI에서 직접 수정할 수 있다. (source index, url, llm model 종류 등)

수정된 내용은 DB `scala_settings` table에 즉각 반영되어, 다른 화면에서도 바로 적용되어야 한다. (index 추가하는 경우, main 화면에서 추가된 index를 프로세스 종료 없이 바로 선택 가능 등)

settings 화면에서 설정 가능한 모든 값은 DB `scala_settings` table에서 관리되는 값과 항상 동일해야 한다. 

모든 설정 변경은 hot-reload로 반영된다. 백엔드가 각 파이프라인 실행(run) 시작 시점에 현재 `scala_settings` 값을 읽어 source/OpenSearch 연결을 구성하므로, URL·model·system prompt 변경도 다음 run부터 자동 반영되며 컨테이너 재시작·프로세스 종료가 필요 없다. (인프라 접속 정보는 `scala_settings`가 아니라 `.env`에서 관리하므로, Settings 변경으로 재시작이 유발될 일이 없다.)

사용자는 `enter` 키를 입력받아 main 화면으로 이동할 수 있다. 

필수로 필요한 설정값은 아래와 같다. 
- agent 별 model 명 
- openai api key (`.env`에서 관리하며, settings 화면에는 read-only로만 표시한다. TUI에서 수정하지 않는다.)
- 연결 가능한 source url
- 연결 가능한 index
- `scala` 결과가 저장될 opensearch url
- `scala` 결과가 저장될 opensearch index


### Agent 기능 요구사항 

Agent 별 기능 요구사항은 다음과 같다. 

| Agent | 역할 | 주요 기능 |
|---|---|---|
| Orchestrator Agent | 전체 workflow 관리 | 작업 분배 및 작업 결과를 사용자와 직접적으로 소통하는 Agent |
| Schema Profiler Agent | 스키마 프로파일 분석 | OCSF 필드 중 매핑 가능한 것 있는 지 판단, 커스텀된 필드인지 판단하는 Agent. 토큰 이코노미를 위해 캐시 조회도 담당. |
| Normalization Agent | 정규화 Rule 생성 및 적용 | 프로파일 분석 내용과 검증 결과를 바탕으로 필드 매핑 Rule을 생성하고, 원본 데이터에 Rule을 적용하여 정규화 데이터를 생성하는 Agent |
| Validator Agent | 데이터 정합성 검증 | 정규화 처리가 올바른지 판단하는 Agent |
| Lineage Agent | 리니지 메타데이터 생성 | 원본 Data Source와 최종 정규화된 데이터 간 추적 연결성 보장을 하는 Agent |
| Load Agent | 정규화 데이터 적재 | Opensearch sdk, api를 이용하여 정규화된 데이터를 적재하는 Agent |
| Caching Agent | 캐싱 저장 처리 | 정규화 과정에서 확정된 source field와 OCSF field 간 매핑 결과를 Redis Cache에 저장하는 Agent |

각 agent 간의 연결관계는 `PRD.md`의 `7. 주요 워크플로우`에 포함된 mermaid 부분을 참고한다. 


#### Orchestrator Agent

- 역할 : 전체 workflow 관리
- 주요 기능 : 작업 분배 및 작업 결과를 사용자와 직접적으로 소통하는 Agent

사용자의 입력에 대해 적합한 명령을 다른 agent에게 전달하고, agent의 수행 결과를 취합하여 사용자에게 제공한다.

`사용자`와의 모든 직접 소통 채널은 `Orchestrator Agent`가 단독으로 소유한다. 즉, `Validator Agent` 등 다른 agent가 Human Feedback을 요청하는 경우에도, `Orchestrator Agent`가 요청 내용을 `사용자`에게 전달(`OA → US`)하고 `사용자`의 응답을 다시 해당 agent에게 전달(`OA → 요청 agent`)하는 **중계자** 역할을 한다. 이때 추천 매핑 등 Feedback 요청 내용 자체는 이를 요청한 agent가 생성하며, `Orchestrator Agent`는 생성에 관여하지 않고 전달만 담당한다. (`PRD.md`의 `7. 주요 워크플로우` mermaid 8~11번 참고)

전체 파이프라인 실행 결과는 `Caching Agent`, `Load Agent`, `Lineage Agent`의 실행 결과로 처리한다. 즉, `Orchestrator Agent`는 `Caching Agent`, `Load Agent`, `Lineage Agent`의 실행 결과를 종합하여 최종 처리 결과를 도출한다.


#### Schema Profiler Agent 

- 역할 : 스키마 프로파일 분석
- 주요 기능 : OCSF 필드 중 매핑 가능한 것 있는 지 판단, 커스텀된 필드인지 판단하는 Agent. 토큰 이코노미를 위해 캐시 조회도 담당.

캐시 key는 source_type + index_name + field_name + field_type 으로 계산한다.

- source_type : source 인스턴스 식별값으로 **연결 URL**을 사용한다. (solution 이름만으로 구분하면 서로 다른 인스턴스의 동일 index 이름이 캐시를 공유해 오적용될 수 있으므로 URL 단위로 분리한다.)
- index_name : 원본 데이터 저장된 index
- field_name : 원본 데이터의 field 
- field_type : 원본 데이터의 데이터 타입 


#### Normalization Agent 

- 역할 : 정규화 Rule 생성 및 적용
- 주요 기능 : 프로파일 분석 내용과 검증 결과를 바탕으로 필드 매핑 Rule을 생성하고, 원본 데이터에 Rule을 적용하여 정규화 데이터를 생성하는 Agent

매핑이 필요한 필드에 대해 OCSF 필드를 어떻게 매핑할 지 Rule을 세팅한다. 즉, elasticsearch, splunk sdk로 직접 데이터를 가져오고 취합하는 코드를 생성하는 것이 아닌, 정해진 코드에 필요한 parameter 세팅을 하는 역할이다. 
(각 source solution 별로 작업해야 할 sdk 기능은 제한되어 있으므로 굳이 모든 코드를 생성하지 않음.)


#### Validator Agent 

- 역할 : 데이터 정합성 검증
- 주요 기능 : 정규화 처리가 올바른지 판단하는 Agent

정규화 처리가 올바르게 되었는지 판단한다. human feedback 결과를 수용하기 전, 한 번 더 자가 검증을 수행한다. 이후 다른 agent에게 필요한 요청을 보낸다.


#### Lineage Agent 

- 역할 : 리니지 메타데이터 생성
- 주요 기능 : 원본 Data Source와 최종 정규화된 데이터 간 추적 연결성 보장을 하는 Agent

`Load Agent`로부터 정규화된 데이터를 Opensearch에 적재함으로써 얻은 opensearch의 document id(`_id`)를 받는다. 
이를 이용하여 원본 데이터와 적재된 정규화된 데이터 간 data lineage를 위한 메타데이터를 생성하고, postgresql을 통해 관리한다.
lineage 추적을 위해 "원본 source / index", "정규화 문서 저장된 source / index", "원본 document id 등 식별자", "opensearch _id", "작업 실행 id 등 식별자" 를 메타데이터로 관리한다. 

Agent의 실행 결과는 `Orchestrator Agent`에게 전달한다.


#### Load Agent 

- 역할 : 정규화 데이터 적재
- 주요 기능 : Opensearch sdk, api를 이용하여 정규화된 데이터를 적재하는 Agent

`Normalization Agent`로부터 정규화 데이터 적재 요청을 받으면 Opensearch에 적재 역할을 수행하는 에이전트이다. 
정규화된 데이터 적재 후 `Lineage Agent`에게 적재 정보 (정규화 문서 저장된 source / index, opensearch _id 값 등)을 전달해야 한다.

Agent의 실행 결과는 `Orchestrator Agent`에게 전달한다.


#### Caching Agent 

- 역할 : 캐싱 저장 처리
- 주요 기능 : 정규화 과정에서 확정된 source field와 OCSF field 간 매핑 결과를 Redis Cache에 저장하는 Agent

캐시 저장 시 사용하는 cache key 값은 `Schema Profiler Agent`에서의 설명과 동일하다. `Normalization Agent`에서 정규화 확정 시에만 redis에 캐시 저장을 처리한다. 

Agent의 실행 결과는 `Orchestrator Agent`에게 전달한다.


### 기타 기능 요구사항 
- `사용자`와의 interactive한 동작이 필요한 경우 (`enter`키를 입력 받아 다음 화면으로 전환 등), 모든 경우에 대해 적합한 메시지를 `사용자`에게 제공해야 한다.
- 변동 가능한 설정은 모두 DB `scala_settings` table로 관리가 되어야 한다. (agent 시스템 프롬프트, 선택 가능한 index, source url 등)

#### SCALA 데이터 관리 요구사항 

구체적인 settings 관련 table 설계는 `RDB-TABLES.md` 파일을 참고하여라. 
데이터 별 저장되는 위치는 아래 표와 같다.

| 데이터 | 저장 위치 | 
| --- | --- | 
| API Key, Password | .env | 
| 인프라 관련 접속 정보 (Postgresql, Redis, Chroma 등 접속 정보) | .env |
| Elasticsearch, Kibana, Opensearch, Splunk 로그인 / auth token 정보 | .env |
| Agent 모델 종류, 시스템 프롬프트 | Postgresql `scala_settings` table |
| SIEM 등 데이터 source url 및 index | Postgresql `scala_settings` table |
| 정규화 데이터 저장용 Opensearch url 및 index | Postgresql `scala_settings` table |
| 웹 콘솔 (Kibana, Splunk, Opensearch dashboard 등) | Postgresql `scala_settings` table |
| Data Lineage Metadata | Postgresql `scala_data_lineage_metadata` table | 
| API Token 비용 등 llm 사용 이력 | Postgresql `scala_agent_usage` table |
| SCALA 실행 관련 metadata (run_id 등) | Postgresql `scala_runs` table |
| source data field -> OCSF 매핑에 사용된 cache | Redis | 
| OCSF 표준 임베딩 (RAG) | ChromaDB | 
