package app

import (
	"regexp"
	"strings"
	"testing"
)

var ansiPattern = regexp.MustCompile(`\x1b\[[0-9;]*m`)

// newModelAtDataSamples는 test helpers test의 화면 출력과 상태 전이를 확인한다.
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

// newModelAtWorkflowGate는 test helpers test의 화면 출력과 상태 전이를 확인한다.
func newModelAtWorkflowGate() *Model {
	model := newModelAtDataSamples()
	model.UpdateKey("enter")
	return model
}

// typeText는 test helpers test의 화면 출력과 상태 전이를 확인한다.
func typeText(model *Model, text string) {
	for _, r := range text {
		model.UpdateKey(string(r))
	}
}

// assertContains는 테스트 조건을 검증한다.
func assertContains(t *testing.T, got string, want string) {
	t.Helper()
	got = stripANSI(got)
	if !strings.Contains(got, want) {
		t.Fatalf("expected view to contain %q\nview:\n%s", want, got)
	}
}

// assertNotContains는 테스트 조건을 검증한다.
func assertNotContains(t *testing.T, got string, want string) {
	t.Helper()
	got = stripANSI(got)
	if strings.Contains(got, want) {
		t.Fatalf("expected view not to contain %q\nview:\n%s", want, got)
	}
}

// assertContainsRaw는 테스트 조건을 검증한다.
func assertContainsRaw(t *testing.T, got string, want string) {
	t.Helper()
	if !strings.Contains(got, want) {
		t.Fatalf("expected raw view to contain %q\nview:\n%q", want, got)
	}
}

// stripANSI는 test helpers test의 화면 출력과 상태 전이를 확인한다.
func stripANSI(value string) string {
	return ansiPattern.ReplaceAllString(value, "")
}
