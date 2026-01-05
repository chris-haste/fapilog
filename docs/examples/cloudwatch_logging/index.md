# CloudWatch Logging (LocalStack)

Run the CloudWatch sink locally with LocalStack using the example in
`examples/cloudwatch_logging/`.

## Steps

```bash
cd examples/cloudwatch_logging
docker-compose up -d
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_REGION=us-east-1
export FAPILOG_CLOUDWATCH__ENDPOINT_URL=http://localhost:4566
export FAPILOG_CLOUDWATCH__LOG_GROUP_NAME=/example/fastapi
uvicorn main:app --reload
```

Hit `http://localhost:8000/` and fetch logs:

```bash
aws --endpoint-url http://localhost:4566 logs get-log-events \
  --log-group-name /example/fastapi \
  --log-stream-name local
```

Use `FAPILOG_CORE__INTERNAL_LOGGING_ENABLED=true` to see diagnostics during
development.
