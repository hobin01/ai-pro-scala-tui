from __future__ import annotations

import json
import re
import shutil
import ssl
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

import certifi

from scala_backend.errors import ProviderError

OCSF_RELEASE_URL = "https://github.com/ocsf/ocsf-schema/archive/refs/tags/{version}.zip"


@dataclass(frozen=True)
class OcsfField:
    """OcsfField 객체의 책임을 정의한다."""

    name: str
    type_name: str
    caption: str
    description: str


class LocalOcsfIndex:
    """LocalOcsfIndex 객체의 책임을 정의한다."""

    def __init__(self, path: Path) -> None:
        """객체 초기 상태를 준비한다."""
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def upsert(self, fields: list[OcsfField]) -> int:
        """upsert 동작을 처리한다."""
        data = [field.__dict__ for field in fields]
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        return len(fields)

    def query(self, text: str, top_k: int = 3) -> list[OcsfField]:
        """query 동작을 처리한다."""
        if not self.path.exists():
            return []
        data = json.loads(self.path.read_text())
        fields = [OcsfField(**item) for item in data]
        tokens = _tokens(text)
        ranked = sorted(fields, key=lambda field: _score(tokens, field), reverse=True)
        return ranked[:top_k]


def ingest_official_ocsf(version: str, target: Path) -> int:
    """ingest official ocsf 동작을 처리한다."""
    fields = load_official_ocsf_fields(version)
    return LocalOcsfIndex(target).upsert(fields)


def load_official_ocsf_fields(version: str) -> list[OcsfField]:
    """load official ocsf fields 데이터를 로드한다."""
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "ocsf.zip"
        try:
            _download_release(
                OCSF_RELEASE_URL.format(version=version),
                archive,
            )
        except OSError as exc:
            raise ProviderError(f"failed to download official OCSF {version}") from exc
        with zipfile.ZipFile(archive) as zip_file:
            fields = parse_ocsf_zip(zip_file)
    if not fields:
        fields = _fallback_fields()
    return fields


def parse_ocsf_zip(zip_file: zipfile.ZipFile) -> list[OcsfField]:
    """parse ocsf zip 값을 파싱한다."""
    fields: dict[str, OcsfField] = {}
    for name in zip_file.namelist():
        if not name.endswith(".json"):
            continue
        try:
            data = json.loads(zip_file.read(name).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, KeyError):
            continue
        for field in _extract_fields(data):
            fields[field.name] = field
    return sorted(fields.values(), key=lambda field: field.name)


def _download_release(url: str, archive: Path) -> None:
    """download release 내부 처리를 수행한다."""
    context = ssl.create_default_context(cafile=certifi.where())
    request = urllib.request.Request(url, headers={"User-Agent": "scala-backend"})
    with (
        urllib.request.urlopen(request, context=context, timeout=60) as response,
        archive.open("wb") as target,
    ):
        shutil.copyfileobj(response, target)


def _extract_fields(data: object) -> list[OcsfField]:
    """extract fields 내부 처리를 수행한다."""
    if not isinstance(data, dict):
        return []
    attrs = data.get("attributes")
    if isinstance(attrs, dict):
        return [
            OcsfField(
                name=str(name),
                type_name=str(value.get("type", "unknown"))
                if isinstance(value, dict)
                else "unknown",
                caption=str(value.get("caption", name))
                if isinstance(value, dict)
                else str(name),
                description=str(value.get("description", ""))
                if isinstance(value, dict)
                else "",
            )
            for name, value in attrs.items()
        ]
    found: list[OcsfField] = []
    for value in data.values():
        if isinstance(value, dict):
            found.extend(_extract_fields(value))
    return found


def _fallback_fields() -> list[OcsfField]:
    """fallback fields 내부 처리를 수행한다."""
    return [
        OcsfField("src_endpoint.ip", "ip", "Source IP", "Source endpoint IP address"),
        OcsfField(
            "dst_endpoint.port", "integer", "Destination Port", "Destination port"
        ),
        OcsfField("activity_name", "string", "Activity", "Observed activity name"),
    ]


def _score(tokens: set[str], field: OcsfField) -> int:
    """score 내부 처리를 수행한다."""
    haystack = _tokens(f"{field.name} {field.caption} {field.description}")
    return len(tokens & haystack)


def _tokens(text: str) -> set[str]:
    """tokens 내부 처리를 수행한다."""
    base = set(re.findall(r"[a-z0-9]+", text.lower().replace("_", " ")))
    expanded = set(base)
    for token in base:
        if token.endswith("ip") and len(token) > 2:
            expanded.add(token[:-2])
            expanded.add("ip")
    return expanded
