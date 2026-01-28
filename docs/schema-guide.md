<!-- AUTO-GENERATED: do not edit by hand. Run scripts/generate_env_matrix.py -->
# Schema Guide

## Settings JSON Schemas

### CoreSettings

```json
{
  "description": "Core logging and performance settings.\n\nKeep this minimal and stable; prefer plugin-specific settings elsewhere.",
  "properties": {
    "app_name": {
      "default": "fapilog",
      "description": "Logical application name",
      "title": "App Name",
      "type": "string"
    },
    "atexit_drain_enabled": {
      "default": true,
      "description": "Register atexit handler to drain pending logs on normal process exit",
      "title": "Atexit Drain Enabled",
      "type": "boolean"
    },
    "atexit_drain_timeout_seconds": {
      "default": 2.0,
      "description": "Maximum seconds to wait for log drain during atexit handler",
      "exclusiveMinimum": 0.0,
      "title": "Atexit Drain Timeout Seconds",
      "type": "number"
    },
    "backpressure_wait_ms": {
      "default": 50,
      "description": "Milliseconds to wait for queue space before dropping",
      "minimum": 0,
      "title": "Backpressure Wait Ms",
      "type": "integer"
    },
    "batch_max_size": {
      "default": 256,
      "description": "Maximum number of events per batch before a flush is triggered",
      "minimum": 1,
      "title": "Batch Max Size",
      "type": "integer"
    },
    "batch_timeout_seconds": {
      "default": 0.25,
      "description": "Maximum time to wait before flushing a partial batch",
      "exclusiveMinimum": 0.0,
      "title": "Batch Timeout Seconds",
      "type": "number"
    },
    "benchmark_file_path": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Optional path used by performance benchmarks",
      "title": "Benchmark File Path"
    },
    "capture_unhandled_enabled": {
      "default": false,
      "description": "Automatically install unhandled exception hooks (sys/asyncio)",
      "title": "Capture Unhandled Enabled",
      "type": "boolean"
    },
    "context_binding_enabled": {
      "default": true,
      "description": "Enable per-task bound context via logger.bind/unbind/clear",
      "title": "Context Binding Enabled",
      "type": "boolean"
    },
    "default_bound_context": {
      "additionalProperties": true,
      "description": "Default bound context applied at logger creation when enabled",
      "title": "Default Bound Context",
      "type": "object"
    },
    "diagnostics_output": {
      "default": "stderr",
      "description": "Output stream for internal diagnostics: stderr (default, Unix convention) or stdout (backward compat)",
      "enum": [
        "stderr",
        "stdout"
      ],
      "title": "Diagnostics Output",
      "type": "string"
    },
    "drop_on_full": {
      "default": true,
      "description": "If True, drop events after backpressure_wait_ms elapses when queue is full",
      "title": "Drop On Full",
      "type": "boolean"
    },
    "drop_summary_window_seconds": {
      "default": 60.0,
      "description": "Window in seconds for aggregating drop/dedupe summary events. Summaries are emitted at most once per window.",
      "minimum": 1.0,
      "title": "Drop Summary Window Seconds",
      "type": "number"
    },
    "emit_drop_summary": {
      "default": false,
      "description": "Emit summary log events when events are dropped due to backpressure or deduplicated due to error dedupe window",
      "title": "Emit Drop Summary",
      "type": "boolean"
    },
    "enable_metrics": {
      "default": false,
      "description": "Enable Prometheus-compatible metrics",
      "title": "Enable Metrics",
      "type": "boolean"
    },
    "enable_redactors": {
      "default": true,
      "description": "Enable redactors stage between enrichers and sink emission",
      "title": "Enable Redactors",
      "type": "boolean"
    },
    "enrichers": {
      "description": "Enricher plugins to use (by name)",
      "items": {
        "type": "string"
      },
      "title": "Enrichers",
      "type": "array"
    },
    "error_dedupe_window_seconds": {
      "default": 5.0,
      "description": "Seconds to suppress duplicate ERROR logs with the same message; 0 disables deduplication",
      "minimum": 0.0,
      "title": "Error Dedupe Window Seconds",
      "type": "number"
    },
    "exceptions_enabled": {
      "default": true,
      "description": "Enable structured exception serialization for log calls",
      "title": "Exceptions Enabled",
      "type": "boolean"
    },
    "exceptions_max_frames": {
      "default": 10,
      "description": "Maximum number of stack frames to capture for exceptions",
      "minimum": 1,
      "title": "Exceptions Max Frames",
      "type": "integer"
    },
    "exceptions_max_stack_chars": {
      "default": 20000,
      "description": "Maximum total characters for serialized stack string",
      "minimum": 1000,
      "title": "Exceptions Max Stack Chars",
      "type": "integer"
    },
    "fallback_raw_max_bytes": {
      "anyOf": [
        {
          "minimum": 1,
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Optional limit for raw fallback output bytes; payloads exceeding this are truncated with '[truncated]' marker",
      "title": "Fallback Raw Max Bytes"
    },
    "fallback_redact_mode": {
      "default": "minimal",
      "description": "Redaction mode for fallback stderr output: 'inherit' uses pipeline redactors, 'minimal' applies built-in sensitive field masking, 'none' writes unredacted (opt-in to legacy behavior)",
      "enum": [
        "inherit",
        "minimal",
        "none"
      ],
      "title": "Fallback Redact Mode",
      "type": "string"
    },
    "fallback_scrub_raw": {
      "default": true,
      "description": "Apply keyword scrubbing to raw (non-JSON) fallback output; set to False for debugging when raw output is needed",
      "title": "Fallback Scrub Raw",
      "type": "boolean"
    },
    "filters": {
      "description": "Filter plugins to apply before enrichment (by name)",
      "items": {
        "type": "string"
      },
      "title": "Filters",
      "type": "array"
    },
    "flush_on_critical": {
      "default": false,
      "description": "Immediately flush ERROR and CRITICAL logs (bypass batching) to reduce log loss on abrupt shutdown",
      "title": "Flush On Critical",
      "type": "boolean"
    },
    "internal_logging_enabled": {
      "default": false,
      "description": "Emit DEBUG/WARN diagnostics for internal errors",
      "title": "Internal Logging Enabled",
      "type": "boolean"
    },
    "log_level": {
      "default": "INFO",
      "description": "Default log level",
      "enum": [
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR"
      ],
      "title": "Log Level",
      "type": "string"
    },
    "max_queue_size": {
      "default": 10000,
      "description": "Maximum in-memory queue size for async processing",
      "minimum": 1,
      "title": "Max Queue Size",
      "type": "integer"
    },
    "processors": {
      "description": "Processor plugins to use (by name)",
      "items": {
        "type": "string"
      },
      "title": "Processors",
      "type": "array"
    },
    "redaction_fail_mode": {
      "default": "warn",
      "description": "Behavior when _apply_redactors() catches an unexpected exception: 'open' passes original event, 'closed' drops the event, 'warn' (default) passes event but emits diagnostic warning",
      "enum": [
        "open",
        "closed",
        "warn"
      ],
      "title": "Redaction Fail Mode",
      "type": "string"
    },
    "redaction_max_depth": {
      "anyOf": [
        {
          "minimum": 1,
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": 6,
      "description": "Optional max depth guardrail for nested redaction",
      "title": "Redaction Max Depth"
    },
    "redaction_max_keys_scanned": {
      "anyOf": [
        {
          "minimum": 1,
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": 5000,
      "description": "Optional max keys scanned guardrail for redaction",
      "title": "Redaction Max Keys Scanned"
    },
    "redactors": {
      "description": "Redactor plugins to use (by name); defaults to ['url_credentials'] for secure defaults; set to [] to disable all redaction",
      "items": {
        "type": "string"
      },
      "title": "Redactors",
      "type": "array"
    },
    "redactors_order": {
      "description": "Ordered list of redactor plugin names to apply",
      "items": {
        "type": "string"
      },
      "title": "Redactors Order",
      "type": "array"
    },
    "resource_pool_acquire_timeout_seconds": {
      "default": 2.0,
      "description": "Default acquire timeout for pools",
      "exclusiveMinimum": 0.0,
      "title": "Resource Pool Acquire Timeout Seconds",
      "type": "number"
    },
    "resource_pool_max_size": {
      "default": 8,
      "description": "Default max size for resource pools",
      "minimum": 1,
      "title": "Resource Pool Max Size",
      "type": "integer"
    },
    "sensitive_fields_policy": {
      "description": "Optional list of dotted paths for sensitive fields policy; warning if no redactors configured",
      "items": {
        "type": "string"
      },
      "title": "Sensitive Fields Policy",
      "type": "array"
    },
    "serialize_in_flush": {
      "default": false,
      "description": "If True, pre-serialize envelopes once during flush and pass SerializedView to sinks that support write_serialized",
      "title": "Serialize In Flush",
      "type": "boolean"
    },
    "shutdown_timeout_seconds": {
      "default": 3.0,
      "description": "Maximum time to flush on shutdown signals",
      "exclusiveMinimum": 0.0,
      "title": "Shutdown Timeout Seconds",
      "type": "number"
    },
    "signal_handler_enabled": {
      "default": true,
      "description": "Install signal handlers for SIGTERM/SIGINT to enable graceful drain",
      "title": "Signal Handler Enabled",
      "type": "boolean"
    },
    "sink_circuit_breaker_enabled": {
      "default": false,
      "description": "Enable circuit breaker for sink fault isolation",
      "title": "Sink Circuit Breaker Enabled",
      "type": "boolean"
    },
    "sink_circuit_breaker_failure_threshold": {
      "default": 5,
      "description": "Number of consecutive failures before opening circuit",
      "minimum": 1,
      "title": "Sink Circuit Breaker Failure Threshold",
      "type": "integer"
    },
    "sink_circuit_breaker_recovery_timeout_seconds": {
      "default": 30.0,
      "description": "Seconds to wait before probing a failed sink",
      "exclusiveMinimum": 0.0,
      "title": "Sink Circuit Breaker Recovery Timeout Seconds",
      "type": "number"
    },
    "sink_parallel_writes": {
      "default": false,
      "description": "Write to multiple sinks in parallel instead of sequentially",
      "title": "Sink Parallel Writes",
      "type": "boolean"
    },
    "sinks": {
      "description": "Sink plugins to use (by name); falls back to env-based default when empty",
      "items": {
        "type": "string"
      },
      "title": "Sinks",
      "type": "array"
    },
    "strict_envelope_mode": {
      "default": false,
      "description": "If True, drop emission when envelope cannot be produced; otherwise fallback to best-effort serialization with diagnostics",
      "title": "Strict Envelope Mode",
      "type": "boolean"
    },
    "worker_count": {
      "default": 1,
      "description": "Number of worker tasks for flush processing",
      "minimum": 1,
      "title": "Worker Count",
      "type": "integer"
    }
  },
  "title": "CoreSettings",
  "type": "object"
}
```

### SecuritySettings

```json
{
  "$defs": {
    "AccessControlSettings": {
      "description": "Settings for access control and authorization.",
      "properties": {
        "allow_anonymous_read": {
          "default": false,
          "description": "Permit read access without authentication (discouraged)",
          "title": "Allow Anonymous Read",
          "type": "boolean"
        },
        "allow_anonymous_write": {
          "default": false,
          "description": "Permit write access without authentication (never recommended)",
          "title": "Allow Anonymous Write",
          "type": "boolean"
        },
        "allowed_roles": {
          "description": "List of roles granted access to protected operations",
          "items": {
            "type": "string"
          },
          "title": "Allowed Roles",
          "type": "array"
        },
        "auth_mode": {
          "default": "token",
          "description": "Authentication mode used by integrations (library-agnostic)",
          "enum": [
            "none",
            "basic",
            "token",
            "oauth2"
          ],
          "title": "Auth Mode",
          "type": "string"
        },
        "enabled": {
          "default": true,
          "description": "Enable access control checks across the system",
          "title": "Enabled",
          "type": "boolean"
        },
        "require_admin_for_sensitive_ops": {
          "default": true,
          "description": "Require admin role for sensitive or destructive operations",
          "title": "Require Admin For Sensitive Ops",
          "type": "boolean"
        }
      },
      "title": "AccessControlSettings",
      "type": "object"
    },
    "EncryptionSettings": {
      "description": "Settings controlling encryption for sensitive data and transport.\n\nThis model is intentionally conservative with defaults matching\nenterprise expectations.",
      "properties": {
        "algorithm": {
          "default": "AES-256",
          "description": "Primary encryption algorithm",
          "enum": [
            "AES-256",
            "ChaCha20-Poly1305",
            "AES-128"
          ],
          "title": "Algorithm",
          "type": "string"
        },
        "enabled": {
          "default": true,
          "description": "Enable encryption features",
          "title": "Enabled",
          "type": "boolean"
        },
        "env_var_name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Environment variable holding key material",
          "title": "Env Var Name"
        },
        "key_file_path": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Filesystem path to key material",
          "title": "Key File Path"
        },
        "key_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Key identifier for KMS/Vault sources",
          "title": "Key Id"
        },
        "key_source": {
          "anyOf": [
            {
              "enum": [
                "env",
                "file",
                "kms",
                "vault"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Source for key material",
          "title": "Key Source"
        },
        "min_tls_version": {
          "default": "1.2",
          "description": "Minimum TLS version for transport",
          "enum": [
            "1.2",
            "1.3"
          ],
          "title": "Min Tls Version",
          "type": "string"
        },
        "rotate_interval_days": {
          "default": 90,
          "description": "Recommended key rotation interval",
          "minimum": 0,
          "title": "Rotate Interval Days",
          "type": "integer"
        }
      },
      "title": "EncryptionSettings",
      "type": "object"
    }
  },
  "description": "Aggregated security settings for the library.",
  "properties": {
    "access_control": {
      "$ref": "#/$defs/AccessControlSettings",
      "description": "Authentication/authorization and role-based access control"
    },
    "encryption": {
      "$ref": "#/$defs/EncryptionSettings",
      "description": "Cryptography, key management, and data protection settings"
    }
  },
  "title": "SecuritySettings",
  "type": "object"
}
```

### ObservabilitySettings

```json
{
  "$defs": {
    "AlertingSettings": {
      "properties": {
        "enabled": {
          "default": false,
          "description": "Enable emitting alerts from the logging pipeline",
          "title": "Enabled",
          "type": "boolean"
        },
        "min_severity": {
          "default": "ERROR",
          "description": "Minimum alert severity to emit (filter threshold)",
          "enum": [
            "INFO",
            "WARNING",
            "ERROR",
            "CRITICAL"
          ],
          "title": "Min Severity",
          "type": "string"
        }
      },
      "title": "AlertingSettings",
      "type": "object"
    },
    "LoggingSettings": {
      "properties": {
        "format": {
          "default": "json",
          "description": "Output format for logs (machine-friendly JSON or text)",
          "enum": [
            "json",
            "text"
          ],
          "title": "Format",
          "type": "string"
        },
        "include_correlation": {
          "default": true,
          "description": "Include correlation IDs and trace/span metadata in logs",
          "title": "Include Correlation",
          "type": "boolean"
        },
        "sampling_rate": {
          "default": 1.0,
          "description": "DEPRECATED: Use core.filters=['sampling'] with filter_config.sampling instead. Log sampling probability in range 0.0\u20131.0.",
          "maximum": 1.0,
          "minimum": 0.0,
          "title": "Sampling Rate",
          "type": "number"
        }
      },
      "title": "LoggingSettings",
      "type": "object"
    },
    "MetricsSettings": {
      "properties": {
        "enabled": {
          "default": false,
          "description": "Enable internal metrics collection/export",
          "title": "Enabled",
          "type": "boolean"
        },
        "exporter": {
          "default": "prometheus",
          "description": "Metrics exporter to use ('prometheus' or 'none')",
          "enum": [
            "prometheus",
            "none"
          ],
          "title": "Exporter",
          "type": "string"
        },
        "port": {
          "default": 8000,
          "description": "TCP port for metrics exporter",
          "maximum": 65535,
          "minimum": 1,
          "title": "Port",
          "type": "integer"
        }
      },
      "title": "MetricsSettings",
      "type": "object"
    },
    "MonitoringSettings": {
      "properties": {
        "enabled": {
          "default": false,
          "description": "Enable health/monitoring checks and endpoints",
          "title": "Enabled",
          "type": "boolean"
        },
        "endpoint": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Monitoring endpoint URL",
          "title": "Endpoint"
        }
      },
      "title": "MonitoringSettings",
      "type": "object"
    },
    "TracingSettings": {
      "properties": {
        "enabled": {
          "default": false,
          "description": "Enable distributed tracing features",
          "title": "Enabled",
          "type": "boolean"
        },
        "provider": {
          "default": "otel",
          "description": "Tracing backend provider ('otel' or 'none')",
          "enum": [
            "otel",
            "none"
          ],
          "title": "Provider",
          "type": "string"
        },
        "sampling_rate": {
          "default": 0.1,
          "description": "Trace sampling probability in range 0.0\u20131.0",
          "maximum": 1.0,
          "minimum": 0.0,
          "title": "Sampling Rate",
          "type": "number"
        }
      },
      "title": "TracingSettings",
      "type": "object"
    }
  },
  "properties": {
    "alerting": {
      "$ref": "#/$defs/AlertingSettings",
      "description": "Alerting configuration"
    },
    "logging": {
      "$ref": "#/$defs/LoggingSettings",
      "description": "Logging output format and correlation settings"
    },
    "metrics": {
      "$ref": "#/$defs/MetricsSettings",
      "description": "Metrics configuration (exporter and port)"
    },
    "monitoring": {
      "$ref": "#/$defs/MonitoringSettings",
      "description": "Monitoring configuration (health/endpoint)"
    },
    "tracing": {
      "$ref": "#/$defs/TracingSettings",
      "description": "Tracing configuration"
    }
  },
  "title": "ObservabilitySettings",
  "type": "object"
}
```

### PluginsSettings

```json
{
  "description": "Settings controlling plugin behavior.",
  "properties": {
    "allow_external": {
      "default": false,
      "description": "Allow loading plugins from entry points (security risk)",
      "title": "Allow External",
      "type": "boolean"
    },
    "allowlist": {
      "description": "If non-empty, only these plugin names are allowed",
      "items": {
        "type": "string"
      },
      "title": "Allowlist",
      "type": "array"
    },
    "denylist": {
      "description": "Plugin names to block from loading",
      "items": {
        "type": "string"
      },
      "title": "Denylist",
      "type": "array"
    },
    "enabled": {
      "default": true,
      "description": "Enable plugin loading",
      "title": "Enabled",
      "type": "boolean"
    },
    "validation_mode": {
      "default": "disabled",
      "description": "Plugin validation mode: disabled, warn, or strict",
      "title": "Validation Mode",
      "type": "string"
    }
  },
  "title": "PluginsSettings",
  "type": "object"
}
```

## LogEnvelope Schema

### LogEnvelope v1.x (from file)

```json
{
  "$id": "https://fapilog.dev/schemas/log_envelope_v1.json",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "additionalProperties": false,
  "description": "Canonical log schema v1.1 with semantic field groupings: context (request/trace identifiers), diagnostics (runtime/operational data), and data (user-provided structured data).",
  "properties": {
    "log": {
      "additionalProperties": true,
      "properties": {
        "context": {
          "additionalProperties": true,
          "description": "Request/trace context - identifies WHO and WHAT request",
          "properties": {
            "correlation_id": {
              "type": "string"
            },
            "request_id": {
              "type": "string"
            },
            "span_id": {
              "type": "string"
            },
            "tenant_id": {
              "type": "string"
            },
            "trace_id": {
              "type": "string"
            },
            "user_id": {
              "type": "string"
            }
          },
          "type": "object"
        },
        "data": {
          "additionalProperties": true,
          "description": "User-provided structured data from log call extra args",
          "type": "object"
        },
        "diagnostics": {
          "additionalProperties": true,
          "description": "Runtime/operational context - identifies WHERE and system state",
          "properties": {
            "env": {
              "type": "string"
            },
            "exception": {
              "type": "object"
            },
            "host": {
              "type": "string"
            },
            "pid": {
              "type": "integer"
            },
            "python": {
              "type": "string"
            },
            "service": {
              "type": "string"
            }
          },
          "type": "object"
        },
        "level": {
          "description": "Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL",
          "type": "string"
        },
        "logger": {
          "description": "Logger name",
          "type": "string"
        },
        "message": {
          "description": "Human-readable log message",
          "type": "string"
        },
        "tags": {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        "timestamp": {
          "description": "RFC3339 UTC timestamp with Z suffix and millisecond precision",
          "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{3})?Z$",
          "type": "string"
        }
      },
      "required": [
        "timestamp",
        "level",
        "message",
        "context",
        "diagnostics",
        "data"
      ],
      "type": "object"
    },
    "schema_version": {
      "const": "1.1",
      "type": "string"
    }
  },
  "required": [
    "schema_version",
    "log"
  ],
  "title": "Fapilog Log Envelope v1.1",
  "type": "object"
}
```