package app

import (
	"strings"
)

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
	default:
		if m.input == "" {
			return "> _"
		}
		return "> " + m.input
	}
}

func settingsRows(m *Model) []string {
	rows := []string{
		"Elasticsearch URL        " + m.settings.elasticsearchURL,
		"Splunk URL               " + m.settings.splunkURL,
		"Orchestrator model       " + m.settings.orchestratorModel,
		"Schema Profiler model    " + m.settings.profilerModel,
		"Normalization model      " + m.settings.normalizationModel,
		"Validator model          " + m.settings.validatorModel,
		"OpenAI API key           " + m.settings.apiKeyMasked + " (read-only · .env)",
		"Elasticsearch indices    logs-2024, firewall-idx",
		"Splunk indices           main, security",
		"OpenSearch URL           " + m.settings.openSearchURL,
		"Result index             " + m.settings.resultIndex,
		"Kibana                   " + m.settings.kibanaURL,
		"Splunk Web               " + m.settings.splunkWebURL,
		"OpenSearch Dashboards    " + m.settings.openSearchDash,
	}
	return append(rows, "Back to main")
}

func (m *Model) backSettingsRow() int {
	return len(settingsRows(m)) - 1
}
