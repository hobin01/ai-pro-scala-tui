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

func TestSettingsRestartConfirmationFlow(t *testing.T) {
	model := NewModel()
	typeText(model, "/settings")
	model.UpdateKey("enter")
	for range 9 {
		model.UpdateKey("down")
	}
	model.UpdateKey("enter")
	typeText(model, "-v2")
	model.UpdateKey("enter")
	assertContains(t, model.View(), "pending restart: 1")
	assertContains(t, model.View(), "OpenSearch URL           https://opensearch.local:9200-v2 * pending")
	for range 5 {
		model.UpdateKey("down")
	}
	model.UpdateKey("enter")
	view := model.View()
	assertContains(t, view, "1 change needs a restart")
	assertContains(t, view, "Restart now")
	assertContains(t, view, "Keep editing")
	assertContains(t, view, "Leave without restart")

	model.UpdateKey("enter")
	view = model.View()
	assertContains(t, view, "restarting")
	assertContains(t, view, "restart: opensearch")
	model.AdvanceLoading()
	view = model.View()
	assertContains(t, view, "Restart complete")
	assertContains(t, view, "Settings applied")
}

func TestSplunkRestartPendingIsFieldSpecific(t *testing.T) {
	model := NewModel()
	typeText(model, "/settings")
	model.UpdateKey("enter")
	model.UpdateKey("down")
	model.UpdateKey("enter")
	typeText(model, "-v2")
	model.UpdateKey("enter")

	view := model.View()
	assertContains(t, view, "pending restart: 1")
	assertContains(t, view, "Splunk URL               https://splunk.local:8089-v2 * pending")
	assertNotContains(t, view, "Elasticsearch URL        https://es.local:9200 * pending")
	assertNotContains(t, view, "OpenSearch URL           https://opensearch.local:9200 * pending")

	for range 13 {
		model.UpdateKey("down")
	}
	model.UpdateKey("enter")
	view = model.View()
	assertContains(t, view, "1 change needs a restart")
	assertNotContains(t, view, "2 changes need a restart")
}
