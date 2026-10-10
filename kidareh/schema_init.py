"""Coordinate feature-owned database schema setup during application initialization.

Schema definitions remain beside their owning feature for this incremental refactor,
but production startup now prepares them before serving requests. The initializers
are intentionally idempotent so existing deployments can be upgraded safely.
"""


def initialize_feature_schemas() -> None:
    """Initialize schemas for messaging/support and seller monetization."""
    # Import lazily to avoid route imports while the core module is being loaded.
    from .routes.communications import ensure_tables as initialize_communications
    from .routes.monetization import ensure_tables as initialize_monetization

    initialize_communications()
    initialize_monetization()
