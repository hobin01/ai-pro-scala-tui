package app

import "strings"

func (m *Model) moveSettings(delta int) {
	m.settingsCursor = clamp(m.settingsCursor+delta, 0, len(settingsRows(m))-1)
}

func (m *Model) enterSettings() {
	if m.settingsCursor == 6 {
		m.notice = "API key is read-only and must stay in .env."
		return
	}
	if m.settingsCursor == 7 || m.settingsCursor == 8 {
		m.notice = "Source index rows are read-only demo fixtures."
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
	case 9:
		return m.settings.openSearchURL
	case 10:
		return m.settings.resultIndex
	default:
		return ""
	}
}

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
	case 9:
		m.settings.openSearchURL = value
	case 10:
		m.settings.resultIndex = value
	}
	m.editingSetting = false
	m.editValue = ""
	m.notice = "Setting saved."
}
