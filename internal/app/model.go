package app

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

func (m *Model) SetSize(width int, height int) {
	if width > 0 {
		m.width = width
	}
	if height > 0 {
		m.height = height
	}
}

func (m *Model) Size() (int, int) {
	return m.width, m.height
}

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
