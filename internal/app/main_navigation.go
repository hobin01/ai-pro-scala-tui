package app

func (m *Model) enterMain() {
	switch m.menuCursor {
	case 0:
		m.openSources()
	case 1:
		if !m.viewResultsOpen {
			m.viewResultsOpen = true
			m.viewResultsCursor = 0
			return
		}
		m.openResultView()
	case 2:
		m.route = routeSettings
		m.settingsCursor = 0
	}
}

func (m *Model) openResultView() {
	switch m.viewResultsCursor {
	case 0:
		m.route = routeLineage
		m.clearLineage()
	case 1:
		m.route = routeWorkflow
		m.workflowGate = false
		m.workflowScroll = 0
	case 2:
		m.route = routeMonitoring
		m.monitoringScope = clamp(m.monitoringScope, 0, 2)
	}
}

func (m *Model) moveMain(delta int) {
	if m.viewResultsOpen && m.menuCursor == 1 {
		nextCursor := m.viewResultsCursor + delta
		if nextCursor >= 0 && nextCursor <= 2 {
			m.viewResultsCursor = nextCursor
			return
		}
	}
	m.menuCursor = clamp(m.menuCursor+delta, 0, 2)
}

func (m *Model) updateMonitoringKey(key string) {
	switch key {
	case "left":
		m.page(-1)
	case "right":
		m.page(1)
	case "enter":
		m.route = routeMain
	}
}
