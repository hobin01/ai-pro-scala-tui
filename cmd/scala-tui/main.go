package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"strings"
	"time"

	"charm.land/bubbles/v2/spinner"
	tea "charm.land/bubbletea/v2"
	"charm.land/lipgloss/v2"
	"github.com/charmbracelet/colorprofile"
	"github.com/hobin01/ai-pro-scala-tui/internal/app"
	"github.com/hobin01/ai-pro-scala-tui/internal/backendrpc"
)

// tickMsg는 TUI 메시지 데이터를 표현한다.
type tickMsg time.Time

// backendReadyMsg는 TUI 메시지 데이터를 표현한다.
type backendReadyMsg struct{}

// backendErrMsg는 TUI 메시지 데이터를 표현한다.
type backendErrMsg struct {
	method string
	err    error
}

// backendSettingsMsg는 TUI 메시지 데이터를 표현한다.
type backendSettingsMsg app.BackendSettings

// backendSamplesMsg는 TUI 메시지 데이터를 표현한다.
type backendSamplesMsg app.SamplesFetchResult

// backendProgressMsg는 TUI 메시지 데이터를 표현한다.
type backendProgressMsg app.BackendProgress

// backendSampleProgressMsg는 TUI 메시지 데이터를 표현한다.
type backendSampleProgressMsg app.SampleFetchProgress

// backendRunStartedMsg는 TUI 메시지 데이터를 표현한다.
type backendRunStartedMsg string

// backendRunStatusMsg는 TUI 메시지 데이터를 표현한다.
type backendRunStatusMsg app.RunStatus

// backendOutputChunkMsg는 TUI 메시지 데이터를 표현한다.
type backendOutputChunkMsg string

// backendFeedbackMsg는 TUI 메시지 데이터를 표현한다.
type backendFeedbackMsg struct {
	id      backendrpc.RequestID
	request app.FeedbackRequest
}

// backendLineageMsg는 TUI 메시지 데이터를 표현한다.
type backendLineageMsg app.LineageLookupResult

// backendMonitoringMsg는 TUI 메시지 데이터를 표현한다.
type backendMonitoringMsg app.MonitoringResult

// tuiModel는 main에서 사용하는 타입을 정의한다.
type tuiModel struct {
	core     *app.Model
	spinner  spinner.Model
	backend  *backendrpc.Client
	mockMode bool
}

// main은 TUI 실행 흐름을 시작한다.
func main() {
	var backendAddr string
	var mockMode bool
	flag.StringVar(&backendAddr, "backend", envDefault("SCALA_BACKEND_ADDR", "127.0.0.1:8765"), "backend TCP JSON-RPC address")
	flag.BoolVar(&mockMode, "mock", os.Getenv("SCALA_TUI_MOCK") == "1", "run with fixture data instead of backend")
	flag.Parse()

	core := app.NewModel()
	var client *backendrpc.Client
	if !mockMode {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		var err error
		client, err = backendrpc.Dial(ctx, backendAddr)
		cancel()
		if err != nil {
			fmt.Fprintf(os.Stderr, "scala-tui: connect backend %s: %v\n", backendAddr, err)
			fmt.Fprintln(os.Stderr, "start the backend with `make docker-backend-up`, or use `--mock` for fixture mode")
			os.Exit(1)
		}
		defer client.Close()
		core.SetBackendRuntime(true)
		core.RequestInitialData()
	}

	model := tuiModel{
		core:     core,
		spinner:  spinner.New(spinner.WithStyle(lipgloss.NewStyle().Foreground(lipgloss.Color("45")))),
		backend:  client,
		mockMode: mockMode,
	}
	if _, err := tea.NewProgram(model, tea.WithColorProfile(colorprofile.ANSI256)).Run(); err != nil {
		fmt.Fprintf(os.Stderr, "scala-tui: %v\n", err)
		os.Exit(1)
	}
}

// Init는 관련 동작을 처리한다.
func (m tuiModel) Init() tea.Cmd {
	if !m.mockMode {
		return tea.Batch(tick(), m.nextBackendAction(), m.waitBackend())
	}
	return tick()
}

// Update는 모델 상태를 갱신한다.
func (m tuiModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tickMsg:
		m.core.AdvancePipeline()
		return m, tick()
	case tea.WindowSizeMsg:
		m.core.SetSize(msg.Width, msg.Height)
		return m, nil
	case tea.KeyPressMsg:
		if msg.String() == "ctrl+v" {
			return m, tea.ReadClipboard
		}
		if text, ok := m.core.CopyKey(msg.String()); ok {
			return m, tea.SetClipboard(text)
		}
		if m.core.UpdateKey(msg.String()) {
			return m, tea.Quit
		}
		return m, m.afterStateChange(nil)
	case tea.PasteMsg:
		m.core.Paste(msg.Content)
		return m, m.afterStateChange(nil)
	case tea.ClipboardMsg:
		m.core.Paste(msg.Content)
		return m, m.afterStateChange(nil)
	case backendSettingsMsg:
		m.core.ApplySettings(app.BackendSettings(msg))
		return m, m.afterStateChange(nil)
	case backendSamplesMsg:
		m.core.ApplySamplesResult(app.SamplesFetchResult(msg))
		return m, m.afterStateChange(nil)
	case backendSampleProgressMsg:
		m.core.ApplySamplesProgress(app.SampleFetchProgress(msg))
		return m, tea.Batch(m.afterStateChange(nil), m.waitBackend())
	case backendProgressMsg:
		m.core.ApplyProgress(app.BackendProgress(msg))
		return m, tea.Batch(m.afterStateChange(nil), m.waitBackend())
	case backendRunStartedMsg:
		m.core.ApplyPipelineStarted(string(msg))
		return m, m.afterStateChange(nil)
	case backendRunStatusMsg:
		m.core.ApplyRunStatus(app.RunStatus(msg))
		return m, tea.Batch(m.afterStateChange(nil), m.waitBackend())
	case backendOutputChunkMsg:
		m.core.ApplyOutputChunk(string(msg))
		return m, tea.Batch(m.afterStateChange(nil), m.waitBackend())
	case backendFeedbackMsg:
		m.core.ApplyFeedbackRequest(msg.id.String(), msg.request)
		return m, tea.Batch(m.afterStateChange(nil), m.waitBackend())
	case backendLineageMsg:
		m.core.ApplyLineageResult(app.LineageLookupResult(msg))
		return m, m.afterStateChange(nil)
	case backendMonitoringMsg:
		m.core.ApplyMonitoring(app.MonitoringResult(msg))
		return m, m.afterStateChange(nil)
	case backendErrMsg:
		m.core.ApplyBackendError(msg.method, msg.err.Error())
		return m, m.afterStateChange(nil)
	case backendReadyMsg:
		return m, m.waitBackend()
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

// View는 화면 문자열을 렌더링한다.
func (m tuiModel) View() tea.View {
	content := m.core.View()
	content = strings.Replace(content, "{spinner}", m.spinner.View(), 1)
	view := tea.NewView(content)
	view.AltScreen = true
	return view
}

// tick는 관련 동작을 처리한다.
func tick() tea.Cmd {
	return tea.Tick(350*time.Millisecond, func(t time.Time) tea.Msg {
		return tickMsg(t)
	})
}

// afterStateChange는 관련 동작을 처리한다.
func (m tuiModel) afterStateChange(extra tea.Cmd) tea.Cmd {
	commands := []tea.Cmd{}
	if extra != nil {
		commands = append(commands, extra)
	}
	if !m.mockMode {
		commands = append(commands, m.nextBackendAction())
	}
	if m.core.IsPipelineRunning() {
		commands = append(commands, tick())
	}
	return tea.Batch(commands...)
}

// nextBackendAction는 관련 동작을 처리한다.
func (m tuiModel) nextBackendAction() tea.Cmd {
	if m.backend == nil {
		return nil
	}
	action, ok := m.core.ConsumeBackendAction()
	if !ok {
		return nil
	}
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()
		switch action.Method {
		case "settings.get":
			var result app.BackendSettings
			if err := m.backend.Call(ctx, action.Method, action.Params, &result); err != nil {
				return backendErrMsg{method: action.Method, err: err}
			}
			return backendSettingsMsg(result)
		case "settings.set":
			if err := m.backend.Call(ctx, action.Method, action.Params, nil); err != nil {
				return backendErrMsg{method: action.Method, err: err}
			}
			return backendReadyMsg{}
		case "samples.fetch":
			var result app.SamplesFetchResult
			if err := m.backend.Call(ctx, action.Method, action.Params, &result); err != nil {
				return backendErrMsg{method: action.Method, err: err}
			}
			return backendSamplesMsg(result)
		case "pipeline.run":
			var result struct {
				RunID string `json:"run_id"`
			}
			if err := m.backend.Call(ctx, action.Method, action.Params, &result); err != nil {
				return backendErrMsg{method: action.Method, err: err}
			}
			return backendRunStartedMsg(result.RunID)
		case "lineage.lookup":
			var result app.LineageLookupResult
			if err := m.backend.Call(ctx, action.Method, action.Params, &result); err != nil {
				return backendErrMsg{method: action.Method, err: err}
			}
			return backendLineageMsg(result)
		case "monitoring.query":
			var result app.MonitoringResult
			if err := m.backend.Call(ctx, action.Method, action.Params, &result); err != nil {
				return backendErrMsg{method: action.Method, err: err}
			}
			return backendMonitoringMsg(result)
		case "feedback.request":
			response, ok := action.Params.(app.FeedbackResponse)
			if !ok {
				return backendErrMsg{method: action.Method, err: fmt.Errorf("invalid feedback response payload")}
			}
			if err := m.backend.Respond(ctx, backendrpc.RequestIDFromString(action.RequestID), response); err != nil {
				return backendErrMsg{method: action.Method, err: err}
			}
			return backendReadyMsg{}
		default:
			return backendErrMsg{method: action.Method, err: fmt.Errorf("unsupported backend action")}
		}
	}
}

// waitBackend는 관련 동작을 처리한다.
func (m tuiModel) waitBackend() tea.Cmd {
	if m.backend == nil {
		return nil
	}
	return func() tea.Msg {
		inbound, ok := <-m.backend.Incoming()
		if !ok {
			return backendErrMsg{method: "backend", err: fmt.Errorf("connection closed")}
		}
		return decodeInbound(inbound)
	}
}

// decodeInbound는 관련 동작을 처리한다.
func decodeInbound(inbound backendrpc.Inbound) tea.Msg {
	switch inbound.Method {
	case "progress":
		var sampleProgress app.SampleFetchProgress
		if err := json.Unmarshal(inbound.Params, &sampleProgress); err == nil && sampleProgress.Target.Index != "" {
			return backendSampleProgressMsg(sampleProgress)
		}
		var progress app.BackendProgress
		if err := json.Unmarshal(inbound.Params, &progress); err != nil {
			return backendErrMsg{method: inbound.Method, err: err}
		}
		return backendProgressMsg(progress)
	case "run.status":
		var status app.RunStatus
		if err := json.Unmarshal(inbound.Params, &status); err != nil {
			return backendErrMsg{method: inbound.Method, err: err}
		}
		return backendRunStatusMsg(status)
	case "output.chunk":
		var payload struct {
			Text string `json:"text"`
		}
		if err := json.Unmarshal(inbound.Params, &payload); err != nil {
			return backendErrMsg{method: inbound.Method, err: err}
		}
		return backendOutputChunkMsg(payload.Text)
	case "feedback.request":
		var request app.FeedbackRequest
		if err := json.Unmarshal(inbound.Params, &request); err != nil {
			return backendErrMsg{method: inbound.Method, err: err}
		}
		return backendFeedbackMsg{id: inbound.ID, request: request}
	default:
		return backendErrMsg{method: inbound.Method, err: fmt.Errorf("unsupported backend event")}
	}
}

// envDefault는 관련 동작을 처리한다.
func envDefault(key string, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}
