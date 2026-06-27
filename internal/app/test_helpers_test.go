package app

import (
	"regexp"
	"strings"
	"testing"
)

var ansiPattern = regexp.MustCompile(`\x1b\[[0-9;]*m`)

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
	got = stripANSI(got)
	if !strings.Contains(got, want) {
		t.Fatalf("expected view to contain %q\nview:\n%s", want, got)
	}
}

func assertNotContains(t *testing.T, got string, want string) {
	t.Helper()
	got = stripANSI(got)
	if strings.Contains(got, want) {
		t.Fatalf("expected view not to contain %q\nview:\n%s", want, got)
	}
}

func assertContainsRaw(t *testing.T, got string, want string) {
	t.Helper()
	if !strings.Contains(got, want) {
		t.Fatalf("expected raw view to contain %q\nview:\n%q", want, got)
	}
}

func stripANSI(value string) string {
	return ansiPattern.ReplaceAllString(value, "")
}
