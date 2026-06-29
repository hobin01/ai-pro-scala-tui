package app

import "strings"

// moveSettings는 관련 동작을 처리한다.
func (m *Model) moveSettings(delta int) {
	m.settingsCursor = clamp(m.settingsCursor+delta, 0, len(settingsRows(m))-1)
}

// enterSettings는 관련 동작을 처리한다.
func (m *Model) enterSettings() {
	if m.settingsCursor == 6 {
		m.notice = "API key is read-only and must stay in .env."
		return
	}
	if m.settingsCursor >= 11 && m.settingsCursor <= 13 {
		m.notice = "Web console URLs are read-only display links."
		return
	}
	if m.settingsCursor == m.backSettingsRow() {
		m.route = routeMain
		return
	}
	m.editingSetting = true
	m.editValue = m.currentSettingValue()
}

// updateSettingEdit는 관련 동작을 처리한다.
func (m *Model) updateSettingEdit(key string) {
	switch key {
	case "enter":
		m.saveSetting()
	case "esc", "up", "down":
		m.editingSetting = false
		m.editValue = ""
	case "backspace":
		m.editValue = trimLastRune(m.editValue)
	default:
		if isText(key) || key == "space" {
			m.editValue += displayKey(key)
		}
	}
}

// currentSettingValue는 관련 동작을 처리한다.
func (m *Model) currentSettingValue() string {
	switch m.settingsCursor {
	case 0:
		return m.settings.elasticsearchURL
	case 1:
		return m.settings.splunkURL
	case 2:
		return m.settings.orchestratorModel
	case 3:
		return m.settings.profilerModel
	case 4:
		return m.settings.normalizationModel
	case 5:
		return m.settings.validatorModel
	case 7:
		return strings.Join(m.settings.elasticsearchIndices, ", ")
	case 8:
		return strings.Join(m.settings.splunkIndices, ", ")
	case 9:
		return m.settings.openSearchURL
	case 10:
		return m.settings.resultIndex
	default:
		return ""
	}
}

// saveSetting는 관련 동작을 처리한다.
func (m *Model) saveSetting() {
	value := strings.TrimSpace(m.editValue)
	if value == "" {
		m.notice = "Setting cannot be empty."
		return
	}
	switch m.settingsCursor {
	case 0:
		m.settings.elasticsearchURL = value
	case 1:
		m.settings.splunkURL = value
	case 2:
		m.settings.orchestratorModel = value
		m.monitoring = defaultMonitoring(m.settings)
	case 3:
		m.settings.profilerModel = value
		m.monitoring = defaultMonitoring(m.settings)
	case 4:
		m.settings.normalizationModel = value
		m.monitoring = defaultMonitoring(m.settings)
	case 5:
		m.settings.validatorModel = value
		m.monitoring = defaultMonitoring(m.settings)
	case 7:
		indices := parseCSV(value)
		if len(indices) == 0 {
			m.notice = "Setting cannot be empty."
			return
		}
		m.settings.elasticsearchIndices = indices
		m.sources = sourcesFromSettings(m.settings)
		m.selected = reconcileSelected(m.selected, m.sources)
	case 8:
		indices := parseCSV(value)
		if len(indices) == 0 {
			m.notice = "Setting cannot be empty."
			return
		}
		m.settings.splunkIndices = indices
		m.sources = sourcesFromSettings(m.settings)
		m.selected = reconcileSelected(m.selected, m.sources)
	case 9:
		m.settings.openSearchURL = value
	case 10:
		m.settings.resultIndex = value
	}
	if key, backendValue, ok := m.currentSettingBackendValue(value); ok {
		m.queueBackendAction(BackendAction{
			Method: "settings.set",
			Params: SettingsSetParams{Key: key, Value: backendValue},
		})
	}
	m.editingSetting = false
	m.editValue = ""
	m.notice = "Setting saved."
}

// currentSettingBackendValue는 관련 동작을 처리한다.
func (m *Model) currentSettingBackendValue(value string) (string, any, bool) {
	switch m.settingsCursor {
	case 0:
		return "source.elasticsearch.url", value, true
	case 1:
		return "source.splunk.url", value, true
	case 2:
		return "agent.orchestrator.model", value, true
	case 3:
		return "agent.schema_profiler.model", value, true
	case 4:
		return "agent.normalization.model", value, true
	case 5:
		return "agent.validator.model", value, true
	case 7:
		return "source.elasticsearch.indices", parseCSV(value), true
	case 8:
		return "source.splunk.indices", parseCSV(value), true
	case 9:
		return "output.opensearch.url", value, true
	case 10:
		return "output.opensearch.index", value, true
	default:
		return "", nil, false
	}
}
