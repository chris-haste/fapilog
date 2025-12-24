from fapilog.core.settings import Settings


def test_worker_count_default_and_env(monkeypatch):
    # Default
    s = Settings()
    assert s.core.worker_count == 1

    # Env override
    monkeypatch.setenv("FAPILOG_CORE__WORKER_COUNT", "3")
    s2 = Settings()
    assert s2.core.worker_count == 3

    # Cleanup
    monkeypatch.delenv("FAPILOG_CORE__WORKER_COUNT", raising=False)
