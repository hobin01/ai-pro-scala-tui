package app

import "testing"

func TestInitialModelRendersSCALA(t *testing.T) {
	model := NewModel()

	view := model.View()

	assertContains(t, view, "SCALA")
	assertContains(t, view, "Collect & Normalize")
	assertContains(t, view, "View Results")
	assertNotContains(t, view, "Header | Content | Input | Footer")
	assertContains(t, view, "ctrl+c quit")
}

func TestSourceSelectionToWorkflowGate(t *testing.T) {
	model := NewModel()

	model.UpdateKey("enter")
	assertContains(t, model.View(), "Source Selection")

	model.UpdateKey("space")
	model.UpdateKey("enter")
	assertContains(t, model.View(), "Select at least 2 sources")

	model.UpdateKey("down")
	model.UpdateKey("space")
	model.UpdateKey("enter")
	assertContains(t, model.View(), "Data Samples")
	assertContains(t, model.View(), "Fetching samples")
	model.AdvanceLoading()
	assertContains(t, model.View(), "[1/2]")
	assertContains(t, model.View(), "src_ip")

	model.UpdateKey("enter")
	assertContains(t, model.View(), "Agent Workflow Graph")
	assertContains(t, model.View(), "Start pipeline")
}

func TestUnknownCommandAndEmptySelectionGuard(t *testing.T) {
	model := NewModel()

	typeText(model, "/lineag")
	model.UpdateKey("enter")
	assertContains(t, model.View(), `Unknown command "/lineag". Try /help.`)

	model = NewModel()
	model.UpdateKey("enter")
	model.UpdateKey("enter")
	assertContains(t, model.View(), "Select at least 2 sources")
	assertContains(t, model.View(), "selected: 0")
}

func TestCommandHelpAndDataSamplePagination(t *testing.T) {
	model := newModelAtDataSamples()

	assertContains(t, model.View(), "[1/2]")
	model.UpdateKey("right")
	view := model.View()
	assertContains(t, view, "[2/2]")
	assertContains(t, view, "clientip")
	assertContains(t, view, "raw_msg")

	typeText(model, "/help")
	model.UpdateKey("enter")
	assertContains(t, model.View(), "Commands")
	assertContains(t, model.View(), "/settings")
}

func TestUnknownCommandRendersErrorAndKeepsInput(t *testing.T) {
	model := NewModel()

	typeText(model, "/lineag")
	model.UpdateKey("enter")
	view := model.View()

	assertContains(t, view, `✗ Unknown command "/lineag". Try /help.`)
	assertContains(t, view, "> /lineag")
}
