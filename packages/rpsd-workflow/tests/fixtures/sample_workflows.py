"""
Sample workflows and activities for testing
"""

from rpsd_workflow.engine import default_engine


# Sample workflows for orders domain
@default_engine.workflow(
    name="process_order", domain="orders", description="Process customer order"
)
def process_order_workflow(ctx, input_data):
    """Process a customer order through multiple steps"""
    order_id = input_data.get("order_id")

    # Mock workflow logic
    result = {
        "order_id": order_id,
        "status": "processed",
        "steps_completed": ["validation", "payment", "fulfillment"],
    }

    return result


@default_engine.workflow(name="cancel_order", domain="orders")
def cancel_order_workflow(ctx, input_data):
    """Cancel an existing order"""
    return {"order_id": input_data.get("order_id"), "status": "cancelled"}


# Sample activities for orders domain
@default_engine.activity(name="validate_payment", domain="orders")
def validate_payment_activity(input_data):
    """Validate payment information"""
    return {"payment_valid": True, "transaction_id": "txn_123"}


@default_engine.activity(name="check_inventory", domain="orders")
def check_inventory_activity(input_data):
    """Check product inventory"""
    return {"in_stock": True, "quantity_available": 100}


# Sample workflows for validation domain
@default_engine.workflow(name="validate_file", domain="validation", version="1.0")
def validate_file_workflow(ctx, input_data):
    """Validate uploaded file"""
    return {
        "file_path": input_data.get("file_path"),
        "validation_status": "passed",
        "errors": [],
    }


@default_engine.activity(name="scan_virus", domain="validation")
def scan_virus_activity(input_data):
    """Scan file for viruses"""
    return {"clean": True, "scan_time": "2024-01-01T10:00:00Z"}


# Sample workflow with custom domain extraction
def custom_domain_workflow(ctx, input_data):
    """Workflow with custom domain logic"""
    return {"status": "completed"}


# Apply decorator manually to test different module patterns
custom_domain_workflow.__module__ = "workflows_shipping.workflows"
default_engine.workflow()(custom_domain_workflow)
