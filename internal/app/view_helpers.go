package app

import (
	"fmt"
	"strings"
)

// renderHelp는 slash command 도움말 블록을 본문에 붙인다.
func renderHelp(b *strings.Builder) {
	fmt.Fprintln(b, "\nCommands")
	fmt.Fprintln(b, "/source-selection  /data-samples  /agent-workflow")
	fmt.Fprintln(b, "/lineage-viewer    /agent-monitoring  /settings  /main")
}

// renderBlock는 lineage 문서 섹션을 제목과 들여쓴 줄로 출력한다.
func renderBlock(b *strings.Builder, title string, lines []string) {
	fmt.Fprintf(b, "%s\n", title)
	for _, line := range lines {
		fmt.Fprintf(b, "  %s\n", line)
	}
	fmt.Fprintln(b)
}

// cursor는 선택된 행에만 강조 cursor glyph를 표시한다.
func cursor(active bool) string {
	if active {
		return renderCursor("▸")
	}
	return " "
}

// fmtInt는 숫자를 TUI label에 넣을 문자열로 바꾼다.
func fmtInt(value int) string {
	return fmt.Sprintf("%d", value)
}

// noticeStyle은 notice 문구 성격에 맞춰 오류, 성공, 강조 색을 고른다.
func noticeStyle(value string) string {
	if strings.HasPrefix(value, "✗") || strings.Contains(value, "Select at least") || strings.Contains(value, "read-only") {
		return errorStyle.Render(value)
	}
	if strings.HasPrefix(value, "Copied") || strings.HasPrefix(value, "Settings") || strings.Contains(value, "loaded") {
		return renderSuccess(value)
	}
	return accentStyle.Render(value)
}

// selectedSourceSummary는 선택 source 개수와 종류 요약을 만든다.
func (m *Model) selectedSourceSummary() string {
	selected := m.selectedSources()
	if len(selected) == 0 {
		return "0"
	}
	return fmt.Sprintf("%d · %s", len(selected), selectedKindSummary(selected))
}

// selectedKindSummary는 선택 source를 종류별 개수 문자열로 요약한다.
func selectedKindSummary(selected []source) string {
	counts := map[string]int{}
	kinds := []string{}
	for _, source := range selected {
		if counts[source.kind] == 0 {
			kinds = append(kinds, source.kind)
		}
		counts[source.kind]++
	}
	parts := make([]string, 0, len(kinds))
	for _, kind := range kinds {
		parts = append(parts, fmt.Sprintf("%s ×%d", kind, counts[kind]))
	}
	return strings.Join(parts, ", ")
}

// agentActivity는 mock monitoring row의 최근 활동 문구를 채운다.
func agentActivity(name string) string {
	switch name {
	case "Orchestrator":
		return "showed final result"
	case "Schema Profiler":
		return "profiled fields"
	case "Normalization":
		return "generated rules"
	case "Validator":
		return "validated run"
	case "Load":
		return "loaded docs"
	case "Caching":
		return "cached mappings"
	case "Lineage":
		return "recorded lineage"
	default:
		return "-"
	}
}

// mainItemDescription은 main menu 항목의 보조 설명을 반환한다.
func mainItemDescription(item string) string {
	switch item {
	case "Collect & Normalize":
		return "run the normalization pipeline"
	case "View Results":
		return "lineage · workflow graph · monitoring"
	case "Settings":
		return "sources · indices · models"
	default:
		return ""
	}
}

// mainResultCommand는 View Results 하위 항목의 slash command를 반환한다.
func mainResultCommand(item string) string {
	switch item {
	case "Lineage Viewer":
		return "/lineage-viewer"
	case "Agent Workflow Graph":
		return "/agent-workflow"
	case "Agent Monitoring":
		return "/agent-monitoring"
	default:
		return ""
	}
}

// totalDocs는 선택 source들의 문서 수 합계를 계산한다.
func totalDocs(sources []source) int {
	total := 0
	for _, source := range sources {
		total += source.docs
	}
	return total
}

// limit는 앞에서부터 최대 개수만 남겨 preview 길이를 제한한다.
func limit(values []string, max int) []string {
	if len(values) <= max {
		return values
	}
	return values[:max]
}

// tail은 stream에서 마지막 최대 개수만 남겨 최근 로그를 보여준다.
func tail(values []string, max int) []string {
	if len(values) <= max {
		return values
	}
	return values[len(values)-max:]
}
