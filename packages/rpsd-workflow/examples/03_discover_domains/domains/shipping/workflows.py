"""
Shipping domain workflows and activities.

These will be auto-discovered by the WorkflowEngine.discover_domains() method.
The domain name "shipping" is automatically extracted from the module path:
    domains.shipping.workflows -> domain: "shipping"
"""

from rpsd_workflow import activity, workflow


@workflow(name="ship_order", description="Ship an order to the customer")
def ship_order_workflow(ctx, input_data):
    """Orchestrate the shipping process for an order."""
    return {
        "order_id": input_data.get("order_id"),
        "tracking_number": f"TRK-{input_data.get('order_id', 'UNKNOWN')}",
        "status": "shipped",
    }


@workflow(name="return_order", description="Process a return shipment")
def return_order_workflow(ctx, input_data):
    """Handle return shipping for an order."""
    return {
        "order_id": input_data.get("order_id"),
        "return_label": f"RET-{input_data.get('order_id', 'UNKNOWN')}",
        "status": "return_initiated",
    }


@activity(name="get_shipping_rate", description="Get shipping rate for an order")
def get_shipping_rate_activity(input_data):
    """Calculate shipping rate based on destination and weight."""
    weight = input_data.get("weight_kg", 1.0)
    destination = input_data.get("destination", "domestic")
    base_rate = 5.0 if destination == "domestic" else 15.0
    return {
        "rate": base_rate + (weight * 2.0),
        "currency": "USD",
        "estimated_days": 3 if destination == "domestic" else 7,
    }


@activity(name="create_shipping_label", description="Create shipping label")
def create_shipping_label_activity(input_data):
    """Generate a shipping label for the order."""
    return {
        "label_url": f"https://labels.example.com/{input_data.get('order_id')}",
        "carrier": input_data.get("carrier", "default"),
    }
