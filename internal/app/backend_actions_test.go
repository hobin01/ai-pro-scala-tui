package app

import "testing"

func TestBackendActionContract(t *testing.T) {
	model := NewModel()

	model.RequestInitialData()
	action, ok := model.ConsumeBackendAction()
	if !ok {
		t.Fatal("expected initial settings.get action")
	}
	if action.Method != "settings.get" {
		t.Fatalf("initial action = %q, want settings.get", action.Method)
	}

	model.ApplySettings(BackendSettings{
		Agents: map[string]BackendAgentSettings{
			"orchestrator":    {Model: "gpt-5.4"},
			"schema_profiler": {Model: "gpt-5.4-mini"},
			"normalization":   {Model: "gpt-5.4"},
			"validator":       {Model: "gpt-5.4"},
		},
		Sources: map[string]BackendSourceSettings{
			"elasticsearch": {URL: "http://localhost:9200", Indices: []string{"logs-2026"}},
			"splunk":        {URL: "https://localhost:8089", Indices: []string{"main"}},
		},
		Output: BackendOutputSettings{
			OpenSearch: BackendOpenSearchSettings{
				URL:   "http://localhost:9201",
				Index: "scala-normalized",
			},
		},
		Consoles: map[string]BackendConsoleSettings{
			"kibana":     {URL: "http://localhost:5601"},
			"splunk":     {URL: "http://localhost:8000"},
			"opensearch": {URL: "http://localhost:5602"},
		},
		OpenAIAPIKeyMasked: "sk-****-test",
	})

	model.UpdateKey("enter")
	assertContains(t, model.View(), "logs-2026")
	model.UpdateKey("space")
	model.UpdateKey("down")
	model.UpdateKey("space")
	model.UpdateKey("enter")
	action = mustConsumeAction(t, model, "samples.fetch")
	samplesParams := action.Params.(SamplesFetchParams)
	if len(samplesParams.Sources) != 2 {
		t.Fatalf("samples sources = %d, want 2", len(samplesParams.Sources))
	}

	model.ApplySamplesProgress(SampleFetchProgress{
		Target: SourceRef{Solution: "elasticsearch", Index: "logs-2026"},
		Status: "fetching",
	})
	model.ApplySamplesResult(SamplesFetchResult{
		Indices: []IndexSamples{
			{
				Solution: "elasticsearch",
				Index:    "logs-2026",
				Fields: []FieldSample{
					{Name: "src_ip", Type: "ip", Samples: []any{"10.0.0.5"}},
				},
			},
		},
	})
	view := model.View()
	assertContains(t, view, "src_ip")
	assertContains(t, view, "10.0.0.5")

	model.UpdateKey("enter")
	model.UpdateKey("enter")
	action = mustConsumeAction(t, model, "pipeline.run")
	pipelineParams := action.Params.(PipelineRunParams)
	if len(pipelineParams.Sources) != 2 {
		t.Fatalf("pipeline sources = %d, want 2", len(pipelineParams.Sources))
	}
	model.ApplyPipelineStarted("run-1")
	model.ApplyProgress(BackendProgress{Agent: "schema_profiler", Message: "profiled fields"})
	model.ApplyFeedbackRequest("srv-1", FeedbackRequest{
		Field:          FeedbackField{SourceField: "clientip", Type: "string", Samples: []any{"10.0.0.5"}},
		Recommendation: FeedbackRecommendation{OCSFField: "src_endpoint.ip", OCSFType: "ip", Why: "source IP"},
	})
	assertContains(t, model.View(), "clientip")
	model.UpdateKey("enter")
	action = mustConsumeAction(t, model, "feedback.request")
	feedbackParams := action.Params.(FeedbackResponse)
	if feedbackParams.Decision != "approve" || action.RequestID != "srv-1" {
		t.Fatalf("feedback action = %#v", action)
	}
	model.ApplyRunStatus(RunStatus{
		Status:         "completed",
		OpenSearchLink: "http://localhost:9201/scala-normalized",
		Summary:        RunSummary{Mapped: 13, KeptRaw: 2, Loaded: 2, Lineage: 2, Cached: 1},
	})
	assertContains(t, model.View(), "http://localhost:9201/scala-normalized")

	typeText(model, "/lineage-viewer")
	model.UpdateKey("enter")
	typeText(model, "scala-run-1")
	model.UpdateKey("enter")
	action = mustConsumeAction(t, model, "lineage.lookup")
	lineageParams := action.Params.(LineageLookupParams)
	if lineageParams.OpenSearchID != "scala-run-1" {
		t.Fatalf("lineage id = %q", lineageParams.OpenSearchID)
	}
	model.ApplyLineageResult(LineageLookupResult{
		Found: true,
		Metadata: LineageMetadata{
			SourceSolution:  "splunk",
			SourceIndex:     "main",
			SourceDocID:     "raw-1",
			OpenSearchIndex: "scala-normalized",
			OpenSearchID:    "scala-run-1",
		},
		RawDocument:        map[string]any{"clientip": "10.0.0.5"},
		NormalizedDocument: map[string]any{"src_endpoint.ip": "10.0.0.5"},
	})
	assertContains(t, model.View(), "src_endpoint.ip=10.0.0.5")

	typeText(model, "/agent-monitoring")
	model.UpdateKey("enter")
	action = mustConsumeAction(t, model, "monitoring.query")
	monitoringParams := action.Params.(MonitoringQueryParams)
	if monitoringParams.Scope != "session" {
		t.Fatalf("monitoring scope = %q", monitoringParams.Scope)
	}
	model.ApplyMonitoring(MonitoringResult{
		Scope: "session",
		AsOf:  "12:00",
		Total: MonitoringTotal{Runs: 1, Tokens: 100, Cost: 0.12, LastRunID: "run-1"},
		Agents: []MonitoringAgent{
			{Agent: "orchestrator", Model: "gpt-5.4", LastActivity: "showed final result", Tokens: 100, Cost: 0.12},
		},
	})
	assertContains(t, model.View(), "run-1")
	assertContains(t, model.View(), "$0.1200")
}

func mustConsumeAction(t *testing.T, model *Model, method string) BackendAction {
	t.Helper()
	action, ok := model.ConsumeBackendAction()
	if !ok {
		t.Fatalf("expected action %s", method)
	}
	if action.Method != method {
		t.Fatalf("action = %q, want %q", action.Method, method)
	}
	return action
}
