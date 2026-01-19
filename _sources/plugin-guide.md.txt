<!-- AUTO-GENERATED: do not edit by hand. Run scripts/generate_env_matrix.py -->
# Plugin Catalog

| Name | Type | Version | API | Author | Description |
|------|------|---------|-----|--------|-------------|
| context_vars | enricher | 1.1.0 | 1.1 | Fapilog Core | Adds request/trace identifiers (request_id, user_id, trace_id) to context group. |
| field_mask | redactor | 1.0.0 | 1.0 | Fapilog Core | Masks configured fields in structured events. |
| http | sink | 1.0.0 | 1.0 | Fapilog Core | Async HTTP sink that POSTs JSON to a configured endpoint. |
| kubernetes | enricher | 1.1.0 | 1.1 | Fapilog Core | Adds K8s pod metadata (pod, namespace, node, deployment) to diagnostics group. |
| mmap_persistence | sink | 1.0.0 | 1.0 | Fapilog Core | Memory-mapped file sink for zero-copy friendly persistence. |
| regex_mask | redactor | 1.0.0 | 1.0 | Fapilog Core | Masks values for fields whose dot-paths match configured regex patterns. |
| rotating_file | sink | 1.0.0 | 1.0 | Fapilog Core | Async rotating file sink with size/time rotation and retention |
| routing | sink | 1.0.0 | 1.0 | Fapilog Core | Routes log events to different sinks based on log level. |
| runtime_info | enricher | 1.1.0 | 1.1 | Fapilog Core | Adds runtime/system info (host, pid, python) to diagnostics group. |
| size_guard | processor | 1.0.0 | 1.0 | Fapilog Core | Enforces maximum payload size for downstream compatibility. |
| stdout_json | sink | 1.0.0 | 1.0 | Fapilog Core | Async stdout JSONL sink |
| stdout_pretty | sink | 1.0.0 | 1.0 | Fapilog Core | Async stdout pretty console sink |
| url_credentials | redactor | 1.0.0 | 1.0 | Fapilog Core | Strips user:pass@ credentials from URL-like strings. |
| webhook | sink | 1.0.0 | 1.0 | Fapilog Core | Webhook sink that POSTs JSON with optional signing. |
| zero_copy | processor | 1.0.0 | 1.0 | Fapilog Core | Zero-copy pass-through processor for performance benchmarking. |
