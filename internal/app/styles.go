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

// renderStatus는 header status 값에 상태별 색을 입힌다.
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

// renderInput은 하단 입력 줄에 입력 전용 색을 입힌다.
func renderInput(value string) string {
	return inputStyle.Render(value)
}

// renderCursor는 선택 cursor glyph를 강조색으로 표시한다.
func renderCursor(value string) string {
	return accentStyle.Bold(true).Render(value)
}

// renderSuccess는 성공 메시지에 녹색 계열 색을 입힌다.
func renderSuccess(value string) string {
	return successStyle.Render(value)
}

// renderWarning는 확인이 필요한 문구에 노란색 계열 색을 입힌다.
func renderWarning(value string) string {
	return warningStyle.Render(value)
}
