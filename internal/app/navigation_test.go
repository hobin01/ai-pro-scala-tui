package app

import "testing"

// TestLineageViewerFoundAndNotFound는 관련 동작을 검증한다.
func TestLineageViewerFoundAndNotFound(t *testing.T) {
	model := NewModel()

	typeText(model, "/lineage-viewer")
	model.UpdateKey("enter")
	typeText(model, "aZ12bQ8")
	model.UpdateKey("enter")
	assertContains(t, model.View(), "Looking up lineage")
	model.AdvanceLoading()
	view := model.View()
	assertContains(t, view, "OpenSearch (normalized)")
	assertContains(t, view, "Source (raw)")
	assertContains(t, view, "custom_attr")

	model = NewModel()
	typeText(model, "/lineage-viewer")
	model.UpdateKey("enter")
	typeText(model, "zzz9")
	model.UpdateKey("enter")
	model.AdvanceLoading()
	assertContains(t, model.View(), `No lineage found for _id "zzz9"`)
}

// TestAgentMonitoringScopesAndNoLLMRows는 관련 동작을 검증한다.
func TestAgentMonitoringScopesAndNoLLMRows(t *testing.T) {
	model := NewModel()

	typeText(model, "/agent-monitoring")
	model.UpdateKey("enter")
	assertContains(t, model.View(), "Agent Monitoring")
	assertContains(t, model.View(), "scope: Session")

	model.UpdateKey("right")
	view := model.View()
	assertContains(t, view, "scope: Today")
	assertContains(t, view, "Load")
	assertContains(t, view, "-- (no LLM)")
	assertContains(t, view, "Caching")
	assertContains(t, view, "cost unavailable")
}

// TestAgentMonitoringRejectsHiddenTextInput는 관련 동작을 검증한다.
func TestAgentMonitoringRejectsHiddenTextInput(t *testing.T) {
	model := NewModel()

	typeText(model, "/agent-monitoring")
	model.UpdateKey("enter")
	typeText(model, "/settings")
	model.UpdateKey("enter")

	view := model.View()
	assertContains(t, view, "Welcome. SCALA")
	assertNotContains(t, view, "OpenAI API key")
	assertNotContains(t, view, "Type /help")
}

// TestDocumentedMainAndBoundaryStates는 관련 동작을 검증한다.
func TestDocumentedMainAndBoundaryStates(t *testing.T) {
	model := NewModel()
	view := model.View()
	assertContains(t, view, "Collect & Normalize")
	assertContains(t, view, "View Results")
	assertContains(t, view, "Settings")
	assertNotContains(t, view, "Agent Monitoring")
	assertNotContains(t, view, "Lineage Viewer")

	model.UpdateKey("down")
	model.UpdateKey("enter")
	view = model.View()
	assertContains(t, view, "▸ Lineage Viewer")
	assertContains(t, view, "Agent Workflow Graph")
	assertContains(t, view, "Agent Monitoring")
	model.UpdateKey("enter")
	assertContains(t, model.View(), "Lineage Viewer")

	model = NewModel()
	model.UpdateKey("down")
	model.UpdateKey("enter")
	model.UpdateKey("down")
	model.UpdateKey("enter")
	assertContains(t, model.View(), "Agent workflow graph")
	assertContains(t, model.View(), "enter to return to main.")

	model = NewModel()
	model.UpdateKey("down")
	model.UpdateKey("enter")
	model.UpdateKey("down")
	model.UpdateKey("down")
	model.UpdateKey("enter")
	assertContains(t, model.View(), "Agent Monitoring")

	model = NewModel()
	model.sources = nil
	model.UpdateKey("enter")
	assertContains(t, model.View(), "No data sources are configured")
	model.UpdateKey("space")
	assertContains(t, model.View(), "No data sources are configured")
}

// TestDataSamplesFailureActions는 관련 동작을 검증한다.
func TestDataSamplesFailureActions(t *testing.T) {
	model := NewModel()
	model.UpdateKey("enter")
	model.UpdateKey("space")
	model.UpdateKey("down")
	model.UpdateKey("space")
	model.UpdateKey("enter")
	assertContains(t, model.View(), "Fetching samples")
	model.AdvanceLoading()
	model.UpdateKey("right")
	view := model.View()
	assertContains(t, view, "fetch failed")
	assertContains(t, view, "Could not fetch samples")
	assertContains(t, view, "Retry")
	assertContains(t, view, "Back to sources")
	assertContains(t, view, "Open Settings")

	model.UpdateKey("down")
	model.UpdateKey("down")
	model.UpdateKey("enter")
	assertContains(t, model.View(), "Settings")
}
