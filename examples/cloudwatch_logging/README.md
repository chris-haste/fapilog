# CloudWatch Logging Example (LocalStack)

This example shows how to send logs to AWS CloudWatch Logs using LocalStack.

## Prereqs

- Python 3.8+
- Docker
- LocalStack image
- `boto3` (`pip install fapilog[cloudwatch]` or `pip install boto3`)

## Quick start

```bash
docker-compose up -d
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_REGION=us-east-1
export FAPILOG_CLOUDWATCH__ENDPOINT_URL=http://localhost:4566
export FAPILOG_CLOUDWATCH__LOG_GROUP_NAME=/example/fastapi
uvicorn main:app --reload
```

Hit `http://localhost:8000/` and then inspect logs in LocalStack:

```bash
aws --endpoint-url http://localhost:4566 logs get-log-events \
  --log-group-name /example/fastapi \
  --log-stream-name local
```
