package app

func (m *Model) lookupLineage(id string) {
	m.lineageLoading = true
	m.lineageLookupID = id
	m.lineageResult = nil
	m.lineageNotFound = ""
}

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

func (m *Model) clearLineage() {
	m.lineageLoading = false
	m.lineageLookupID = ""
	m.lineageResult = nil
	m.lineageNotFound = ""
}
