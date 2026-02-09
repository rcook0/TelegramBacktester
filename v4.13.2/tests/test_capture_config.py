from src.capture.ctrader_capture import CTraderCapture, CTraderCaptureConfig


def test_capture_init():
    cap = CTraderCapture(CTraderCaptureConfig(access_token='x', symbols=['XAUUSD']))
    assert cap.cfg.symbols == ['XAUUSD']
