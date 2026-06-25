## 프로젝트 개요

### AI-PRO

AI-PRO : 본 프로젝트 수행을 위한 서포터 이름이다. 개발 시 `AI-PRO`라는 이름은 사용하지 않고 작업한다. 즉, 해당 이름은 신경쓰지 않고 작업한다.

### 호칭 구분

`You`, `너` : 프로젝트 개발을 담당하는 AGENT(Codex, Claude Code 등)를 의미한다.

`Scala-Agent`, `Scala-agent`, `scala-agent` : SCALA 동작을 담당하는 Agent를 의미한다. 즉, `scala-docs/PRD.md`의 "## 6. Scala-Agents"에 있는 Agent를 의미한다.

`사용자`, `나` : `너`와 대화를 통해 개발을 진행하고, `Scala-Agent`와 interactive 대화를 통해 프로젝트 실행을 하는 주체이다. 

### SCALA

SCALA : Security Canonical Alignment & Lineage Automation

SCALA는 이기종 보안 데이터 source를 분석하고, OCSF 기반 Canonical Schema로 정규화된 데이터를 Opensearch에 적재하고 원천 데이터 추적 기능을 제공하는 `Scala-Agent` 기반 ETL 자동화 시스템이다. 

현재 프로젝트에서는 Elasticsearch, Splunk를 중심으로 데이터 정규화를 처리한다. 하지만 추후 QRadar, ArcSight 등 다른 SIEM 솔루션과 SOAR, WAF 등 여러 보안솔루션으로의 확장 가능한 구조로 개발을 수행해야 한다.

### TUI (Terminal User Interface)

SCALA는 TUI 형식으로 사용자와 interactive하게 소통한다. 즉, `Scala-Agent`에게 요청, `Scala-Agent`의 응답은 터미널 프로그램을 통해 동작하며, `사용자`는 터미널을 이용하여 `Scala-Agent` 동작 상태, 수행 결과를 확인할 수 있다. 


## 프로젝트 목표 

### 현재 목표 

SCALA의 현재 목표 중 주요 내용은 다음과 같다. 자세한 내용은 PRD.md (`scala-docs/PRD.md`) 를 참고한다.

- Elasticsearch, Splunk에 저장된 서로 다른 필드의 이름, 타입을 OCSF에 맞는 정규화된 데이터로 취합하여 Opensearch에 적재한다.
- `Scala-Agent`가 판단하기 애매하거나 어려운 것은 `사용자`와 interactive한 소통을 통해 취합할 필드를 확정한다.
- 누락되는 데이터 없이 모든 데이터가 Opensearch에 적재되어야 하며, 모든 적재된 데이터에 대해 원본 데이터와의 Lineage가 가능해야 한다.  

### 미래 목표 

현재 프로젝트가 아닌 미래의 목표는 다음과 같다. 그러므로 아래 사항에 대해서는 개발 시 현재는 염두하지 않는다. 

- 비정상 종료에 따른 복구 기능
- CI/CD
- Opensearch 클러스터링
- 사용자 인증
- 권한 관리 
- 기타 프로덕션 레벨의 운영 요소


## 프로젝트 디렉토리 및 파일 구성 요소 

```text
ai-pro-scala-tui/
├── AGENTS.md               # `You` 기본 지침 
├── PLANS.md               # `You` 가 프로젝트 수행을 위한 전반적인 계획 단계 
├── README.md               # 프로젝트 전체 설명 
└── your-docs/              # `You`가 코드 개발 시 필요한 문서 저장 디렉토리
    ├── CODING-RULES.md         # 코드 개발 시 지켜야 할 규칙들 (컨벤션 규칙, 사용하면 좋은 skill 목록 등)
    ├── GITOPS-RULES.md         # 코드 개발 시 지켜야 할 git 관리 방법 
    └── README.md               # 코드 개발에 대한 설명 
└── your-work-history/      # `You`가 작업한 이력 저장 디렉토리 
    ├── TEMPLATE.md             # 작업 이력 작성 시 사용할 템플릿
    └── README.md               # 작업 이력 관리에 대한 설명
└── scala-docs/             # SCALA 프로젝트와 관련된 문서 저장 디렉토리 
    ├── FRD.md                  # FRD, 기능 요구사항 정의서 
    ├── PRD.md                  # PRD, 제품 요구사항 정의서
    ├── SW-ARCHITECTURE.md      # SW 아키텍처 구성 내용 
    ├── TUI-DESIGN.md           # TUI 디자인 관련 문서 
    ├── tui-pages/              # TUI 페이지별 상세 문서(mockup) 디렉토리 
    ├── WORKFLOW.md             # SCALA 전체 워크플로우 
    └── README.md               # 관련 문서들에 대한 설명
```

## 프로젝트 규칙 및 제약사항

1. 코드 작성 시, 추상화와 재사용성을 고려하여 인터페이스 기반으로 개발을 수행한다. 이는 미래 목표 달성과도 연관이 있으므로 인터페이스 설계에 주의를 기울여야 한다. 
2. Docker 이미지 다운로드, 외부 자료 다운로드 필요 시, 반드시 검증된 공식 사이트 및 자료만 다운로드를 한다. 즉, 인터넷과 관련된 것은 보안에 유의하여야 한다.
3. `your-docs`의 `CODING-RULES.md, GITOPS-RULES.md`를 반드시 지켜서 코딩 및 git 관리를 한다. 
4. `scala-docs`, `your-docs` 내의 문서 수정이 필요한 경우, `사용자`에게 확인 받은 뒤 수정한다. 예를 들어, 프로그램 워크플로우 과정에서 오류가 있거나 문서 상 논리가 이상한 경우가 있는 경우, `scala-docs/WORKFLOW.md` 파일을 `사용자`에게 어떤 부분에 오류가 있으니 어떻게 수정하면 되겠다를 제안한다. 그리고 `사용자`가 허용 시 문서를 수정한다. 
5. `your-work-history`의 문서는 `TEMPLATE.md`에 맞게 자유롭게 작성한다. 
6. `.env` 파일에 중요 환경 변수 값들이 저장되어 있다. `너`는 직접 읽어서 사용해도 되고, 수정해도 되지만, git commit은 절대 하면 안 된다. `.env.example` 파일만 commit하여 다른 개발자도 사용할 수 있도록 한다.
7. `사용자`와의 대화 과정, 코드 작업 과정에서 `md` 등 문서 수정이 필요한 경우, 즉각적으로 수정하고 사용자에게 수정된 내용을 알린다.