"""
Key provider implementations for enterprise key management backends.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import importlib
import os
import time
from pathlib import Path
from typing import Protocol

from .config import TamperConfig


class KeyProvider(Protocol):
    """Protocol for retrieving and using signing keys."""

    async def get_key(self, key_id: str) -> bytes | None:
        """Retrieve key material by ID."""

    async def sign(self, key_id: str, data: bytes) -> bytes:
        """Sign data using key (remote or local)."""

    async def verify(self, key_id: str, data: bytes, signature: bytes) -> bool:
        """Verify signature using key."""

    async def rotate_check(self) -> bool:
        """Check for rotation and refresh cache."""


def _decode_key(raw: bytes | None) -> bytes | None:
    """Decode base64url or raw key material to 32 bytes."""
    if raw is None:
        return None
    padding = b"=" * (-len(raw) % 4)
    candidates = []
    try:
        candidates.append(base64.urlsafe_b64decode(raw + padding))
    except Exception:
        pass
    candidates.append(raw)
    for c in candidates:
        if len(c) == 32:
            return c
    return None


class _CachedProvider:
    def __init__(self, cache_ttl: int) -> None:
        self._cache_ttl = cache_ttl
        self._cached_key: bytes | None = None
        self._cache_expires: float = 0.0

    def _cache_get(self) -> bytes | None:
        if self._cached_key and time.time() < self._cache_expires:
            return self._cached_key
        return None

    def _cache_set(self, key: bytes | None) -> None:
        if key:
            self._cached_key = key
            self._cache_expires = time.time() + self._cache_ttl
        else:
            self._cached_key = None
            self._cache_expires = 0.0

    async def rotate_check(self) -> bool:
        if self._cached_key and time.time() >= self._cache_expires:
            self._cached_key = None
            return True
        return False


class EnvKeyProvider(_CachedProvider):
    """Key provider backed by environment variables."""

    def __init__(self, env_var: str, cache_ttl: int = 300) -> None:
        super().__init__(cache_ttl)
        self._env_var = env_var

    async def get_key(self, key_id: str) -> bytes | None:  # noqa: ARG002
        cached = self._cache_get()
        if cached:
            return cached
        val = os.getenv(self._env_var)
        key = _decode_key(val.encode("utf-8")) if val else None
        self._cache_set(key)
        return key

    async def sign(self, key_id: str, data: bytes) -> bytes:  # noqa: ARG002
        key = await self.get_key(self._env_var)
        if not key:
            return b""
        return hmac.new(key, data, hashlib.sha256).digest()

    async def verify(self, key_id: str, data: bytes, signature: bytes) -> bool:  # noqa: ARG002
        key = await self.get_key(self._env_var)
        if not key:
            return False
        expected = hmac.new(key, data, hashlib.sha256).digest()
        return hmac.compare_digest(expected, signature)


class FileKeyProvider(_CachedProvider):
    """Key provider backed by local files."""

    def __init__(self, path: str | Path, cache_ttl: int = 300) -> None:
        super().__init__(cache_ttl)
        self._path = Path(path)

    async def get_key(self, key_id: str) -> bytes | None:  # noqa: ARG002
        cached = self._cache_get()
        if cached:
            return cached
        raw: bytes | None = None
        if self._path.is_file():
            try:
                raw = await asyncio.to_thread(self._path.read_bytes)
            except Exception:
                raw = None
        else:
            candidate = self._path / f"{key_id}.key"
            if candidate.exists():
                raw = await asyncio.to_thread(candidate.read_bytes)
        key = _decode_key(raw)
        self._cache_set(key)
        return key

    async def sign(self, key_id: str, data: bytes) -> bytes:  # noqa: ARG002
        key = await self.get_key(key_id)
        if not key:
            return b""
        return hmac.new(key, data, hashlib.sha256).digest()

    async def verify(self, key_id: str, data: bytes, signature: bytes) -> bool:  # noqa: ARG002
        key = await self.get_key(key_id)
        if not key:
            return False
        expected = hmac.new(key, data, hashlib.sha256).digest()
        return hmac.compare_digest(expected, signature)


class AwsKmsProvider(_CachedProvider):
    """AWS KMS provider with optional remote signing."""

    def __init__(
        self,
        key_id: str,
        region: str | None = None,
        cache_ttl: int = 300,
        use_kms_signing: bool = False,
        client: object | None = None,
    ) -> None:
        super().__init__(cache_ttl)
        self._key_id = key_id
        self._use_kms_signing = use_kms_signing
        if client is None:
            boto3 = importlib.import_module("boto3")
            client = boto3.client("kms", region_name=region)
        self._client = client

    async def get_key(self, key_id: str) -> bytes | None:  # noqa: ARG002
        if self._use_kms_signing:
            return None
        cached = self._cache_get()
        if cached:
            return cached
        response = await asyncio.to_thread(
            self._client.generate_data_key, KeyId=self._key_id, KeySpec="AES_256"
        )
        key = response.get("Plaintext")
        if isinstance(key, bytes):
            self._cache_set(key)
            return key
        return None

    async def sign(self, key_id: str, data: bytes) -> bytes:  # noqa: ARG002
        if self._use_kms_signing:
            response = await asyncio.to_thread(
                self._client.sign,
                KeyId=self._key_id,
                Message=data,
                MessageType="RAW",
                SigningAlgorithm="HMAC_SHA_256",
            )
            return response.get("Signature", b"")
        key = await self.get_key(self._key_id)
        if not key:
            return b""
        return hmac.new(key, data, hashlib.sha256).digest()

    async def verify(self, key_id: str, data: bytes, signature: bytes) -> bool:  # noqa: ARG002
        if self._use_kms_signing:
            try:
                await asyncio.to_thread(
                    self._client.verify,
                    KeyId=self._key_id,
                    Message=data,
                    Signature=signature,
                    MessageType="RAW",
                    SigningAlgorithm="HMAC_SHA_256",
                )
                return True
            except Exception as exc:
                invalid_exc = getattr(
                    getattr(self._client, "exceptions", None),
                    "KMSInvalidSignatureException",
                    None,
                )
                if invalid_exc and isinstance(exc, invalid_exc):
                    return False
                return False
        key = await self.get_key(self._key_id)
        if not key:
            return False
        expected = hmac.new(key, data, hashlib.sha256).digest()
        return hmac.compare_digest(expected, signature)


class GcpKmsProvider(_CachedProvider):
    """Google Cloud KMS provider; prefers KMS-native MAC signing."""

    def __init__(
        self,
        key_id: str,
        cache_ttl: int = 300,
        use_kms_signing: bool = True,
        client: object | None = None,
    ) -> None:
        super().__init__(cache_ttl)
        self._key_id = key_id
        self._use_kms_signing = use_kms_signing
        if client is None:
            kms_mod = importlib.import_module("google.cloud.kms_v1")
            client = kms_mod.KeyManagementServiceClient()
        self._client = client

    async def get_key(self, key_id: str) -> bytes | None:  # noqa: ARG002
        if self._use_kms_signing:
            return None
        # KMS does not export symmetric keys; enforce signing mode
        return None

    async def sign(self, key_id: str, data: bytes) -> bytes:  # noqa: ARG002
        if not self._use_kms_signing:
            return b""
        response = await asyncio.to_thread(
            self._client.mac_sign,
            request={"name": self._key_id, "data": data},
        )
        return getattr(response, "mac", b"")

    async def verify(self, key_id: str, data: bytes, signature: bytes) -> bool:  # noqa: ARG002
        if not self._use_kms_signing:
            return False
        response = await asyncio.to_thread(
            self._client.mac_verify,
            request={"name": self._key_id, "data": data, "mac": signature},
        )
        return bool(getattr(response, "success", False))


class AzureKeyVaultProvider(_CachedProvider):
    """Azure Key Vault provider using CryptographyClient for signing."""

    def __init__(
        self,
        key_id: str,
        cache_ttl: int = 300,
        tenant_id: str | None = None,
        client_id: str | None = None,
        use_kms_signing: bool = True,
        crypto_client: object | None = None,
    ) -> None:
        super().__init__(cache_ttl)
        self._key_id = key_id
        self._use_kms_signing = use_kms_signing
        if crypto_client is None:
            identity = importlib.import_module("azure.identity")
            if tenant_id and client_id:
                credential = identity.ClientSecretCredential(
                    tenant_id=tenant_id,
                    client_id=client_id,
                    client_secret=os.environ.get("AZURE_CLIENT_SECRET", ""),
                )
            else:
                credential = identity.DefaultAzureCredential()
            crypto_mod = importlib.import_module("azure.keyvault.keys.crypto")
            crypto_client = crypto_mod.CryptographyClient(self._key_id, credential)
        self._crypto_client = crypto_client

    async def get_key(self, key_id: str) -> bytes | None:  # noqa: ARG002
        return None  # Keys are not exported

    async def sign(self, key_id: str, data: bytes) -> bytes:  # noqa: ARG002
        if not self._use_kms_signing:
            return b""
        from azure.keyvault.keys.crypto import SignatureAlgorithm  # type: ignore

        result = await asyncio.to_thread(
            self._crypto_client.sign,
            SignatureAlgorithm.hs256,
            data,
        )
        return getattr(result, "signature", b"")

    async def verify(self, key_id: str, data: bytes, signature: bytes) -> bool:  # noqa: ARG002
        if not self._use_kms_signing:
            return False
        from azure.keyvault.keys.crypto import SignatureAlgorithm  # type: ignore

        result = await asyncio.to_thread(
            self._crypto_client.verify,
            SignatureAlgorithm.hs256,
            data,
            signature,
        )
        return bool(getattr(result, "is_valid", False))


class VaultProvider(_CachedProvider):
    """HashiCorp Vault Transit provider."""

    def __init__(
        self,
        addr: str,
        key_name: str,
        auth_method: str = "token",
        token: str | None = None,
        role_id: str | None = None,
        secret_id: str | None = None,
        cache_ttl: int = 300,
    ) -> None:
        super().__init__(cache_ttl)
        hvac = importlib.import_module("hvac")
        self._client = hvac.Client(url=addr)
        self._key_name = key_name
        self._auth_method = auth_method
        self._token = token
        self._role_id = role_id
        self._secret_id = secret_id
        self._authenticate()

    def _authenticate(self) -> None:
        if self._auth_method == "token":
            self._client.token = self._token or os.environ.get("VAULT_TOKEN")
        elif self._auth_method == "approle":
            self._client.auth.approle.login(
                role_id=self._role_id, secret_id=self._secret_id
            )
        elif self._auth_method == "kubernetes":
            sa_token = Path("/var/run/secrets/kubernetes.io/serviceaccount/token")
            jwt = sa_token.read_text() if sa_token.exists() else ""
            self._client.auth.kubernetes.login(role=self._role_id, jwt=jwt)

    async def get_key(self, key_id: str) -> bytes | None:  # noqa: ARG002
        return None  # Keys stay in Vault

    async def sign(self, key_id: str, data: bytes) -> bytes:  # noqa: ARG002
        payload = base64.b64encode(data).decode()
        response = await asyncio.to_thread(
            self._client.secrets.transit.sign_data,
            name=self._key_name,
            hash_input=payload,
            hash_algorithm="sha2-256",
            signature_algorithm="pkcs1v15",
        )
        signature = response["data"]["signature"]
        return base64.b64decode(signature.split(":")[-1])

    async def verify(self, key_id: str, data: bytes, signature: bytes) -> bool:  # noqa: ARG002
        sig_b64 = base64.b64encode(signature).decode()
        payload = base64.b64encode(data).decode()
        response = await asyncio.to_thread(
            self._client.secrets.transit.verify_signed_data,
            name=self._key_name,
            hash_input=payload,
            signature=f"vault:v1:{sig_b64}",
            hash_algorithm="sha2-256",
        )
        return bool(response["data"]["valid"])


def create_key_provider(config: TamperConfig) -> KeyProvider:
    """Create a concrete KeyProvider from configuration."""
    if config.key_source == "env":
        return EnvKeyProvider(
            config.key_env_var, cache_ttl=config.key_cache_ttl_seconds
        )
    if config.key_source == "file":
        path = config.key_file_path or ""
        return FileKeyProvider(path, cache_ttl=config.key_cache_ttl_seconds)
    if config.key_source == "aws-kms":
        try:
            return AwsKmsProvider(
                key_id=config.key_id,
                region=config.aws_region,
                cache_ttl=config.key_cache_ttl_seconds,
                use_kms_signing=config.use_kms_signing,
            )
        except ImportError as exc:
            raise ImportError(
                "AWS KMS support requires boto3. Install with: pip install fapilog-tamper[aws]"
            ) from exc
    if config.key_source == "gcp-kms":
        try:
            return GcpKmsProvider(
                key_id=config.key_id,
                cache_ttl=config.key_cache_ttl_seconds,
                use_kms_signing=config.use_kms_signing,
            )
        except ImportError as exc:
            raise ImportError(
                "GCP KMS support requires google-cloud-kms. "
                "Install with: pip install fapilog-tamper[gcp]"
            ) from exc
    if config.key_source == "azure-keyvault":
        try:
            return AzureKeyVaultProvider(
                key_id=config.key_id,
                cache_ttl=config.key_cache_ttl_seconds,
                tenant_id=config.azure_tenant_id,
                client_id=config.azure_client_id,
                use_kms_signing=config.use_kms_signing,
            )
        except ImportError as exc:
            raise ImportError(
                "Azure Key Vault support requires azure-keyvault-keys and azure-identity. "
                "Install with: pip install fapilog-tamper[azure]"
            ) from exc
    if config.key_source == "vault":
        try:
            return VaultProvider(
                addr=config.vault_addr or os.environ.get("VAULT_ADDR", ""),
                key_name=config.key_id,
                auth_method=config.vault_auth_method,
                token=os.environ.get("VAULT_TOKEN"),
                role_id=config.vault_role,
                cache_ttl=config.key_cache_ttl_seconds,
            )
        except ImportError as exc:
            raise ImportError(
                "Vault support requires hvac. Install with: pip install fapilog-tamper[vault]"
            ) from exc
    raise ValueError(f"Unknown key_source: {config.key_source}")
