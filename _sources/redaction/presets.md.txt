# Redaction Presets

One-liner compliance protection for GDPR, CCPA, HIPAA, PCI-DSS, and more.

> **Disclaimer:** Redaction presets are provided as a convenience to help protect sensitive data in logs. They represent a best-effort approach based on common field naming conventions and cannot guarantee complete coverage of all sensitive data in your application. Field-name matching does not detect sensitive content within arbitrarily-named fields. You are responsible for verifying that redaction meets your compliance requirements through thorough testing before deploying to production. Fapilog and its maintainers accept no liability for data exposure resulting from misconfiguration, incomplete coverage, or reliance on these presets without adequate verification.

## Quick Start

```python
from fapilog import LoggerBuilder

# GDPR compliance in one line
logger = LoggerBuilder().with_redaction(preset="GDPR_PII").build()

logger.info("signup", email="john@example.com", phone="+1-555-1234")
# Output: {"data": {"email": "***", "phone": "***"}}
```

## Available Presets

### Regulation Presets

| Preset | Regulation | Region | Description |
|--------|------------|--------|-------------|
| `GDPR_PII` | GDPR | EU | EU General Data Protection Regulation |
| `GDPR_PII_UK` | UK-GDPR | UK | UK GDPR (includes NHS, NI numbers) |
| `CCPA_PII` | CCPA | US-CA | California Consumer Privacy Act |
| `HIPAA_PHI` | HIPAA | US | Protected Health Information |
| `PCI_DSS` | PCI-DSS | Global | Payment card data |
| `CREDENTIALS` | N/A | Global | Authentication secrets |

### Building Block Presets

| Preset | Description | Example Fields |
|--------|-------------|----------------|
| `CONTACT_INFO` | Contact information | email, phone, address |
| `PERSONAL_IDENTIFIERS` | Personal identity | name, dob, gender |
| `ONLINE_IDENTIFIERS` | Digital identifiers | ip_address, device_id, cookie_id |
| `FINANCIAL_IDENTIFIERS` | Financial accounts | iban, account_number |
| `US_GOVERNMENT_IDS` | US government IDs | ssn, passport, drivers_license |
| `UK_GOVERNMENT_IDS` | UK government IDs | ni_number, nhs_number |
| `EU_GOVERNMENT_IDS` | EU government IDs | national_id, passport |

## Using Presets

### Single Preset

```python
from fapilog import LoggerBuilder

logger = LoggerBuilder().with_redaction(preset="GDPR_PII").build()
```

### Multiple Presets

Combine presets for multi-regulation compliance:

```python
# Healthcare + payment data
logger = (
    LoggerBuilder()
    .with_redaction(preset=["HIPAA_PHI", "PCI_DSS"])
    .build()
)
```

### Preset with Custom Fields

Presets and custom fields are additive:

```python
logger = (
    LoggerBuilder()
    .with_redaction(preset="GDPR_PII")
    .with_redaction(fields=["internal_user_id", "employee_badge"])
    .build()
)
```

### Environment Presets with Redaction

The `production`, `production-latency`, `fastapi`, and `serverless` environment presets automatically apply the `CREDENTIALS` preset:

```python
from fapilog import get_logger

# Automatically redacts passwords, API keys, tokens
logger = get_logger(preset="production")
logger = get_logger(preset="production-latency")  # Same redaction, optimized for latency
```

The `hardened` preset applies comprehensive redaction from HIPAA_PHI, PCI_DSS, and CREDENTIALS presets:

```python
# Maximum security for regulated environments
logger = get_logger(preset="hardened")
```

To add compliance presets to other environment presets:

```python
logger = (
    LoggerBuilder()
    .with_preset("production")  # Includes CREDENTIALS
    .with_redaction(preset="HIPAA_PHI")  # Add HIPAA protection
    .build()
)
```

See [Presets Guide](../user-guide/presets.md) for complete environment preset documentation.

## Preset Inheritance

Presets can extend other presets. Inheritance is resolved at configuration time for performance.

```
GDPR_PII
├── CONTACT_INFO
├── PERSONAL_IDENTIFIERS
├── ONLINE_IDENTIFIERS
├── FINANCIAL_IDENTIFIERS
└── EU_GOVERNMENT_IDS

GDPR_PII_UK
├── GDPR_PII (all fields above)
└── UK_GOVERNMENT_IDS (nhs_number, ni_number)
```

### Example: GDPR_PII_UK

```python
from fapilog.redaction import resolve_preset_fields

fields, patterns = resolve_preset_fields("GDPR_PII_UK")

# Includes all GDPR_PII fields plus UK-specific:
assert "email" in fields      # From CONTACT_INFO via GDPR_PII
assert "nhs_number" in fields  # From UK_GOVERNMENT_IDS
assert "ni_number" in fields   # From UK_GOVERNMENT_IDS
```

## Discovering Presets

### List All Presets

```python
from fapilog import LoggerBuilder

presets = LoggerBuilder.list_redaction_presets()
print(presets)
# ['CCPA_PII', 'CONTACT_INFO', 'CREDENTIALS', 'EU_GOVERNMENT_IDS',
#  'FINANCIAL_IDENTIFIERS', 'GDPR_PII', 'GDPR_PII_UK', 'HIPAA_PHI',
#  'ONLINE_IDENTIFIERS', 'PCI_DSS', 'PERSONAL_IDENTIFIERS',
#  'UK_GOVERNMENT_IDS', 'US_GOVERNMENT_IDS']
```

### Get Preset Details

```python
info = LoggerBuilder.get_redaction_preset_info("GDPR_PII")

print(info["name"])        # "GDPR_PII"
print(info["description"]) # "GDPR Article 4 personal data identifiers"
print(info["regulation"])  # "GDPR"
print(info["region"])      # "EU"
print(info["tags"])        # ["gdpr", "pii", "eu"]
print(info["extends"])     # ["CONTACT_INFO", "PERSONAL_IDENTIFIERS", ...]
print(info["fields"][:5])  # ["email", "phone", "name", "address", ...]
print(info["patterns"][:3]) # ["(?i).*email.*", "(?i).*phone.*", ...]
```

### Filter Presets by Metadata

```python
from fapilog.redaction import (
    get_presets_by_regulation,
    get_presets_by_region,
    get_presets_by_tag,
)

# By regulation
gdpr_presets = get_presets_by_regulation("GDPR")
# ["GDPR_PII"]

# By region
us_presets = get_presets_by_region("US")
# ["CCPA_PII", "HIPAA_PHI", "US_GOVERNMENT_IDS"]

# By tag
healthcare = get_presets_by_tag("healthcare")
# ["HIPAA_PHI"]
```

## Complete Field Reference

This section lists every field covered by each preset. Use Ctrl+F to search for specific field names.

---

### Building Block Presets

#### CONTACT_INFO

Contact information fields:

```
email, e_mail, email_address
phone, phone_number, telephone, mobile, cell, fax
address, street, street_address, postal_address
postcode, postal_code, zipcode, zip_code, zip
city, town, state, province, country
```

**Patterns:** `.*email.*`, `.*phone.*`, `.*mobile.*`, `.*address.*`, `.*postcode.*`, `.*zipcode.*`

#### PERSONAL_IDENTIFIERS

Personal identity fields:

```
name, first_name, last_name, full_name, surname
given_name, middle_name, maiden_name, nickname
dob, date_of_birth, birth_date, birthday, age
gender, sex
```

**Patterns:** `.*\bname\b.*`, `.*\bdob\b.*`, `.*birth.*`

#### ONLINE_IDENTIFIERS

Digital/online identifiers:

```
ip, ip_address, ipv4, ipv6, client_ip, remote_ip
device_id, device_identifier, udid, idfa, gaid
mac_address, hardware_id
user_agent, browser_fingerprint
cookie_id, tracking_id, visitor_id
```

**Patterns:** `.*\bip\b.*`, `.*device.?id.*`, `.*mac.?addr.*`

#### FINANCIAL_IDENTIFIERS

Financial account identifiers:

```
iban, bic, swift
bank_account, account_number, account_no
sort_code, routing_number, bsb
```

**Patterns:** `.*\biban\b.*`, `.*account.?(num|no).*`, `.*routing.*`

#### US_GOVERNMENT_IDS

US government-issued identifiers:

```
ssn, social_security, social_security_number
itin, ein
passport, passport_number
drivers_license, driver_license, dl_number
```

**Patterns:** `.*\bssn\b.*`, `.*social.?security.*`

#### UK_GOVERNMENT_IDS

UK government-issued identifiers:

```
national_insurance, ni_number, nino
nhs_number
passport, passport_number
driving_licence, licence_number
```

**Patterns:** `.*national.?insurance.*`, `.*\bni.?(num|no)\b.*`, `.*\bnino\b.*`, `.*\bnhs\b.*`

#### EU_GOVERNMENT_IDS

EU government-issued identifiers:

```
national_id, id_number, identity_number, id_card
passport, passport_number
tax_id, tin, vat_number
drivers_license, licence_number
```

**Patterns:** `.*national.?id.*`, `.*passport.*`, `.*\btin\b.*`, `.*tax.?id.*`, `.*licen[cs]e.*`

---

### Regulation Presets

#### CREDENTIALS

Authentication and authorization secrets:

```
password, passwd, pwd, pass
secret, api_secret, client_secret, shared_secret
token, access_token, refresh_token, auth_token, bearer_token, jwt
api_key, apikey, api_token
private_key, secret_key, signing_key, encryption_key
authorization, auth_header
session_id, session_token, session_key
cookie, session_cookie, auth_cookie
otp, totp, mfa_code, verification_code
```

**Patterns:** `.*password.*`, `.*passwd.*`, `.*\bsecret\b.*`, `.*\btoken\b.*`, `.*api.?key.*`, `.*private.?key.*`, `.*auth.*`, `.*\botp\b.*`

#### GDPR_PII

EU GDPR Article 4 personal data.

**Inherits all fields from:** CONTACT_INFO, PERSONAL_IDENTIFIERS, ONLINE_IDENTIFIERS, FINANCIAL_IDENTIFIERS, EU_GOVERNMENT_IDS

**Additional fields:**
```
biometric_data, genetic_data, health_data
```

**Total coverage:** 70+ fields including all inherited fields listed above.

#### GDPR_PII_UK

UK GDPR personal data (post-Brexit variant).

**Inherits all fields from:** GDPR_PII, UK_GOVERNMENT_IDS

**Total coverage:** All GDPR_PII fields plus UK-specific:
```
national_insurance, ni_number, nino, nhs_number
driving_licence, licence_number
```

#### CCPA_PII

California Consumer Privacy Act personal information.

**Inherits all fields from:** CONTACT_INFO, PERSONAL_IDENTIFIERS, ONLINE_IDENTIFIERS, FINANCIAL_IDENTIFIERS, US_GOVERNMENT_IDS

**Additional fields:**
```
household_id, inferred_preferences, purchase_history
```

#### HIPAA_PHI

HIPAA Protected Health Information (18 identifier categories).

**Inherits all fields from:** CONTACT_INFO, PERSONAL_IDENTIFIERS, US_GOVERNMENT_IDS

**Additional fields:**
```
mrn, medical_record_number, patient_id
health_plan_id, beneficiary_id
account_number, certificate_number, license_number
vehicle_id, vin
device_serial, device_identifier
url, web_url
biometric_id, fingerprint, voiceprint
photo, image
```

**Patterns:** `.*\bmrn\b.*`, `.*medical.?record.*`, `.*patient.?id.*`, `.*health.?plan.*`

#### PCI_DSS

PCI-DSS cardholder data elements:

```
card_number, credit_card, cc_number, pan
cvv, cvc, cvv2, cid, security_code, card_security
expiry, expiry_date, expiration, exp_date, exp_month, exp_year
cardholder, cardholder_name, card_holder
card_pin, pin
track_data, track1, track2
```

**Patterns:** `.*card.?(num|no).*`, `.*credit.?card.*`, `.*\bcvv\b.*`, `.*\bcvc\b.*`, `.*expir.*`, `.*cardholder.*`, `.*\bpan\b.*`

## Best Practices

### 1. Use Presets Over Manual Configuration

```python
# Good: preset handles field list maintenance
logger = LoggerBuilder().with_redaction(preset="GDPR_PII").build()

# Avoid: manual list is hard to maintain
logger = LoggerBuilder().with_redaction(
    fields=["email", "phone", "name", ...]  # 30+ fields
).build()
```

### 2. Combine Presets for Multi-Regulation

```python
# Healthcare company processing payments
logger = (
    LoggerBuilder()
    .with_redaction(preset=["HIPAA_PHI", "PCI_DSS", "CREDENTIALS"])
    .build()
)
```

### 3. Extend Presets with Domain-Specific Fields

```python
logger = (
    LoggerBuilder()
    .with_redaction(preset="GDPR_PII")
    .with_redaction(fields=["internal_customer_id", "crm_reference"])
    .build()
)
```

### 4. Audit What's Covered

```python
# For compliance documentation
info = LoggerBuilder.get_redaction_preset_info("HIPAA_PHI")
print("HIPAA PHI fields covered:")
for field in sorted(info["fields"]):
    print(f"  - {field}")
```

### 5. Test Redaction in CI

See [Testing Redaction](testing.md) for comprehensive examples.

## Limitations

1. **Field-name matching only** - Presets match field names, not field content. A field named `description` containing an email address won't be caught.

2. **No runtime registration** - Custom presets cannot be added at runtime (future feature).

3. **Best-effort coverage** - Presets cover common field names but cannot anticipate all variations. Extend with custom fields for your domain.

## Related

- [Compliance Redaction Cookbook](../cookbook/compliance-redaction.md) - What works and what doesn't
- [Configuration](configuration.md) - Builder API, Settings, environment variables
- [Behavior](behavior.md) - What gets redacted and when
- [Testing](testing.md) - Verify redaction in CI
