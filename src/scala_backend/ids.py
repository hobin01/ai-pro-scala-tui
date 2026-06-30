from __future__ import annotations

import hashlib

from scala_backend.models import RawDocument


def stable_opensearch_id(doc: RawDocument) -> str:
    source_key = "\x00".join(
        [doc.source_solution, doc.source_index, doc.source_doc_id],
    )
    digest = hashlib.sha256(source_key.encode("utf-8")).hexdigest()[:24]
    return f"scala-{digest}"
