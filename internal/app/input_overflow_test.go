package app

import (
	"strings"
	"testing"

	"charm.land/lipgloss/v2"
)

// TestLineageView_wrapsLongDocumentLines_whenViewportIsNarrow는 input overflow test의 화면 출력과 상태 전이를 확인한다.
func TestLineageView_wrapsLongDocumentLines_whenViewportIsNarrow(t *testing.T) {
	// Given
	model := modelWithLineageResult()
	model.SetSize(64, 22)

	// When
	view := model.View()

	// Then
	assertContains(t, view, "tail-marker")
	assertFrameLinesWithinWidth(t, view, 64)
}

// TestLineageView_scrollsLongResults_whenContentExceedsViewport는 input overflow test의 화면 출력과 상태 전이를 확인한다.
func TestLineageView_scrollsLongResults_whenContentExceedsViewport(t *testing.T) {
	// Given
	model := modelWithLineageResult()
	model.SetSize(72, 12)

	// When
	for range 60 {
		model.UpdateKey("down")
	}

	// Then
	assertContains(t, model.View(), "bottom-marker")
}

// TestMonitoringView_scrollsLongResults_whenContentExceedsViewport는 input overflow test의 화면 출력과 상태 전이를 확인한다.
func TestMonitoringView_scrollsLongResults_whenContentExceedsViewport(t *testing.T) {
	// Given
	model := NewModel()
	model.SetSize(82, 12)
	typeText(model, "/agent-monitoring")
	model.UpdateKey("enter")
	model.ApplyMonitoring(MonitoringResult{
		Scope: "session",
		AsOf:  "12:00",
		Total: MonitoringTotal{Runs: 1, Tokens: 1, Cost: floatPtr(0.01), CostSource: "openai_costs_api", LastRunID: "run-1"},
		Agents: []MonitoringAgent{
			{Agent: "orchestrator", Model: "gpt-5.4", LastActivity: "activity-01", Tokens: 1, Cost: 0.01},
			{Agent: "schema_profiler", Model: "gpt-5.4", LastActivity: "activity-02", Tokens: 1, Cost: 0.01},
			{Agent: "normalization", Model: "gpt-5.4", LastActivity: "activity-03", Tokens: 1, Cost: 0.01},
			{Agent: "validator", Model: "gpt-5.4", LastActivity: "activity-04", Tokens: 1, Cost: 0.01},
			{Agent: "load", Model: "--", LastActivity: "activity-05", Tokens: 0, Cost: 0},
			{Agent: "caching", Model: "--", LastActivity: "activity-06", Tokens: 0, Cost: 0},
			{Agent: "lineage", Model: "--", LastActivity: "bottom-monitor-marker", Tokens: 0, Cost: 0},
		},
	})

	// When
	for range 20 {
		model.UpdateKey("down")
	}

	// Then
	assertContains(t, model.View(), "bottom-monitor-marker")
}

// modelWithLineageResult는 input overflow test의 화면 출력과 상태 전이를 확인한다.
func modelWithLineageResult() *Model {
	model := NewModel()
	typeText(model, "/lineage-viewer")
	model.UpdateKey("enter")
	typeText(model, "os-visible-123")
	model.UpdateKey("enter")
	model.ApplyLineageResult(LineageLookupResult{
		Found: true,
		Metadata: LineageMetadata{
			SourceSolution:  "splunk",
			SourceIndex:     "main",
			SourceDocID:     "raw-1",
			OpenSearchIndex: "scala-normalized",
			OpenSearchID:    "os-visible-123",
		},
		RawDocument: map[string]any{
			"raw_start": "top",
			"raw_01":    "value",
			"raw_02":    "value",
			"raw_03":    "value",
			"raw_04":    "value",
			"raw_05":    "value",
			"raw_06":    "value",
			"raw_07":    "value",
			"raw_08":    "value",
			"raw_09":    "value",
			"raw_10":    "bottom-marker",
		},
		NormalizedDocument: map[string]any{
			"wrapped_field": "prefix-" + strings.Repeat("x", 90) + "-tail-marker",
		},
	})
	return model
}

// assertFrameLinesWithinWidth는 테스트 조건을 검증한다.
func assertFrameLinesWithinWidth(t *testing.T, view string, width int) {
	t.Helper()
	for _, line := range strings.Split(stripANSI(view), "\n") {
		if got := lipgloss.Width(line); got > width {
			t.Fatalf("line width = %d, want <= %d\nline: %q\nview:\n%s", got, width, line, stripANSI(view))
		}
	}
}
