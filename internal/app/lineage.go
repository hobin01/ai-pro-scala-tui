package app

// lookupLineage는 입력 _id를 lineage.lookup 요청으로 큐에 넣는다.
func (m *Model) lookupLineage(id string) {
	m.lineageLoading = true
	m.lineageLookupID = id
	m.lineageResult = nil
	m.lineageNotFound = ""
	m.queueBackendAction(BackendAction{
		Method: "lineage.lookup",
		Params: LineageLookupParams{OpenSearchID: id},
	})
}

// resolveLineage는 mock lineage map에서 조회 결과를 채운다.
func (m *Model) resolveLineage() {
	id := m.lineageLookupID
	record, ok := m.lineage[id]
	m.lineageLoading = false
	m.lineageResult = nil
	m.lineageNotFound = ""
	if !ok {
		m.lineageNotFound = `No lineage found for _id "` + id + `"`
		return
	}
	m.lineageResult = &record
}

// clearLineage는 Lineage Viewer의 조회 입력과 결과 상태를 비운다.
func (m *Model) clearLineage() {
	m.lineageLoading = false
	m.lineageLookupID = ""
	m.lineageResult = nil
	m.lineageNotFound = ""
}
