"""Skill schema and validation using jsonschema."""
from jsonschema import validate, ValidationError

SCHEMA = {
    "type": "object",
    "required": ["metadata", "inputs", "outputs", "implementation"],
    "properties": {
        "metadata": {
            "type": "object",
            "required": ["name", "version", "description", "author"],
            "properties": {
                "name": {"type": "string"},
                "version": {"type": "string"},
                "description": {"type": "string"},
                "author": {"type": "string"},
            },
        },
        "inputs": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "type", "required"],
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string"},
                    "required": {"type": "boolean"},
                },
            },
        },
        "outputs": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "type"],
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string"},
                },
            },
        },
        "implementation": {
            "type": "object",
            "required": ["language", "code"],
            "properties": {
                "language": {"type": "string"},
                "code": {"type": "string"},
            },
        },
    },
}

def validate_skill(skill: dict) -> None:
    try:
        validate(instance=skill, schema=SCHEMA)
    except ValidationError as e:
        raise ValueError(f"Skill validation failed: {e.message}")
