"""Platform registry for dynamic dispatch to platform-specific modules."""

from typing import Dict, Any, Protocol
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)


class Platform(str, Enum):
    """Supported e-commerce platforms."""
    AMAZON = "amazon"
    SHOPIFY = "shopify"


class AuthModuleProtocol(Protocol):
    """Protocol for authentication modules."""

    async def get_authorization_url(self, **kwargs) -> tuple[str, str]:
        """Get OAuth authorization URL and state."""
        ...

    async def exchange_code_for_tokens(self, code: str, **kwargs) -> Any:
        """Exchange authorization code for tokens."""
        ...

    async def refresh_access_token(self, refresh_token: str, **kwargs) -> Any:
        """Refresh access token (if applicable)."""
        ...


class FetcherModuleProtocol(Protocol):
    """Protocol for fetcher modules."""

    async def fetch_reviews(self, credentials: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch reviews from the platform."""
        ...


class NormalizerModuleProtocol(Protocol):
    """Protocol for normalizer modules."""

    def normalize(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize raw platform data to unified schema."""
        ...


class PlatformModules:
    """Container for platform-specific modules."""

    def __init__(self, auth, fetcher, normalizer):
        self.auth = auth
        self.fetcher = fetcher
        self.normalizer = normalizer


class PlatformRegistry:
    """Registry for managing platform-specific modules."""

    def __init__(self):
        self._platforms: Dict[str, PlatformModules] = {}

    def register(self, platform: str, auth, fetcher, normalizer):
        """
        Register a platform with its modules.

        Args:
            platform: Platform identifier (e.g., "amazon", "shopify")
            auth: Authentication module
            fetcher: Fetcher module
            normalizer: Normalizer module
        """
        self._platforms[platform.lower()] = PlatformModules(
            auth=auth,
            fetcher=fetcher,
            normalizer=normalizer
        )
        logger.info("platform_registered", platform=platform)

    def get(self, platform: str) -> PlatformModules:
        """
        Get modules for a platform.

        Args:
            platform: Platform identifier

        Returns:
            PlatformModules instance

        Raises:
            ValueError: If platform is not registered
        """
        platform_lower = platform.lower()
        if platform_lower not in self._platforms:
            raise ValueError(
                f"Unsupported platform: {platform}. "
                f"Available platforms: {', '.join(self._platforms.keys())}"
            )
        return self._platforms[platform_lower]

    def is_supported(self, platform: str) -> bool:
        """Check if a platform is supported."""
        return platform.lower() in self._platforms

    def list_platforms(self) -> list[str]:
        """List all registered platforms."""
        return list(self._platforms.keys())


# Global registry instance
platform_registry = PlatformRegistry()


def get_platform_modules(platform: str) -> PlatformModules:
    """
    Convenience function to get platform modules.

    Args:
        platform: Platform identifier

    Returns:
        PlatformModules instance

    Raises:
        ValueError: If platform is not supported
    """
    return platform_registry.get(platform)
