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
    "drop_on_full": {
      "default": true,
      "description": "If True, drop events after backpressure_wait_ms elapses when queue is full",
      "title": "Drop On Full",
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
      "default": 50,
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
    "strict_envelope_mode": {
      "default": false,
      "description": "If True, drop emission when envelope cannot be produced; otherwise fallback to best-effort serialization with diagnostics",
      "title": "Strict Envelope Mode",
      "type": "boolean"
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
          "description": "Log sampling probability in range 0.0\u20131.0",
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
  "description": "Settings controlling plugin discovery and load behavior.",
  "properties": {
    "allowlist": {
      "description": "If non-empty, only plugin names in this list are considered during load",
      "items": {
        "type": "string"
      },
      "title": "Allowlist",
      "type": "array"
    },
    "denylist": {
      "description": "Plugin names to skip during discovery/load",
      "items": {
        "type": "string"
      },
      "title": "Denylist",
      "type": "array"
    },
    "discovery_paths": {
      "description": "Additional filesystem paths to scan for local plugins",
      "items": {
        "type": "string"
      },
      "title": "Discovery Paths",
      "type": "array"
    },
    "enabled": {
      "default": true,
      "description": "Enable plugin discovery and loading",
      "title": "Enabled",
      "type": "boolean"
    },
    "load_on_startup": {
      "description": "Plugins to eagerly load during registry.initialize() if discovered",
      "items": {
        "type": "string"
      },
      "title": "Load On Startup",
      "type": "array"
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
  "properties": {
    "log": {
      "additionalProperties": true,
      "properties": {
        "context": {
          "type": "object"
        },
        "diagnostics": {
          "type": "object"
        },
        "level": {
          "type": "string"
        },
        "logger": {
          "type": "string"
        },
        "message": {
          "type": "string"
        },
        "span_id": {
          "type": "string"
        },
        "tags": {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        "timestamp": {
          "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d{3})?Z$",
          "type": "string"
        },
        "trace_id": {
          "type": "string"
        }
      },
      "required": [
        "timestamp",
        "level",
        "message",
        "context",
        "diagnostics"
      ],
      "type": "object"
    },
    "schema_version": {
      "const": "1.0",
      "type": "string"
    }
  },
  "required": [
    "schema_version",
    "log"
  ],
  "title": "Fapilog Log Envelope v1.0",
  "type": "object"
}
```