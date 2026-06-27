## CODING RULES for you

### Go language Coding Convention

#### 포매팅 / 도구
- `goimports`로 import를 자동 정렬하며, 표준 라이브러리 / 서드파티 그룹을 분리한다.
- 린트는 `golangci-lint`를 사용하고, CI에서 통과를 필수로 한다.
- 들여쓰기는 탭(tab)을 사용한다. (gofmt 기본값)
- `go mod`로 프로젝트 패키지 관리를 수행한다. 

#### 네이밍
- 식별자는 `MixedCaps` / `mixedCaps`를 사용하고 언더스코어(`_`)는 쓰지 않는다.
- 외부 공개(exported)는 `PascalCase`, 패키지 내부(unexported)는 `camelCase`.
- 약어는 대소문자를 통일한다. (`userID`, `httpClient`, `parseURL` — `userId`, `Http` 금지)
- 패키지명은 짧고 소문자 단수형, 언더스코어 없이. (`util`, `auth` / `utils_pkg` 금지)
- 인터페이스는 단일 메서드일 때 `-er` 접미사를 권장한다. (`Reader`, `Renderer`)
- 패키지명과 타입명이 겹치는 stutter를 피한다. (`http.Server` O / `http.HTTPServer` X)

#### 에러 처리
- 에러는 함수의 마지막 반환값으로 두고, 발생 직후 `if err != nil`로 즉시 처리한다.
- 에러를 전파할 때는 컨텍스트를 덧붙여 wrapping 한다: `fmt.Errorf("작업 실패: %w", err)`.
- 에러 비교/추출은 `errors.Is`, `errors.As`를 사용한다. (문자열 비교 금지)
- 라이브러리/내부 로직에서는 `panic`을 쓰지 않는다. (복구 불가능한 초기화 실패 등 예외적 상황만 허용)

#### 구조 / 스타일
- 디렉토리는 `cmd/`(실행 엔트리포인트), `internal/`(외부 비공개 코드)로 구분한다.
- 외부 입출력/취소가 관여하는 함수는 `context.Context`를 첫 번째 인자로 받는다.
- 리소스 정리는 `defer`로 처리한다. (파일, 락, 연결 등)
- 가드 절(early return)로 중첩을 줄인다. else 블록을 깊게 쌓지 않는다.
- 메서드 리시버 이름은 짧게(1~2자) 유지하고, 한 타입 내에서 포인터/값 리시버를 일관되게 사용한다.
- 전역 가변 상태(global mutable state)를 피한다.

#### 주석 / 문서화
- 공개(exported) 식별자에는 doc comment를 단다.
- doc comment는 식별자 이름으로 시작하는 완전한 문장으로 쓴다.
  예) `// Render draws the current view to the screen.`


### Python Coding Convention

#### 포매팅 / 도구
- 스타일의 기준은 PEP 8을 따른다.
- 포매터는 `black`(또는 `ruff format`)을 사용하고, 라인 길이는 88자를 기본으로 한다.
- 린터는 `ruff`를 사용하며, CI에서 통과를 필수로 한다.
- import 정렬은 `isort`(또는 `ruff`)로 자동화한다.
- 들여쓰기는 공백 4칸(4 spaces)을 사용한다.
- 패키지 관리는 `uv`로 한다.

#### 네이밍
- 함수 / 변수 / 모듈: `snake_case`
- 클래스: `PascalCase`
- 상수: `UPPER_SNAKE_CASE`
- 내부 전용(비공개)은 선행 언더스코어 `_name`을 사용한다.
- 의미 없는 약어 대신 풀어 쓴 이름을 선호한다.

#### 타입 힌트
- 모든 함수/메서드의 시그니처(인자, 반환값)에 타입 힌트를 단다.
- 정적 타입 검사는 `mypy`(또는 `pyright`)로 수행하고, 특히 외부 경계를 넘는 데이터에는 엄격하게 적용한다.

#### import
- 절대 경로 import를 기본으로 한다.
- import는 표준 라이브러리 / 서드파티 / 로컬 모듈 순서로 그룹을 나눈다.
- 와일드카드 import(`from module import *`)는 금지한다.

#### 예외 처리
- `except:` 또는 `except Exception:`으로 모든 예외를 광범위하게 잡지 않는다. 구체적인 예외 타입을 명시한다.
- 도메인 에러는 커스텀 예외 클래스를 정의해 사용한다.
- 예외를 삼키지(silent pass) 않는다. 처리하거나 로깅 후 재전파한다.

#### 스타일
- 문자열 포매팅은 f-string을 사용한다. (`%`, `.format()`보다 우선)
- 파일/경로 처리는 `os.path` 대신 `pathlib`을 사용한다.
- 리소스 관리는 컨텍스트 매니저(`with`)를 사용한다.

#### 문서화
- 공개 함수/클래스/모듈에는 docstring을 단다. (PEP 257)
- docstring 스타일은 Google 또는 NumPy 스타일 중 하나로 프로젝트 전체에서 통일한다.


### IPC Convention (Go ↔ Python)

#### 프로토콜
- 통신은 **JSON-RPC 2.0** 스펙을 따른다.
- 모든 메시지는 UTF-8 JSON 객체이며, 최상위에 `"jsonrpc": "2.0"` 필드를 반드시 포함한다.
- 메시지 프레이밍은 **개행 구분(newline-delimited JSON)**을 사용한다. 즉, 한 메시지 = 한 줄(JSON에 내부 개행을 넣지 않는다).

#### 메시지 종류
- **Request** (응답이 필요한 호출): `jsonrpc`, `method`, `params`, `id` 포함.
- **Response** (요청에 대한 응답): `jsonrpc`, `id`, 그리고 `result` 또는 `error` 중 정확히 하나 포함.
- **Notification** (응답이 불필요한 단방향 통지): `id`를 생략한다. (진행률, 로그 스트림 등)

#### 필드 규칙
- `method` 이름은 `snake_case`를 사용하고, 네임스페이스가 필요하면 점(`.`)으로 구분한다. (예: `task.run`, `session.cancel`)
- `params`는 **named parameters(객체)**를 사용한다. positional(배열)은 쓰지 않는다.
- 경계를 넘는 모든 필드명은 `snake_case`로 통일한다.
  - Go 측은 구조체에 JSON 태그로 매핑한다. (예: `UserID string \`json:"user_id"\``)
  - Python 측은 `snake_case`이므로 그대로 매핑된다.

#### id 관리
- `id`는 **Go(클라이언트) 측에서 생성**하며, 요청마다 증가하는 정수 또는 UUID를 사용한다.
- 응답의 `id`는 요청의 `id`와 반드시 일치해야 하며, Go 측은 이를 기준으로 요청-응답을 매칭한다.

#### 동작 과정 
- Go Bubbletea는 `사용자` 요청을 입력받는다. 
- Go Bubbletea는 Python App의 실행 / `Scala-Agent` 응답 결과를 Json-RPC 2.0으로 받아와 streaming 형식으로 `사용자`에게 보여준다. 


### Error Handling Convention

에러는 **프로토콜 레벨**과 **애플리케이션 레벨** 두 층으로 나눠 처리한다.

#### 에러 객체 구조 (JSON-RPC)
- 에러는 응답의 `error` 필드에 담으며, 다음 구조를 따른다:
  - `code` (정수): 에러 분류 코드
  - `message` (문자열): 사람이 읽을 수 있는 짧은 설명
  - `data` (선택): 추가 정보(상세 메시지, 컨텍스트 등)

#### 에러 코드 규칙
- 프로토콜 레벨 에러는 JSON-RPC 표준 코드를 그대로 쓴다:
  | 코드 | 의미 |
  |--------|------|
  | -32700 | Parse error (잘못된 JSON) |
  | -32600 | Invalid Request (스펙 위반) |
  | -32601 | Method not found |
  | -32602 | Invalid params |
  | -32603 | Internal error |
- 애플리케이션 레벨 에러는 **-32000 ~ -32099 범위**의 커스텀 코드를 정의해 사용한다. (예: `-32001` = 작업 실행 실패, `-32002` = 리소스 없음) 코드 의미는 한 곳에 표로 정리해 양쪽이 공유한다.


### 공통 원칙 
- 에러는 **삼키지 않는다.** 처리하거나, 로깅 후 전파하거나, 사용자에게 전달하거나 셋 중 하나는 반드시 한다.
- 사용자 대상 메시지와 개발자 대상 로그를 분리한다. (사용자에겐 친절하게, 로그엔 자세하게)
- 모든 개발 코드에 주석을 **한국어**로 간결하게 작성한다.
- 현재 프로젝트에서는 강제 종료 시 복구 방안 등의 운영 요소는 고려하지 않으므로 너무 복잡하지 않은 개발을 수행한다. 
- 단 로컬 환경에서 요구사항이 모두 정상적으로 동작해야 한다. 
- 구현 시, 적합한 디자인 패턴을 사용하며, 추상화를 통해 service, data layer 구분 등 interface 기반의 구현을 수행한다.


### Usefule Skills / Plugins

아래 skills, plugins을 적극 활용한다. 해당 내용을 찾을 수 없으면 사용자에게 설치를 요청한다. 
아래 이외의 skills, plugins 중 개발에 활용할 수 있는 설치된 것들이 있다면 적극적으로 활용한다. 

- Go 개발 관련 : `cc-skills-golang`
- 최소 개발 원칙 : `karpathy-guidelines`
- 적절한 용도의 프레임워크 사용, 최적의 코드 작성 : `ponytail`
- 주석 작성 시 사람과 같이 작성 : `humanizer` (주석 작성 시 이 파일의 어투 참고하여 작성)
- Docker 설정 관련 : `docker-development`
- brainstorming, planning, code-review : `superpowers`
