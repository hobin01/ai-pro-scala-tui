package app

import (
	"strings"
	"testing"
)

func newModelAtDataSamples() *Model {
	model := NewModel()
	model.UpdateKey("enter")
	model.UpdateKey("space")
	model.UpdateKey("down")
	model.UpdateKey("down")
	model.UpdateKey("space")
	model.UpdateKey("enter")
	model.AdvanceLoading()
	return model
}

func newModelAtWorkflowGate() *Model {
	model := newModelAtDataSamples()
	model.UpdateKey("enter")
	return model
}

func typeText(model *Model, text string) {
	for _, r := range text {
		model.UpdateKey(string(r))
	}
}

func assertContains(t *testing.T, got string, want string) {
	t.Helper()
	if !strings.Contains(got, want) {
		t.Fatalf("expected view to contain %q\nview:\n%s", want, got)
	}
}

func assertNotContains(t *testing.T, got string, want string) {
	t.Helper()
	if strings.Contains(got, want) {
		t.Fatalf("expected view not to contain %q\nview:\n%s", want, got)
	}
}
