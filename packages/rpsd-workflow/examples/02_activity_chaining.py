"""
Activity Chaining with Dapr Workflows

This example demonstrates the core pattern of Dapr workflows: calling activities
sequentially using `yield ctx.call_activity()`. This is how you build workflows
that orchestrate multiple steps.

What you'll learn:
- How to call activities from within a workflow using ctx.call_activity()
- How to chain activity results (output of one becomes input to next)
- How to handle conditional logic based on activity results
- The yield-based pattern that enables Dapr's durable execution

Important: Domains are Organizational Only
-----------------------------------------
The "domain" concept in rpsd-workflow is purely for organization and filtering.
When activities are registered with Dapr, they use only their function name
(e.g., "validate_order"), not the full domain-prefixed name ("orders.validate_order").

This means:
- Use function references when calling activities (type-safe, recommended)
- Domains help YOU organize code, but Dapr doesn't see them at runtime
- Activities from any domain can technically call activities from other domains

Running this example:
    uv run python packages/rpsd-workflow/examples/02_activity_chaining.py
"""

from rpsd_workflow import activity, default_engine, workflow

# =============================================================================
# Define Activities
# =============================================================================
# Activities are the individual units of work that the workflow orchestrates.
# Each activity should do ONE thing and return a result.


@activity(
    domain="orders",
    description="Validate order data and check required fields",
)
def validate_order(input_data: dict) -> dict:
    """
    Validate that the order has all required fields.

    Activities receive only input_data (no context) because they are
    stateless units of work that can be retried independently.
    """
    order_id = input_data.get("order_id")
    customer_email = input_data.get("email")
    items = input_data.get("items", [])

    errors = []
    if not order_id:
        errors.append("Missing order_id")
    if not customer_email:
        errors.append("Missing email")
    if not items:
        errors.append("No items in order")

    return {
        "valid": len(errors) == 0,
        "order_id": order_id,
        "errors": errors,
    }


@activity(
    domain="orders",
    description="Check inventory availability for order items",
)
def check_inventory(input_data: dict) -> dict:
    """Check if all items are in stock."""
    items = input_data.get("items", [])

    # Simulated inventory check
    available_items = []
    unavailable_items = []

    for item in items:
        # Simulate: items with quantity <= 10 are available
        if item.get("quantity", 0) <= 10:
            available_items.append(item)
        else:
            unavailable_items.append(item)

    return {
        "available": len(unavailable_items) == 0,
        "available_items": available_items,
        "unavailable_items": unavailable_items,
    }


@activity(
    domain="orders",
    description="Process payment for the order",
)
def process_payment(input_data: dict) -> dict:
    """Process the payment transaction."""
    amount = input_data.get("amount", 0)
    method = input_data.get("method", "credit_card")

    # Simulated payment processing
    success = amount > 0 and amount < 10000  # Simple validation

    return {
        "success": success,
        "amount": amount,
        "method": method,
        "transaction_id": f"TXN-{hash(str(amount)) % 100000:05d}" if success else None,
        "error": None if success else "Payment validation failed",
    }


@activity(
    domain="orders",
    description="Send order confirmation email",
)
def send_confirmation(input_data: dict) -> dict:
    """Send confirmation email to customer."""
    order_id = input_data.get("order_id")
    email = input_data.get("email")
    transaction_id = input_data.get("transaction_id")

    # Simulated email sending
    return {
        "sent": True,
        "recipient": email,
        "order_id": order_id,
        "transaction_id": transaction_id,
        "message": f"Confirmation sent to {email} for order {order_id}",
    }


# =============================================================================
# Define Workflow with Activity Chaining
# =============================================================================
# This workflow demonstrates the yield ctx.call_activity() pattern.


@workflow(
    domain="orders",
    description="Complete order processing with validation, payment, and confirmation",
    version="1.0",
)
def process_order_workflow(ctx, input_data: dict):
    """
    Process an order through multiple activities.

    This demonstrates the core Dapr workflow pattern:
    1. Each `yield ctx.call_activity(...)` suspends the workflow
    2. Dapr executes the activity and checkpoints the result
    3. The workflow resumes with the activity's return value
    4. If the workflow fails, it can resume from the last checkpoint

    Note: We pass the activity FUNCTION directly (not a string name).
    This is type-safe and the recommended approach.
    """
    order = input_data.get("order", {})

    # -------------------------------------------------------------------------
    # Step 1: Validate the order
    # -------------------------------------------------------------------------
    # yield suspends here until validate_order completes
    validation = yield ctx.call_activity(validate_order, input=order)

    if not validation.get("valid"):
        return {
            "status": "failed",
            "step": "validation",
            "errors": validation.get("errors", []),
        }

    # -------------------------------------------------------------------------
    # Step 2: Check inventory
    # -------------------------------------------------------------------------
    # The workflow is checkpointed after validation, so if this fails,
    # we don't re-run validation on retry
    inventory = yield ctx.call_activity(
        check_inventory,
        input={"items": order.get("items", [])},
    )

    if not inventory.get("available"):
        return {
            "status": "failed",
            "step": "inventory",
            "unavailable_items": inventory.get("unavailable_items", []),
        }

    # -------------------------------------------------------------------------
    # Step 3: Process payment
    # -------------------------------------------------------------------------
    payment = yield ctx.call_activity(
        process_payment,
        input={
            "amount": order.get("total", 0),
            "method": order.get("payment_method", "credit_card"),
        },
    )

    if not payment.get("success"):
        return {
            "status": "failed",
            "step": "payment",
            "error": payment.get("error"),
        }

    # -------------------------------------------------------------------------
    # Step 4: Send confirmation
    # -------------------------------------------------------------------------
    confirmation = yield ctx.call_activity(
        send_confirmation,
        input={
            "order_id": order.get("order_id"),
            "email": order.get("email"),
            "transaction_id": payment.get("transaction_id"),
        },
    )

    # -------------------------------------------------------------------------
    # Return final result
    # -------------------------------------------------------------------------
    return {
        "status": "completed",
        "order_id": order.get("order_id"),
        "transaction_id": payment.get("transaction_id"),
        "confirmation_sent": confirmation.get("sent"),
    }


# =============================================================================
# Main demonstration
# =============================================================================


def main():
    """Demonstrate activity chaining concepts."""
    print("Activity Chaining with Dapr Workflows")
    print("=" * 50)
    print()

    # -------------------------------------------------------------------------
    # Show registered items
    # -------------------------------------------------------------------------
    print("Registered Workflows and Activities")
    print("-" * 50)

    info = default_engine.get_info()
    print(f"Total workflows: {info['total_workflows']}")
    print(f"Total activities: {info['total_activities']}")
    print()

    print("Workflows:")
    for full_name, metadata in default_engine.workflows.items():
        print(f"  {full_name}")
        print(f"    Description: {metadata.description}")
        print(f"    Version: {metadata.version}")
    print()

    print("Activities:")
    for full_name, metadata in default_engine.activities.items():
        print(f"  {full_name}")
        print(f"    Description: {metadata.description}")
    print()

    # -------------------------------------------------------------------------
    # Explain the pattern
    # -------------------------------------------------------------------------
    print("The yield ctx.call_activity() Pattern")
    print("-" * 50)
    print(
        """
In Dapr workflows, you orchestrate activities using yield:

    @workflow(domain="orders")
    def my_workflow(ctx, input_data):
        # Each yield suspends the workflow until the activity completes
        result1 = yield ctx.call_activity(activity_one, input=data1)

        # Use the result to decide what to do next
        if result1["success"]:
            result2 = yield ctx.call_activity(activity_two, input=data2)
            return {"status": "done", "result": result2}

        return {"status": "failed"}

Key points:
- Pass the activity FUNCTION directly (not a string name)
- Each yield creates a checkpoint - if the workflow fails, it resumes here
- Activity results are passed back through yield
- Workflows can have conditional logic based on activity results
"""
    )

    # -------------------------------------------------------------------------
    # Note about domains
    # -------------------------------------------------------------------------
    print("About Domains")
    print("-" * 50)
    print(
        """
Domains are an rpsd-workflow organizational concept, NOT a Dapr feature.

When you register with Dapr:
- Dapr sees: "validate_order", "check_inventory", etc.
- Dapr does NOT see: "orders.validate_order"

The domain helps YOU:
- Organize related workflows/activities together
- Filter what gets registered with enabled_domains=["orders"]
- Discover and inspect: default_engine.domains["orders"]

But at runtime, Dapr only knows the function names.
"""
    )

    # -------------------------------------------------------------------------
    # Show how to run with Dapr
    # -------------------------------------------------------------------------
    print("Running with Dapr")
    print("-" * 50)
    print(
        """
To run this workflow with an actual Dapr runtime:

    from dapr.ext.workflow import WorkflowRuntime, DaprWorkflowClient

    # Register all workflows and activities
    runtime = WorkflowRuntime()
    default_engine.register_with_runtime(runtime)
    runtime.start()

    # Start a workflow instance
    client = DaprWorkflowClient()
    instance_id = client.schedule_new_workflow(
        workflow=process_order_workflow,
        input={
            "order": {
                "order_id": "ORD-12345",
                "email": "customer@example.com",
                "items": [{"sku": "ITEM-001", "quantity": 2}],
                "total": 99.99,
                "payment_method": "credit_card",
            }
        },
    )

    # Wait for completion
    result = client.wait_for_workflow_completion(instance_id)
    print(result)
"""
    )

    print("=" * 50)
    print("Example complete!")


if __name__ == "__main__":
    main()
