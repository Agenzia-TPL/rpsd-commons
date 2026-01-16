"""
Order domain workflows and activities.

These will be auto-discovered by the WorkflowEngine.discover_domains() method.
The domain name "orders" is automatically extracted from the module path:
    domains.orders.workflows -> domain: "orders"
"""

from rpsd_workflow import activity, workflow


@workflow(name="process_order", description="Process a customer order")
def process_order_workflow(ctx, input_data):
    """Process a customer order through the fulfillment pipeline."""
    return {
        "order_id": input_data.get("order_id"),
        "status": "processed",
        "total": input_data.get("total", 0.0),
    }


@workflow(name="cancel_order", description="Cancel an existing order")
def cancel_order_workflow(ctx, input_data):
    """Cancel an existing order and initiate refund."""
    return {
        "order_id": input_data.get("order_id"),
        "status": "cancelled",
        "refund_initiated": True,
    }


@activity(name="validate_order", description="Validate order details")
def validate_order_activity(input_data):
    """Validate order has required fields and valid quantities."""
    order_id = input_data.get("order_id")
    items = input_data.get("items", [])
    return {
        "valid": bool(order_id and items),
        "order_id": order_id,
        "item_count": len(items),
    }


@activity(name="calculate_total", description="Calculate order total")
def calculate_total_activity(input_data):
    """Calculate the total price for an order."""
    items = input_data.get("items", [])
    total = sum(item.get("price", 0) * item.get("quantity", 1) for item in items)
    return {"total": total, "currency": "USD"}
