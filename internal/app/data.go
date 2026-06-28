package app

type source struct {
	id         string
	kind       string
	alias      string
	index      string
	docs       int
	fetchError string
	fields     []field
}

type field struct {
	name   string
	kind   string
	values []string
}

type settings struct {
	elasticsearchURL     string
	splunkURL            string
	elasticsearchIndices []string
	splunkIndices        []string
	openSearchURL        string
	orchestratorModel    string
	profilerModel        string
	normalizationModel   string
	validatorModel       string
	apiKeyMasked         string
	resultIndex          string
	kibanaURL            string
	splunkWebURL         string
	openSearchDash       string
}

type lineageRecord struct {
	id         string
	source     string
	rawMeta    []string
	rawDoc     []string
	normalMeta []string
	normalDoc  []string
}

type monitoringSnapshot struct {
	scope       string
	totalRuns   int
	totalDocs   int
	totalTokens int
	totalCost   string
	asOf        string
	lastRunID   string
	agentRows   []monitoringRow
	emptyState  bool
}

type monitoringRow struct {
	name     string
	model    string
	tokens   string
	cost     string
	activity string
}

func defaultSources() []source {
	return []source{
		{
			id:    "es-logs-2024",
			kind:  "Elasticsearch",
			alias: "es-prod",
			index: "logs-2024",
			docs:  1000,
			fields: []field{
				{name: "@timestamp", kind: "date", values: []string{"2026-06-25T01:02:03Z", "2026-06-25T01:02:04Z"}},
				{name: "src_ip", kind: "ip", values: []string{"10.0.0.5", "192.168.1.20", "172.16.0.9"}},
				{name: "dst_port", kind: "long", values: []string{"443", "8080", "22", "53", "3389"}},
				{name: "action", kind: "keyword", values: []string{"allow", "deny"}},
				{name: "user_name", kind: "text", values: []string{"alice", "bob", "(null)"}},
				{name: "bytes_out", kind: "long", values: []string{"1240", "88", "4096"}},
				{name: "tmp_note", kind: "text", values: []string{"\"test\"", "\"\"", "check-later"}},
			},
		},
		{
			id:         "es-firewall-idx",
			kind:       "Elasticsearch",
			alias:      "es-prod",
			index:      "firewall-idx",
			docs:       500,
			fetchError: "Connection refused (https://es-prod:9200).",
			fields: []field{
				{name: "src_ip", kind: "ip", values: []string{"10.0.0.5", "192.168.1.20"}},
				{name: "dst_port", kind: "long", values: []string{"443", "8080"}},
			},
		},
		{
			id:    "splunk-main",
			kind:  "Splunk",
			alias: "splunk-soc",
			index: "main",
			docs:  1000,
			fields: []field{
				{name: "_time", kind: "string", values: []string{"2026-06-25 01:02:03"}},
				{name: "clientip", kind: "string", values: []string{"\"10.0.0.5\"", "\"192.168.1.20\""}},
				{name: "port", kind: "string", values: []string{"\"443\"", "\"8080\""}},
				{name: "status", kind: "string", values: []string{"allow", "block"}},
				{name: "src_user", kind: "string", values: []string{"alice", "—", "bob"}},
				{name: "raw_msg", kind: "string", values: []string{"\"...syslog text...\""}},
			},
		},
		{
			id:    "splunk-security",
			kind:  "Splunk",
			alias: "splunk-soc",
			index: "security",
			docs:  1000,
			fields: []field{
				{name: "EventCode", kind: "number", values: []string{"4624", "4625", "4688"}},
				{name: "src_ip", kind: "string", values: []string{"10.0.7.14", "10.0.8.22", "<empty>"}},
				{name: "user", kind: "string", values: []string{"alice", "svc_backup", "bob"}},
			},
		},
	}
}

func defaultSettings() settings {
	return settings{
		elasticsearchURL:     "https://es.local:9200",
		splunkURL:            "https://splunk.local:8089",
		elasticsearchIndices: []string{"logs-2024", "firewall-idx"},
		splunkIndices:        []string{"main", "security"},
		openSearchURL:        "https://opensearch.local:9200",
		orchestratorModel:    "gpt-5.4",
		profilerModel:        "gpt-5.4",
		normalizationModel:   "gpt-5.4",
		validatorModel:       "gpt-5.4",
		apiKeyMasked:         "sk-****-demo",
		resultIndex:          "scala-normalized/security-events",
		kibanaURL:            "https://kibana.local:5601",
		splunkWebURL:         "https://splunk-soc:8000",
		openSearchDash:       "https://opensearch.local:5601",
	}
}

func defaultLineage() map[string]lineageRecord {
	return map[string]lineageRecord{
		"aZ12bQ8": {
			id:     "aZ12bQ8",
			source: "Splunk main",
			rawMeta: []string{
				"source_system=splunk-soc",
				"source_index=main",
				"source_sourcetype=pan:traffic",
			},
			rawDoc: []string{
				`clientip=10.0.7.14`,
				`dest_port="443"`,
				`action=allowed`,
				`custom_attr=waf=edge`,
			},
			normalMeta: []string{
				"_index=scala-normalized/security-events",
				"_id=aZ12bQ8",
				"schema=OCSF Network Activity",
			},
			normalDoc: []string{
				`src_endpoint.ip=10.0.7.14`,
				`dst_endpoint.port=443`,
				`activity_name=Allowed`,
				`custom_attr=waf=edge`,
			},
		},
	}
}

func defaultMonitoring(settings settings) []monitoringSnapshot {
	rows := []monitoringRow{
		{name: "Orchestrator", model: settings.orchestratorModel, tokens: "4,820 tokens", cost: "$0.0284"},
		{name: "Schema Profiler", model: settings.profilerModel, tokens: "3,420 tokens", cost: "$0.0198"},
		{name: "Normalization", model: settings.normalizationModel, tokens: "6,120 tokens", cost: "$0.0419"},
		{name: "Validator", model: settings.validatorModel, tokens: "2,460 tokens", cost: "$0.0142"},
		{name: "Load", model: "-- (no LLM)", tokens: "0 tokens", cost: "$0.0000"},
		{name: "Caching", model: "-- (no LLM)", tokens: "0 tokens", cost: "$0.0000"},
		{name: "Lineage", model: "-- (no LLM)", tokens: "0 tokens", cost: "$0.0000"},
	}
	return []monitoringSnapshot{
		{scope: "Session", totalRuns: 1, totalDocs: 2000, totalCost: "$0.0703", asOf: "2026-06-27 16:04 KST", lastRunID: "run-demo-001", agentRows: rows},
		{scope: "Today", totalRuns: 3, totalDocs: 6000, totalCost: "$0.2109", asOf: "2026-06-27 16:04 KST", lastRunID: "run-demo-003", agentRows: rows},
		{scope: "All-time", totalRuns: 0, totalDocs: 0, totalCost: "$0.0000", asOf: "2026-06-27 16:04 KST", lastRunID: "-", emptyState: true},
	}
}
