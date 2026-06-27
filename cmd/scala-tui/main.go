package main

import (
	"fmt"
	"os"
	"strings"
	"time"

	"charm.land/bubbles/v2/spinner"
	tea "charm.land/bubbletea/v2"
	"charm.land/lipgloss/v2"
	"github.com/charmbracelet/colorprofile"
	"github.com/hobin01/ai-pro-scala-tui/internal/app"
)

type tickMsg time.Time

type tuiModel struct {
	core    *app.Model
	spinner spinner.Model
}

func main() {
	model := tuiModel{
		core:    app.NewModel(),
		spinner: spinner.New(spinner.WithStyle(lipgloss.NewStyle().Foreground(lipgloss.Color("45")))),
	}
	if _, err := tea.NewProgram(model, tea.WithColorProfile(colorprofile.ANSI256)).Run(); err != nil {
		fmt.Fprintf(os.Stderr, "scala-tui: %v\n", err)
		os.Exit(1)
	}
}

func (m tuiModel) Init() tea.Cmd {
	return tick()
}

func (m tuiModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tickMsg:
		m.core.AdvancePipeline()
		return m, tick()
	case tea.WindowSizeMsg:
		m.core.SetSize(msg.Width, msg.Height)
		return m, nil
	case tea.KeyPressMsg:
		if m.core.UpdateKey(msg.String()) {
			return m, tea.Quit
		}
	}
	var cmd tea.Cmd
	m.spinner, cmd = m.spinner.Update(msg)
	if cmd != nil {
		return m, cmd
	}
	if m.core.IsPipelineRunning() {
		return m, tick()
	}
	return m, nil
}

func (m tuiModel) View() tea.View {
	content := m.core.View()
	content = strings.Replace(content, "{spinner}", m.spinner.View(), 1)
	view := tea.NewView(content)
	view.AltScreen = true
	return view
}

func tick() tea.Cmd {
	return tea.Tick(350*time.Millisecond, func(t time.Time) tea.Msg {
		return tickMsg(t)
	})
}
