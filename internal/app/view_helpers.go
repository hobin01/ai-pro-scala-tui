package app

import (
	"fmt"
	"strings"
)

func renderRestartConfirm(b *strings.Builder, confirmCursor int, pendingRestart int) {
	if pendingRestart == 1 {
		fmt.Fprintln(b, "1 change needs a restart to take effect:")
	} else {
		fmt.Fprintf(b, "%d changes need a restart to take effect:\n", pendingRestart)
	}
	fmt.Fprintln(b, "Restart the affected containers now?")
	options := []string{"Restart now", "Keep editing", "Leave without restart"}
	for i, option := range options {
		fmt.Fprintf(b, "%s %s\n", cursor(i == confirmCursor), option)
	}
}

func renderRestarting(b *strings.Builder, targets []string) {
	fmt.Fprintln(b, "restarting...")
	fmt.Fprintln(b, "Applying changes - restarting affected containers...")
	fmt.Fprintln(b, "settings saved")
	for _, target := range targets {
		fmt.Fprintf(b, "restart: %s\n", target)
	}
	fmt.Fprintln(b, "Navigation is disabled until restart completes.")
}

func renderHelp(b *strings.Builder) {
	fmt.Fprintln(b, "\nCommands")
	fmt.Fprintln(b, "/source-selection  /data-samples  /agent-workflow")
	fmt.Fprintln(b, "/lineage-viewer    /agent-monitoring  /settings  /main")
}

func renderBlock(b *strings.Builder, title string, lines []string) {
	fmt.Fprintf(b, "%s\n", title)
	for _, line := range lines {
		fmt.Fprintf(b, "  %s\n", line)
	}
	fmt.Fprintln(b)
}

func cursor(active bool) string {
	if active {
		return renderCursor("▸")
	}
	return " "
}

func fmtInt(value int) string {
	return fmt.Sprintf("%d", value)
}

func noticeStyle(value string) string {
	if strings.HasPrefix(value, "✗") || strings.Contains(value, "Select at least") || strings.Contains(value, "read-only") {
		return errorStyle.Render(value)
	}
	return accentStyle.Render(value)
}

func (m *Model) selectedSourceSummary() string {
	selected := m.selectedSources()
	if len(selected) == 0 {
		return "0"
	}
	return fmt.Sprintf("%d · %s", len(selected), selectedKindSummary(selected))
}

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

func totalDocs(sources []source) int {
	total := 0
	for _, source := range sources {
		total += source.docs
	}
	return total
}

func limit(values []string, max int) []string {
	if len(values) <= max {
		return values
	}
	return values[:max]
}

func tail(values []string, max int) []string {
	if len(values) <= max {
		return values
	}
	return values[len(values)-max:]
}
