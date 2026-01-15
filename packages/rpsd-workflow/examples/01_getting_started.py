"""
Getting Started with rpsd-workflow

This example shows how to define and register workflows and activities
using the rpsd-workflow engine. Perfect for first-time users!

What you'll learn:
- How to define a workflow with the @workflow decorator
- How to define an activity with the @activity decorator
- How to organize workflows by domain
- How to inspect registered workflows and activities
- How to access workflow metadata

This is a quick introduction to the workflow engine concepts.

Note: This example demonstrates the registration and metadata system.
In production, you would integrate with a Dapr WorkflowRuntime using
the register_with_runtime() method.
"""

from rpsd_workflow import activity, default_engine, workflow

# =============================================================================
# Step 1: Define Workflows
# =============================================================================
# Workflows are the main orchestration units. They receive a context (ctx)
# and input data, and can coordinate multiple activities.


@workflow(
    domain="orders",
    description="Process a customer order end-to-end",
    version="1.0",
)
def process_order(ctx, input_data: dict) -> dict:
    """
    Main order processing workflow.

    In a real Dapr workflow, you would call activities like:
        result = yield ctx.call_activity(validate_payment, data)

    For this example, we just return a processed result.
    """
    order_id = input_data.get("order_id", "unknown")
    return {
        "order_id": order_id,
        "status": "processed",
        "message": f"Order {order_id} has been processed",
    }


@workflow(
    domain="orders",
    description="Cancel an existing order",
    version="1.0",
)
def cancel_order(ctx, input_data: dict) -> dict:
    """Cancel an order and trigger refund process."""
    order_id = input_data.get("order_id", "unknown")
    reason = input_data.get("reason", "customer request")
    return {
        "order_id": order_id,
        "status": "cancelled",
        "reason": reason,
    }


# =============================================================================
# Step 2: Define Activities
# =============================================================================
# Activities are the individual units of work. They receive input data
# and perform a specific task (validation, API calls, calculations, etc.)


@activity(
    domain="orders",
    description="Validate payment information",
)
def validate_payment(input_data: dict) -> dict:
    """Validate that payment details are correct."""
    payment_method = input_data.get("payment_method", "credit_card")
    amount = input_data.get("amount", 0)
    return {
        "valid": amount > 0,
        "payment_method": payment_method,
        "amount": amount,
    }


@activity(
    domain="orders",
    description="Update inventory after order",
)
def update_inventory(input_data: dict) -> dict:
    """Update stock levels after an order is placed."""
    product_id = input_data.get("product_id", "unknown")
    quantity = input_data.get("quantity", 1)
    return {
        "product_id": product_id,
        "quantity_reserved": quantity,
        "success": True,
    }


# =============================================================================
# Step 3: Define workflows in a different domain
# =============================================================================
# Domains help organize related workflows and activities together.


@workflow(
    domain="validation",
    description="Validate uploaded files",
    version="2.0",
)
def validate_file(ctx, input_data: dict) -> dict:
    """Main file validation workflow."""
    file_path = input_data.get("file_path", "")
    return {
        "file_path": file_path,
        "valid": bool(file_path),
        "checks_passed": ["format", "size", "content"],
    }


@activity(
    domain="validation",
    description="Check file format and extension",
)
def check_file_format(input_data: dict) -> dict:
    """Verify the file has a valid format."""
    file_path = input_data.get("file_path", "")
    extension = file_path.split(".")[-1] if "." in file_path else ""
    allowed = ["pdf", "txt", "csv", "json"]
    return {
        "extension": extension,
        "allowed": extension.lower() in allowed,
    }


# =============================================================================
# Main demonstration
# =============================================================================


def main():
    """Demonstrate the workflow engine capabilities."""
    print("Getting Started with rpsd-workflow")
    print("=" * 40)
    print()

    # -------------------------------------------------------------------------
    # Show what's registered
    # -------------------------------------------------------------------------
    print("Step 1: Inspecting the Workflow Engine")
    print("-" * 40)

    info = default_engine.get_info()
    print(f"Registered domains: {info['domains']}")
    print(f"Total workflows: {info['total_workflows']}")
    print(f"Total activities: {info['total_activities']}")
    print()
    print("Domain breakdown:")
    for domain, details in info["domain_details"].items():
        print(f"  {domain}:")
        print(f"    - Workflows: {details['workflows']}")
        print(f"    - Activities: {details['activities']}")
    print()

    # -------------------------------------------------------------------------
    # List registered workflows with metadata
    # -------------------------------------------------------------------------
    print("Step 2: Workflow Metadata")
    print("-" * 40)

    for full_name, metadata in default_engine.workflows.items():
        print(f"Workflow: {full_name}")
        print(f"  Name: {metadata.name}")
        print(f"  Domain: {metadata.domain}")
        print(f"  Description: {metadata.description}")
        print(f"  Version: {metadata.version}")
        print()

    # -------------------------------------------------------------------------
    # List registered activities with metadata
    # -------------------------------------------------------------------------
    print("Step 3: Activity Metadata")
    print("-" * 40)

    for full_name, metadata in default_engine.activities.items():
        print(f"Activity: {full_name}")
        print(f"  Name: {metadata.name}")
        print(f"  Domain: {metadata.domain}")
        print(f"  Description: {metadata.description}")
        print()

    # -------------------------------------------------------------------------
    # Demonstrate that decorated functions still work normally
    # -------------------------------------------------------------------------
    print("Step 4: Calling Functions Directly")
    print("-" * 40)
    print("Decorated functions remain callable for testing and debugging.")
    print()

    # Call a workflow function directly (without Dapr context)
    order_result = process_order(None, {"order_id": "ORD-12345"})
    print(f"process_order result: {order_result}")

    # Call an activity function directly
    payment_result = validate_payment(
        {"payment_method": "credit_card", "amount": 99.99}
    )
    print(f"validate_payment result: {payment_result}")

    inventory_result = update_inventory({"product_id": "PROD-001", "quantity": 2})
    print(f"update_inventory result: {inventory_result}")
    print()

    # -------------------------------------------------------------------------
    # Accessing domains structure
    # -------------------------------------------------------------------------
    print("Step 5: Accessing Domain Structure")
    print("-" * 40)
    print("The engine organizes workflows and activities by domain:")
    print()

    for domain_name, domain_info in default_engine.domains.items():
        print(f"Domain: {domain_name}")
        wf_names = [wf.name for wf in domain_info["workflows"]]
        act_names = [act.name for act in domain_info["activities"]]
        print(f"  Workflows: {wf_names}")
        print(f"  Activities: {act_names}")
    print()

    # -------------------------------------------------------------------------
    # Production usage note
    # -------------------------------------------------------------------------
    print("Step 6: Production Integration (Dapr)")
    print("-" * 40)
    print("In production, register workflows with a Dapr WorkflowRuntime:")
    print()
    print("    from dapr.ext.workflow import WorkflowRuntime")
    print()
    print("    runtime = WorkflowRuntime()")
    print("    wf_count, act_count = default_engine.register_with_runtime(runtime)")
    print()
    print("You can also filter by domain:")
    print()
    print(
        '    default_engine.register_with_runtime(runtime, enabled_domains=["orders"])'
    )
    print()

    print("Success!")
    print("-" * 40)
    print("You've learned how to:")
    print("  1. Define workflows with @workflow decorator")
    print("  2. Define activities with @activity decorator")
    print("  3. Organize by domain for better structure")
    print("  4. Inspect registered items with get_info()")
    print("  5. Access metadata for workflows and activities")
    print("  6. Call decorated functions directly for testing")


if __name__ == "__main__":
    main()
