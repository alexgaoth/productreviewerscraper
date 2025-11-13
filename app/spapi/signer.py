"""AWS Signature Version 4 signing for SP-API requests."""

import hashlib
import hmac
from datetime import datetime
from typing import Dict, Optional
from urllib.parse import quote, urlparse
import structlog

logger = structlog.get_logger(__name__)


class SigV4Signer:
    """AWS Signature Version 4 request signer."""

    def __init__(
        self,
        access_key: str,
        secret_key: str,
        region: str = "us-east-1",
        service: str = "execute-api",
    ):
        """
        Initialize SigV4 signer.

        Args:
            access_key: AWS access key ID
            secret_key: AWS secret access key
            region: AWS region
            service: AWS service name (execute-api for SP-API)
        """
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self.service = service

    @staticmethod
    def _sign(key: bytes, msg: str) -> bytes:
        """HMAC-SHA256 signing."""
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    def _get_signature_key(self, date_stamp: str) -> bytes:
        """Derive signing key."""
        k_date = self._sign(f"AWS4{self.secret_key}".encode("utf-8"), date_stamp)
        k_region = self._sign(k_date, self.region)
        k_service = self._sign(k_region, self.service)
        k_signing = self._sign(k_service, "aws4_request")
        return k_signing

    @staticmethod
    def _canonical_uri(path: str) -> str:
        """Create canonical URI."""
        if not path:
            return "/"
        # Encode each path segment
        parts = path.split("/")
        encoded_parts = [quote(part, safe="") for part in parts]
        return "/".join(encoded_parts)

    @staticmethod
    def _canonical_query_string(params: Optional[Dict[str, str]]) -> str:
        """Create canonical query string."""
        if not params:
            return ""

        # Sort and encode parameters
        sorted_params = sorted(params.items())
        encoded_params = [
            f"{quote(k, safe='')}={quote(str(v), safe='')}"
            for k, v in sorted_params
        ]
        return "&".join(encoded_params)

    @staticmethod
    def _canonical_headers(headers: Dict[str, str]) -> str:
        """Create canonical headers string."""
        # Lowercase and sort headers
        canonical = []
        for key in sorted(headers.keys()):
            canonical.append(f"{key.lower()}:{headers[key].strip()}\n")
        return "".join(canonical)

    @staticmethod
    def _signed_headers(headers: Dict[str, str]) -> str:
        """Create signed headers string."""
        return ";".join(sorted([h.lower() for h in headers.keys()]))

    @staticmethod
    def _hash_payload(payload: str) -> str:
        """Create SHA256 hash of payload."""
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def sign_request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        payload: str = "",
        params: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """
        Sign an HTTP request using AWS SigV4.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL
            headers: Request headers (must include 'host' and 'x-amz-date')
            payload: Request body
            params: Query parameters

        Returns:
            Updated headers with Authorization header
        """
        # Parse URL
        parsed = urlparse(url)
        canonical_uri = self._canonical_uri(parsed.path)
        canonical_querystring = self._canonical_query_string(params)

        # Get timestamp from x-amz-date header
        amz_date = headers.get("x-amz-date")
        if not amz_date:
            raise ValueError("x-amz-date header is required")

        date_stamp = amz_date[:8]  # YYYYMMDD

        # Hash payload
        payload_hash = self._hash_payload(payload)

        # Add payload hash to headers
        headers_to_sign = {**headers, "x-amz-content-sha256": payload_hash}

        # Create canonical request
        canonical_headers_str = self._canonical_headers(headers_to_sign)
        signed_headers_str = self._signed_headers(headers_to_sign)

        canonical_request = "\n".join([
            method.upper(),
            canonical_uri,
            canonical_querystring,
            canonical_headers_str,
            signed_headers_str,
            payload_hash,
        ])

        # Create string to sign
        algorithm = "AWS4-HMAC-SHA256"
        credential_scope = f"{date_stamp}/{self.region}/{self.service}/aws4_request"
        canonical_request_hash = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()

        string_to_sign = "\n".join([
            algorithm,
            amz_date,
            credential_scope,
            canonical_request_hash,
        ])

        # Calculate signature
        signing_key = self._get_signature_key(date_stamp)
        signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

        # Create authorization header
        authorization_header = (
            f"{algorithm} "
            f"Credential={self.access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers_str}, "
            f"Signature={signature}"
        )

        # Return headers with authorization
        signed_headers = {**headers_to_sign, "Authorization": authorization_header}

        logger.debug(
            "request_signed",
            method=method,
            url=url,
            signed_headers=signed_headers_str,
        )

        return signed_headers


def get_amz_date() -> str:
    """Get current timestamp in Amazon date format (ISO8601)."""
    return datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
