package app

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// TestHumanFeedbackStreamingCompletion는 관련 동작을 검증한다.
func TestHumanFeedbackStreamingCompletion(t *testing.T) {
	model := newModelAtWorkflowGate()

	model.UpdateKey("enter")
	assertContains(t, model.View(), "Human Feedback")
	assertContains(t, model.View(), "⌧ agent running")

	for range 4 {
		model.AdvancePipeline()
	}
	assertContains(t, model.View(), "Review field recommendation")
	assertContains(t, model.View(), "Approve recommendation")

	model.UpdateKey("enter")
	for range 4 {
		model.AdvancePipeline()
	}

	view := model.View()
	assertContains(t, view, "Pipeline complete")
	assertContains(t, view, "Loaded 2,000 docs")
	assertContains(t, view, "Lineage recorded")
	assertContains(t, view, "opensearch://scala-normalized/security-events")
}

// TestHumanFeedbackBlocksInputWhileAgentsRun는 관련 동작을 검증한다.
func TestHumanFeedbackBlocksInputWhileAgentsRun(t *testing.T) {
	model := newModelAtWorkflowGate()

	model.UpdateKey("enter")
	typeText(model, "/settings")
	model.UpdateKey("enter")

	view := model.View()
	assertContains(t, view, "Human Feedback")
	assertContains(t, view, "⌧ agent running")
	assertNotContains(t, view, "Settings")
	assertNotContains(t, view, "/settings")
}

// TestScriptedFullFlowTranscript는 관련 동작을 검증한다.
func TestScriptedFullFlowTranscript(t *testing.T) {
	model := NewModel()
	views := []string{model.View()}

	model.UpdateKey("enter")
	views = append(views, model.View())
	model.UpdateKey("space")
	model.UpdateKey("down")
	model.UpdateKey("space")
	model.UpdateKey("enter")
	views = append(views, model.View())
	model.AdvanceLoading()
	views = append(views, model.View())
	model.UpdateKey("enter")
	views = append(views, model.View())
	model.UpdateKey("enter")
	views = append(views, model.View())
	for range 4 {
		model.AdvancePipeline()
	}
	views = append(views, model.View())
	model.UpdateKey("enter")
	for range 4 {
		model.AdvancePipeline()
	}
	views = append(views, model.View())

	typeText(model, "/lineage-viewer")
	model.UpdateKey("enter")
	typeText(model, "aZ12bQ8")
	model.UpdateKey("enter")
	model.AdvanceLoading()
	views = append(views, model.View())
	typeText(model, "/agent-monitoring")
	model.UpdateKey("enter")
	views = append(views, model.View())
	model.UpdateKey("enter")
	typeText(model, "/settings")
	model.UpdateKey("enter")
	views = append(views, model.View())

	transcript := strings.Join(views, "\n\n--- screen ---\n\n")
	for _, want := range []string{
		"SCALA",
		"Source Selection",
		"Data Samples",
		"Fetching samples",
		"Agent Workflow Graph",
		"Human Feedback",
		"Pipeline complete",
		"Lineage Viewer",
		"Agent Monitoring",
		"Settings",
		"Kibana",
		"Splunk Web",
		"OpenSearch Dashboards",
	} {
		assertContains(t, transcript, want)
	}
	if path := os.Getenv("SCALA_TUI_TRANSCRIPT"); path != "" {
		if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
			t.Fatalf("create transcript dir: %v", err)
		}
		if err := os.WriteFile(path, []byte(transcript), 0o644); err != nil {
			t.Fatalf("write transcript: %v", err)
		}
	}
}
