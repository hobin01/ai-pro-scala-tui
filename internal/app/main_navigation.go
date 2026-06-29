package app

// enterMain는 enter 키 입력에서 다음 route나 실행 여부를 결정한다.
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

// openResultView는 View Results 하위 메뉴 선택을 실제 result route로 연다.
func (m *Model) openResultView() {
	switch m.viewResultsCursor {
	case 0:
		m.route = routeLineage
		m.contentScroll = 0
		m.clearLineage()
	case 1:
		m.route = routeWorkflow
		m.workflowGate = false
		m.workflowScroll = 0
	case 2:
		m.route = routeMonitoring
		m.monitoringScope = clamp(m.monitoringScope, 0, 2)
		m.contentScroll = 0
		m.queueMonitoringQuery()
	}
}

// moveMain는 현재 화면 cursor를 유효 범위 안에서 이동한다.
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

// updateMonitoringKey는 monitoring scope 이동과 본문 스크롤 키를 처리한다.
func (m *Model) updateMonitoringKey(key string) {
	switch key {
	case "left":
		m.page(-1)
		m.queueMonitoringQuery()
	case "right":
		m.page(1)
		m.queueMonitoringQuery()
	case "up":
		m.scrollContent(-1)
	case "down":
		m.scrollContent(1)
	case "enter":
		m.route = routeMain
	}
}
