"""AWS Secrets Manager integration."""

import json
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


class SecretsManager:
    """Manager for AWS Secrets Manager."""

    def __init__(self):
        """Initialize secrets manager client."""
        if settings.secrets_manager_enabled:
            self.client = boto3.client(
                "secretsmanager",
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
            )
        else:
            self.client = None

    def get_secret(self, secret_arn: str) -> Dict[str, Any]:
        """
        Retrieve secret from AWS Secrets Manager.

        Args:
            secret_arn: ARN of the secret

        Returns:
            Secret data as dict

        Raises:
            Exception: If secret retrieval fails
        """
        if not self.client:
            raise ValueError("Secrets Manager is not enabled")

        try:
            logger.info("retrieving_secret", arn=secret_arn)

            response = self.client.get_secret_value(SecretId=secret_arn)

            # Parse secret string
            if "SecretString" in response:
                secret_data = json.loads(response["SecretString"])
            else:
                # Binary secret
                secret_data = response["SecretBinary"]

            logger.info("secret_retrieved", arn=secret_arn)
            return secret_data

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            logger.error("secret_retrieval_failed", arn=secret_arn, error_code=error_code)

            if error_code == "ResourceNotFoundException":
                raise ValueError(f"Secret not found: {secret_arn}")
            elif error_code == "AccessDeniedException":
                raise ValueError(f"Access denied to secret: {secret_arn}")
            else:
                raise

    def get_lwa_credentials(self) -> Optional[Dict[str, str]]:
        """
        Get LWA credentials from Secrets Manager.

        Returns:
            Dict with client_id and client_secret, or None if not enabled
        """
        if not settings.secrets_manager_enabled or not settings.lwa_secrets_arn:
            return None

        secret_data = self.get_secret(settings.lwa_secrets_arn)

        return {
            "client_id": secret_data.get("client_id"),
            "client_secret": secret_data.get("client_secret"),
        }

    def get_spapi_credentials(self) -> Optional[Dict[str, str]]:
        """
        Get SP-API credentials from Secrets Manager.

        Returns:
            Dict with AWS credentials, or None if not enabled
        """
        if not settings.secrets_manager_enabled or not settings.spapi_secrets_arn:
            return None

        secret_data = self.get_secret(settings.spapi_secrets_arn)

        return {
            "aws_access_key_id": secret_data.get("aws_access_key_id"),
            "aws_secret_access_key": secret_data.get("aws_secret_access_key"),
            "role_arn": secret_data.get("role_arn"),
        }


# Global secrets manager instance
secrets_manager = SecretsManager()
