<!-- AUTO-GENERATED: do not edit by hand. Run scripts/generate_env_matrix.py -->
# Plugin Catalog

| Name | Type | Version | API | Author | Description |
|------|------|---------|-----|--------|-------------|
| context-vars-enricher | enricher | 1.0.0 | 1.0 | Fapilog Core | Adds context variables like request_id and user_id when available. |
| field-mask | redactor | 1.0.0 | 1.0 | Fapilog Core | Masks configured fields in structured events. |
| http | sink | 1.0.0 | 1.0 | Fapilog Core | Async HTTP sink that POSTs JSON to a configured endpoint. |
| regex-mask | redactor | 1.0.0 | 1.0 | Fapilog Core | Masks values for fields whose dot-paths match configured regex patterns. |
| rotating-file | sink | 1.0.0 | 1.0 | Fapilog Core | Async rotating file sink with size/time rotation and retention |
| runtime-info-enricher | enricher | 1.0.0 | 1.0 | Fapilog Core | Adds runtime/system information such as host, pid, and python version. |
| stdout-json | sink | 1.0.0 | 1.0 | Fapilog Core | Async stdout JSONL sink |
| url-credentials | redactor | 1.0.0 | 1.0 | Fapilog Core | Strips user:pass@ credentials from URL-like strings. |
| webhook | sink | 1.0.0 | 1.0 | Fapilog Core | Webhook sink that POSTs JSON with optional signing. |
| zero-copy | processor | 1.0.0 | 1.0 | Fapilog Core | Zero-copy pass-through processor for performance benchmarking. |
