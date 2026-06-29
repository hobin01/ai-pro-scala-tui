package main

import (
	"regexp"
	"strings"
	"testing"

	"charm.land/bubbles/v2/spinner"
	tea "charm.land/bubbletea/v2"
	"github.com/hobin01/ai-pro-scala-tui/internal/app"
)

var testANSIPattern = regexp.MustCompile(`\x1b\[[0-9;]*m`)

// TestPasteMsg_appendsToActiveCommandInput는 관련 동작을 검증한다.
func TestPasteMsg_appendsToActiveCommandInput(t *testing.T) {
	// Given
	model := tuiModel{
		core:    app.NewModel(),
		spinner: spinner.New(),
	}

	// When
	updated, _ := model.Update(tea.PasteMsg{Content: "/settings"})
	got := updated.(tuiModel)
	got.core.UpdateKey("enter")

	// Then
	if !strings.Contains(stripANSI(got.core.View()), "Settings") {
		t.Fatalf("expected pasted command to open settings, got:\n%s", stripANSI(got.core.View()))
	}
}

// TestPasteMsg_appendsToActiveSettingEdit는 관련 동작을 검증한다.
func TestPasteMsg_appendsToActiveSettingEdit(t *testing.T) {
	// Given
	core := app.NewModel()
	typeKeys(core, "/settings")
	core.UpdateKey("enter")
	core.UpdateKey("enter")
	model := tuiModel{
		core:    core,
		spinner: spinner.New(),
	}

	// When
	updated, _ := model.Update(tea.PasteMsg{Content: "-pasted"})
	got := updated.(tuiModel)

	// Then
	if !strings.Contains(stripANSI(got.core.View()), "edit: https://es.local:9200-pasted") {
		t.Fatalf("expected paste to append to setting edit, got:\n%s", stripANSI(got.core.View()))
	}
}

// TestPasteMsg_appendsToActiveFeedbackComment는 관련 동작을 검증한다.
func TestPasteMsg_appendsToActiveFeedbackComment(t *testing.T) {
	// Given
	core := app.NewModel()
	core.ApplyFeedbackRequest("request-1", app.FeedbackRequest{
		Field:          app.FeedbackField{SourceField: "clientip", Type: "string"},
		Recommendation: app.FeedbackRecommendation{OCSFField: "src_endpoint.ip", OCSFType: "ip"},
	})
	core.UpdateKey("down")
	core.UpdateKey("down")
	core.UpdateKey("enter")
	model := tuiModel{
		core:    core,
		spinner: spinner.New(),
	}

	// When
	updated, _ := model.Update(tea.PasteMsg{Content: "please keep both"})
	got := updated.(tuiModel)

	// Then
	if !strings.Contains(stripANSI(got.core.View()), "Feedback input enabled: please keep both") {
		t.Fatalf("expected paste to append to feedback comment, got:\n%s", stripANSI(got.core.View()))
	}
}

// TestCopyKey_returnsClipboardCommandForLineageID는 관련 동작을 검증한다.
func TestCopyKey_returnsClipboardCommandForLineageID(t *testing.T) {
	// Given
	core := app.NewModel()
	typeKeys(core, "/lineage-viewer")
	core.UpdateKey("enter")
	typeKeys(core, "os-copy-1")
	core.UpdateKey("enter")
	core.ApplyLineageResult(app.LineageLookupResult{
		Found: true,
		Metadata: app.LineageMetadata{
			SourceSolution:  "splunk",
			SourceIndex:     "main",
			SourceDocID:     "raw-1",
			OpenSearchIndex: "scala-normalized",
			OpenSearchID:    "os-copy-1",
		},
		RawDocument:        map[string]any{"clientip": "10.0.0.5"},
		NormalizedDocument: map[string]any{"src_endpoint.ip": "10.0.0.5"},
	})
	model := tuiModel{
		core:    core,
		spinner: spinner.New(),
	}

	// When
	_, cmd := model.Update(tea.KeyPressMsg(tea.Key{Code: 'y', Mod: tea.ModCtrl}))

	// Then
	if cmd == nil {
		t.Fatalf("expected ctrl+y on lineage result to return a clipboard command")
	}
}

// typeKeys는 관련 동작을 처리한다.
func typeKeys(model *app.Model, text string) {
	for _, r := range text {
		model.UpdateKey(string(r))
	}
}

// stripANSI는 관련 동작을 처리한다.
func stripANSI(value string) string {
	return testANSIPattern.ReplaceAllString(value, "")
}
