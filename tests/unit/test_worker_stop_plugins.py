import pytest

from fapilog.core import worker


class _Plugin:
    def __init__(
        self,
        kind: str,
        name: str,
        call_log: list[str],
        *,
        raise_exc: bool = False,
    ) -> None:
        self.kind = kind
        self.name = name
        self._call_log = call_log
        self._raise_exc = raise_exc

    async def stop(self) -> None:  # pragma: no cover - exercised via stop_plugins
        self._call_log.append(f"{self.kind}-{self.name}")
        if self._raise_exc:
            raise RuntimeError(f"{self.kind}-{self.name}-fail")


@pytest.mark.asyncio
async def test_stop_plugins_stops_in_reverse_and_warns(monkeypatch):
    call_log: list[str] = []
    warnings: list[tuple[str, str, dict[str, object]]] = []

    def fake_warn(component: str, message: str, **fields: object) -> None:
        warnings.append((component, message, fields))

    monkeypatch.setattr(worker, "warn", fake_warn)

    processors = [
        _Plugin("processor", "p1", call_log),
        _Plugin("processor", "p2", call_log),
    ]
    filters = [
        _Plugin("filter", "f1", call_log, raise_exc=True),
        _Plugin("filter", "f2", call_log),
    ]
    redactors = [_Plugin("redactor", "r1", call_log)]
    enrichers = [
        _Plugin("enricher", "e1", call_log),
        _Plugin("enricher", "e2", call_log, raise_exc=True),
    ]

    await worker.stop_plugins(processors, filters, redactors, enrichers)

    assert call_log == [
        "processor-p2",
        "processor-p1",
        "filter-f2",
        "filter-f1",
        "redactor-r1",
        "enricher-e2",
        "enricher-e1",
    ]
    assert any(w[0] == "filter" and w[1] == "plugin stop failed" for w in warnings)
    assert any(w[0] == "enricher" and w[1] == "plugin stop failed" for w in warnings)


@pytest.mark.asyncio
async def test_stop_plugins_swallows_warn_failures(monkeypatch):
    call_log: list[str] = []

    def raising_warn(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("warn failed")

    monkeypatch.setattr(worker, "warn", raising_warn)

    await worker.stop_plugins(
        [_Plugin("processor", "p1", call_log, raise_exc=True)], [], [], []
    )

    assert call_log == ["processor-p1"]
