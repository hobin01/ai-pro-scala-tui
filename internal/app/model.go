package app

// route는 model에서 사용하는 타입을 정의한다.
type route string

const (
	routeMain       route = "main"
	routeSources    route = "sources"
	routeSamples    route = "samples"
	routeWorkflow   route = "workflow"
	routeFeedback   route = "feedback"
	routeLineage    route = "lineage"
	routeMonitoring route = "monitoring"
	routeSettings   route = "settings"
)

// Model는 model에서 사용하는 타입을 정의한다.
type Model struct {
	width             int
	height            int
	route             route
	input             string
	notice            string
	showHelp          bool
	menuCursor        int
	viewResultsOpen   bool
	viewResultsCursor int
	sourceCursor      int
	selected          map[string]bool
	samplePage        int
	sampleErrorCursor int
	sampleLoading     bool
	workflowGate      bool
	workflowCursor    int
	workflowScroll    int
	contentScroll     int
	pipelineRunning   bool
	pipelineDone      bool
	pipelineIndex     int
	stream            []string
	activeRunID       string
	lastRunStatus     *RunStatus
	feedbackWaiting   bool
	feedbackCursor    int
	feedbackComment   bool
	feedbackRequestID string
	feedbackRequest   *FeedbackRequest
	lineageLoading    bool
	lineageLookupID   string
	lineageResult     *lineageRecord
	lineageNotFound   string
	monitoringScope   int
	settingsCursor    int
	editingSetting    bool
	editValue         string
	settings          settings
	sources           []source
	lineage           map[string]lineageRecord
	monitoring        []monitoringSnapshot
	backendRuntime    bool
	backendActions    []BackendAction
}

// NewModel는 관련 동작을 처리한다.
func NewModel() *Model {
	s := defaultSettings()
	return &Model{
		width:      100,
		height:     30,
		route:      routeMain,
		selected:   make(map[string]bool),
		settings:   s,
		sources:    defaultSources(),
		lineage:    defaultLineage(),
		monitoring: defaultMonitoring(s),
	}
}

// SetSize는 관련 동작을 처리한다.
func (m *Model) SetSize(width int, height int) {
	if width > 0 {
		m.width = width
	}
	if height > 0 {
		m.height = height
	}
}

// Size는 관련 동작을 처리한다.
func (m *Model) Size() (int, int) {
	return m.width, m.height
}

// UpdateKey는 모델 상태를 갱신한다.
func (m *Model) UpdateKey(key string) bool {
	key = normalizeKey(key)
	m.showHelp = false
	if key == "ctrl+c" {
		return true
	}
	if m.pipelineRunning {
		return false
	}
	if m.route == routeMonitoring {
		m.updateMonitoringKey(key)
		return false
	}
	if m.editingSetting {
		m.updateSettingEdit(key)
		return false
	}
	if m.feedbackComment {
		m.updateFeedbackComment(key)
		return false
	}
	switch key {
	case "up":
		m.move(-1)
	case "down":
		m.move(1)
	case "left":
		m.page(-1)
	case "right":
		m.page(1)
	case "space":
		m.space()
	case "backspace":
		m.input = trimLastRune(m.input)
	case "enter":
		m.enter()
	default:
		if isText(key) {
			m.input += key
		}
	}
	return false
}

// Paste는 관련 동작을 처리한다.
func (m *Model) Paste(text string) {
	if text == "" || m.pipelineRunning {
		return
	}
	switch {
	case m.editingSetting:
		m.editValue += text
	case m.feedbackComment:
		m.input += text
	case m.route != routeMonitoring:
		m.input += text
	}
}

// CopyKey는 관련 동작을 처리한다.
func (m *Model) CopyKey(key string) (string, bool) {
	key = normalizeKey(key)
	switch key {
	case "ctrl+y", "alt+y":
		return m.CopyOpenSearchID()
	case "y":
		if m.route == routeLineage && m.input == "" && m.lineageResult != nil {
			return m.CopyOpenSearchID()
		}
	}
	return "", false
}

// CopyOpenSearchID는 관련 동작을 처리한다.
func (m *Model) CopyOpenSearchID() (string, bool) {
	if m.lineageResult == nil || m.lineageResult.id == "" {
		if m.lastRunStatus == nil || len(m.lastRunStatus.LineageRefs) == 0 {
			m.notice = "No OpenSearch _id visible to copy."
			return "", false
		}
		id := m.lastRunStatus.LineageRefs[0].OpenSearchID
		m.notice = "Copied OpenSearch _id: " + id
		return id, true
	}
	m.notice = "Copied OpenSearch _id: " + m.lineageResult.id
	return m.lineageResult.id, true
}

// scrollContent는 관련 동작을 처리한다.
func (m *Model) scrollContent(delta int) {
	m.contentScroll = max(0, m.contentScroll+delta)
}

// AdvanceLoading는 관련 동작을 처리한다.
func (m *Model) AdvanceLoading() {
	if m.backendRuntime {
		return
	}
	if m.sampleLoading {
		m.sampleLoading = false
		m.notice = "Samples loaded from dummy fixtures."
	}
	if m.lineageLoading {
		m.resolveLineage()
	}
}
