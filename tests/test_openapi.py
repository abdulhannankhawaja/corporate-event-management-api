"""Tests for generated OpenAPI metadata and examples."""

from app.main import app

EXPECTED_SUCCESS_STATUS = {
    ("/health", "get"): "200",
    ("/events", "post"): "201",
    ("/events", "get"): "200",
    ("/events/{event_id}", "get"): "200",
    ("/events/{event_id}", "put"): "200",
    ("/events/{event_id}", "delete"): "204",
    ("/events/{event_id}/registrations", "post"): "201",
    ("/events/{event_id}/registrations", "get"): "200",
    ("/registrations/{registration_id}", "delete"): "204",
    ("/auth/signup", "post"): "201",
    ("/auth/login", "post"): "200",
}


def test_openapi_defines_descriptive_tags() -> None:
    """Document each API tag with a description."""
    schema = app.openapi()

    tags = {tag["name"]: tag.get("description") for tag in schema["tags"]}
    assert set(tags) == {"Events", "Registrations", "Authentication", "Health"}
    assert all(tags.values())


def test_operations_document_success_status_codes_and_responses() -> None:
    """Document each route's success status and response representation."""
    schema = app.openapi()

    for (path, method), status_code in EXPECTED_SUCCESS_STATUS.items():
        operation = schema["paths"][path][method]
        assert status_code in operation["responses"]
        if status_code != "204":
            assert operation["responses"][status_code].get("content")


def test_success_response_models_have_examples() -> None:
    """Provide representative examples for successful response models."""
    schema = app.openapi()

    for model_name in (
        "EventRead",
        "RegistrationRead",
        "UserRead",
        "HealthRead",
        "Token",
    ):
        assert "example" in schema["components"]["schemas"][model_name]


def test_operations_document_error_schemas_and_examples() -> None:
    """Use the shared error schema and examples for documented error codes."""
    schema = app.openapi()
    error_codes = {"401", "404", "409", "422", "500"}

    for path in schema["paths"].values():
        for operation in path.values():
            if not isinstance(operation, dict) or "responses" not in operation:
                continue
            assert operation.get("summary")
            assert operation.get("description")
            for status, response in operation["responses"].items():
                if status not in error_codes:
                    continue
                content = response["content"]["application/json"]
                assert content["schema"]["$ref"].endswith("/ErrorResponse")
                assert content["example"]["detail"]


def test_request_bodies_have_examples() -> None:
    """Provide an example for every documented request body."""
    schema = app.openapi()

    for path in schema["paths"].values():
        for operation in path.values():
            if not isinstance(operation, dict):
                continue
            request_body = operation.get("requestBody")
            if request_body is None:
                continue
            for media in request_body["content"].values():
                if "example" in media or "examples" in media:
                    continue
                schema_reference = media["schema"]["$ref"]
                schema_name = schema_reference.rsplit("/", maxsplit=1)[-1]
                component = schema["components"]["schemas"][schema_name]
                assert "example" in component or "examples" in component
