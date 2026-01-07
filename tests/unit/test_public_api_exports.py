def test_import_star_exports_only_public_symbols():
    ns: dict[str, object] = {}
    exec("from fapilog import *", ns, ns)
    # Exclude __builtins__ which is injected by exec(), keep __version__
    exported = {name for name in ns if name != "__builtins__"}

    import fapilog

    assert exported == set(fapilog.__all__)
    assert {"DrainResult", "LogEvent", "Settings", "__version__"} <= exported
    # Ensure config classes and typing helpers aren't exported
    assert "AuditSinkConfig" not in exported
    assert "Any" not in exported
