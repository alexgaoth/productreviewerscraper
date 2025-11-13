# Amazon Seller Reviews Ingestion Service

A production-ready microservice for ingesting Amazon seller reviews via the Selling Partner API (SP-API). This service handles Login with Amazon (LWA) OAuth, manages refresh tokens securely, fetches reviews with AWS Signature V4 authentication, and stores both raw and normalized data to S3.

## Features

- **LWA OAuth Integration**: Complete OAuth 2.0 flow for seller authorization
- **Secure Token Management**: Encrypted storage of refresh tokens with automatic refresh
- **SP-API Integration**: AWS SigV4-signed requests to Amazon's Selling Partner API
- **Robust Job System**: Celery-based async job processing with Redis
- **Dual Storage**: Raw API responses and normalized canonical data in S3
- **Rate Limiting**: Token bucket rate limiter with 429 response handling
- **Retry Logic**: Exponential backoff for transient errors
- **Monitoring**: Prometheus metrics for observability
- **RESTful API**: FastAPI-based endpoints for frontend/backend integration
- **Production Ready**: Docker support, comprehensive logging, error handling

## Architecture

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│  Frontend   │────────▶│  FastAPI     │────────▶│   Celery    │
│             │         │  REST API    │         │   Workers   │
└─────────────┘         └──────────────┘         └─────────────┘
                               │                        │
                               ▼                        ▼
                        ┌──────────────┐         ┌─────────────┐
                        │  PostgreSQL  │         │   Amazon    │
                        │   Database   │         │   SP-API    │
                        └──────────────┘         └─────────────┘
                               │                        │
                               │                        ▼
                               │                 ┌─────────────┐
                               └────────────────▶│     S3      │
                                                 │   Storage   │
                                                 └─────────────┘
```

## Technology Stack

- **Framework**: FastAPI (Python 3.11+)
- **Job Queue**: Celery + Redis
- **Database**: SQLAlchemy (SQLite/PostgreSQL)
- **Cloud**: AWS (S3, Secrets Manager)
- **Authentication**: LWA OAuth 2.0 + AWS SigV4
- **Monitoring**: Prometheus, Structlog
- **Testing**: Pytest, pytest-asyncio
- **Deployment**: Docker, Docker Compose

## Quick Start

### Prerequisites

- Python 3.11+
- Redis
- AWS Account with S3 and Secrets Manager
- Amazon Seller Central Developer Account
- SP-API Application Registration

### Installation

1. **Clone the repository**

```bash
git clone <repository-url>
cd productreviewerscraper
```

2. **Install dependencies**

```bash
pip install -r requirements.txt
```

3. **Configure environment**

```bash
cp .env.example .env
# Edit .env with your credentials
```

4. **Generate encryption key**

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Add to .env as ENCRYPTION_KEY
```

5. **Initialize database**

```bash
python -c "from app.database import init_db; init_db()"
```

### Running Locally

**Terminal 1: Start API server**
```bash
make run
# or
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2: Start Celery worker**
```bash
make worker
# or
celery -A app.worker.celery_app worker --loglevel=info
```

**Terminal 3: Start Redis (if not running)**
```bash
redis-server
```

### Running with Docker

```bash
# Build and start all services
make docker-build
make docker-up

# View logs
make docker-logs

# Stop services
make docker-down
```

Access the API at: `http://localhost:8000`

API Documentation: `http://localhost:8000/docs`

## Configuration

### Environment Variables

See `.env.example` for all configuration options. Key variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `LWA_CLIENT_ID` | Login with Amazon client ID | Yes |
| `LWA_CLIENT_SECRET` | Login with Amazon client secret | Yes |
| `LWA_REDIRECT_URI` | OAuth callback URI | Yes |
| `SPAPI_AWS_ACCESS_KEY_ID` | AWS credentials for SigV4 | Yes |
| `SPAPI_AWS_SECRET_ACCESS_KEY` | AWS secret key for SigV4 | Yes |
| `ENCRYPTION_KEY` | Fernet key for token encryption | Yes |
| `S3_BUCKET_RAW` | S3 bucket for raw data | Yes |
| `S3_BUCKET_PROCESSED` | S3 bucket for processed data | Yes |
| `DATABASE_URL` | Database connection string | Yes |
| `REDIS_URL` | Redis connection string | Yes |

### AWS Setup

1. **S3 Buckets**: Create two S3 buckets (raw and processed)
2. **IAM Role**: Create IAM role with S3 write permissions
3. **Secrets Manager** (optional): Store LWA and SP-API credentials
4. **SP-API Credentials**: Register app in Amazon Seller Central

## API Endpoints

### Authentication

#### Start OAuth Flow
```http
GET /api/v1/auth/amazon/start?seller_id=A1SELLER
```

Returns redirect URL to Amazon authorization page.

#### OAuth Callback
```http
POST /api/v1/auth/amazon/callback
Content-Type: application/json

{
  "code": "auth_code_from_amazon",
  "state": "csrf_state_token",
  "seller_id": "A1SELLER",
  "marketplace_id": "ATVPDKIKX0DER"
}
```

Response:
```json
{
  "ok": true,
  "seller_id": "A1SELLER",
  "message": "Authorization successful"
}
```

### Review Fetching

#### Fetch Reviews
```http
POST /api/v1/fetch/reviews
Content-Type: application/json

{
  "seller_id": "A1SELLER",
  "marketplace_id": "ATVPDKIKX0DER",
  "asins": ["B07EXAMPLE1", "B08EXAMPLE2"],
  "mode": "full"
}
```

Response:
```json
{
  "job_id": "job-20251113-abc123",
  "status": "pending",
  "message": "Job queued successfully",
  "asins_count": 2
}
```

#### Get Job Status
```http
GET /api/v1/jobs/{job_id}/status
```

Response:
```json
{
  "job_id": "job-20251113-abc123",
  "status": "success",
  "seller_id": "A1SELLER",
  "total_asins": 2,
  "completed_asins": 2,
  "failed_asins": 0,
  "total_reviews_fetched": 245,
  "s3_raw_keys": ["s3://..."],
  "s3_processed_keys": ["s3://..."],
  "duration_seconds": 45.2
}
```

### Seller Management

#### Get Seller Token Metadata
```http
GET /api/v1/seller/{seller_id}/tokens
```

#### Get Seller Jobs
```http
GET /api/v1/seller/{seller_id}/jobs?limit=10
```

## Data Schema

### Normalized Review Format

```json
{
  "job_id": "job-20251113-abc123",
  "seller_id": "A1SELLER",
  "marketplace_id": "ATVPDKIKX0DER",
  "asin": "B07EXAMPLE",
  "fetched_at": "2025-11-13T14:30:00Z",
  "reviews_count": 123,
  "reviews": [
    {
      "review_id": "R1EXAMPLE",
      "reviewer_id": "A2REVIEWER",
      "display_name": "John D.",
      "rating": 5,
      "title": "Great product",
      "body": "Excellent quality and fast shipping.",
      "verified_purchase": true,
      "helpful_votes": 10,
      "language": "en-US",
      "review_date": "2025-11-01T00:00:00Z",
      "asin": "B07EXAMPLE",
      "marketplace_id": "ATVPDKIKX0DER"
    }
  ],
  "meta": {
    "pages_fetched": 3,
    "next_token": null,
    "fetch_duration_seconds": 12.5
  }
}
```

## Testing

```bash
# Run all tests
make test

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_sigv4.py
```

## Monitoring

### Prometheus Metrics

Metrics are exposed on port 9090 (configurable):

- `reviews_fetched_total` - Total reviews fetched
- `jobs_started_total` - Total jobs started
- `jobs_completed_total` - Total jobs completed
- `lwa_refresh_failures_total` - LWA token refresh failures
- `spapi_rate_limits_total` - Rate limit hits
- `s3_put_duration_seconds` - S3 operation latency

### Logging

Structured JSON logs to stdout using structlog:

```json
{
  "event": "reviews_fetched",
  "job_id": "job-123",
  "asin": "B07EXAMPLE",
  "reviews_count": 50,
  "timestamp": "2025-11-13T14:30:00Z",
  "level": "info"
}
```

## Security

- **Encrypted Tokens**: Refresh tokens encrypted with Fernet (AES-128)
- **Secrets Manager**: Production credentials stored in AWS Secrets Manager
- **No Token Logging**: Access/refresh tokens never logged
- **IAM Roles**: Use IAM roles instead of long-lived keys where possible
- **HTTPS Only**: All external API calls over HTTPS
- **Input Validation**: Pydantic schema validation on all endpoints

## Rate Limiting

Per-seller token bucket with configurable:
- Refill rate: 2 requests/second (default)
- Burst capacity: 10 requests (default)
- 429 handling: Respect `Retry-After` headers

## Error Handling

- **401/403**: Token refresh attempt, then mark seller for reauthorization
- **429**: Exponential backoff with jitter
- **5xx**: Retry with exponential backoff (max 3 retries)
- **Network errors**: Automatic retry with backoff

## Deployment

### Production Checklist

- [ ] Generate strong encryption key
- [ ] Configure AWS Secrets Manager
- [ ] Set up S3 buckets with lifecycle policies
- [ ] Configure IAM roles/permissions
- [ ] Set up monitoring/alerting
- [ ] Configure log aggregation
- [ ] Set resource limits (CPU/memory)
- [ ] Enable HTTPS/TLS
- [ ] Configure CORS appropriately
- [ ] Set up database backups
- [ ] Configure auto-scaling for workers

### Docker Production

```bash
# Build for production
docker build -t reviews-api:latest .
docker build -f Dockerfile.worker -t reviews-worker:latest .

# Run with production settings
docker run -d \
  --name reviews-api \
  -p 8000:8000 \
  --env-file .env.production \
  reviews-api:latest
```

## Troubleshooting

### Common Issues

**Token refresh fails**
- Check LWA credentials in Secrets Manager
- Verify seller hasn't revoked access
- Check encryption key is correct

**SP-API 403 errors**
- Verify SP-API credentials
- Check IAM role permissions
- Ensure SigV4 signing is correct

**Worker not processing jobs**
- Check Redis connection
- Verify Celery broker URL
- Check worker logs for errors

**S3 upload fails**
- Verify IAM permissions
- Check bucket names
- Ensure AWS credentials are valid

## License

MIT License - See LICENSE file for details
