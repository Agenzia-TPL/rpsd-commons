"""
Test workflow definitions for orders domain
"""

from rpsd_workflow.engine import default_engine


@default_engine.workflow(name="process_order", description="Process customer order")
def process_order_workflow(ctx, input_data):
    """Process a customer order"""
    return {
        "order_id": input_data.get("order_id"),
        "status": "processed",
        "total": 100.0,
    }


@default_engine.workflow(name="cancel_order", description="Cancel existing order")
def cancel_order_workflow(ctx, input_data):
    """Cancel a customer order"""
    return {
        "order_id": input_data.get("order_id"),
        "status": "cancelled",
        "refund_amount": 100.0,
    }


@default_engine.activity(name="validate_payment", description="Validate payment method")
def validate_payment_activity(input_data):
    """Validate customer payment"""
    return {
        "valid": True,
        "payment_method": input_data.get("payment_method", "credit_card"),
    }


@default_engine.activity(
    name="update_inventory", description="Update product inventory"
)
def update_inventory_activity(input_data):
    """Update inventory after order"""
    return {"updated": True, "remaining_stock": 50}
