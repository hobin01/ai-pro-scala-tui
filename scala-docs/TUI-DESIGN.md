## TUI DESIGN

TUI : Terminal User Interface

주요 목적 : 터미널을 통해 `사용자`의 입력을 받은 뒤 `scala-agent`의 동작 과정, 처리 결과를 사용자에게 스트리밍으로 출력함

### 주요 key binding

| key input | 역할 |
| --- | --- |
| ↑ ↓ | 키보드 상하 입력으로 선택창 이동 |
| ← → | 키보드 좌우 입력으로 페이지 이동 |
| `space` | `space` 키 입력으로 단일, 복수 선택 기능 (선택 후 해제 포함) selector 역할일 때만 선택 기능을 하며, 그 외에는 공백 입력으로 사용됨 |
| `enter` | `enter` 키 입력으로 `사용자`의 현재 입력 내용 `scala`에게 전송 |
| `ctrl` + `enter` OR `shift` + `enter` | 줄바꿈 입력. `scala`에게 전송하면 안 됨 | 
| `esc` | `esc` 키 입력으로 `scala-agent` 동작 중지. interupt 역할 |
| `ctrl` + c | 프로세스 강제 종료 | 
| `/` + <command> | command 입력기. 특정 페이지 이동, 명령어 help 기능 |

이외 필요한 key binding은 `tui-pages`에서 페이지 별로 정의한다.

### TUI 페이지 별 상세 문서

`tui-pages` 디렉토리 하위 문서 참고

### TUI 개발 시 주의 사항

- 전체적인 Terminal UI 구성은 영어를 기본으로 구성한다. 
- 단, 한국어 입력과 한국어 출력을 지원해야 한다.
- 폰트와 글자 색이 있을 시, 검은 터미널 배경과 혼돈되지 않도록 어두운 계열은 사용하지 않는다.
- 글자와 박스의 구분이 필요한 경우, 비슷한 색을 사용하지 않는다. (ex. 파란색 글자, 하늘색 박스 -> 금지 대상)
- TUI 문구와 선택창, 입출력은 사람인 사용자가 쉽게 알아볼 수 있도록 간결한 문구, 명확한 구분과 공백으로 구성한다. 

### Useful skills

`ui-ux-pro-max` skill 내용 참고하여 현재 프로젝트에 연관된 skill 적용
