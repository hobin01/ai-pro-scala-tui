import io
import json
import zipfile
from pathlib import Path

from scala_backend.ocsf import LocalOcsfIndex, parse_ocsf_zip


def test_ocsf_zip_parser_extracts_attributes() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_file:
        zip_file.writestr(
            "ocsf-schema-1.8.0/objects/network.json",
            json.dumps(
                {
                    "attributes": {
                        "src_endpoint.ip": {
                            "type": "ip",
                            "caption": "Source IP",
                            "description": "Source endpoint IP address",
                        }
                    }
                },
            ),
        )
    buffer.seek(0)

    with zipfile.ZipFile(buffer) as zip_file:
        fields = parse_ocsf_zip(zip_file)

    assert fields[0].name == "src_endpoint.ip"
    assert fields[0].type_name == "ip"


def test_local_ocsf_index_returns_matching_candidates(tmp_path: Path) -> None:
    index = LocalOcsfIndex(tmp_path / "ocsf.json")
    fields = parse_ocsf_zip(_fixture_zip())

    index.upsert(fields)

    candidates = index.query("clientip string 10.0.0.5")
    assert candidates[0].name == "src_endpoint.ip"


def _fixture_zip() -> zipfile.ZipFile:
    buffer = io.BytesIO()
    zip_file = zipfile.ZipFile(buffer, "w")
    zip_file.writestr(
        "schema.json",
        json.dumps(
            {
                "attributes": {
                    "src_endpoint.ip": {
                        "type": "ip",
                        "caption": "Client source IP",
                        "description": "Client IP address",
                    },
                    "dst_endpoint.port": {
                        "type": "integer",
                        "caption": "Destination Port",
                        "description": "Destination network port",
                    },
                }
            },
        ),
    )
    zip_file.close()
    buffer.seek(0)
    return zipfile.ZipFile(buffer)
