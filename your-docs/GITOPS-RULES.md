## GITOPS-RULES

### Branch 전략

- 기본 브랜치는 `main`이며, 항상 배포/실행 가능한 상태를 유지한다. `main`에 직접 push 하지 않는다.
- 모든 작업은 `main`에서 분기한 **단기(short-lived) 브랜치**에서 진행하고, 완료되면 PR로 병합 후 삭제한다.
- 브랜치 이름은 `<type>/<간단한-설명>` 형식의 소문자 + 하이픈(kebab-case)으로 짓는다.
  - 예) `feat/json-rpc-client`, `fix/update-blocking`, `docs/coding-rules`
- `<type>`은 커밋 타입(아래 참조)과 동일한 어휘를 사용한다. (`feat`, `fix`, `docs`, `refactor`, `chore` 등)
- 브랜치는 가능한 한 작게 유지하고 자주 병합한다. 오래 살아남는 브랜치는 충돌과 리뷰 부담을 키운다.
- 이슈 트래커를 쓴다면 이슈 번호를 포함해도 좋다. (예) `feat/42-task-cancel`


### Commit 메시지 작성 방법 

**Conventional Commits** 형식을 따른다.

- type (필수): 커밋의 성격

|type|설명|
|---|---|
|feat|새로운 기능|
|fix|버그 수정|
|docs|문서 변경|
|style|포맷·세미콜론 등 코드 의미에 영향 없는 변경|
|refactor|기능 변화 없는 코드 구조 개선|
|test|테스트 추가/수정|
|chore|빌드, 설정, 의존성 등 잡무|

- scope (선택): 영향 범위. (예: tui, backend, ipc)
- subject (필수): 변경 내용을 명령형 현재 시제로 간결하게. 끝에 마침표를 찍지 않는다.
  - 권장: add task cancel notification
  - 지양: added task cancel notification.

- body (선택): "무엇을"보다 "왜" 변경했는지를 설명한다. 한 줄에 72자 내외로 줄바꿈한다.
- footer (선택): 이슈 참조나 호환성 깨짐을 명시한다.
  - 이슈 연결: Closes #42
  - 호환성 깨짐: BREAKING CHANGE: <설명>

메시지 작성 추가 원칙은 다음과 같다.

- 제목 줄(첫 줄)은 50자 내외로 유지한다.
- 하나의 커밋은 하나의 논리적 변경만 담는다. 서로 무관한 변경을 한 커밋에 섞지 않는다.
- 동작하지 않는 중간 상태를 그대로 커밋하지 않는다. (필요시 커밋 정리 후 push)


### PR 및 merge 방법 

- 모든 변경은 PR(Pull Request)을 통해서만 main에 병합한다.
- PR은 작게 유지한다. 리뷰 가능한 단위(대략 수백 줄 이하)를 권장한다.
- PR 제목은 커밋 컨벤션과 동일한 형식을 따르고, 본문에는 다음을 포함한다.
  - 무엇을 / 왜 변경했는지
  - 테스트 방법 또는 확인 절차
  - 관련 이슈 링크 (Closes #42)

- Merge 조건
  - 린트, 테스트, 빌드 검사가 모두 통과해야 한다. (CI/CD 파이프라인 구축 자체는 현재 범위 밖이므로, 호스팅 CI 없이 로컬에서 해당 검사를 수행하여 통과를 확인한다.)
  - 리뷰에서 제기된 코멘트는 해결(resolve)되어야 한다.

- 머지 전략: PR 단위로 Squash and Merge를 기본으로 한다. 여러 작업 커밋을 하나의 의미 있는 커밋으로 합쳐 main 히스토리를 깔끔하게 유지한다.
- 병합이 끝난 브랜치는 삭제한다.
- main의 변경을 가져올 때는 rebase를 우선한다. (불필요한 merge 커밋을 줄여 히스토리를 선형으로 유지)


### 공통 사항

- `너`는 단독으로 작업을 수행하므로, code reviewer 관련 능력을 발휘하여 정확한 코드 리뷰 후 Merge를 수행한다. 
- branch origin push 후에는 `gh`를 이용하여 github 관련 작업을 수행하면 된다.
- 작업 완료 후 사용하지 않는 branch는 로컬과 origin 모두에서 삭제한다.
- `main` branch에는 항상 실행 가능한 최신 버전이 반영되도록 한다. 
