from __future__ import annotations

import json

from fapilog.core.settings import Settings


def test_settings_to_json_and_dict_roundtrip() -> None:
    s = Settings()
    d = s.to_dict()
    j = s.to_json()
    assert isinstance(d, dict)
    parsed = json.loads(j)
    assert isinstance(parsed, dict)
