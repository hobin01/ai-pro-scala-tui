package app

import "strings"

type pipelineEvent struct {
	text     string
	feedback bool
}

func (m *Model) AdvancePipeline() {
	m.AdvanceLoading()
	if m.backendRuntime {
		return
	}
	if !m.pipelineRunning || m.pipelineDone {
		return
	}
	events := []pipelineEvent{
		{text: "Source Profiler read 2 selected sources"},
		{text: "Schema Profiler found mismatched source.ip/clientip fields"},
		{text: "Normalizer proposed src_endpoint.ip from clientip"},
		{text: "Review field recommendation: map clientip -> src_endpoint.ip", feedback: true},
		{text: "Validator accepted feedback and resumed"},
		{text: "Load wrote 2,000 docs to OpenSearch"},
		{text: "Lineage recorded for 2,000 normalized documents"},
		{text: "Cache updated for future source suggestions"},
	}
	if m.pipelineIndex >= len(events) {
		m.finishPipeline()
		return
	}
	event := events[m.pipelineIndex]
	m.stream = append(m.stream, event.text)
	m.pipelineIndex++
	if event.feedback {
		m.pipelineRunning = false
		m.feedbackWaiting = true
		return
	}
	if m.pipelineIndex >= len(events) {
		m.finishPipeline()
	}
}

func (m *Model) IsPipelineRunning() bool {
	return m.pipelineRunning
}

func (m *Model) startPipeline() {
	m.route = routeFeedback
	m.pipelineRunning = true
	m.pipelineDone = false
	m.feedbackWaiting = false
	m.feedbackCursor = 0
	m.pipelineIndex = 0
	m.lastRunStatus = nil
	m.feedbackRequestID = ""
	m.feedbackRequest = nil
	m.stream = []string{"Pipeline started with dummy runner"}
	m.notice = ""
	if m.backendRuntime {
		m.stream = []string{"Pipeline requested from backend"}
	}
	m.queuePipelineRun()
}

func (m *Model) enterFeedback() {
	if m.pipelineDone {
		m.route = routeMain
		return
	}
	if !m.feedbackWaiting {
		return
	}
	switch m.feedbackCursor {
	case 0:
		m.stream = append(m.stream, "Approved recommendation")
		m.queueFeedbackResponse("approve", "")
		m.resumePipeline()
	case 1:
		m.stream = append(m.stream, "Kept raw field as custom_attr")
		m.queueFeedbackResponse("keep_raw", "")
		m.resumePipeline()
	case 2:
		m.feedbackComment = true
		m.input = ""
		m.notice = "Comment input enabled for re-review."
	}
}

func (m *Model) resumePipeline() {
	m.feedbackWaiting = false
	m.pipelineRunning = true
}

func (m *Model) finishPipeline() {
	m.pipelineRunning = false
	m.feedbackWaiting = false
	m.pipelineDone = true
	m.stream = append(m.stream, "Pipeline complete", "Loaded 2,000 docs", "Lineage recorded", "opensearch://"+m.settings.resultIndex)
}

func (m *Model) updateFeedbackComment(key string) {
	switch key {
	case "enter":
		comment := strings.TrimSpace(m.input)
		if comment == "" {
			comment = "no comment"
		}
		m.stream = append(m.stream, "Reviewer comment: "+comment, "Re-review complete: clientip remains best source field")
		m.queueFeedbackResponse("comment", comment)
		m.input = ""
		m.feedbackComment = false
		if m.backendRuntime {
			m.feedbackWaiting = false
			m.pipelineRunning = true
			return
		}
		m.feedbackWaiting = true
		m.feedbackCursor = 0
	case "backspace":
		m.input = trimLastRune(m.input)
	default:
		if isText(key) || key == "space" {
			m.input += displayKey(key)
		}
	}
}
