package app

// lookupLineage는 관련 동작을 처리한다.
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

// resolveLineage는 관련 동작을 처리한다.
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

// clearLineage는 관련 동작을 처리한다.
func (m *Model) clearLineage() {
	m.lineageLoading = false
	m.lineageLookupID = ""
	m.lineageResult = nil
	m.lineageNotFound = ""
}
