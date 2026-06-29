package app

import (
	"fmt"
	"strings"
)

// renderMain은 main menu와 View Results 하위 메뉴를 출력한다.
func (m *Model) renderMain(b *strings.Builder) {
	fmt.Fprintln(b, "Welcome. SCALA normalizes heterogeneous SIEM data into OCSF and loads")
	fmt.Fprintln(b, "it into OpenSearch with full document lineage.")
	fmt.Fprintln(b)
	fmt.Fprintln(b, "How it works")
	fmt.Fprintln(b, "  1. Select 2+ data sources  (Elasticsearch / Splunk indices)")
	fmt.Fprintln(b, "  2. Review field & value samples")
	fmt.Fprintln(b, "  3. Confirm the agent workflow, then run the pipeline")
	fmt.Fprintln(b)
	fmt.Fprintln(b, "What would you like to do?")
	items := []string{"Collect & Normalize", "View Results", "Settings"}
	for i, item := range items {
		marker := cursor(i == m.menuCursor)
		if item == "View Results" && m.viewResultsOpen {
			marker = "▾"
		}
		fmt.Fprintf(b, "  %s %-20s %s\n", marker, item, mainItemDescription(item))
		if item == "View Results" && m.viewResultsOpen {
			resultItems := []string{"Lineage Viewer", "Agent Workflow Graph", "Agent Monitoring"}
			for j, resultItem := range resultItems {
				fmt.Fprintf(b, "      %s %-21s %s\n", cursor(i == m.menuCursor && j == m.viewResultsCursor), resultItem, mainResultCommand(resultItem))
			}
		}
	}
}

// renderSources는 source 목록과 선택 상태를 출력한다.
func (m *Model) renderSources(b *strings.Builder) {
	fmt.Fprintln(b, "Source Selection")
	if len(m.sources) == 0 {
		fmt.Fprintln(b, "No data sources are configured yet.")
		fmt.Fprintln(b, "Add sources in Settings, then return here.")
		fmt.Fprintln(b, "> Open Settings   /settings")
		return
	}
	fmt.Fprintln(b, "Select 2 or more sources to normalize, then press enter.")
	fmt.Fprintf(b, "selected: %s\n\n", m.selectedSourceSummary())
	lastGroup := ""
	for i, source := range m.sources {
		group := source.kind + " · " + source.alias
		if group != lastGroup {
			fmt.Fprintf(b, "%s\n", strings.ReplaceAll(group, " · ", "  ·  "))
			lastGroup = group
		}
		box := "[ ]"
		if m.selected[source.id] {
			box = "[x]"
		}
		fmt.Fprintf(b, "  %s %s %s\n", cursor(i == m.sourceCursor), box, source.index)
	}
	if len(m.selectedSources()) >= 2 {
		fmt.Fprintf(b, "\n%s %s sources selected (%s) — press enter.\n", renderSuccess("✓"), fmtInt(len(m.selectedSources())), selectedKindSummary(m.selectedSources()))
	}
}

// renderSamples는 선택 source의 field sample 또는 loading 상태를 출력한다.
func (m *Model) renderSamples(b *strings.Builder) {
	selected := m.selectedSources()
	if len(selected) == 0 {
		fmt.Fprintln(b, "Data Samples\nNo selected sources.")
		return
	}
	if m.sampleLoading {
		fmt.Fprintln(b, "Data Samples")
		fmt.Fprintln(b, "{spinner} Fetching samples from selected sources...")
		for i, source := range selected {
			status := "·"
			if i == 0 {
				status = renderSuccess("✓")
			}
			if i == 1 {
				status = "{spinner}"
			}
			fmt.Fprintf(b, "  %-14s · %-18s %s\n", source.kind, source.index, status)
		}
		return
	}
	page := clamp(m.samplePage, 0, len(selected)-1)
	source := selected[page]
	fmt.Fprintln(b, "Data Samples")
	fmt.Fprintf(b, "Loaded %d sources · %d docs\n", len(selected), totalDocs(selected))
	fmt.Fprintf(b, "[%d/%d] %s · %s · 5 samples · %d fields\n\n", page+1, len(selected), source.kind, source.index, len(source.fields))
	if source.fetchError != "" {
		m.renderSampleFailure(b, source)
		return
	}
	fmt.Fprintln(b, "Field                Type     Sample values (≤5)")
	fmt.Fprintln(b, "────────────         ───────  ──────────────────────────────────────")
	for _, field := range source.fields {
		fmt.Fprintf(b, "%-20s %-8s %s\n", field.name, field.kind, strings.Join(limit(field.values, 5), " · "))
	}
	fmt.Fprintln(b, "\nPress enter to continue to the agent workflow graph.")
}

// renderSampleFailure는 sample fetch 실패 원인과 복구 선택지를 출력한다.
func (m *Model) renderSampleFailure(b *strings.Builder, source source) {
	fmt.Fprintln(b, "fetch failed")
	fmt.Fprintln(b, "✗ Could not fetch samples from this source.")
	fmt.Fprintf(b, "%s · %s\n", source.alias, source.index)
	fmt.Fprintln(b, source.fetchError)
	options := []string{"Retry", "Back to sources", "Open Settings"}
	for i, option := range options {
		fmt.Fprintf(b, "%s %s\n", cursor(i == m.sampleErrorCursor), option)
	}
}

// renderFeedback은 agent stream, human review 질문, 완료 요약을 출력한다.
func (m *Model) renderFeedback(b *strings.Builder) {
	fmt.Fprintln(b, "Human Feedback")
	if m.pipelineRunning {
		fmt.Fprintln(b, "{spinner} Agents running")
		fmt.Fprintln(b, "Mapping progress  ████████░░░░░░░░  8 / 13 fields")
	}
	for _, line := range tail(m.stream, 12) {
		fmt.Fprintf(b, "- %s\n", line)
	}
	if m.feedbackWaiting {
		request := m.feedbackRequest
		fieldName := "clientip"
		fieldType := "string"
		samples := []string{"\"10.0.0.5\"", "\"192.168.1.20\""}
		ocsfField := "src_endpoint.ip"
		ocsfType := "ip"
		why := "name+value look like a source IP; cast string→ip"
		if request != nil {
			fieldName = request.Field.SourceField
			fieldType = request.Field.Type
			samples = displayValues(request.Field.Samples)
			ocsfField = request.Recommendation.OCSFField
			ocsfType = request.Recommendation.OCSFType
			why = request.Recommendation.Why
		}
		fmt.Fprintln(b, "\nReview field recommendation")
		fmt.Fprintln(b, renderWarning("⚑ The agent is unsure about this field."))
		fmt.Fprintf(b, "  Source field   %-15s (%s)\n", fieldName, fieldType)
		fmt.Fprintf(b, "  Sample values  %s\n", strings.Join(samples, " · "))
		fmt.Fprintf(b, "  Recommended    %-15s (OCSF, %s)\n", ocsfField, ocsfType)
		fmt.Fprintf(b, "  Why            %s\n", why)
		fmt.Fprintln(b, "How should this map?")
		options := []string{"Approve recommendation", "Keep raw", "Comment & re-review"}
		for i, option := range options {
			fmt.Fprintf(b, "%s %s\n", cursor(i == m.feedbackCursor), option)
		}
	}
	if m.pipelineDone {
		summary := RunSummary{Mapped: 13, KeptRaw: 2, Loaded: 2000, Lineage: 2000, Cached: 5}
		link := m.settings.openSearchDash
		if m.lastRunStatus != nil {
			summary = m.lastRunStatus.Summary
			if m.lastRunStatus.OpenSearchLink != "" {
				link = m.lastRunStatus.OpenSearchLink
			}
		}
		fmt.Fprintf(b, "\n%s Normalization complete   %d mapped · %d kept raw (custom_attr)\n", renderSuccess("✓"), summary.Mapped, summary.KeptRaw)
		fmt.Fprintf(b, "%s Loaded %s docs to OpenSearch  (%s)\n", renderSuccess("✓"), fmtInt(summary.Loaded), m.settings.resultIndex)
		fmt.Fprintf(b, "%s Lineage recorded for %s docs  (PostgreSQL)\n", renderSuccess("✓"), fmtInt(summary.Lineage))
		fmt.Fprintf(b, "%s %s mappings cached  (Redis)\n", renderSuccess("✓"), fmtInt(summary.Cached))
		if m.lastRunStatus != nil && len(m.lastRunStatus.LineageRefs) > 0 {
			fmt.Fprintf(b, "Sample lineage _id: %s\n", m.lastRunStatus.LineageRefs[0].OpenSearchID)
		}
		fmt.Fprintln(b, "View results in OpenSearch:")
		fmt.Fprintf(b, "  %s\n", link)
		fmt.Fprintln(b, "Press enter to return to main.")
	}
}

// renderLineage는 OpenSearch _id 기준 raw/normalized 추적 결과를 출력한다.
func (m *Model) renderLineage(b *strings.Builder) {
	fmt.Fprintln(b, "Lineage Viewer")
	if m.lineageLoading {
		fmt.Fprintf(b, "{spinner} Looking up lineage for %q...\n", m.lineageLookupID)
		fmt.Fprintln(b, "  ✓ metadata (PostgreSQL)")
		fmt.Fprintln(b, "  {spinner} fetching original raw document (Splunk · main)")
		fmt.Fprintln(b, "  · fetching normalized document (OpenSearch)")
		return
	}
	if m.lineageResult == nil && m.lineageNotFound == "" {
		fmt.Fprintln(b, "Trace a normalized OpenSearch document back to its source.")
		fmt.Fprintln(b, "Enter an OpenSearch document _id to look up its lineage.")
		fmt.Fprintln(b, "(find the _id in the OpenSearch dashboard link from a run)")
		return
	}
	if m.lineageNotFound != "" {
		fmt.Fprintf(b, "%s %s\n", errorStyle.Render("✗"), m.lineageNotFound)
		fmt.Fprintln(b, "- the id may be wrong, or")
		fmt.Fprintln(b, "- the document was not produced by SCALA.")
		fmt.Fprintln(b, "Check the _id in the OpenSearch dashboard and try again.")
		return
	}
	record := m.lineageResult
	fmt.Fprintf(b, "_id %s · source %s\n\n", record.id, record.source)
	fmt.Fprintln(b, "▲ traces back to")
	renderBlock(b, "OpenSearch (normalized)", append(record.normalMeta, record.normalDoc...))
	renderBlock(b, "Source (raw)", append(record.rawMeta, record.rawDoc...))
	renderBlock(b, "Original raw document", record.rawDoc)
	renderBlock(b, "Normalized document (OCSF)", record.normalDoc)
}

// renderMonitoring은 scope별 agent token/activity snapshot을 출력한다.
func (m *Model) renderMonitoring(b *strings.Builder) {
	snapshots := m.monitoring
	scope := clamp(m.monitoringScope, 0, len(snapshots)-1)
	snapshot := snapshots[scope]
	fmt.Fprintln(b, "Agent Monitoring")
	fmt.Fprintf(b, "scope: %s · as of %s\n", snapshot.scope, snapshot.asOf)
	if snapshot.emptyState {
		fmt.Fprintln(b, "No agent activity yet")
		fmt.Fprintln(b, "Run a normalization pipeline first (Collect & Normalize).")
		return
	}
	if snapshot.totalTokens > 0 || snapshot.totalDocs == 0 {
		fmt.Fprintf(b, "Total  %d runs · %s · %d tokens   (last run %s)\n\n", snapshot.totalRuns, snapshot.totalCost, snapshot.totalTokens, snapshot.lastRunID)
	} else {
		fmt.Fprintf(b, "Total  %d docs · %s   (last run %s)\n\n", snapshot.totalDocs, snapshot.totalCost, snapshot.lastRunID)
	}
	fmt.Fprintln(b, "Agent             Model          Last activity         Tokens")
	fmt.Fprintln(b, "──────────────    ───────────    ───────────────────   ──────")
	for _, row := range snapshot.agentRows {
		activity := row.activity
		if activity == "" {
			activity = agentActivity(row.name)
		}
		fmt.Fprintf(b, "%-17s %-14s %-20s %s\n", row.name, row.model, activity, row.tokens)
	}
}

// renderSettings는 편집 가능한 설정 행과 read-only URL 행을 출력한다.
func (m *Model) renderSettings(b *strings.Builder) {
	fmt.Fprintln(b, "Settings")
	for i, row := range settingsRows(m) {
		fmt.Fprintf(b, "%s %s\n", cursor(i == m.settingsCursor), row)
	}
}
