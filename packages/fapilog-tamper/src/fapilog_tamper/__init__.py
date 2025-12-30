"""
fapilog-tamper: tamper-evident logging add-on for fapilog.
"""

from .canonical import b64url_decode, b64url_encode, canonicalize
from .chain_state import GENESIS_HASH, ChainStatePersistence
from .config import TamperConfig
from .enricher import IntegrityEnricher
from .plugin import TamperSealedPlugin, TamperSealedPluginClass
from .sealed_sink import ManifestGenerator, SealedSink
from .types import ChainState, IntegrityFields

__all__ = [
    "TamperSealedPlugin",
    "TamperSealedPluginClass",
    "TamperConfig",
    "IntegrityFields",
    "ChainState",
    "ChainStatePersistence",
    "IntegrityEnricher",
    "GENESIS_HASH",
    "SealedSink",
    "ManifestGenerator",
    "canonicalize",
    "b64url_encode",
    "b64url_decode",
]
