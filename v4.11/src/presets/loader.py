import os, json

def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_preset_bundle(name: str, base_dir: str = None):
    base_dir = base_dir or os.path.join(os.path.dirname(__file__), "..", "..", "presets")
    root = os.path.join(base_dir, name)
    sym  = _load_json(os.path.join(root, "symbol_map.json"))
    con  = _load_json(os.path.join(root, "contract_map.json"))
    conv = _load_json(os.path.join(root, "conv_map.json"))
    return {"symbol_map": sym, "contract_map": con, "conv_map": conv}
