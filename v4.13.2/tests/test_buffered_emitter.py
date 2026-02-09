from src.capture.buffered_emitter import BufferedEmitter, BufferedEmitterConfig

def test_emitter_coalesces_quotes():
    em = BufferedEmitter(BufferedEmitterConfig(flush_interval_sec=0.1))
    em.update_quote("X", {"symbol":"X","bid":1})
    em.update_quote("X", {"symbol":"X","bid":2})
    out = []
    em.flush(on_quote=lambda q: out.append(q))
    assert len(out) == 1
    assert out[0]["bid"] == 2
