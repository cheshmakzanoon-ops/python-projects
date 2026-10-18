"""SARIF 2.1.0 export using official OASIS schema and stable partial fingerprints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import quote

import jsonschema

from pp_pytrace.reporting.models import Diagnostic
from pp_pytrace.rules.registry import RULES


def sarif(diagnostics: tuple[Diagnostic, ...]) -> dict[str, Any]:
    results = []
    for item in diagnostics:
        region = {
            "startLine": item.location.line,
            "startColumn": item.location.column,
            "endLine": item.location.end_line,
            "endColumn": max(item.location.end_column, item.location.column + 1)
            if item.location.end_line == item.location.line
            else item.location.end_column,
        }
        results.append(
            {
                "ruleId": item.rule_id,
                "level": "warning" if item.severity == "warning" else "error",
                "message": {"text": item.message},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": quote(item.path, safe="/")},
                            "region": region,
                        }
                    }
                ],
                "partialFingerprints": {"pytrace/v1": item.identifier},
                "properties": {"confidence": item.confidence, "coverage": item.coverage},
                "codeFlows": [
                    {
                        "threadFlows": [
                            {
                                "locations": [
                                    {
                                        "location": {
                                            "physicalLocation": {
                                                "artifactLocation": {
                                                    "uri": quote(item.path, safe="/")
                                                },
                                                "region": {"startLine": event.line},
                                            },
                                            "message": {"text": event.message},
                                        }
                                    }
                                    for event in item.evidence
                                ]
                            }
                        ]
                    }
                ],
            }
        )
    return {
        "version": "2.1.0",
        "$schema": "https://docs.oasis-open.org/sarif/sarif/v2.1.0/cos02/schemas/sarif-schema-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "PyTrace",
                        "version": "0.1.0",
                        "rules": [
                            {"id": key, "shortDescription": {"text": value}}
                            for key, value in RULES.items()
                        ],
                    }
                },
                "columnKind": "unicodeCodePoints",
                "results": results,
            }
        ],
    }


def validate(document: dict[str, Any]) -> None:
    schema = json.loads(Path(__file__).with_name("sarif-schema-2.1.0.json").read_text())
    jsonschema.Draft4Validator(schema).validate(document)
