# Shopify Integration Guide

This document describes the Shopify integration architecture and how it extends the existing Amazon review fetching service to support multiple e-commerce platforms.

## Overview

The service now supports both **Amazon** and **Shopify** through a modular, platform-agnostic architecture. New platforms can be easily added by implementing three core modules: Auth, Fetcher, and Normalizer.

## Architecture

### Platform Registry System

Located in `app/platforms/registry.py`, the platform registry provides dynamic dispatch to platform-specific modules:

```python
from app.platforms.registry import get_platform_modules

# Get modules for a specific platform
modules = get_platform_modules("shopify")  # or "amazon"

# Use the modules
auth_client = modules.auth
fetcher = modules.fetcher
normalizer = modules.normalizer
```

### Supported Platforms

- **Amazon**: SP-API integration with LWA OAuth
- **Shopify**: Admin API integration with OAuth 2.0

## Database Schema Changes

### Seller Table

Now supports multiple platforms:

```python
class Seller(Base):
    id: str                          # seller_id or shop_id
    platform: str                    # "amazon" or "shopify"
    marketplace_id: str (optional)   # For Amazon only

    # Amazon-specific
    lwa_client_id: str (optional)
    encrypted_refresh_token: str (optional)

    # Shopify-specific
    encrypted_access_token: str (optional)  # Permanent token

    # Common fields
    access_token_cached: str
    access_token_expires_at: datetime
    status: SellerStatus
```

### FetchJob Table

Platform-agnostic job tracking:

```python
class FetchJob(Base):
    id: str
    platform: str                    # "amazon" or "shopify"
    seller_id: str
    marketplace_id: str (optional)   # Amazon only

    # Platform-specific item lists
    asins: JSON (optional)           # For Amazon
    product_ids: JSON (optional)     # For Shopify
    request_params: JSON (optional)  # Additional params

    # Progress tracking
    total_items: int
    completed_items: int
    failed_items: int
```

### ASINFetchResult Table

Now tracks items from any platform:

```python
class ASINFetchResult(Base):
    platform: str
    asin: str (optional)             # For Amazon
    product_id: str (optional)       # For Shopify
```

## S3 Storage Structure

Platform-specific paths for data isolation:

```
# Raw data
s3://bucket/raw/{platform}/{seller_id}/{item_id}/{YYYY}/{MM}/{DD}/{job_id}/{page}.json

# Processed data
s3://bucket/processed/{platform}/{seller_id}/{item_id}/{YYYY}/{MM}/{DD}/{job_id}.json

# Examples
s3://bucket/raw/amazon/A1SELLER123/ATVPDKIKX0DER/B00123456/2025/11/13/job-xxx/page1.json
s3://bucket/raw/shopify/my-store/all/2025/11/13/job-yyy/page1.json
```

## Shopify Implementation

### 1. Authentication (`app/auth/shopify_auth.py`)

Implements Shopify OAuth 2.0:

```python
from app.auth.shopify_auth import shopify_auth_client

# Generate authorization URL
url, state = shopify_auth_client.get_authorization_url(
    shop="my-store",  # or "my-store.myshopify.com"
    state="optional-csrf-token"
)

# Exchange code for permanent access token
token_response = await shopify_auth_client.exchange_code_for_token(
    shop="my-store.myshopify.com",
    code="authorization_code_from_callback"
)

# token_response.access_token - permanent, no refresh needed
# token_response.shop - normalized shop domain
# token_response.scope - granted permissions
```

**Scopes**: `read_products,read_product_listings,read_orders,read_customers`

### 2. Fetcher (`app/fetchers/shopify_fetcher.py`)

Retrieves review data from Shopify metafields:

```python
from app.fetchers.shopify_fetcher import shopify_fetcher

# Fetch reviews
raw_data = await shopify_fetcher.fetch_reviews(
    credentials={
        "shop": "my-store.myshopify.com",
        "access_token": "permanent_access_token"
    },
    params={
        "product_ids": [123, 456],  # Optional, fetch all if None
        "namespace": "reviews"       # Metafield namespace
    }
)

# Returns
{
    "platform": "shopify",
    "shop": "my-store.myshopify.com",
    "namespace": "reviews",
    "raw_metafields": [...]
}
```

**Note**: Shopify doesn't natively support reviews. This implementation:
- Fetches metafields from a custom namespace (default: "reviews")
- Can be extended to integrate with review apps (Judge.me, Loox, etc.)
- Iterates through products to gather metafield-based review data

### 3. Normalizer (`app/normalizers/shopify_normalizer.py`)

Transforms Shopify data to unified schema:

```python
from app.normalizers.shopify_normalizer import shopify_normalizer

normalized = shopify_normalizer.normalize(raw_data)

# Output schema (matches Amazon format)
{
    "platform": "shopify",
    "shop": "my-store.myshopify.com",
    "reviews_count": 42,
    "reviews": [
        {
            "review_id": "...",
            "display_name": "...",
            "rating": 5,
            "title": "...",
            "body": "...",
            "verified_purchase": true,
            "review_date": "...",
            "product_id": "...",
            "platform": "shopify"
        }
    ]
}
```

## Configuration

### Environment Variables

Add to `.env`:

```bash
# Shopify OAuth
SHOPIFY_CLIENT_ID=your_shopify_app_client_id
SHOPIFY_CLIENT_SECRET=your_shopify_app_client_secret
SHOPIFY_REDIRECT_URI=https://your-domain.com/auth/shopify/callback
SHOPIFY_API_VERSION=2024-10
SHOPIFY_SCOPES=read_products,read_product_listings,read_orders,read_customers
```

### Shopify App Setup

1. **Create a Shopify Partner Account**: https://partners.shopify.com/
2. **Create an App**:
   - App type: Custom app or Public app
   - App URL: Your service URL
   - Allowed redirection URL(s): `{SHOPIFY_REDIRECT_URI}`
3. **Set Scopes**: At minimum:
   - `read_products` - Access product data
   - `read_product_listings` - Access published products
4. **Get Credentials**:
   - API key → `SHOPIFY_CLIENT_ID`
   - API secret key → `SHOPIFY_CLIENT_SECRET`

## API Endpoints (To Be Implemented)

### Shopify OAuth

**Start OAuth Flow**
```http
GET /auth/shopify/start?shop=my-store
```

Redirects to Shopify authorization page.

**OAuth Callback**
```http
POST /auth/shopify/callback
Content-Type: application/json

{
  "shop": "my-store.myshopify.com",
  "code": "authorization_code",
  "state": "csrf_token",
  "shop_name": "My Store",
  "shop_email": "owner@example.com"
}
```

Returns:
```json
{
  "ok": true,
  "shop_id": "my-store.myshopify.com",
  "message": "Authorization successful"
}
```

### Review Fetching

**Fetch Reviews**
```http
POST /fetch/reviews
Content-Type: application/json

{
  "platform": "shopify",
  "shop_id": "my-store.myshopify.com",
  "product_ids": [123, 456],
  "namespace": "reviews"
}
```

Returns:
```json
{
  "job_id": "job-20251113120000-abc123",
  "status": "pending",
  "platform": "shopify",
  "message": "Job queued successfully"
}
```

**Get Job Status**
```http
GET /jobs/{job_id}/status
```

Returns:
```json
{
  "job_id": "job-xxx",
  "platform": "shopify",
  "shop_id": "my-store.myshopify.com",
  "status": "success",
  "total_items": 10,
  "completed_items": 10,
  "total_reviews_fetched": 42,
  "s3_raw_keys": ["s3://..."],
  "s3_processed_keys": ["s3://..."]
}
```

## Worker Implementation (To Be Completed)

The worker needs to be refactored to use the platform registry:

```python
from app.platforms.registry import get_platform_modules

async def run_job(job):
    # Get platform-specific modules
    modules = get_platform_modules(job.platform)

    # Get credentials
    seller = get_seller(job.seller_id)
    credentials = build_credentials(seller, job.platform)

    # Fetch reviews
    raw_data = await modules.fetcher.fetch_reviews(
        credentials=credentials,
        params=build_params(job)
    )

    # Save raw data
    await s3_storage.save_raw_response(
        platform=job.platform,
        seller_id=job.seller_id,
        job_id=job.id,
        ...
    )

    # Normalize
    normalized = modules.normalizer.normalize(raw_data)

    # Save normalized
    await s3_storage.save_normalized_data(
        platform=job.platform,
        ...
    )
```

## Adding New Platforms

To add a new platform (e.g., eBay, Etsy):

1. **Create Auth Module** (`app/auth/{platform}_auth.py`)
   - Implement OAuth flow
   - Must have: `get_authorization_url()`, `exchange_code_for_tokens()`, `refresh_access_token()`

2. **Create Fetcher** (`app/fetchers/{platform}_fetcher.py`)
   - Implement API client
   - Must have: `fetch_reviews(credentials, params)` returning raw data

3. **Create Normalizer** (`app/normalizers/{platform}_normalizer.py`)
   - Transform to unified schema
   - Must have: `normalize(raw_data)` returning standardized format

4. **Register Platform** in `app/platforms/init_platforms.py`:
   ```python
   platform_registry.register(
       platform="ebay",
       auth=ebay_auth_client,
       fetcher=ebay_fetcher,
       normalizer=ebay_normalizer,
   )
   ```

5. **Update Database**:
   - Add platform-specific credential fields if needed
   - Update enums/constraints

## Testing

### Unit Tests

```bash
pytest tests/test_shopify_auth.py
pytest tests/test_shopify_fetcher.py
pytest tests/test_shopify_normalizer.py
```

### Integration Test Example

```python
# Mock Shopify API
@pytest.mark.asyncio
async def test_shopify_review_fetch():
    with aioresponses() as m:
        # Mock OAuth
        m.post(
            "https://my-store.myshopify.com/admin/oauth/access_token",
            payload={"access_token": "token", "scope": "read_products"}
        )

        # Mock products API
        m.get(
            re.compile(r".*/admin/api/.*/products.json"),
            payload={"products": [...]}
        )

        # Test fetcher
        result = await shopify_fetcher.fetch_reviews(...)
        assert result["platform"] == "shopify"
```

## Production Considerations

### Security

- **Token Encryption**: Shopify access tokens are encrypted using `app.crypto.encrypt_refresh_token()`
- **HTTPS Required**: All Shopify callbacks must use HTTPS
- **CSRF Protection**: Use `state` parameter in OAuth flow
- **Webhook Verification**: Verify HMAC signatures for webhook events

### Rate Limiting

Shopify enforces rate limits:
- **REST Admin API**: 2 requests/second (can burst to 40)
- **GraphQL Admin API**: Cost-based (1000 points/second)

Implement token bucket rate limiting similar to Amazon's implementation.

### Monitoring

Track metrics:
- OAuth success/failure rates
- API response times
- Review fetch success rates per shop
- Token expiration/revocation events

### Error Handling

Common Shopify errors:
- `401`: Invalid/expired token → trigger reauthorization
- `403`: Insufficient permissions → check scopes
- `429`: Rate limit → back off and retry
- `5xx`: Shopify server error → exponential backoff

## Migration Guide

### Database Migration

```sql
-- Add platform support to sellers table
ALTER TABLE sellers ADD COLUMN platform VARCHAR(20) NOT NULL DEFAULT 'amazon';
ALTER TABLE sellers ADD COLUMN encrypted_access_token TEXT NULL;
ALTER TABLE sellers ALTER COLUMN marketplace_id DROP NOT NULL;
ALTER TABLE sellers ALTER COLUMN lwa_client_id DROP NOT NULL;
ALTER TABLE sellers ALTER COLUMN encrypted_refresh_token DROP NOT NULL;

-- Add platform support to fetch_jobs table
ALTER TABLE fetch_jobs ADD COLUMN platform VARCHAR(20) NOT NULL DEFAULT 'amazon';
ALTER TABLE fetch_jobs ADD COLUMN product_ids JSON NULL;
ALTER TABLE fetch_jobs ADD COLUMN request_params JSON NULL;
ALTER TABLE fetch_jobs ADD COLUMN total_items INTEGER DEFAULT 0;
ALTER TABLE fetch_jobs ADD COLUMN completed_items INTEGER DEFAULT 0;
ALTER TABLE fetch_jobs ADD COLUMN failed_items INTEGER DEFAULT 0;
ALTER TABLE fetch_jobs ALTER COLUMN marketplace_id DROP NOT NULL;
ALTER TABLE fetch_jobs ALTER COLUMN asins DROP NOT NULL;

-- Add platform support to asin_fetch_results table
ALTER TABLE asin_fetch_results ADD COLUMN platform VARCHAR(20) NOT NULL DEFAULT 'amazon';
ALTER TABLE asin_fetch_results ADD COLUMN product_id VARCHAR(50) NULL;
ALTER TABLE asin_fetch_results ALTER COLUMN asin DROP NOT NULL;

-- Create indexes
CREATE INDEX idx_sellers_platform ON sellers(platform);
CREATE INDEX idx_fetch_jobs_platform ON fetch_jobs(platform);
CREATE INDEX idx_asin_fetch_results_platform ON asin_fetch_results(platform);
CREATE INDEX idx_asin_fetch_results_product_id ON asin_fetch_results(product_id);
```

### Backward Compatibility

- Existing Amazon integrations continue to work unchanged
- Legacy fields (`total_asins`, `completed_asins`) maintained for backward compat
- Default platform is "amazon" for existing records

## Next Steps

1. ✅ Platform registry system
2. ✅ Shopify auth, fetcher, normalizer modules
3. ✅ Database schema updates
4. ✅ S3 storage with platform paths
5. ⏳ Update seller service for multi-platform
6. ⏳ Refactor worker tasks
7. ⏳ Update API routes
8. ⏳ Write comprehensive tests
9. ⏳ Deploy database migrations
10. ⏳ Update frontend to support platform selection

## Resources

- [Shopify OAuth Documentation](https://shopify.dev/docs/apps/auth/oauth)
- [Shopify Admin API](https://shopify.dev/docs/api/admin-rest)
- [Metafields Guide](https://shopify.dev/docs/apps/custom-data/metafields)
- [Review Apps Integration](https://apps.shopify.com/categories/marketing-product-reviews)

## Support

For questions or issues:
1. Check this documentation
2. Review the code in `app/platforms/`, `app/auth/shopify_*`, `app/fetchers/shopify_*`
3. Run tests: `pytest tests/test_shopify_*`
4. Check logs for detailed error messages
