# Auto-Discovery of Domain Workflows

This example demonstrates the `discover_domains()` method of `WorkflowEngine`, which automatically finds and registers workflows and activities from organized domain packages.

## What This Example Shows

- How to structure domain packages for auto-discovery
- How `discover_domains()` finds and imports workflow modules
- How domains are automatically detected from module paths
- How to inspect discovered workflows and activities
- Two discovery modes: local packages vs installed packages

## Directory Structure

```
03_discover_domains/
├── main.py              # Main script demonstrating discovery
├── README.md            # This file
└── domains/             # Base package for discovery
    ├── __init__.py      # Empty (package marker)
    ├── orders/          # Order domain
    │   ├── __init__.py
    │   └── workflows.py # Order workflows and activities
    └── shipping/        # Shipping domain
        ├── __init__.py
        └── workflows.py # Shipping workflows and activities
```

## Running the Example

```bash
cd packages/rpsd-workflow/examples/03_discover_domains
uv run python main.py
```

## Two Discovery Modes

The `discover_domains()` method supports two modes:

### Mode 1: Local Package Discovery (this example)

```python
default_engine.discover_domains("domains")
```

- Imports the specified base package
- Walks all submodules using `pkgutil.walk_packages()`
- Best for: **monorepo, single application**

### Mode 2: Installed Package Discovery (fallback)

```python
default_engine.discover_domains()  # No argument, or non-existent package
```

- Triggers when base package import fails (ImportError)
- Scans installed packages via `importlib.metadata.distributions()`
- Matches packages named: `*-workflows` or `workflows-*`
- Best for: **microservices, plugin architectures**

**Examples of matched package names:**
| Package Name | Python Module | Domain |
|--------------|---------------|--------|
| `orders-workflows` | `orders_workflows` | `orders` |
| `workflows-shipping` | `workflows_shipping` | `shipping` |
| `payments-workflows` | `payments_workflows` | `payments` |

## Production Pattern

In production, there should be **ONE shared `default_engine` singleton**:

```python
# Domain module: domains/orders/workflows.py
from rpsd_workflow import workflow, activity

@workflow(description="Process order")  # Domain auto-detected from module path
def process_order(ctx, input_data):
    pass

# Main application
from rpsd_workflow import default_engine

# Option 1: Local package discovery
default_engine.discover_domains("domains")

# Option 2: Installed package discovery (scans *-workflows packages)
default_engine.discover_domains()
```

## How It Works

1. **Package Structure**: Domain packages are organized under a base package (e.g., `domains/`)
2. **Singleton Engine**: All domain modules use `from rpsd_workflow import workflow, activity`
3. **Discovery**: `default_engine.discover_domains("domains")` imports all modules
4. **Registration**: When modules are imported, decorators register with the shared `default_engine`
5. **Domain Detection**: Domain names are extracted from module paths (e.g., `domains.orders.workflows` → domain: `orders`)
