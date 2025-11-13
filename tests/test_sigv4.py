"""Tests for AWS SigV4 signing."""

import pytest
from datetime import datetime
from app.spapi.signer import SigV4Signer, get_amz_date


def test_get_amz_date():
    """Test AMZ date formatting."""
    date = get_amz_date()
    assert len(date) == 16
    assert date.endswith("Z")
    assert "T" in date


def test_signer_initialization():
    """Test SigV4 signer initialization."""
    signer = SigV4Signer(
        access_key="test_key",
        secret_key="test_secret",
        region="us-east-1",
        service="execute-api",
    )

    assert signer.access_key == "test_key"
    assert signer.secret_key == "test_secret"
    assert signer.region == "us-east-1"
    assert signer.service == "execute-api"


def test_canonical_uri():
    """Test canonical URI generation."""
    assert SigV4Signer._canonical_uri("") == "/"
    assert SigV4Signer._canonical_uri("/") == "/"
    assert SigV4Signer._canonical_uri("/path/to/resource") == "/path/to/resource"


def test_canonical_query_string():
    """Test canonical query string generation."""
    assert SigV4Signer._canonical_query_string(None) == ""
    assert SigV4Signer._canonical_query_string({}) == ""

    params = {"foo": "bar", "baz": "qux"}
    result = SigV4Signer._canonical_query_string(params)
    assert "baz=qux" in result
    assert "foo=bar" in result


def test_sign_request():
    """Test request signing."""
    signer = SigV4Signer(
        access_key="AKIAIOSFODNN7EXAMPLE",
        secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        region="us-east-1",
        service="execute-api",
    )

    headers = {
        "host": "example.com",
        "x-amz-date": "20251113T120000Z",
    }

    signed_headers = signer.sign_request(
        method="GET",
        url="https://example.com/path",
        headers=headers,
        payload="",
    )

    assert "Authorization" in signed_headers
    assert "AWS4-HMAC-SHA256" in signed_headers["Authorization"]
    assert "Credential=" in signed_headers["Authorization"]
    assert "SignedHeaders=" in signed_headers["Authorization"]
    assert "Signature=" in signed_headers["Authorization"]
    assert "x-amz-content-sha256" in signed_headers
