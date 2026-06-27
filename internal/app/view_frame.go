package app

import (
	"strings"

	"charm.land/lipgloss/v2"
)

const minFrameWidth = 60
const minFrameHeight = 12

func (m *Model) renderFrame(content string, notice string, input string, footer string) string {
	width := m.width
	if width < minFrameWidth {
		width = minFrameWidth
	}
	height := m.height
	if height < minFrameHeight {
		height = minFrameHeight
	}
	innerWidth := width - 4
	contentRows := strings.Split(strings.TrimRight(content, "\n"), "\n")
	if len(contentRows) == 1 && contentRows[0] == "" {
		contentRows = nil
	}
	reserved := 4
	if notice != "" {
		reserved++
	}
	contentHeight := height - reserved
	if contentHeight < 1 {
		contentHeight = 1
	}

	lines := make([]string, 0, height)
	lines = append(lines, m.frameTop(width))
	for i := 0; i < contentHeight; i++ {
		row := ""
		if i < len(contentRows) {
			row = contentRows[i]
		}
		lines = append(lines, frameRow(row, innerWidth))
	}
	lines = append(lines, frameSeparator(width))
	if notice != "" {
		lines = append(lines, frameRow(notice, innerWidth))
	}
	lines = append(lines, frameRow(input, innerWidth))
	lines = append(lines, frameBottom(footer, width))
	return strings.Join(lines, "\n")
}

func (m *Model) footerLine() string {
	switch m.route {
	case routeSources:
		return "↑↓ move · space toggle · enter confirm · /help"
	case routeSamples:
		return "←→ index · ↑↓ scroll · enter continue · /help"
	case routeWorkflow:
		if m.workflowGate {
			return "↑↓ choose · enter select · /help · ctrl+c quit"
		}
		return "enter back · /help · ctrl+c quit"
	case routeFeedback:
		return "enter select · agents stream · ctrl+c quit"
	case routeLineage:
		return "enter lookup/back · /help · ctrl+c quit"
	case routeMonitoring:
		return "←/→ scope · enter back · /help · ctrl+c quit"
	case routeSettings:
		return "↑↓ move · enter edit/select · /help · ctrl+c quit"
	default:
		return "↑↓ move · enter select · /help · ctrl+c quit"
	}
}

func (m *Model) frameTop(width int) string {
	return frameHeaderLine(m.headerContext(), m.headerStatus(), width)
}

func (m *Model) headerContext() string {
	switch m.route {
	case routeMain:
		return "Security Canonical Alignment & Lineage Automation"
	case routeSources:
		return "Select data sources"
	case routeSamples:
		return "Data samples"
	case routeWorkflow:
		return "Agent workflow graph"
	case routeFeedback:
		if m.pipelineRunning {
			return "Pipeline running"
		}
		if m.feedbackWaiting {
			return "Human feedback needed"
		}
		if m.pipelineDone {
			return "Pipeline complete"
		}
		return "Human feedback"
	case routeLineage:
		return "Lineage viewer"
	case routeMonitoring:
		return "Agent monitoring"
	case routeSettings:
		return "Settings"
	default:
		return "Security Canonical Alignment & Lineage Automation"
	}
}

func (m *Model) headerStatus() string {
	switch {
	case m.pipelineRunning:
		return "running: Normalization"
	case m.restarting:
		return "running: restart..."
	case m.route == routeSources:
		return "selected: " + fmtInt(len(m.selectedSources()))
	case m.route == routeSamples && m.sampleLoading:
		return "fetching…"
	case m.route == routeSamples:
		total := len(m.selectedSources())
		if total == 0 {
			return "[0/0]"
		}
		page := clamp(m.samplePage, 0, total-1)
		source := m.selectedSources()[page]
		return "[" + fmtInt(page+1) + "/" + fmtInt(total) + "] " + source.kind + " · " + source.index
	case m.route == routeWorkflow && m.workflowGate:
		return "ready · sources: " + fmtInt(len(m.selectedSources()))
	case m.route == routeFeedback && m.feedbackWaiting:
		return "needs input"
	case m.route == routeFeedback && m.pipelineDone:
		return "done"
	case m.route == routeLineage && m.lineageLoading:
		return "running: lineage..."
	case m.route == routeSettings && m.pendingRestart > 0:
		return fmtInt(m.pendingRestart) + " changes pending restart"
	case m.route == routeMonitoring:
		return "scope: " + defaultMonitoring(m.settings)[clamp(m.monitoringScope, 0, 2)].scope
	default:
		return "idle"
	}
}

func frameBottom(footer string, width int) string {
	return frameTitleLine("└", "┘", footer, width)
}

func frameTitleLine(left string, right string, text string, width int) string {
	bodyWidth := width - 2
	label := "─ " + text + " "
	if lipgloss.Width(label) > bodyWidth {
		label = fitLine(label, bodyWidth)
	}
	padding := bodyWidth - lipgloss.Width(label)
	return left + label + strings.Repeat("─", padding) + right
}

func frameHeaderLine(context string, status string, width int) string {
	bodyWidth := width - 2
	prefix := "─ SCALA · " + context + " "
	suffix := " " + status + " ─"
	if lipgloss.Width(prefix)+lipgloss.Width(suffix) > bodyWidth {
		prefix = fitLine(prefix, bodyWidth-lipgloss.Width(suffix))
	}
	padding := bodyWidth - lipgloss.Width(prefix) - lipgloss.Width(suffix)
	if padding < 0 {
		padding = 0
	}
	return "┌" + prefix + strings.Repeat("─", padding) + suffix + "┐"
}

func frameSeparator(width int) string {
	return "├" + strings.Repeat("─", width-2) + "┤"
}

func frameRow(value string, width int) string {
	return "│ " + fitLine(value, width) + " │"
}

func fitLine(value string, width int) string {
	if width <= 0 {
		return ""
	}
	value = strings.ReplaceAll(value, "\t", "  ")
	for lipgloss.Width(value) > width {
		runes := []rune(value)
		if len(runes) == 0 {
			return ""
		}
		value = string(runes[:len(runes)-1])
	}
	return value + strings.Repeat(" ", width-lipgloss.Width(value))
}
