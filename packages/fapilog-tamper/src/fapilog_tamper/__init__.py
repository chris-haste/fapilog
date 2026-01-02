"""
fapilog-tamper: tamper-evident logging add-on for fapilog.
"""

from .canonical import b64url_decode, b64url_encode, canonicalize
from .chain_state import GENESIS_HASH, ChainStatePersistence
from .config import (
    IntegrityEnricherConfig,
    SealedSinkConfig,
    TamperConfig,
    coerce_tamper_config,
)
from .enricher import IntegrityEnricher
from .plugin import TamperSealedPlugin, TamperSealedPluginClass
from .providers import (
    AwsKmsProvider,
    AzureKeyVaultProvider,
    EnvKeyProvider,
    FileKeyProvider,
    GcpKmsProvider,
    KeyProvider,
    VaultProvider,
    create_key_provider,
)
from .sealed_sink import ManifestGenerator, SealedSink
from .types import ChainState, IntegrityFields
from .verify import (
    EnvKeyStore,
    FileKeyStore,
    KeyStore,
    Verifier,
    VerifyError,
    VerifyReport,
    run_self_check,
    verify_chain_across_files,
    write_manifest,
)

__all__ = [
    "TamperSealedPlugin",
    "TamperSealedPluginClass",
    "TamperConfig",
    "IntegrityEnricherConfig",
    "SealedSinkConfig",
    "coerce_tamper_config",
    "IntegrityFields",
    "ChainState",
    "ChainStatePersistence",
    "IntegrityEnricher",
    "GENESIS_HASH",
    "SealedSink",
    "ManifestGenerator",
    "Verifier",
    "VerifyReport",
    "VerifyError",
    "KeyStore",
    "EnvKeyStore",
    "FileKeyStore",
    "EnvKeyProvider",
    "FileKeyProvider",
    "AwsKmsProvider",
    "GcpKmsProvider",
    "AzureKeyVaultProvider",
    "VaultProvider",
    "KeyProvider",
    "create_key_provider",
    "run_self_check",
    "verify_chain_across_files",
    "write_manifest",
    "canonicalize",
    "b64url_encode",
    "b64url_decode",
]
