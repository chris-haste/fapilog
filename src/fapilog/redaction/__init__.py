"""Redaction presets for common compliance regulations.

This module provides named collections of field patterns for redacting
sensitive data. Presets are composable via inheritance and can be
combined at runtime.

Example:
    >>> from fapilog.redaction import list_redaction_presets, get_redaction_preset
    >>> presets = list_redaction_presets()
    >>> gdpr = get_redaction_preset("GDPR_PII")
    >>> print(gdpr.description)
    GDPR Article 4 personal data identifiers
"""

from __future__ import annotations

from .presets import (
    BUILTIN_PRESETS,
    CCPA_PII,
    CONTACT_INFO,
    CREDENTIALS,
    EU_GOVERNMENT_IDS,
    FINANCIAL_IDENTIFIERS,
    GDPR_PII,
    GDPR_PII_UK,
    HIPAA_PHI,
    ONLINE_IDENTIFIERS,
    PCI_DSS,
    PERSONAL_IDENTIFIERS,
    UK_GOVERNMENT_IDS,
    US_GOVERNMENT_IDS,
    RedactionPreset,
)
from .registry import (
    get_presets_by_region,
    get_presets_by_regulation,
    get_presets_by_tag,
    get_redaction_preset,
    list_redaction_presets,
    resolve_preset_fields,
)

__all__ = [
    # Dataclass
    "RedactionPreset",
    # Registry functions
    "get_redaction_preset",
    "list_redaction_presets",
    "resolve_preset_fields",
    "get_presets_by_regulation",
    "get_presets_by_region",
    "get_presets_by_tag",
    # Built-in presets (for direct access)
    "BUILTIN_PRESETS",
    "CONTACT_INFO",
    "PERSONAL_IDENTIFIERS",
    "ONLINE_IDENTIFIERS",
    "FINANCIAL_IDENTIFIERS",
    "US_GOVERNMENT_IDS",
    "UK_GOVERNMENT_IDS",
    "EU_GOVERNMENT_IDS",
    "GDPR_PII",
    "GDPR_PII_UK",
    "CCPA_PII",
    "HIPAA_PHI",
    "PCI_DSS",
    "CREDENTIALS",
]
