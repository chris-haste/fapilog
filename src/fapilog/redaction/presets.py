"""Redaction preset definitions for common compliance regulations.

This module provides named collections of field patterns for redacting
sensitive data. Presets are composable via inheritance and can be
combined at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RedactionPreset:
    """A named collection of field patterns for redaction.

    Presets can extend other presets via the `extends` field,
    allowing hierarchical composition (e.g., GDPR_PII_UK extends GDPR_PII).

    Attributes:
        name: Unique identifier for the preset.
        description: Human-readable description of what the preset covers.
        fields: Exact field names to redact (e.g., "email", "phone").
        patterns: Regex patterns to match against field paths.
        extends: Parent preset names to inherit fields/patterns from.
        regulation: Compliance regulation this preset addresses (e.g., "GDPR").
        region: Geographic region this preset applies to (e.g., "EU", "UK").
        tags: Arbitrary tags for filtering and discovery.
    """

    name: str
    description: str
    fields: tuple[str, ...] = field(default_factory=tuple)
    patterns: tuple[str, ...] = field(default_factory=tuple)
    extends: tuple[str, ...] = field(default_factory=tuple)
    regulation: str | None = None
    region: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)

    def resolve(
        self,
        registry: dict[str, RedactionPreset],
        *,
        _visited: frozenset[str] | None = None,
    ) -> tuple[set[str], set[str]]:
        """Resolve all fields and patterns including inherited ones.

        Args:
            registry: Dictionary mapping preset names to preset objects.
            _visited: Internal set to detect circular inheritance.

        Returns:
            Tuple of (fields_set, patterns_set) including all inherited values.

        Raises:
            ValueError: If circular inheritance is detected.
        """
        visited = _visited or frozenset()

        if self.name in visited:
            cycle = " -> ".join([*visited, self.name])
            raise ValueError(f"Circular inheritance detected: {cycle}")

        visited = visited | {self.name}

        all_fields: set[str] = set(self.fields)
        all_patterns: set[str] = set(self.patterns)

        for parent_name in self.extends:
            parent = registry.get(parent_name)
            if parent:
                parent_fields, parent_patterns = parent.resolve(
                    registry, _visited=visited
                )
                all_fields.update(parent_fields)
                all_patterns.update(parent_patterns)

        return all_fields, all_patterns


# =============================================================================
# Base Presets (building blocks)
# =============================================================================

CONTACT_INFO = RedactionPreset(
    name="CONTACT_INFO",
    description="Contact information fields (email, phone, address)",
    tags=("pii", "contact"),
    fields=(
        "email",
        "e_mail",
        "email_address",
        "phone",
        "phone_number",
        "telephone",
        "mobile",
        "cell",
        "fax",
        "address",
        "street",
        "street_address",
        "postal_address",
        "postcode",
        "postal_code",
        "zipcode",
        "zip_code",
        "zip",
        "city",
        "town",
        "state",
        "province",
        "country",
    ),
    patterns=(
        r"(?i).*email.*",
        r"(?i).*phone.*",
        r"(?i).*mobile.*",
        r"(?i).*address.*",
        r"(?i).*postcode.*",
        r"(?i).*zipcode.*",
    ),
)

PERSONAL_IDENTIFIERS = RedactionPreset(
    name="PERSONAL_IDENTIFIERS",
    description="Personal identity fields (name, DOB)",
    tags=("pii", "identity"),
    fields=(
        "name",
        "first_name",
        "last_name",
        "full_name",
        "surname",
        "given_name",
        "middle_name",
        "maiden_name",
        "nickname",
        "dob",
        "date_of_birth",
        "birth_date",
        "birthday",
        "age",
        "gender",
        "sex",
    ),
    patterns=(
        r"(?i).*\bname\b.*",
        r"(?i).*\bdob\b.*",
        r"(?i).*birth.*",
    ),
)

ONLINE_IDENTIFIERS = RedactionPreset(
    name="ONLINE_IDENTIFIERS",
    description="Online/digital identifiers (IP, device ID, cookies)",
    tags=("pii", "digital"),
    fields=(
        "ip",
        "ip_address",
        "ipv4",
        "ipv6",
        "client_ip",
        "remote_ip",
        "device_id",
        "device_identifier",
        "udid",
        "idfa",
        "gaid",
        "mac_address",
        "hardware_id",
        "user_agent",
        "browser_fingerprint",
        "cookie_id",
        "tracking_id",
        "visitor_id",
    ),
    patterns=(
        r"(?i).*\bip\b.*",
        r"(?i).*device.?id.*",
        r"(?i).*mac.?addr.*",
    ),
)

FINANCIAL_IDENTIFIERS = RedactionPreset(
    name="FINANCIAL_IDENTIFIERS",
    description="Financial account identifiers (IBAN, account numbers)",
    tags=("pii", "financial"),
    fields=(
        "iban",
        "bic",
        "swift",
        "bank_account",
        "account_number",
        "account_no",
        "sort_code",
        "routing_number",
        "bsb",
    ),
    patterns=(
        r"(?i).*\biban\b.*",
        r"(?i).*account.?(num|no).*",
        r"(?i).*routing.*",
    ),
)

# =============================================================================
# Government ID Presets (regional)
# =============================================================================

US_GOVERNMENT_IDS = RedactionPreset(
    name="US_GOVERNMENT_IDS",
    description="US government-issued identifiers",
    regulation="US",
    region="US",
    tags=("government-id", "us"),
    fields=(
        "ssn",
        "social_security",
        "social_security_number",
        "itin",
        "ein",
        "passport",
        "passport_number",
        "drivers_license",
        "driver_license",
        "dl_number",
    ),
    patterns=(
        r"(?i).*\bssn\b.*",
        r"(?i).*social.?security.*",
    ),
)

UK_GOVERNMENT_IDS = RedactionPreset(
    name="UK_GOVERNMENT_IDS",
    description="UK government-issued identifiers",
    region="UK",
    tags=("government-id", "uk"),
    fields=(
        "national_insurance",
        "ni_number",
        "nino",
        "nhs_number",
        "passport",
        "passport_number",
        "driving_licence",
        "licence_number",
    ),
    patterns=(
        r"(?i).*national.?insurance.*",
        r"(?i).*\bni.?(num|no)\b.*",
        r"(?i).*\bnino\b.*",
        r"(?i).*\bnhs\b.*",
    ),
)

EU_GOVERNMENT_IDS = RedactionPreset(
    name="EU_GOVERNMENT_IDS",
    description="EU government-issued identifiers (generic)",
    region="EU",
    tags=("government-id", "eu"),
    fields=(
        "national_id",
        "id_number",
        "identity_number",
        "id_card",
        "passport",
        "passport_number",
        "tax_id",
        "tin",
        "vat_number",
        "drivers_license",
        "licence_number",
    ),
    patterns=(
        r"(?i).*national.?id.*",
        r"(?i).*passport.*",
        r"(?i).*\btin\b.*",
        r"(?i).*tax.?id.*",
        r"(?i).*licen[cs]e.*",
    ),
)

# =============================================================================
# Regulation Presets (compose from building blocks)
# =============================================================================

GDPR_PII = RedactionPreset(
    name="GDPR_PII",
    description="GDPR Article 4 personal data identifiers",
    regulation="GDPR",
    region="EU",
    tags=("gdpr", "pii", "eu"),
    extends=(
        "CONTACT_INFO",
        "PERSONAL_IDENTIFIERS",
        "ONLINE_IDENTIFIERS",
        "FINANCIAL_IDENTIFIERS",
        "EU_GOVERNMENT_IDS",
    ),
    fields=("biometric_data", "genetic_data", "health_data"),
)

GDPR_PII_UK = RedactionPreset(
    name="GDPR_PII_UK",
    description="UK GDPR personal data identifiers (post-Brexit UK variant)",
    regulation="UK-GDPR",
    region="UK",
    tags=("gdpr", "pii", "uk"),
    extends=("GDPR_PII", "UK_GOVERNMENT_IDS"),
)

CCPA_PII = RedactionPreset(
    name="CCPA_PII",
    description="California Consumer Privacy Act personal information",
    regulation="CCPA",
    region="US-CA",
    tags=("ccpa", "pii", "us"),
    extends=(
        "CONTACT_INFO",
        "PERSONAL_IDENTIFIERS",
        "ONLINE_IDENTIFIERS",
        "FINANCIAL_IDENTIFIERS",
        "US_GOVERNMENT_IDS",
    ),
    fields=("household_id", "inferred_preferences", "purchase_history"),
)

HIPAA_PHI = RedactionPreset(
    name="HIPAA_PHI",
    description="HIPAA Protected Health Information identifiers",
    regulation="HIPAA",
    region="US",
    tags=("hipaa", "phi", "healthcare", "us"),
    extends=("CONTACT_INFO", "PERSONAL_IDENTIFIERS", "US_GOVERNMENT_IDS"),
    fields=(
        "mrn",
        "medical_record_number",
        "patient_id",
        "health_plan_id",
        "beneficiary_id",
        "account_number",
        "certificate_number",
        "license_number",
        "vehicle_id",
        "vin",
        "device_serial",
        "device_identifier",
        "url",
        "web_url",
        "biometric_id",
        "fingerprint",
        "voiceprint",
        "photo",
        "image",
    ),
    patterns=(
        r"(?i).*\bmrn\b.*",
        r"(?i).*medical.?record.*",
        r"(?i).*patient.?id.*",
        r"(?i).*health.?plan.*",
    ),
)

PCI_DSS = RedactionPreset(
    name="PCI_DSS",
    description="PCI-DSS cardholder data elements",
    regulation="PCI-DSS",
    tags=("pci", "payment", "financial"),
    fields=(
        "card_number",
        "credit_card",
        "cc_number",
        "pan",
        "cvv",
        "cvc",
        "cvv2",
        "cid",
        "security_code",
        "card_security",
        "expiry",
        "expiry_date",
        "expiration",
        "exp_date",
        "exp_month",
        "exp_year",
        "cardholder",
        "cardholder_name",
        "card_holder",
        "card_pin",
        "pin",
        "track_data",
        "track1",
        "track2",
    ),
    patterns=(
        r"(?i).*card.?(num|no).*",
        r"(?i).*credit.?card.*",
        r"(?i).*\bcvv\b.*",
        r"(?i).*\bcvc\b.*",
        r"(?i).*expir.*",
        r"(?i).*cardholder.*",
        r"(?i).*\bpan\b.*",
    ),
)

CREDENTIALS = RedactionPreset(
    name="CREDENTIALS",
    description="Authentication and authorization secrets",
    tags=("security", "auth", "secrets"),
    fields=(
        "password",
        "passwd",
        "pwd",
        "pass",
        "secret",
        "api_secret",
        "client_secret",
        "shared_secret",
        "token",
        "access_token",
        "refresh_token",
        "auth_token",
        "bearer_token",
        "jwt",
        "api_key",
        "apikey",
        "api_token",
        "private_key",
        "secret_key",
        "signing_key",
        "encryption_key",
        "authorization",
        "auth_header",
        "session_id",
        "session_token",
        "session_key",
        "cookie",
        "session_cookie",
        "auth_cookie",
        "otp",
        "totp",
        "mfa_code",
        "verification_code",
    ),
    patterns=(
        r"(?i).*password.*",
        r"(?i).*passwd.*",
        r"(?i).*\bsecret\b.*",
        r"(?i).*\btoken\b.*",
        r"(?i).*api.?key.*",
        r"(?i).*private.?key.*",
        r"(?i).*auth.*",
        r"(?i).*\botp\b.*",
    ),
)

# =============================================================================
# Registry
# =============================================================================

BUILTIN_PRESETS: dict[str, RedactionPreset] = {
    # Base building blocks
    "CONTACT_INFO": CONTACT_INFO,
    "PERSONAL_IDENTIFIERS": PERSONAL_IDENTIFIERS,
    "ONLINE_IDENTIFIERS": ONLINE_IDENTIFIERS,
    "FINANCIAL_IDENTIFIERS": FINANCIAL_IDENTIFIERS,
    # Regional government IDs
    "US_GOVERNMENT_IDS": US_GOVERNMENT_IDS,
    "UK_GOVERNMENT_IDS": UK_GOVERNMENT_IDS,
    "EU_GOVERNMENT_IDS": EU_GOVERNMENT_IDS,
    # Regulation presets
    "GDPR_PII": GDPR_PII,
    "GDPR_PII_UK": GDPR_PII_UK,
    "CCPA_PII": CCPA_PII,
    "HIPAA_PHI": HIPAA_PHI,
    "PCI_DSS": PCI_DSS,
    "CREDENTIALS": CREDENTIALS,
}
