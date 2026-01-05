# Azure Monitor Logs (preview)

Azure integration follows the same batching/auth patterns as other cloud sinks.

- Use Azure AD application or Managed Identity for authentication.
- Send logs to the Data Collector API endpoint.
- Recommended approach: derive a sink from `CloudSinkBase` and post to `_azure.com/api/logs?api-version=2016-04-01`.

> A full reference sink is planned; adapt the Datadog pattern with Azure auth handlers in the meantime.
