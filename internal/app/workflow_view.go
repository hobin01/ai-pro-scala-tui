package app

import (
	"fmt"
	"strings"
)

// renderWorkflow는 workflow gate 또는 static graph 본문을 출력한다.
func (m *Model) renderWorkflow(b *strings.Builder) {
	if m.workflowGate {
		m.renderWorkflowGate(b)
		return
	}
	for _, line := range workflowViewLines(m.settings) {
		fmt.Fprintln(b, line)
	}
}

// renderWorkflowGate는 pipeline 시작 전 확인 선택지를 출력한다.
func (m *Model) renderWorkflowGate(b *strings.Builder) {
	fmt.Fprintln(b, "Agent Workflow Graph")
	fmt.Fprintln(b, "State A와 동일한 흐름도 + agent 레전드")
	fmt.Fprintf(b, "\nRun the normalization pipeline on %d selected sources?\n", len(m.selectedSources()))
	options := []string{"Start pipeline", "Back to samples"}
	for i, option := range options {
		fmt.Fprintf(b, "%s %s\n", cursor(i == m.workflowCursor), option)
	}
}

// workflowViewLines는 static agent graph와 agent legend 줄을 만든다.
func workflowViewLines(settings settings) []string {
	return []string{
		"How SCALA processes your data (Agent pipeline topology)",
		"",
		"Sources: Elasticsearch · Splunk · (future)",
		"    └─▶ SIEM Connector ─▶ Orchestrator      (schema/sample)",
		"User ─▶ Orchestrator ─▶ Schema Profiler",
		"    Schema Profiler ─▶ Redis                (cache lookup)",
		"      ├─ miss ─▶ ChromaDB OCSF ─▶ Normalization",
		"      └─ hit  ─▶ reuse cached mapping ─▶ Normalization",
		"Normalization ─▶ Validator",
		"    └─ fail ─▶ Orchestrator ─▶ User         (human feedback)",
		"               User ─▶ Orchestrator ─▶ Validator",
		"               Validator ─▶ Validator ─▶ Normalization (re-chk)",
		"Normalization ─▶ Load    ─▶ OpenSearch",
		"              ├─▶ Caching ─▶ Redis",
		"              └─▶ Lineage ─▶ PostgreSQL",
		"    Load ─▶ Lineage                         (OpenSearch _id)",
		"Processing Agents ─▶ Orchestrator ─▶ User   (final result)",
		"",
		"Agent            Role                        Model",
		"───────────────  ──────────────────────────  ─────────────",
		fmt.Sprintf("Orchestrator     workflow 관리 · 사용자 소통   %s", settings.orchestratorModel),
		fmt.Sprintf("Schema Profiler  스키마 프로파일 · 캐시 조회    %s", settings.profilerModel),
		fmt.Sprintf("Normalization    정규화 Rule 생성 · 적용       %s", settings.normalizationModel),
		fmt.Sprintf("Validator        데이터 정합성 검증            %s", settings.validatorModel),
		"Load             정규화 데이터 적재            — (no LLM)",
		"Caching          매핑 캐시 저장                — (no LLM)",
		"Lineage          리니지 메타데이터 생성         — (no LLM)",
	}
}
