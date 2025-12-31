"""
Tests for KeyProvider implementations and factory in fapilog-tamper.
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

# Add fapilog-tamper to path before importing
_tamper_src = (
    Path(__file__).resolve().parents[2] / "packages" / "fapilog-tamper" / "src"
)
if _tamper_src.exists():
    sys.path.insert(0, str(_tamper_src))

try:
    import fapilog_tamper  # noqa: F401
except ImportError:
    pytest.skip("fapilog-tamper not available", allow_module_level=True)


class _DummySink:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.entries: list[dict] = []

    async def write(self, entry: dict) -> None:
        self.entries.append(entry)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")


class _FakeProvider:
    def __init__(self) -> None:
        self.sign_calls = 0
        self.get_calls = 0

    async def get_key(self, key_id: str) -> bytes:
        self.get_calls += 1
        return b"K" * 32

    async def sign(self, key_id: str, data: bytes) -> bytes:
        self.sign_calls += 1
        return b"S" * 32

    async def verify(self, key_id: str, data: bytes, signature: bytes) -> bool:
        return signature == b"S" * 32

    async def rotate_check(self) -> bool:
        return False


@pytest.mark.asyncio
async def test_env_provider_cache_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    """EnvKeyProvider should cache keys until TTL expires."""
    from fapilog_tamper.config import TamperConfig

    monkeypatch.setenv("ENV_KMS_KEY", base64.urlsafe_b64encode(b"A" * 32).decode())
    # Fake time progression
    now = {"value": 1000.0}
    time_ns = SimpleNamespace(time=lambda: now["value"])
    monkeypatch.setattr("fapilog_tamper.providers.time", time_ns)

    from fapilog_tamper.providers import EnvKeyProvider

    provider = EnvKeyProvider(env_var="ENV_KMS_KEY", cache_ttl=5)
    first = await provider.get_key("ignored")
    assert first == b"A" * 32

    now["value"] += 3
    monkeypatch.setenv("ENV_KMS_KEY", base64.urlsafe_b64encode(b"B" * 32).decode())
    second = await provider.get_key("ignored")
    assert second == first  # cache hit

    now["value"] += 4  # expire cache
    third = await provider.get_key("ignored")
    assert third == b"B" * 32
    assert provider._cache_expires > now["value"] - 1  # type: ignore[attr-defined]

    # Ensure factory still allows env/file values in config enum
    TamperConfig(key_source="env")
    TamperConfig(key_source="file")


@pytest.mark.asyncio
async def test_env_provider_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Env provider should handle missing keys gracefully."""
    from fapilog_tamper.providers import EnvKeyProvider

    provider = EnvKeyProvider(env_var="MISSING_KEY", cache_ttl=1)
    assert await provider.rotate_check() is False
    assert await provider.get_key("unused") is None
    assert await provider.sign("unused", b"data") == b""
    assert await provider.verify("unused", b"data", b"sig") is False
    monkeypatch.setenv("MISSING_KEY", "short")
    assert await provider.get_key("unused") is None


@pytest.mark.asyncio
async def test_provider_factory_missing_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Factory should raise helpful errors when optional deps are missing."""
    import importlib

    from fapilog_tamper.config import TamperConfig

    real_import = importlib.import_module

    def _raise_on_boto3(name: str, *args, **kwargs):  # type: ignore[override]
        if name == "boto3":
            raise ImportError("boto3 missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", _raise_on_boto3)
    from fapilog_tamper.providers import create_key_provider

    cfg = TamperConfig(key_source="aws-kms", key_id="alias/test")
    with pytest.raises(ImportError, match="pip install fapilog-tamper\\[aws\\]"):
        create_key_provider(cfg)

    def _raise_on_cloud(name: str, *args, **kwargs):  # type: ignore[override]
        if name in {
            "google.cloud.kms_v1",
            "azure.identity",
            "azure.keyvault.keys.crypto",
            "hvac",
        }:
            raise ImportError(f"{name} missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", _raise_on_cloud)
    with pytest.raises(ImportError):
        create_key_provider(TamperConfig(key_source="gcp-kms", key_id="kid"))
    with pytest.raises(ImportError):
        create_key_provider(TamperConfig(key_source="azure-keyvault", key_id="kid"))
    with pytest.raises(ImportError):
        create_key_provider(TamperConfig(key_source="vault", key_id="kid"))


@pytest.mark.asyncio
async def test_aws_provider_signing_and_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """AWS provider should cache data keys and optionally sign via KMS."""
    from fapilog_tamper.config import TamperConfig

    class _FakeKmsClient:
        def __init__(self) -> None:
            self.generate_calls = 0
            self.sign_calls = 0
            self.verify_calls = 0

        def generate_data_key(self, KeyId: str, KeySpec: str) -> dict:
            self.generate_calls += 1
            return {"Plaintext": b"K" * 32}

        def sign(self, **kwargs) -> dict:
            self.sign_calls += 1
            return {"Signature": b"signed-" + kwargs["Message"]}

        def verify(self, **kwargs) -> dict:
            self.verify_calls += 1
            if kwargs["Signature"] == b"signed-" + kwargs["Message"]:
                return {"SignatureValid": True}
            raise Exception("invalid")

    fake_client = _FakeKmsClient()
    fake_boto = SimpleNamespace(
        client=lambda service_name, region_name=None: fake_client,
        exceptions=SimpleNamespace(KMSInvalidSignatureException=Exception),
    )
    monkeypatch.setitem(sys.modules, "boto3", fake_boto)

    # Fake time for cache expiry
    now = {"value": 10.0}
    monkeypatch.setattr(
        "fapilog_tamper.providers.time", SimpleNamespace(time=lambda: now["value"])
    )

    from fapilog_tamper.providers import create_key_provider

    cfg = TamperConfig(
        key_source="aws-kms",
        key_id="alias/test",
        key_cache_ttl_seconds=1,
        use_kms_signing=False,
    )
    provider = create_key_provider(cfg)
    assert await provider.get_key("alias/test") == b"K" * 32
    await provider.get_key("alias/test")
    assert fake_client.generate_calls == 1  # cached
    now["value"] += 2
    await provider.get_key("alias/test")
    assert fake_client.generate_calls == 2  # refreshed after TTL

    cfg_sign = TamperConfig(
        key_source="aws-kms",
        key_id="alias/sign",
        key_cache_ttl_seconds=1,
        use_kms_signing=True,
    )
    provider_sign = create_key_provider(cfg_sign)
    sig = await provider_sign.sign(cfg_sign.key_id, b"payload")
    assert sig == b"signed-payload"
    assert await provider_sign.verify(cfg_sign.key_id, b"payload", sig) is True
    assert await provider_sign.verify(cfg_sign.key_id, b"payload", b"bad") is False
    assert fake_client.sign_calls == 1
    assert fake_client.verify_calls == 2


@pytest.mark.asyncio
async def test_enricher_and_sink_use_kms_signing(tmp_path: Path) -> None:
    """IntegrityEnricher and SealedSink should defer signing to providers when configured."""
    from fapilog_tamper.canonical import b64url_decode
    from fapilog_tamper.config import TamperConfig
    from fapilog_tamper.enricher import IntegrityEnricher
    from fapilog_tamper.sealed_sink import SealedSink

    provider = _FakeProvider()
    cfg = TamperConfig(
        enabled=True,
        key_source="aws-kms",
        key_id="alias/test",
        use_kms_signing=True,
        state_dir=str(tmp_path),
    )
    enricher = IntegrityEnricher(cfg, provider=provider)
    await enricher.start()
    enriched = await enricher.enrich(
        {"event": "login", "timestamp": "2025-01-01T00:00:00Z"}
    )
    await enricher.stop()

    assert provider.sign_calls == 1
    mac = b64url_decode(enriched["integrity"]["mac"])
    assert mac == b"S" * 32

    sink = SealedSink(_DummySink(tmp_path / "events.jsonl"), cfg, provider=provider)
    await sink.start()
    await sink.write(enriched)
    await sink.stop()

    manifest = json.loads((tmp_path / "events.jsonl.manifest.json").read_text())
    sig_bytes = b64url_decode(manifest["signature"])
    assert sig_bytes == b"S" * 32
    assert provider.sign_calls >= 2  # enricher + manifest


@pytest.mark.asyncio
async def test_file_provider_and_cache_rotation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FileKeyProvider should read from files/directories and support cache rotation."""
    from fapilog_tamper.providers import FileKeyProvider

    key_dir = tmp_path / "keys"
    key_dir.mkdir()
    provider = FileKeyProvider(key_dir, cache_ttl=1)
    assert await provider.get_key("missing") is None

    # Write key and ensure it is loaded and cached
    (key_dir / "kid.key").write_bytes(b"A" * 32)
    first = await provider.get_key("kid")
    assert first == b"A" * 32

    now = {"value": 0.0}
    monkeypatch.setattr(
        "fapilog_tamper.providers.time", SimpleNamespace(time=lambda: now["value"])
    )
    provider._cache_set(b"A" * 32)  # type: ignore[attr-defined]
    now["value"] += 2
    assert await provider.rotate_check() is True
    sig = await provider.sign("kid", b"msg")
    assert await provider.verify("kid", b"msg", sig) is True


@pytest.mark.asyncio
async def test_gcp_and_azure_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    """GCP and Azure providers should call into SDK clients for signing."""
    from fapilog_tamper.config import TamperConfig

    class _FakeGcpClient:
        def mac_sign(self, request: dict) -> SimpleNamespace:
            return SimpleNamespace(mac=b"gcpsign-" + request["data"])

        def mac_verify(self, request: dict) -> SimpleNamespace:
            valid = request["mac"] == b"gcpsign-" + request["data"]
            return SimpleNamespace(success=valid)

    fake_gcp_mod = SimpleNamespace(KeyManagementServiceClient=lambda: _FakeGcpClient())
    monkeypatch.setitem(sys.modules, "google.cloud.kms_v1", fake_gcp_mod)

    from fapilog_tamper.providers import create_key_provider

    gcp_provider = create_key_provider(
        TamperConfig(
            key_source="gcp-kms",
            key_id="projects/x/locations/y/keyRings/z/cryptoKeys/k",
            use_kms_signing=True,
        )
    )
    sig = await gcp_provider.sign("id", b"data")
    assert await gcp_provider.verify("id", b"data", sig) is True
    assert await gcp_provider.get_key("id") is None

    # Azure crypto client stub
    class _FakeCryptoClient:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        def sign(self, algo: object, data: bytes) -> SimpleNamespace:
            return SimpleNamespace(signature=b"az-" + data)

        def verify(
            self, algo: object, data: bytes, signature: bytes
        ) -> SimpleNamespace:
            return SimpleNamespace(is_valid=signature == b"az-" + data)

    class _FakeIdentity:
        def __init__(self, *args, **kwargs) -> None:
            pass

    fake_crypto_mod = SimpleNamespace(
        CryptographyClient=lambda key_id, credential: _FakeCryptoClient(),
        SignatureAlgorithm=SimpleNamespace(hs256="HS256"),
    )
    monkeypatch.setitem(
        sys.modules,
        "azure.identity",
        SimpleNamespace(
            DefaultAzureCredential=_FakeIdentity, ClientSecretCredential=_FakeIdentity
        ),
    )
    monkeypatch.setitem(sys.modules, "azure.keyvault.keys.crypto", fake_crypto_mod)

    azure_provider = create_key_provider(
        TamperConfig(
            key_source="azure-keyvault",
            key_id="https://vault.vault.azure.net/keys/k",
            use_kms_signing=True,
            azure_tenant_id="tenant",
            azure_client_id="client",
        )
    )
    az_sig = await azure_provider.sign("id", b"payload")
    assert await azure_provider.verify("id", b"payload", az_sig)
    assert await azure_provider.get_key("id") is None


@pytest.mark.asyncio
async def test_vault_provider_auth_and_sign(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Vault provider should handle auth methods and sign/verify via transit."""
    from fapilog_tamper.config import TamperConfig
    from fapilog_tamper.providers import create_key_provider

    class _FakeTransit:
        def __init__(self) -> None:
            self.sign_data_calls = 0
            self.verify_calls = 0

        def sign_data(
            self,
            name: str,
            hash_input: str,
            hash_algorithm: str,
            signature_algorithm: str,
        ) -> dict:
            self.sign_data_calls += 1
            return {"data": {"signature": f"vault:v1:{hash_input}"}}

        def verify_signed_data(
            self, name: str, hash_input: str, signature: str, hash_algorithm: str
        ) -> dict:
            self.verify_calls += 1
            valid = signature.endswith(hash_input)
            return {"data": {"valid": valid}}

    class _FakeAuth:
        def __init__(self) -> None:
            self.approle = SimpleNamespace(
                login=lambda role_id=None, secret_id=None: None
            )
            self.kubernetes = SimpleNamespace(login=lambda role=None, jwt=None: None)

    class _FakeClient:
        def __init__(self, url: str) -> None:
            self.url = url
            self.auth = _FakeAuth()
            self.secrets = SimpleNamespace(transit=_FakeTransit())
            self.token = None

    monkeypatch.setitem(sys.modules, "hvac", SimpleNamespace(Client=_FakeClient))

    # Ensure kubernetes path returns a token
    class _FakePath:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def read_text(self) -> str:
            return "jwt-token"

        def exists(self) -> bool:
            return True

    monkeypatch.setattr("fapilog_tamper.providers.Path", _FakePath)

    monkeypatch.setenv("VAULT_TOKEN", "token")
    cfg_token = TamperConfig(
        key_source="vault", key_id="transit/keys/audit", vault_addr="http://vault"
    )
    provider_token = create_key_provider(cfg_token)
    assert await provider_token.sign("id", b"vaultdata-token")

    cfg = TamperConfig(
        key_source="vault",
        key_id="transit/keys/audit",
        vault_addr="http://vault",
        vault_auth_method="approle",
    )
    provider = create_key_provider(cfg)
    sig = await provider.sign("id", b"vaultdata")
    assert await provider.verify("id", b"vaultdata", sig) is True

    cfg_k8s = TamperConfig(
        key_source="vault",
        key_id="transit/keys/audit",
        vault_addr="http://vault",
        vault_auth_method="kubernetes",
        vault_role="role",
    )
    provider_k8s = create_key_provider(cfg_k8s)
    sig2 = await provider_k8s.sign("id", b"vaultdata2")
    assert await provider_k8s.verify("id", b"vaultdata2", sig2)
