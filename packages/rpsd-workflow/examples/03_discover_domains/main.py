"""
Auto-Discovery of Domain Workflows

This example demonstrates the discover_domains() method of WorkflowEngine,
which automatically finds and registers workflows and activities from
organized domain packages.

What you'll learn:
- How to structure domain packages for auto-discovery
- How discover_domains() finds and imports workflow modules
- How domains are automatically detected from module paths
- How to inspect discovered workflows and activities
- Two discovery modes: local packages vs installed packages

Directory structure for this example:
    03_discover_domains/
    ├── main.py              # This file
    └── domains/             # Base package for discovery
        ├── __init__.py
        ├── orders/          # Order domain
        │   ├── __init__.py
        │   └── workflows.py # Contains @workflow and @activity decorators
        └── shipping/        # Shipping domain
            ├── __init__.py
            └── workflows.py # Contains @workflow and @activity decorators

The discover_domains() method supports TWO modes:

1. Local Package Discovery (this example):
   discover_domains("domains")
   - Imports the base package and walks all submodules
   - Best for: monorepo, single application

2. Installed Package Discovery (fallback):
   discover_domains()  # No argument
   - Triggers when base package import fails
   - Scans installed packages matching *-workflows or workflows-*
   - Best for: microservices, plugin architectures

Production Pattern:
- Use the shared `default_engine` singleton (one engine for the entire application)
- Domain modules use `from rpsd_workflow import workflow, activity`
- At application startup, call `default_engine.discover_domains("your.domains")`
"""

from rpsd_workflow import default_engine

# =============================================================================
# Use the default_engine singleton
# =============================================================================
# In production, there should be ONE shared WorkflowEngine instance.
# The rpsd_workflow package exports `default_engine` as the singleton.
#
# Domain modules (domains/orders/workflows.py, etc.) use:
#     from rpsd_workflow import workflow, activity
#
# These decorators register with the same default_engine singleton.


def main():
    """Demonstrate the discover_domains() functionality."""
    print("Auto-Discovery of Domain Workflows")
    print("=" * 50)
    print()

    # -------------------------------------------------------------------------
    # Show initial state (empty)
    # -------------------------------------------------------------------------
    print("Step 1: Initial State (before discovery)")
    print("-" * 50)
    info = default_engine.get_info()
    print(f"Registered domains: {info['domains']}")
    print(f"Total workflows: {info['total_workflows']}")
    print(f"Total activities: {info['total_activities']}")
    print()

    # -------------------------------------------------------------------------
    # Discover domains
    # -------------------------------------------------------------------------
    print("Step 2: Running default_engine.discover_domains('domains')")
    print("-" * 50)
    print("Searching for workflow modules in the 'domains' package...")
    print()

    default_engine.discover_domains("domains")

    print("Discovery complete!")
    print()

    # -------------------------------------------------------------------------
    # Show what was discovered
    # -------------------------------------------------------------------------
    print("Step 3: After Discovery")
    print("-" * 50)
    info = default_engine.get_info()
    print(f"Discovered domains: {info['domains']}")
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
    # List discovered workflows with metadata
    # -------------------------------------------------------------------------
    print("Step 4: Discovered Workflows")
    print("-" * 50)

    for full_name, metadata in default_engine.workflows.items():
        print(f"Workflow: {full_name}")
        print(f"  Domain: {metadata.domain}")
        print(f"  Description: {metadata.description}")
        print()

    # -------------------------------------------------------------------------
    # List discovered activities with metadata
    # -------------------------------------------------------------------------
    print("Step 5: Discovered Activities")
    print("-" * 50)

    for full_name, metadata in default_engine.activities.items():
        print(f"Activity: {full_name}")
        print(f"  Domain: {metadata.domain}")
        print(f"  Description: {metadata.description}")
        print()

    # -------------------------------------------------------------------------
    # Accessing domain structure
    # -------------------------------------------------------------------------
    print("Step 6: Domain Structure")
    print("-" * 50)
    print("The engine organizes discovered items by domain:")
    print()

    for domain_name, domain_info in default_engine.domains.items():
        print(f"Domain: {domain_name}")
        wf_names = [wf.name for wf in domain_info["workflows"]]
        act_names = [act.name for act in domain_info["activities"]]
        print(f"  Workflows: {wf_names}")
        print(f"  Activities: {act_names}")
    print()

    # -------------------------------------------------------------------------
    # How domain detection works
    # -------------------------------------------------------------------------
    print("Step 7: Understanding Domain Detection")
    print("-" * 50)
    print("Domain names are automatically extracted from module paths:")
    print()
    print("  domains.orders.workflows     -> domain: 'orders'")
    print("  domains.shipping.workflows   -> domain: 'shipping'")
    print()
    print("The pattern 'domains.<domain_name>.workflows' is recognized,")
    print("and the second component becomes the domain name.")
    print()

    # -------------------------------------------------------------------------
    # Two discovery modes
    # -------------------------------------------------------------------------
    print("Step 8: Two Discovery Modes")
    print("-" * 50)
    print("discover_domains() supports TWO discovery modes:")
    print()
    print("MODE 1: Local Package Discovery (this example)")
    print("  discover_domains('domains')  # or 'myapp.domains'")
    print("  - Imports the specified package")
    print("  - Walks all submodules using pkgutil.walk_packages()")
    print("  - Best for: monorepo, single application")
    print()
    print("MODE 2: Installed Package Discovery (fallback)")
    print("  discover_domains()  # No argument, or non-existent package")
    print("  - Triggers when base package import fails")
    print("  - Scans installed packages via importlib.metadata")
    print("  - Matches packages named: *-workflows or workflows-*")
    print("  - Best for: microservices, plugin architectures")
    print()
    print("Examples of matched installed package names:")
    print("  - orders-workflows    -> module: orders_workflows")
    print("  - workflows-shipping  -> module: workflows_shipping")
    print("  - payments-workflows  -> module: payments_workflows")
    print()
    print("Domain auto-detection from installed packages:")
    print("  orders_workflows.workflows     -> domain: 'orders'")
    print("  workflows_shipping.workflows   -> domain: 'shipping'")
    print()

    # -------------------------------------------------------------------------
    # Production usage
    # -------------------------------------------------------------------------
    print("Step 9: Production Usage")
    print("-" * 50)
    print("In production, you would typically:")
    print()
    print("  1. Structure your project with a 'domains' package:")
    print("       src/")
    print("         domains/")
    print("           orders/")
    print("             workflows.py  # uses: from rpsd_workflow import workflow")
    print("           shipping/")
    print("             workflows.py")
    print()
    print("  2. Call discover_domains() at application startup:")
    print("       from rpsd_workflow import default_engine")
    print("       default_engine.discover_domains('domains')")
    print()
    print("     Or for distributed packages:")
    print("       default_engine.discover_domains()  # scans installed *-workflows")
    print()
    print("  3. Register discovered workflows with Dapr:")
    print("       from dapr.ext.workflow import WorkflowRuntime")
    print("       runtime = WorkflowRuntime()")
    print("       default_engine.register_with_runtime(runtime)")
    print()
    print("  4. Optionally filter by domain:")
    print("       default_engine.register_with_runtime(")
    print('           runtime, enabled_domains=["orders"]')
    print("       )")
    print()

    print("Success!")
    print("-" * 50)
    print("You've learned how to:")
    print("  1. Structure domain packages for auto-discovery")
    print("  2. Use discover_domains() to find workflow modules")
    print("  3. Understand automatic domain detection from module paths")
    print("  4. Inspect discovered workflows and activities")
    print("  5. Use installed package discovery for distributed workflows")


if __name__ == "__main__":
    main()
