package app

import (
	"strings"

	"charm.land/lipgloss/v2"
)

const (
	ansiBrightBlue   = "45"
	ansiBrightCyan   = "51"
	ansiSoftBlue     = "81"
	ansiBrightGreen  = "82"
	ansiBrightYellow = "226"
	ansiBrightRed    = "203"
)

var (
	accentStyle  = lipgloss.NewStyle().Foreground(lipgloss.Color(ansiBrightCyan))
	borderStyle  = lipgloss.NewStyle().Foreground(lipgloss.Color(ansiBrightBlue))
	errorStyle   = lipgloss.NewStyle().Foreground(lipgloss.Color(ansiBrightRed))
	footerStyle  = lipgloss.NewStyle().Foreground(lipgloss.Color(ansiSoftBlue))
	inputStyle   = lipgloss.NewStyle().Foreground(lipgloss.Color(ansiSoftBlue))
	successStyle = lipgloss.NewStyle().Foreground(lipgloss.Color(ansiBrightGreen))
	statusStyle  = lipgloss.NewStyle().Bold(true)
	titleStyle   = lipgloss.NewStyle().Foreground(lipgloss.Color(ansiBrightCyan)).Bold(true)
	warningStyle = lipgloss.NewStyle().Foreground(lipgloss.Color(ansiBrightYellow))
)

func renderStatus(value string) string {
	label := strings.TrimSpace(value)
	style := statusStyle.Foreground(lipgloss.Color(ansiBrightCyan))
	switch {
	case strings.HasPrefix(label, "running:"), label == "fetching…":
		style = statusStyle.Foreground(lipgloss.Color(ansiBrightBlue))
	case label == "idle", strings.Contains(label, "pending"), label == "needs input":
		style = statusStyle.Foreground(lipgloss.Color(ansiBrightYellow))
	case label == "done":
		style = statusStyle.Foreground(lipgloss.Color(ansiBrightGreen))
	}
	return style.Render(value)
}

func renderInput(value string) string {
	return inputStyle.Render(value)
}

func renderCursor(value string) string {
	return accentStyle.Bold(true).Render(value)
}

func renderSuccess(value string) string {
	return successStyle.Render(value)
}

func renderWarning(value string) string {
	return warningStyle.Render(value)
}
