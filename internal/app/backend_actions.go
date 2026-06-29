package app

import (
	"fmt"
	"sort"
	"strings"
)

type BackendAction struct {
	Method    string
	Params    any
	RequestID string
}

type SourceRef struct {
	Solution string `json:"solution"`
	Index    string `json:"index"`
}

type SettingsSetParams struct {
	Key   string `json:"key"`
	Value any    `json:"value"`
}

type SamplesFetchParams struct {
	Sources []SourceRef `json:"sources"`
}

type PipelineRunParams struct {
	Sources []SourceRef `json:"sources"`
}

type LineageLookupParams struct {
	OpenSearchID string `json:"opensearch_id"`
}

type MonitoringQueryParams struct {
	Scope string `json:"scope"`
}

type FeedbackResponse struct {
	Decision string `json:"decision"`
	Comment  string `json:"comment,omitempty"`
}

type BackendSettings struct {
	Agents             map[string]BackendAgentSettings   `json:"agents"`
	Sources            map[string]BackendSourceSettings  `json:"sources"`
	Output             BackendOutputSettings             `json:"output"`
	Consoles           map[string]BackendConsoleSettings `json:"consoles"`
	OpenAIAPIKeyMasked string                            `json:"openai_api_key_masked"`
}

type BackendAgentSettings struct {
	Model string `json:"model"`
}

type BackendSourceSettings struct {
	URL     string   `json:"url"`
	Indices []string `json:"indices"`
}

type BackendOutputSettings struct {
	OpenSearch BackendOpenSearchSettings `json:"opensearch"`
}

type BackendOpenSearchSettings struct {
	URL   string `json:"url"`
	Index string `json:"index"`
}

type BackendConsoleSettings struct {
	URL string `json:"url"`
}

type SampleFetchProgress struct {
	Target  SourceRef `json:"target"`
	Status  string    `json:"status"`
	Message string    `json:"message"`
}

type SamplesFetchResult struct {
	Indices []IndexSamples `json:"indices"`
}

type IndexSamples struct {
	Solution string        `json:"solution"`
	Index    string        `json:"index"`
	Fields   []FieldSample `json:"fields"`
}

type FieldSample struct {
	Name    string `json:"name"`
	Type    string `json:"type"`
	Samples []any  `json:"samples"`
}

type BackendProgress struct {
	RunID   string `json:"run_id"`
	Agent   string `json:"agent"`
	Message string `json:"message"`
}

type RunStatus struct {
	RunID          string       `json:"run_id"`
	Status         string       `json:"status"`
	Error          string       `json:"error"`
	Summary        RunSummary   `json:"summary"`
	OpenSearchLink string       `json:"opensearch_link"`
	LineageRefs    []LineageRef `json:"lineage_refs"`
}

type RunSummary struct {
	Mapped  int `json:"mapped"`
	KeptRaw int `json:"kept_raw"`
	Loaded  int `json:"loaded"`
	Lineage int `json:"lineage"`
	Cached  int `json:"cached"`
}

type LineageRef struct {
	SourceSolution string `json:"source_solution"`
	SourceIndex    string `json:"source_index"`
	SourceDocID    string `json:"source_doc_id"`
	OpenSearchID   string `json:"opensearch_id"`
}

type FeedbackRequest struct {
	RunID          string                 `json:"run_id"`
	Field          FeedbackField          `json:"field"`
	Recommendation FeedbackRecommendation `json:"recommendation"`
	Options        []string               `json:"options"`
}

type FeedbackField struct {
	SourceField string `json:"source_field"`
	Type        string `json:"type"`
	Samples     []any  `json:"samples"`
}

type FeedbackRecommendation struct {
	OCSFField string `json:"ocsf_field"`
	OCSFType  string `json:"ocsf_type"`
	Action    string `json:"action"`
	Why       string `json:"why"`
}

type LineageLookupResult struct {
	Found              bool            `json:"found"`
	Metadata           LineageMetadata `json:"metadata"`
	RawDocument        map[string]any  `json:"raw_document"`
	NormalizedDocument map[string]any  `json:"normalized_document"`
}

type LineageMetadata struct {
	SourceSolution  string `json:"source_solution"`
	SourceIndex     string `json:"source_index"`
	SourceDocID     string `json:"source_doc_id"`
	OpenSearchIndex string `json:"opensearch_index"`
	OpenSearchID    string `json:"opensearch_id"`
}

type MonitoringResult struct {
	Scope  string            `json:"scope"`
	AsOf   string            `json:"as_of"`
	Total  MonitoringTotal   `json:"total"`
	Agents []MonitoringAgent `json:"agents"`
}

type MonitoringTotal struct {
	Runs       int      `json:"runs"`
	Tokens     int      `json:"tokens"`
	Cost       *float64 `json:"cost"`
	CostSource string   `json:"cost_source"`
	LastRunID  string   `json:"last_run_id"`
}

type MonitoringAgent struct {
	Agent        string  `json:"agent"`
	Model        string  `json:"model"`
	LastActivity string  `json:"last_activity"`
	Tokens       int     `json:"tokens"`
	Cost         float64 `json:"cost"`
}

func (m *Model) SetBackendRuntime(enabled bool) {
	m.backendRuntime = enabled
}

func (m *Model) RequestInitialData() {
	m.queueBackendAction(BackendAction{Method: "settings.get"})
}

func (m *Model) ConsumeBackendAction() (BackendAction, bool) {
	if len(m.backendActions) == 0 {
		return BackendAction{}, false
	}
	action := m.backendActions[0]
	copy(m.backendActions, m.backendActions[1:])
	m.backendActions = m.backendActions[:len(m.backendActions)-1]
	return action, true
}

func (m *Model) ApplySettings(result BackendSettings) {
	if result.OpenAIAPIKeyMasked != "" {
		m.settings.apiKeyMasked = result.OpenAIAPIKeyMasked
	}
	if agent, ok := result.Agents["orchestrator"]; ok && agent.Model != "" {
		m.settings.orchestratorModel = agent.Model
	}
	if agent, ok := result.Agents["schema_profiler"]; ok && agent.Model != "" {
		m.settings.profilerModel = agent.Model
	}
	if agent, ok := result.Agents["normalization"]; ok && agent.Model != "" {
		m.settings.normalizationModel = agent.Model
	}
	if agent, ok := result.Agents["validator"]; ok && agent.Model != "" {
		m.settings.validatorModel = agent.Model
	}
	if sourceSettings, ok := result.Sources["elasticsearch"]; ok {
		m.settings.elasticsearchURL = sourceSettings.URL
		m.settings.elasticsearchIndices = append([]string(nil), sourceSettings.Indices...)
	}
	if sourceSettings, ok := result.Sources["splunk"]; ok {
		m.settings.splunkURL = sourceSettings.URL
		m.settings.splunkIndices = append([]string(nil), sourceSettings.Indices...)
	}
	if result.Output.OpenSearch.URL != "" {
		m.settings.openSearchURL = result.Output.OpenSearch.URL
	}
	if result.Output.OpenSearch.Index != "" {
		m.settings.resultIndex = result.Output.OpenSearch.Index
	}
	if console, ok := result.Consoles["kibana"]; ok && console.URL != "" {
		m.settings.kibanaURL = console.URL
	}
	if console, ok := result.Consoles["splunk"]; ok && console.URL != "" {
		m.settings.splunkWebURL = console.URL
	}
	if console, ok := result.Consoles["opensearch"]; ok && console.URL != "" {
		m.settings.openSearchDash = console.URL
	}
	m.sources = sourcesFromSettings(m.settings)
	m.selected = reconcileSelected(m.selected, m.sources)
	m.monitoring = defaultMonitoring(m.settings)
	m.notice = "Settings loaded from backend."
}

func (m *Model) ApplySamplesProgress(progress SampleFetchProgress) {
	if progress.Status == "error" {
		m.updateSource(progress.Target, func(source *source) {
			source.fetchError = progress.Message
		})
		m.notice = "Sample fetch failed: " + progress.Target.Index
		return
	}
	if progress.Status == "fetching" {
		m.notice = "Fetching samples from " + progress.Target.Index + "..."
		return
	}
	if progress.Status == "done" {
		m.notice = "Samples fetched from " + progress.Target.Index + "."
	}
}

func (m *Model) ApplySamplesResult(result SamplesFetchResult) {
	for _, index := range result.Indices {
		ref := SourceRef{Solution: index.Solution, Index: index.Index}
		m.updateSource(ref, func(source *source) {
			source.fetchError = ""
			source.fields = fieldsFromBackend(index.Fields)
			source.docs = max(source.docs, 0)
		})
	}
	m.sampleLoading = false
	m.notice = "Samples loaded from backend."
}

func (m *Model) ApplyPipelineStarted(runID string) {
	m.activeRunID = runID
	m.route = routeFeedback
	m.pipelineRunning = true
	m.pipelineDone = false
	m.feedbackWaiting = false
	m.stream = append(m.stream, "Pipeline accepted by backend: "+runID)
}

func (m *Model) ApplyProgress(progress BackendProgress) {
	message := progress.Message
	if progress.Agent != "" {
		message = agentLabel(progress.Agent) + ": " + message
	}
	if message != "" {
		m.stream = append(m.stream, message)
	}
}

func (m *Model) ApplyOutputChunk(text string) {
	if text != "" {
		m.stream = append(m.stream, text)
	}
}

func (m *Model) ApplyFeedbackRequest(requestID string, request FeedbackRequest) {
	m.route = routeFeedback
	m.pipelineRunning = false
	m.feedbackWaiting = true
	m.feedbackCursor = 0
	m.feedbackRequestID = requestID
	m.feedbackRequest = &request
	m.stream = append(m.stream, "Human review requested for "+request.Field.SourceField)
}

func (m *Model) ApplyRunStatus(status RunStatus) {
	if status.RunID != "" {
		m.activeRunID = status.RunID
	}
	switch status.Status {
	case "running":
		m.pipelineRunning = true
		m.pipelineDone = false
		m.stream = append(m.stream, "Run status: running")
	case "completed":
		m.pipelineRunning = false
		m.feedbackWaiting = false
		m.pipelineDone = true
		m.lastRunStatus = &status
		m.stream = append(m.stream, "Pipeline complete")
		if status.OpenSearchLink != "" {
			m.stream = append(m.stream, status.OpenSearchLink)
		}
	case "failed":
		m.pipelineRunning = false
		m.feedbackWaiting = false
		m.pipelineDone = true
		if status.Error == "" {
			status.Error = "unknown backend error"
		}
		m.lastRunStatus = &status
		m.stream = append(m.stream, "Pipeline failed: "+status.Error)
	}
}

func (m *Model) ApplyLineageProgress(message string) {
	if message != "" {
		m.notice = message
	}
}

func (m *Model) ApplyLineageResult(result LineageLookupResult) {
	m.lineageLoading = false
	m.lineageResult = nil
	m.lineageNotFound = ""
	if !result.Found {
		m.lineageNotFound = `No lineage found for _id "` + m.lineageLookupID + `"`
		return
	}
	id := result.Metadata.OpenSearchID
	if id == "" {
		id = m.lineageLookupID
	}
	record := lineageRecord{
		id:     id,
		source: strings.TrimSpace(result.Metadata.SourceSolution + " " + result.Metadata.SourceIndex),
		rawMeta: []string{
			"source_system=" + result.Metadata.SourceSolution,
			"source_index=" + result.Metadata.SourceIndex,
			"source_doc_id=" + result.Metadata.SourceDocID,
		},
		rawDoc: mapLines(result.RawDocument),
		normalMeta: []string{
			"_index=" + result.Metadata.OpenSearchIndex,
			"_id=" + id,
			"schema=OCSF",
		},
		normalDoc: mapLines(result.NormalizedDocument),
	}
	m.lineageResult = &record
}

func (m *Model) ApplyMonitoring(result MonitoringResult) {
	snapshot := monitoringSnapshot{
		scope:       displayScope(result.Scope),
		totalRuns:   result.Total.Runs,
		totalTokens: result.Total.Tokens,
		totalCost:   monitoringTotalCost(result.Total),
		asOf:        result.AsOf,
		lastRunID:   result.Total.LastRunID,
		emptyState:  result.Total.Runs == 0 && result.Total.Tokens == 0,
	}
	for _, agent := range result.Agents {
		snapshot.agentRows = append(snapshot.agentRows, monitoringRow{
			name:     agentLabel(agent.Agent),
			model:    emptyDash(agent.Model),
			tokens:   fmt.Sprintf("%d tokens", agent.Tokens),
			cost:     "--",
			activity: emptyDash(agent.LastActivity),
		})
	}
	scope := clamp(scopeIndex(result.Scope), 0, 2)
	for len(m.monitoring) < 3 {
		m.monitoring = append(m.monitoring, monitoringSnapshot{emptyState: true})
	}
	m.monitoring[scope] = snapshot
	m.monitoringScope = scope
}

func (m *Model) ApplyBackendError(method string, message string) {
	if message == "" {
		message = "backend request failed"
	}
	switch method {
	case "samples.fetch":
		m.sampleLoading = false
	case "lineage.lookup":
		m.lineageLoading = false
	case "pipeline.run":
		m.pipelineRunning = false
	}
	m.notice = "✗ " + method + ": " + message
}

func (m *Model) queueBackendAction(action BackendAction) {
	m.backendActions = append(m.backendActions, action)
}

func (m *Model) queueSamplesFetch() {
	m.queueBackendAction(BackendAction{
		Method: "samples.fetch",
		Params: SamplesFetchParams{Sources: sourceRefs(m.selectedSources())},
	})
}

func (m *Model) queuePipelineRun() {
	m.queueBackendAction(BackendAction{
		Method: "pipeline.run",
		Params: PipelineRunParams{Sources: sourceRefs(m.selectedSources())},
	})
}

func (m *Model) queueMonitoringQuery() {
	m.queueBackendAction(BackendAction{
		Method: "monitoring.query",
		Params: MonitoringQueryParams{Scope: scopeName(m.monitoringScope)},
	})
}

func (m *Model) queueFeedbackResponse(decision string, comment string) {
	if m.feedbackRequestID == "" {
		return
	}
	m.queueBackendAction(BackendAction{
		Method:    "feedback.request",
		RequestID: m.feedbackRequestID,
		Params: FeedbackResponse{
			Decision: decision,
			Comment:  comment,
		},
	})
	m.feedbackRequestID = ""
}

func (m *Model) updateSource(ref SourceRef, update func(*source)) {
	for i := range m.sources {
		if m.sources[i].index == ref.Index && solutionFromKind(m.sources[i].kind) == ref.Solution {
			update(&m.sources[i])
			return
		}
	}
}

func sourcesFromSettings(settings settings) []source {
	sources := make([]source, 0, len(settings.elasticsearchIndices)+len(settings.splunkIndices))
	for _, index := range settings.elasticsearchIndices {
		sources = append(sources, source{
			id:    "elasticsearch-" + index,
			kind:  "Elasticsearch",
			alias: "elasticsearch",
			index: index,
		})
	}
	for _, index := range settings.splunkIndices {
		sources = append(sources, source{
			id:    "splunk-" + index,
			kind:  "Splunk",
			alias: "splunk",
			index: index,
		})
	}
	return sources
}

func reconcileSelected(previous map[string]bool, sources []source) map[string]bool {
	next := make(map[string]bool, len(sources))
	for _, source := range sources {
		if previous[source.id] {
			next[source.id] = true
		}
	}
	return next
}

func sourceRefs(sources []source) []SourceRef {
	refs := make([]SourceRef, 0, len(sources))
	for _, source := range sources {
		refs = append(refs, SourceRef{
			Solution: solutionFromKind(source.kind),
			Index:    source.index,
		})
	}
	return refs
}

func solutionFromKind(kind string) string {
	switch strings.ToLower(kind) {
	case "elasticsearch":
		return "elasticsearch"
	case "splunk":
		return "splunk"
	default:
		return strings.ToLower(kind)
	}
}

func fieldsFromBackend(fields []FieldSample) []field {
	converted := make([]field, 0, len(fields))
	for _, item := range fields {
		converted = append(converted, field{
			name:   item.Name,
			kind:   item.Type,
			values: displayValues(item.Samples),
		})
	}
	return converted
}

func displayValues(values []any) []string {
	display := make([]string, 0, len(values))
	for _, value := range values {
		display = append(display, fmt.Sprint(value))
	}
	return display
}

func mapLines(values map[string]any) []string {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	lines := make([]string, 0, len(keys))
	for _, key := range keys {
		lines = append(lines, fmt.Sprintf("%s=%v", key, values[key]))
	}
	return lines
}

func agentLabel(value string) string {
	switch value {
	case "orchestrator":
		return "Orchestrator"
	case "schema_profiler":
		return "Schema Profiler"
	case "normalization":
		return "Normalization"
	case "validator":
		return "Validator"
	case "load":
		return "Load"
	case "caching":
		return "Caching"
	case "lineage":
		return "Lineage"
	default:
		if value == "" {
			return "-"
		}
		return value
	}
}

func scopeName(index int) string {
	switch clamp(index, 0, 2) {
	case 0:
		return "session"
	case 1:
		return "today"
	default:
		return "all_time"
	}
}

func scopeIndex(scope string) int {
	switch scope {
	case "today":
		return 1
	case "all_time":
		return 2
	default:
		return 0
	}
}

func displayScope(scope string) string {
	switch scope {
	case "today":
		return "Today"
	case "all_time":
		return "All-time"
	default:
		return "Session"
	}
}

func emptyDash(value string) string {
	if strings.TrimSpace(value) == "" {
		return "-"
	}
	return value
}

func monitoringTotalCost(total MonitoringTotal) string {
	if total.Cost == nil || total.CostSource == "unavailable" {
		return "cost unavailable"
	}
	return fmt.Sprintf("$%.4f", *total.Cost)
}

func parseCSV(value string) []string {
	parts := strings.Split(value, ",")
	items := make([]string, 0, len(parts))
	for _, part := range parts {
		item := strings.TrimSpace(part)
		if item != "" {
			items = append(items, item)
		}
	}
	return items
}
