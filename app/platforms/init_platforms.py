"""Platform initialization - registers all supported platforms."""

import structlog

from app.platforms.registry import platform_registry, Platform
from app.auth.lwa_client import lwa_client
from app.auth.shopify_auth import shopify_auth_client
from app.fetchers.amazon_fetcher import amazon_fetcher
from app.fetchers.shopify_fetcher import shopify_fetcher
from app.normalizers.amazon_normalizer import amazon_normalizer
from app.normalizers.shopify_normalizer import shopify_normalizer

logger = structlog.get_logger(__name__)


def initialize_platforms():
    """Register all supported platforms with the registry."""

    logger.info("initializing_platforms")

    # Register Amazon
    platform_registry.register(
        platform=Platform.AMAZON,
        auth=lwa_client,
        fetcher=amazon_fetcher,
        normalizer=amazon_normalizer,
    )
    logger.info("platform_registered", platform="amazon")

    # Register Shopify
    platform_registry.register(
        platform=Platform.SHOPIFY,
        auth=shopify_auth_client,
        fetcher=shopify_fetcher,
        normalizer=shopify_normalizer,
    )
    logger.info("platform_registered", platform="shopify")

    logger.info(
        "platforms_initialized",
        platforms=platform_registry.list_platforms(),
    )


# Auto-initialize when module is imported
initialize_platforms()
