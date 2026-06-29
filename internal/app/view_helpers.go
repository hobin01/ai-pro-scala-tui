package app

import (
	"fmt"
	"strings"
)

// renderHelp는 화면 문자열을 렌더링한다.
func renderHelp(b *strings.Builder) {
	fmt.Fprintln(b, "\nCommands")
	fmt.Fprintln(b, "/source-selection  /data-samples  /agent-workflow")
	fmt.Fprintln(b, "/lineage-viewer    /agent-monitoring  /settings  /main")
}

// renderBlock는 화면 문자열을 렌더링한다.
func renderBlock(b *strings.Builder, title string, lines []string) {
	fmt.Fprintf(b, "%s\n", title)
	for _, line := range lines {
		fmt.Fprintf(b, "  %s\n", line)
	}
	fmt.Fprintln(b)
}

// cursor는 관련 동작을 처리한다.
func cursor(active bool) string {
	if active {
		return renderCursor("▸")
	}
	return " "
}

// fmtInt는 관련 동작을 처리한다.
func fmtInt(value int) string {
	return fmt.Sprintf("%d", value)
}

// noticeStyle는 관련 동작을 처리한다.
func noticeStyle(value string) string {
	if strings.HasPrefix(value, "✗") || strings.Contains(value, "Select at least") || strings.Contains(value, "read-only") {
		return errorStyle.Render(value)
	}
	if strings.HasPrefix(value, "Copied") || strings.HasPrefix(value, "Settings") || strings.Contains(value, "loaded") {
		return renderSuccess(value)
	}
	return accentStyle.Render(value)
}

// selectedSourceSummary는 관련 동작을 처리한다.
func (m *Model) selectedSourceSummary() string {
	selected := m.selectedSources()
	if len(selected) == 0 {
		return "0"
	}
	return fmt.Sprintf("%d · %s", len(selected), selectedKindSummary(selected))
}

// selectedKindSummary는 관련 동작을 처리한다.
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

// agentActivity는 관련 동작을 처리한다.
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

// mainItemDescription는 관련 동작을 처리한다.
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

// mainResultCommand는 관련 동작을 처리한다.
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

// totalDocs는 관련 동작을 처리한다.
func totalDocs(sources []source) int {
	total := 0
	for _, source := range sources {
		total += source.docs
	}
	return total
}

// limit는 관련 동작을 처리한다.
func limit(values []string, max int) []string {
	if len(values) <= max {
		return values
	}
	return values[:max]
}

// tail는 관련 동작을 처리한다.
func tail(values []string, max int) []string {
	if len(values) <= max {
		return values
	}
	return values[len(values)-max:]
}
