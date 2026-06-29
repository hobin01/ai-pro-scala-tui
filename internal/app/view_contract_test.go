package app

import "testing"

// TestFrameRendersSharedRegionsAndResponsiveSize는 관련 동작을 검증한다.
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

// TestFrameUsesBrightBlueTerminalPalette는 관련 동작을 검증한다.
func TestFrameUsesBrightBlueTerminalPalette(t *testing.T) {
	view := NewModel().View()

	assertContainsRaw(t, view, "\x1b[38;5;45m")
	assertContainsRaw(t, view, "\x1b[1;38;5;51m")
	assertContainsRaw(t, view, "\x1b[1;38;5;226m")
}

// TestMainPageMatchesDocumentedLandingCopy는 관련 동작을 검증한다.
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

// TestHeaderStatusBadgesFollowRouteState는 관련 동작을 검증한다.
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

// TestMainEnterSplitBetweenCommandInputAndMenuSelection는 관련 동작을 검증한다.
func TestMainEnterSplitBetweenCommandInputAndMenuSelection(t *testing.T) {
	model := NewModel()

	typeText(model, "/settings")
	model.UpdateKey("enter")
	assertContains(t, model.View(), "Settings")

	model = NewModel()
	model.UpdateKey("enter")
	assertContains(t, model.View(), "Source Selection")
}

// TestSourceSelectionUsesDocumentedDummyInputsOnly는 관련 동작을 검증한다.
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

// TestPipelineRunningHeaderNamesActiveAgent는 관련 동작을 검증한다.
func TestPipelineRunningHeaderNamesActiveAgent(t *testing.T) {
	model := newModelAtWorkflowGate()

	model.UpdateKey("enter")

	view := model.View()
	assertContains(t, view, "Pipeline running")
	assertContains(t, view, "running: Normalization")
	assertNotContains(t, view, "running: agents")
}

// TestWorkflowAndSettingsShowAgentSpecificModels는 관련 동작을 검증한다.
func TestWorkflowAndSettingsShowAgentSpecificModels(t *testing.T) {
	model := NewModel()
	model.SetSize(110, 44)

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
	assertContains(t, view, "— (no LLM)")

	typeText(model, "/settings")
	model.UpdateKey("enter")
	view = model.View()
	assertContains(t, view, "Orchestrator model")
	assertContains(t, view, "Schema Profiler model")
	assertContains(t, view, "Normalization model")
	assertContains(t, view, "Validator model")
	assertContains(t, view, "OpenAI API key")
}

// TestWorkflowGraphMatchesPRDCompressedSurface는 관련 동작을 검증한다.
func TestWorkflowGraphMatchesPRDCompressedSurface(t *testing.T) {
	model := NewModel()
	model.SetSize(110, 44)

	typeText(model, "/agent-workflow")
	model.UpdateKey("enter")
	view := model.View()

	for _, text := range []string{
		"How SCALA processes your data (Agent pipeline topology)",
		"Sources: Elasticsearch · Splunk · (future)",
		"└─▶ SIEM Connector ─▶ Orchestrator      (schema/sample)",
		"User ─▶ Orchestrator ─▶ Schema Profiler",
		"Schema Profiler ─▶ Redis                (cache lookup)",
		"├─ miss ─▶ ChromaDB OCSF ─▶ Normalization",
		"└─ hit  ─▶ reuse cached mapping ─▶ Normalization",
		"fail ─▶ Orchestrator ─▶ User         (human feedback)",
		"User ─▶ Orchestrator ─▶ Validator",
		"Validator ─▶ Validator ─▶ Normalization (re-chk)",
		"Normalization ─▶ Load    ─▶ OpenSearch",
		"├─▶ Caching ─▶ Redis",
		"└─▶ Lineage ─▶ PostgreSQL",
		"Load ─▶ Lineage                         (OpenSearch _id)",
		"Processing Agents ─▶ Orchestrator ─▶ User   (final result)",
		"Agent            Role                        Model",
		"workflow 관리 · 사용자 소통",
		"스키마 프로파일 · 캐시 조회",
		"정규화 Rule 생성 · 적용",
		"데이터 정합성 검증",
		"정규화 데이터 적재",
		"매핑 캐시 저장",
		"리니지 메타데이터 생성",
		"enter to return to main.",
	} {
		assertContains(t, view, text)
	}
}

// TestWorkflowViewModeScrollsStaticGraph는 관련 동작을 검증한다.
func TestWorkflowViewModeScrollsStaticGraph(t *testing.T) {
	model := NewModel()
	model.SetSize(110, 12)

	typeText(model, "/agent-workflow")
	model.UpdateKey("enter")
	assertContains(t, model.View(), "How SCALA processes your data")

	for range 20 {
		model.UpdateKey("down")
	}

	assertContains(t, model.View(), "Lineage          리니지 메타데이터 생성")
	assertContains(t, model.View(), "↑↓ scroll · enter back")
}

// TestMonitoringIsReadOnlyWithinSharedFrame는 관련 동작을 검증한다.
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
