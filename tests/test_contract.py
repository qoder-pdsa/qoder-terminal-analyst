"""确保 pydantic 事件模型与 api/agent-event.schema.json 保持一致。"""

import json
from pathlib import Path
from typing import get_args

from qoder_analyst.events import AgentEvent

SCHEMA = json.loads((Path(__file__).parents[1] / "api" / "agent-event.schema.json").read_text())


def _model_types() -> dict[str, set[str]]:
    union = get_args(get_args(AgentEvent)[0])
    return {
        model.model_fields["type"].default: {
            name
            for name, field in model.model_fields.items()
            if field.is_required() or name == "type"
        }
        for model in union
    }


def test_event_types_match_schema() -> None:
    schema_types = {variant["properties"]["type"]["const"] for variant in SCHEMA["oneOf"]}
    assert set(_model_types()) == schema_types


def test_required_fields_match_schema() -> None:
    models = _model_types()
    for variant in SCHEMA["oneOf"]:
        event_type = variant["properties"]["type"]["const"]
        assert set(variant["required"]) == models[event_type], event_type
