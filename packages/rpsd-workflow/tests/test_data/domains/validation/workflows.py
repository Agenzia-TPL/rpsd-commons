"""
Test workflow definitions for validation domain
"""

from rpsd_workflow.engine import default_engine


@default_engine.workflow(name="validate_file", domain="validation", version="1.0")
def validate_file_workflow(ctx, input_data):
    """Validate uploaded file"""
    return {
        "file_path": input_data.get("file_path"),
        "validation_result": "passed",
        "errors": [],
        "warnings": [],
    }


@default_engine.workflow(name="validate_data", domain="validation")
def validate_data_workflow(ctx, input_data):
    """Validate data structure"""
    return {"data_valid": True, "schema_version": "1.0", "validation_errors": []}


@default_engine.activity(name="check_file_format", domain="validation")
def check_file_format_activity(input_data):
    """Check if file format is supported"""
    return {
        "format_supported": True,
        "detected_format": input_data.get("expected_format", "json"),
    }


@default_engine.activity(name="scan_for_malware", domain="validation")
def scan_for_malware_activity(input_data):
    """Scan file for malware"""
    return {
        "clean": True,
        "scan_engine": "test_scanner",
        "scan_time": "2024-01-01T10:00:00Z",
    }
