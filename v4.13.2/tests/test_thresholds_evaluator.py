from src.thresholds.evaluator import evaluate_pack

def test_evaluator_basic_pass_fail():
    pack = {
        "rules":[
            {"id":"a","metric":"recon.x","op":"<=","value":1,"severity":"ERROR","weight":1.0},
        ],
        "scoring":{"warn_penalty":0.25,"error_penalty":1.0,"pass_score":0.75}
    }
    ok = evaluate_pack(pack, {"recon":{"x":0.5}})
    bad = evaluate_pack(pack, {"recon":{"x":2.0}})
    assert ok["status"] == "PASS"
    assert bad["status"] == "FAIL"
