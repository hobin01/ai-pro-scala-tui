package main

import (
	"strings"
	"testing"

	"charm.land/bubbles/v2/spinner"
	tea "charm.land/bubbletea/v2"
	"github.com/hobin01/ai-pro-scala-tui/internal/app"
)

// TestBubbleTeaViewOutputsInitialView는 관련 동작을 검증한다.
func TestBubbleTeaViewOutputsInitialView(t *testing.T) {
	model := tuiModel{
		core:    app.NewModel(),
		spinner: spinner.New(),
	}

	view := model.View()

	if !strings.Contains(view.Content, "SCALA") {
		t.Fatalf("expected rendered output to contain SCALA, got:\n%s", view.Content)
	}
}

// TestBubbleTeaViewUsesAltScreen는 관련 동작을 검증한다.
func TestBubbleTeaViewUsesAltScreen(t *testing.T) {
	model := tuiModel{
		core:    app.NewModel(),
		spinner: spinner.New(),
	}

	view := model.View()

	if !view.AltScreen {
		t.Fatalf("expected Bubble Tea view to request alt screen for full-terminal rendering")
	}
}

// TestWindowSizeMessageUpdatesCoreDimensions는 관련 동작을 검증한다.
func TestWindowSizeMessageUpdatesCoreDimensions(t *testing.T) {
	model := tuiModel{
		core:    app.NewModel(),
		spinner: spinner.New(),
	}

	updated, _ := model.Update(tea.WindowSizeMsg{Width: 100, Height: 30})
	got := updated.(tuiModel)
	width, height := got.core.Size()

	if width != 100 || height != 30 {
		t.Fatalf("expected core size 100x30, got %dx%d", width, height)
	}
}
