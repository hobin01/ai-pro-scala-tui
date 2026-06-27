package app

import "strings"

func (m *Model) moveSettings(delta int) {
	if m.settingsConfirm {
		m.confirmCursor = clamp(m.confirmCursor+delta, 0, 2)
		return
	}
	if !m.restarting {
		m.settingsCursor = clamp(m.settingsCursor+delta, 0, len(settingsRows(m))-1)
	}
}

func (m *Model) enterSettings() {
	if m.restarting {
		return
	}
	if m.settingsConfirm {
		m.enterRestartConfirm()
		return
	}
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
	if m.settingsCursor == m.applySettingsRow() {
		if m.pendingRestart > 0 {
			m.settingsConfirm = true
			m.confirmCursor = 0
		}
		return
	}
	if m.settingsCursor == m.backSettingsRow() {
		if m.pendingRestart > 0 {
			m.settingsConfirm = true
			m.confirmCursor = 0
			return
		}
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
		m.markRestartPending(0)
	case 1:
		m.settings.splunkURL = value
		m.markRestartPending(1)
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
		m.markRestartPending(9)
	case 10:
		m.settings.resultIndex = value
	}
	m.editingSetting = false
	m.editValue = ""
	m.notice = "Setting saved."
}

func (m *Model) markRestartPending(settingsCursor int) {
	switch settingsCursor {
	case 0:
		m.elasticPending = true
	case 1:
		m.splunkPending = true
	case 9:
		m.openSearchPending = true
	}
	m.pendingRestart = m.pendingRestartCount()
}

func (m *Model) pendingRestartCount() int {
	count := 0
	if m.elasticPending {
		count++
	}
	if m.splunkPending {
		count++
	}
	if m.openSearchPending {
		count++
	}
	return count
}

func (m *Model) pendingRestartTargets() []string {
	targets := []string{}
	if m.elasticPending {
		targets = append(targets, "elasticsearch-conn")
	}
	if m.splunkPending {
		targets = append(targets, "splunk-conn")
	}
	if m.openSearchPending {
		targets = append(targets, "opensearch")
	}
	return targets
}

func (m *Model) enterRestartConfirm() {
	switch m.confirmCursor {
	case 0:
		m.settingsConfirm = false
		m.restarting = true
		m.restartComplete = false
		m.notice = ""
	case 1:
		m.settingsConfirm = false
		m.notice = "Keep editing pending settings."
	case 2:
		m.settingsConfirm = false
		m.route = routeMain
		m.notice = "Leave without restart - pending changes will apply later."
	}
}
