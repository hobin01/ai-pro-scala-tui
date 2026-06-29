package app

import (
	"strings"

	"charm.land/lipgloss/v2"
)

const minFrameWidth = 60
const minFrameHeight = 12

// renderFrame는 본문, notice, input, footer를 전체 터미널 frame에 배치한다.
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
	contentRows := wrapRows(
		strings.Split(strings.TrimRight(content, "\n"), "\n"),
		innerWidth,
	)
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
	if m.route == routeWorkflow && !m.workflowGate {
		maxOffset := len(contentRows) - contentHeight
		offset := clamp(m.workflowScroll, 0, maxOffset)
		contentRows = contentRows[offset:]
	} else if m.route == routeLineage || m.route == routeMonitoring {
		maxOffset := len(contentRows) - contentHeight
		m.contentScroll = clamp(m.contentScroll, 0, maxOffset)
		contentRows = contentRows[m.contentScroll:]
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
	lines = append(lines, frameInputRow(input, innerWidth))
	lines = append(lines, frameBottom(footer, width))
	return strings.Join(lines, "\n")
}

// footerLine은 현재 route에서 사용할 키 안내 문구를 고른다.
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
		return "↑↓ scroll · enter back · /help · ctrl+c quit"
	case routeFeedback:
		return "enter select · agents stream · ctrl+c quit"
	case routeLineage:
		return "↑↓ scroll · ctrl+v paste · ctrl+y copy _id · enter lookup/back"
	case routeMonitoring:
		return "←/→ scope · ↑↓ scroll · enter back · /help · ctrl+c quit"
	case routeSettings:
		return "↑↓ move · enter edit/select · /help · ctrl+c quit"
	default:
		return "↑↓ move · enter select · /help · ctrl+c quit"
	}
}

// frameTop은 현재 context와 status를 넣은 상단 border 줄을 만든다.
func (m *Model) frameTop(width int) string {
	return frameHeaderLine(m.headerContext(), m.headerStatus(), width)
}

// headerContext는 route별 header title 문구를 반환한다.
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

// headerStatus는 route별 현재 상태 badge 문구를 반환한다.
func (m *Model) headerStatus() string {
	switch {
	case m.pipelineRunning:
		return "running: Normalization"
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
	case m.route == routeMonitoring:
		return "scope: " + defaultMonitoring(m.settings)[clamp(m.monitoringScope, 0, 2)].scope
	default:
		return "idle"
	}
}

// frameBottom은 footer 문구를 포함한 하단 border 줄을 만든다.
func frameBottom(footer string, width int) string {
	return frameTitleLine("└", "┘", footer, width)
}

// frameTitleLine은 좌우 모서리와 label을 폭에 맞춰 한 줄로 조립한다.
func frameTitleLine(left string, right string, text string, width int) string {
	bodyWidth := width - 2
	label := "─ " + text + " "
	if lipgloss.Width(label) > bodyWidth {
		label = fitLine(label, bodyWidth)
	}
	padding := bodyWidth - lipgloss.Width(label)
	return borderStyle.Render(left) +
		footerStyle.Render(label) +
		borderStyle.Render(strings.Repeat("─", padding)+right)
}

// frameHeaderLine은 SCALA title과 status badge가 들어간 header 줄을 만든다.
func frameHeaderLine(context string, status string, width int) string {
	bodyWidth := width - 2
	prefix := "─ SCALA · " + context + " "
	rawSuffix := " " + status + " ─"
	if lipgloss.Width(prefix)+lipgloss.Width(rawSuffix) > bodyWidth {
		prefix = fitLine(prefix, bodyWidth-lipgloss.Width(rawSuffix))
	}
	padding := bodyWidth - lipgloss.Width(prefix) - lipgloss.Width(rawSuffix)
	if padding < 0 {
		padding = 0
	}
	return borderStyle.Render("┌") +
		titleStyle.Render(prefix) +
		borderStyle.Render(strings.Repeat("─", padding)) +
		" " + renderStatus(status) + borderStyle.Render(" ─") +
		borderStyle.Render("┐")
}

// frameSeparator는 content와 input 영역을 나누는 border 줄을 만든다.
func frameSeparator(width int) string {
	return borderStyle.Render("├" + strings.Repeat("─", width-2) + "┤")
}

// frameRow는 본문 한 줄을 frame 폭에 맞춰 감싼다.
func frameRow(value string, width int) string {
	return borderStyle.Render("│") + " " + fitLine(value, width) + " " + borderStyle.Render("│")
}

// frameInputRow는 입력 줄에 색상 스타일을 입혀 frame 안에 배치한다.
func frameInputRow(value string, width int) string {
	return borderStyle.Render("│") + " " + renderInput(fitLine(value, width)) + " " + borderStyle.Render("│")
}

// fitLine은 표시 폭을 넘지 않도록 문자열을 자르고 padding을 채운다.
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

// wrapRows는 긴 본문 줄을 lipgloss 표시 폭 기준으로 접는다.
func wrapRows(rows []string, width int) []string {
	if width <= 0 {
		return []string{""}
	}
	wrapped := make([]string, 0, len(rows))
	for _, row := range rows {
		row = strings.ReplaceAll(row, "\t", "  ")
		parts := strings.Split(lipgloss.Wrap(row, width, ""), "\n")
		wrapped = append(wrapped, parts...)
	}
	return wrapped
}
