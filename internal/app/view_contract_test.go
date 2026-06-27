package app

import "testing"

func TestFrameRendersSharedRegionsAndResponsiveSize(t *testing.T) {
	model := NewModel()
	model.SetSize(100, 30)

	view := model.View()

	assertContains(t, view, "SCALA · Security Canonical Alignment & Lineage Automation")
	assertContains(t, view, "idle")
	assertContains(t, view, "┌")
	assertContains(t, view, "├")
	assertContains(t, view, "│ > _")
	assertContains(t, view, "ctrl+c quit")
	assertNotContains(t, view, "Header | Content | Input | Footer")
}

func TestFrameUsesBrightBlueTerminalPalette(t *testing.T) {
	view := NewModel().View()

	assertContainsRaw(t, view, "\x1b[38;5;45m")
	assertContainsRaw(t, view, "\x1b[1;38;5;51m")
	assertContainsRaw(t, view, "\x1b[1;38;5;226m")
}

func TestMainPageMatchesDocumentedLandingCopy(t *testing.T) {
	model := NewModel()

	view := model.View()

	assertContains(t, view, "Welcome. SCALA normalizes heterogeneous SIEM data into OCSF")
	assertContains(t, view, "it into OpenSearch with full document lineage.")
	assertContains(t, view, "How it works")
	assertContains(t, view, "1. Select 2+ data sources")
	assertContains(t, view, "2. Review field & value samples")
	assertContains(t, view, "3. Confirm the agent workflow, then run the pipeline")
	assertContains(t, view, "What would you like to do?")
	assertContains(t, view, "▸ Collect & Normalize")
	assertContains(t, view, "View Results")
	assertContains(t, view, "lineage · workflow graph · monitoring")
	assertContains(t, view, "Settings")
	assertContains(t, view, "sources · indices · models")
}

func TestHeaderStatusBadgesFollowRouteState(t *testing.T) {
	model := NewModel()
	assertContains(t, model.View(), "idle")

	model.UpdateKey("enter")
	assertContains(t, model.View(), "selected: 0")

	model.UpdateKey("space")
	model.UpdateKey("down")
	model.UpdateKey("down")
	model.UpdateKey("space")
	assertContains(t, model.View(), "selected: 2")

	model.UpdateKey("enter")
	assertContains(t, model.View(), "fetching…")
	model.AdvanceLoading()
	assertContains(t, model.View(), "[1/2] Elasticsearch · logs-2024")
}

func TestMainEnterSplitBetweenCommandInputAndMenuSelection(t *testing.T) {
	model := NewModel()

	typeText(model, "/settings")
	model.UpdateKey("enter")
	assertContains(t, model.View(), "Settings")

	model = NewModel()
	model.UpdateKey("enter")
	assertContains(t, model.View(), "Source Selection")
}

func TestSourceSelectionUsesDocumentedDummyInputsOnly(t *testing.T) {
	model := NewModel()
	model.UpdateKey("enter")

	view := model.View()
	assertContains(t, view, "Elasticsearch  ·  es-prod")
	assertContains(t, view, "Splunk  ·  splunk-soc")
	assertContains(t, view, "logs-2024")
	assertContains(t, view, "firewall-idx")
	assertContains(t, view, "main")
	assertContains(t, view, "security")
	assertNotContains(t, view, "OpenSearch · normalized")
	assertNotContains(t, view, "docs)")

	model.UpdateKey("space")
	model.UpdateKey("down")
	model.UpdateKey("down")
	model.UpdateKey("space")
	assertContains(t, model.View(), "selected: 2 · Elasticsearch ×1, Splunk ×1")
}

func TestPipelineRunningHeaderNamesActiveAgent(t *testing.T) {
	model := newModelAtWorkflowGate()

	model.UpdateKey("enter")

	view := model.View()
	assertContains(t, view, "Pipeline running")
	assertContains(t, view, "running: Normalization")
	assertNotContains(t, view, "running: agents")
}

func TestWorkflowAndSettingsShowAgentSpecificModels(t *testing.T) {
	model := NewModel()

	typeText(model, "/agent-workflow")
	model.UpdateKey("enter")
	view := model.View()
	assertContains(t, view, "Orchestrator")
	assertContains(t, view, "Schema Profiler")
	assertContains(t, view, "Normalization")
	assertContains(t, view, "Validator")
	assertContains(t, view, "Load")
	assertContains(t, view, "Caching")
	assertContains(t, view, "Lineage")
	assertContains(t, view, "-- (no LLM)")

	typeText(model, "/settings")
	model.UpdateKey("enter")
	view = model.View()
	assertContains(t, view, "Orchestrator model")
	assertContains(t, view, "Schema Profiler model")
	assertContains(t, view, "Normalization model")
	assertContains(t, view, "Validator model")
	assertContains(t, view, "OpenAI API key")
}

func TestMonitoringIsReadOnlyWithinSharedFrame(t *testing.T) {
	model := NewModel()

	typeText(model, "/agent-monitoring")
	model.UpdateKey("enter")
	view := model.View()

	assertContains(t, view, "Agent Monitoring")
	assertContains(t, view, "⌧ read-only view")
	assertContains(t, view, "←/→ scope")
	assertNotContains(t, view, "space toggle")
}
