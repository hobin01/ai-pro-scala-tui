package app

import "strings"

func (m *Model) enter() {
	if m.input != "" {
		m.submitInput()
		return
	}
	switch m.route {
	case routeMain:
		m.enterMain()
	case routeSources:
		m.enterSources()
	case routeSamples:
		m.enterSamples()
	case routeWorkflow:
		m.enterWorkflow()
	case routeFeedback:
		m.enterFeedback()
	case routeLineage:
		m.enterLineage()
	case routeMonitoring:
		m.route = routeMain
	case routeSettings:
		m.enterSettings()
	}
}

func (m *Model) enterSources() {
	if len(m.sources) == 0 {
		m.route = routeSettings
		m.settingsCursor = 0
		return
	}
	if len(m.selectedSources()) < 2 {
		m.notice = "Select at least 2 sources before continuing."
		return
	}
	m.route = routeSamples
	m.samplePage = 0
	m.sampleLoading = true
	m.notice = ""
}

func (m *Model) enterSamples() {
	if m.sampleLoading {
		return
	}
	if source, ok := m.currentSampleSource(); ok && source.fetchError != "" {
		m.enterSampleError()
		return
	}
	m.route = routeWorkflow
	m.workflowGate = true
	m.workflowCursor = 0
	m.notice = ""
}

func (m *Model) enterWorkflow() {
	if m.workflowGate && m.workflowCursor == 1 {
		m.route = routeSamples
		return
	}
	if m.workflowGate {
		m.startPipeline()
		return
	}
	m.route = routeMain
}

func (m *Model) enterLineage() {
	if m.lineageLoading {
		return
	}
	if m.lineageResult != nil || m.lineageNotFound != "" {
		m.clearLineage()
	}
	m.route = routeMain
}

func (m *Model) submitInput() {
	value := strings.TrimSpace(m.input)
	if m.route == routeLineage && value != "" && !strings.HasPrefix(value, "/") {
		m.lookupLineage(value)
		m.input = ""
		return
	}
	if !strings.HasPrefix(value, "/") {
		m.notice = "✗ Type /help to see available commands."
		m.input = ""
		return
	}
	if m.routeCommand(value) {
		m.input = ""
		return
	}
	m.notice = `✗ Unknown command "` + value + `". Try /help.`
}

func (m *Model) routeCommand(command string) bool {
	switch command {
	case "/help":
		m.showHelp = true
	case "/main":
		m.route = routeMain
	case "/source-selection", "/collect":
		m.openSources()
	case "/data-samples":
		if len(m.selectedSources()) < 2 {
			m.notice = "Select at least 2 sources before opening Data Samples."
			return true
		}
		m.route = routeSamples
		m.sampleLoading = true
	case "/agent-workflow":
		m.route = routeWorkflow
		m.workflowGate = false
	case "/lineage-viewer":
		m.route = routeLineage
		m.clearLineage()
	case "/agent-monitoring":
		m.route = routeMonitoring
		m.monitoring = defaultMonitoring(m.settings)
	case "/settings":
		m.route = routeSettings
		m.settingsCursor = 0
		m.notice = ""
	default:
		return false
	}
	return true
}

func (m *Model) move(delta int) {
	switch m.route {
	case routeMain:
		m.moveMain(delta)
	case routeSources:
		m.sourceCursor = clamp(m.sourceCursor+delta, 0, len(m.sources)-1)
	case routeSamples:
		if source, ok := m.currentSampleSource(); ok && source.fetchError != "" {
			m.sampleErrorCursor = clamp(m.sampleErrorCursor+delta, 0, 2)
		}
	case routeWorkflow:
		if m.workflowGate {
			m.workflowCursor = clamp(m.workflowCursor+delta, 0, 1)
		}
	case routeFeedback:
		if m.feedbackWaiting {
			m.feedbackCursor = clamp(m.feedbackCursor+delta, 0, 2)
		}
	case routeSettings:
		m.moveSettings(delta)
	}
}

func (m *Model) page(delta int) {
	switch m.route {
	case routeSamples:
		maxPage := len(m.selectedSources()) - 1
		m.samplePage = clamp(m.samplePage+delta, 0, maxPage)
		m.sampleErrorCursor = 0
	case routeMonitoring:
		m.monitoringScope = clamp(m.monitoringScope+delta, 0, 2)
	}
}

func (m *Model) space() {
	if m.input != "" {
		m.input += " "
		return
	}
	if m.route != routeSources {
		return
	}
	if len(m.sources) == 0 {
		return
	}
	id := m.sources[m.sourceCursor].id
	m.selected[id] = !m.selected[id]
	m.notice = ""
}

func (m *Model) openSources() {
	m.route = routeSources
	m.sourceCursor = 0
	m.notice = ""
}

func (m *Model) selectedSources() []source {
	selected := make([]source, 0, len(m.sources))
	for _, source := range m.sources {
		if m.selected[source.id] {
			selected = append(selected, source)
		}
	}
	return selected
}

func (m *Model) currentSampleSource() (source, bool) {
	selected := m.selectedSources()
	if len(selected) == 0 {
		return source{}, false
	}
	page := clamp(m.samplePage, 0, len(selected)-1)
	return selected[page], true
}

func (m *Model) enterSampleError() {
	switch m.sampleErrorCursor {
	case 0:
		m.sampleLoading = true
		m.notice = ""
	case 1:
		m.route = routeSources
		m.notice = ""
	case 2:
		m.route = routeSettings
		m.settingsCursor = 0
		m.notice = ""
	}
}
