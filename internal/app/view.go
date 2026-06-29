package app

import (
	"strings"
)

// View는 현재 route 본문을 frame, notice, input, footer와 합성한다.
func (m *Model) View() string {
	var content strings.Builder
	switch m.route {
	case routeMain:
		m.renderMain(&content)
	case routeSources:
		m.renderSources(&content)
	case routeSamples:
		m.renderSamples(&content)
	case routeWorkflow:
		m.renderWorkflow(&content)
	case routeFeedback:
		m.renderFeedback(&content)
	case routeLineage:
		m.renderLineage(&content)
	case routeMonitoring:
		m.renderMonitoring(&content)
	case routeSettings:
		m.renderSettings(&content)
	}
	if m.showHelp {
		renderHelp(&content)
	}
	notice := ""
	if m.notice != "" {
		notice = noticeStyle(m.notice)
	}
	return m.renderFrame(content.String(), notice, m.inputLine(), m.footerLine())
}

// inputLine은 현재 route와 edit 상태에 맞는 하단 입력 줄을 만든다.
func (m *Model) inputLine() string {
	switch {
	case m.pipelineRunning:
		return "⌧ agent running — input disabled"
	case m.feedbackComment:
		return "Feedback input enabled: " + m.input
	case m.feedbackWaiting:
		return "Feedback input enabled: choose an option"
	case m.editingSetting:
		return "edit: " + m.editValue
	case m.route == routeLineage:
		if m.input == "" {
			return "_id> _"
		}
		return "_id> " + m.input
	case m.route == routeMonitoring:
		return "⌧ read-only view"
	case m.route == routeWorkflow && !m.workflowGate:
		return "enter to return to main."
	default:
		if m.input == "" {
			return "> _"
		}
		return "> " + m.input
	}
}

// settingsRows는 Settings 화면에 표시할 행 목록을 현재 설정에서 만든다.
func settingsRows(m *Model) []string {
	rows := []string{
		"Elasticsearch URL        " + m.settings.elasticsearchURL,
		"Splunk URL               " + m.settings.splunkURL,
		"Orchestrator model       " + m.settings.orchestratorModel,
		"Schema Profiler model    " + m.settings.profilerModel,
		"Normalization model      " + m.settings.normalizationModel,
		"Validator model          " + m.settings.validatorModel,
		"OpenAI API key           " + m.settings.apiKeyMasked + " (read-only · .env)",
		"Elasticsearch indices    " + strings.Join(m.settings.elasticsearchIndices, ", "),
		"Splunk indices           " + strings.Join(m.settings.splunkIndices, ", "),
		"OpenSearch URL           " + m.settings.openSearchURL,
		"Result index             " + m.settings.resultIndex,
		"Kibana                   " + m.settings.kibanaURL,
		"Splunk Web               " + m.settings.splunkWebURL,
		"OpenSearch Dashboards    " + m.settings.openSearchDash,
	}
	return append(rows, "Back to main")
}

// backSettingsRow는 Settings 화면의 마지막 Back 행 index를 반환한다.
func (m *Model) backSettingsRow() int {
	return len(settingsRows(m)) - 1
}
