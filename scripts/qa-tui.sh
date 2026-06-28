#!/usr/bin/env sh
set -eu

session="${1:-ulw-qa-task-11}"
evidence_dir="${2:-.omo/ulw-loop/evidence}"
mkdir -p "$evidence_dir"
if command -v tmux >/dev/null 2>&1; then
	tmux kill-session -t "$session" 2>/dev/null || true
	tmux new-session -d -s "$session" 'TERM=xterm-256color SCALA_TUI_MOCK=1 ./bin/scala-tui'
	sleep 1
	tmux send-keys -t "$session" Enter Space Down Space Enter
	sleep 1
	tmux send-keys -t "$session" Enter Enter
	sleep 2
	tmux send-keys -t "$session" Enter
	sleep 2
	tmux capture-pane -pt "$session" -S -200 > "$evidence_dir/tui-happy-path.txt"
	tmux kill-session -t "$session"
	exit 0
fi

if command -v expect >/dev/null 2>&1; then
	expect <<EOF
log_file -noappend "$evidence_dir/tui-happy-path.txt"
set timeout 10
spawn env TERM=xterm-256color SCALA_TUI_MOCK=1 ./bin/scala-tui
after 1000
send "\r"
after 150
send " "
after 150
send "\033\[B"
after 150
send " "
after 150
send "\r"
after 900
send "\r"
after 150
send "\r"
after 2200
send "\r"
after 2200
send "\003"
expect eof
EOF
	if ! grep -a 'SCALA' "$evidence_dir/tui-happy-path.txt" >/dev/null 2>&1; then
		case "$evidence_dir" in
			/*) transcript="$evidence_dir/tui-scripted-flow.txt" ;;
			*) transcript="$PWD/$evidence_dir/tui-scripted-flow.txt" ;;
		esac
		{
			echo
			echo "expect pseudo-tty did not expose rendered text in this headless environment."
			echo "See tui-scripted-flow.txt and tui-scripted-flow-test.txt for deterministic screen transcript evidence."
		} >> "$evidence_dir/tui-happy-path.txt"
		SCALA_TUI_TRANSCRIPT="$transcript" go test ./internal/app -run TestScriptedFullFlowTranscript -v > "$evidence_dir/tui-scripted-flow-test.txt" 2>&1
	fi
	exit 0
fi

echo "neither tmux nor expect is installed" > "$evidence_dir/tui-happy-path.txt"
exit 1
