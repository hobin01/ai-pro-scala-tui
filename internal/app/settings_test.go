package app

import "testing"

func TestSettingsHotReloadAndReadOnlyAPIKey(t *testing.T) {
	model := NewModel()

	typeText(model, "/settings")
	model.UpdateKey("enter")
	for range 4 {
		model.UpdateKey("down")
	}
	model.UpdateKey("enter")
	typeText(model, "gpt-5.4-mini")
	model.UpdateKey("enter")
	assertContains(t, model.View(), "gpt-5.4-mini")
	assertNotContains(t, model.View(), "pending restart: 1")

	typeText(model, "/agent-workflow")
	model.UpdateKey("enter")
	assertContains(t, model.View(), "gpt-5.4-mini")

	typeText(model, "/settings")
	model.UpdateKey("enter")
	for range 6 {
		model.UpdateKey("down")
	}
	model.UpdateKey("enter")
	assertContains(t, model.View(), "API key is read-only")
	assertContains(t, model.View(), "read-only · .env")
}

func TestSettingsURLChangesHotReloadWithoutRestartState(t *testing.T) {
	model := NewModel()
	typeText(model, "/settings")
	model.UpdateKey("enter")
	for range 9 {
		model.UpdateKey("down")
	}
	model.UpdateKey("enter")
	typeText(model, "-v2")
	model.UpdateKey("enter")
	view := model.View()
	assertContains(t, view, "OpenSearch URL           https://opensearch.local:9200-v2")
	assertSettingsHasNoRestartState(t, view)

	model.settingsCursor = model.backSettingsRow()
	model.UpdateKey("enter")
	assertContains(t, model.View(), "Welcome. SCALA normalizes")
}

func TestSettingsSourceURLChangesHotReloadWithoutPendingMarkers(t *testing.T) {
	model := NewModel()
	typeText(model, "/settings")
	model.UpdateKey("enter")
	model.UpdateKey("down")
	model.UpdateKey("enter")
	typeText(model, "-v2")
	model.UpdateKey("enter")

	view := model.View()
	assertContains(t, view, "Splunk URL               https://splunk.local:8089-v2")
	assertSettingsHasNoRestartState(t, view)
}

func assertSettingsHasNoRestartState(t *testing.T, view string) {
	t.Helper()
	assertNotContains(t, view, "pending")
	assertNotContains(t, view, "restart")
	assertNotContains(t, view, "Restart")
	assertNotContains(t, view, "Apply pending changes")
}
