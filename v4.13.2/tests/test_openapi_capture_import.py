def test_openapi_capture_importable():
    # The module should import even if optional deps are missing; it exposes a flag.
    from src.capture import ctrader_openapi_capture
    assert hasattr(ctrader_openapi_capture, "CTRADER_OPENAPI_AVAILABLE")
