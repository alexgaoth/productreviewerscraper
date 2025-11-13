# API Documentation

## Base URL

```
http://localhost:8000/api/v1
```

Production: `https://your-domain.com/api/v1`

## Authentication

Most endpoints require seller authentication via LWA OAuth tokens stored in the database.

## Endpoints

### Health Check

#### GET /health

Health check endpoint.

**Response**
```json
{
  "status": "healthy",
  "timestamp": "2025-11-13T14:30:00Z",
  "version": "1.0.0"
}
```

---

### OAuth / Authentication

#### GET /auth/amazon/start

Start OAuth flow by redirecting to Amazon LWA.

**Query Parameters**
- `seller_id` (required): Seller identifier
- `return_to` (optional): Return URL after auth

**Response**

302 Redirect to Amazon authorization page

---

#### POST /auth/amazon/callback

Handle OAuth callback after user authorizes.

**Request Body**
```json
{
  "code": "string",
  "state": "string",
  "seller_id": "string",
  "marketplace_id": "string",
  "seller_name": "string (optional)",
  "seller_email": "string (optional)"
}
```

**Response**
```json
{
  "ok": true,
  "seller_id": "A1SELLER",
  "message": "Authorization successful"
}
```

**Error Response (400)**
```json
{
  "detail": "Authorization failed: invalid code"
}
```

---

#### POST /seller/{seller_id}/refresh-token

Manually trigger token refresh for a seller.

**Path Parameters**
- `seller_id`: Seller ID

**Response**
```json
{
  "ok": true,
  "message": "Token refreshed successfully"
}
```

**Error Response (404)**
```json
{
  "detail": "Seller not found"
}
```

---

#### GET /seller/{seller_id}/tokens

Get seller token metadata (not actual tokens).

**Path Parameters**
- `seller_id`: Seller ID

**Response**
```json
{
  "seller_id": "A1SELLER",
  "marketplace_id": "ATVPDKIKX0DER",
  "status": "active",
  "created_at": "2025-11-01T10:00:00Z",
  "last_token_refresh_at": "2025-11-13T14:00:00Z",
  "last_token_refresh_error": null
}
```

---

### Review Fetching

#### POST /fetch/reviews

Request to fetch reviews for ASINs.

**Request Body**
```json
{
  "seller_id": "string",
  "marketplace_id": "string",
  "asins": ["string"],
  "start_date": "2025-01-01T00:00:00Z (optional)",
  "end_date": "2025-11-01T23:59:59Z (optional)",
  "mode": "full | recent"
}
```

**Response (202)**
```json
{
  "job_id": "job-20251113-abc123",
  "status": "pending",
  "message": "Job queued successfully",
  "asins_count": 2
}
```

**Error Response (404)**
```json
{
  "detail": "Seller not found"
}
```

**Error Response (400)**
```json
{
  "detail": "Seller is not active. Status: reauthorize_required"
}
```

---

#### GET /jobs/{job_id}/status

Get job status.

**Path Parameters**
- `job_id`: Job ID

**Response**
```json
{
  "job_id": "job-20251113-abc123",
  "status": "success",
  "seller_id": "A1SELLER",
  "marketplace_id": "ATVPDKIKX0DER",
  "asins": ["B07EXAMPLE1", "B08EXAMPLE2"],
  "total_asins": 2,
  "completed_asins": 2,
  "failed_asins": 0,
  "total_reviews_fetched": 245,
  "created_at": "2025-11-13T14:00:00Z",
  "started_at": "2025-11-13T14:00:05Z",
  "completed_at": "2025-11-13T14:00:50Z",
  "duration_seconds": 45.2,
  "error_message": null,
  "s3_raw_keys": [
    "s3://bucket/raw/A1SELLER/ATVPDKIKX0DER/B07EXAMPLE1/..."
  ],
  "s3_processed_keys": [
    "s3://bucket/processed/A1SELLER/ATVPDKIKX0DER/B07EXAMPLE1/..."
  ]
}
```

**Status Values**
- `pending`: Job queued
- `in_progress`: Job running
- `success`: All ASINs completed successfully
- `partial_success`: Some ASINs completed
- `failed`: Job failed
- `cancelled`: Job cancelled

---

#### GET /jobs/{job_id}/asins

Get detailed ASIN results for a job.

**Path Parameters**
- `job_id`: Job ID

**Response**
```json
[
  {
    "asin": "B07EXAMPLE1",
    "status": "success",
    "reviews_count": 123,
    "pages_fetched": 3,
    "error_message": null
  },
  {
    "asin": "B08EXAMPLE2",
    "status": "failed",
    "reviews_count": 0,
    "pages_fetched": 0,
    "error_message": "Rate limit exceeded"
  }
]
```

---

#### GET /seller/{seller_id}/jobs

Get recent jobs for a seller.

**Path Parameters**
- `seller_id`: Seller ID

**Query Parameters**
- `limit` (optional): Maximum jobs to return (1-100, default: 10)

**Response**

Array of job status objects (same schema as `/jobs/{job_id}/status`)

---

## Error Codes

| Status Code | Description |
|-------------|-------------|
| 200 | Success |
| 202 | Accepted (async job created) |
| 400 | Bad request |
| 404 | Resource not found |
| 500 | Internal server error |

## Rate Limiting

API endpoints are not rate limited, but review fetching jobs are subject to SP-API rate limits per seller.

## Webhooks (Future)

Future versions may support webhooks for job completion notifications.

**Webhook Payload (Proposed)**
```json
{
  "event": "job.completed",
  "job_id": "job-20251113-abc123",
  "seller_id": "A1SELLER",
  "status": "success",
  "timestamp": "2025-11-13T14:00:50Z",
  "data": {
    "total_reviews_fetched": 245,
    "s3_processed_keys": ["s3://..."]
  }
}
```
