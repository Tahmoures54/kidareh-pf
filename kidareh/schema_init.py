"""Coordinate feature-owned database schema setup during application initialization.

Schema definitions remain beside their owning feature for this incremental refactor,
but production startup now prepares them before serving requests. The initializers
are intentionally idempotent so existing deployments can be upgraded safely.
"""


def initialize_feature_schemas() -> None:
    """Initialize every feature-owned table before requests are served.

    Every initializer is idempotent, so this runs on each startup: databases
    that are already at the latest schema version still pick up tables added by
    a feature module after their last migration.
    """
    # Import lazily to avoid route imports while the core module is being loaded.
    from .routes.auth import ensure_tables as initialize_auth
    from .routes.communications import ensure_tables as initialize_communications
    from .routes.moderation import ensure_tables as initialize_moderation
    from .routes.monetization import ensure_tables as initialize_monetization

    initialize_auth()
    initialize_communications()
    initialize_moderation()
    initialize_monetization()
