from __future__ import annotations
import argparse, subprocess, sys

def parse_args():
    p = argparse.ArgumentParser(description="Shadow batch pipeline: reconcile_v3 batch -> threshold eval batch -> report pack.")
    p.add_argument("--db", required=True)
    p.add_argument("--since", default="")
    p.add_argument("--until", default="")
    p.add_argument("--channel", default="")
    p.add_argument("--symbol", default="")
    p.add_argument("--pack", default="shadow_gate_v1")
    p.add_argument("--pack-version", default="1.0")
    p.add_argument("--out-dir", default="./reports")
    p.add_argument("--out-prefix", default="report")
    p.add_argument("--overwrite", action="store_true")
    return p.parse_args()

def _run(cmd):
    print(">", " ".join(cmd))
    r = subprocess.run(cmd, check=False)
    if r.returncode != 0:
        raise SystemExit(r.returncode)

def main():
    a = parse_args()
    common = []
    if a.since: common += ["--since", a.since]
    if a.until: common += ["--until", a.until]
    if a.channel: common += ["--channel", a.channel]
    if a.symbol: common += ["--symbol", a.symbol]

    rec_cmd = [sys.executable, "-m", "src.runners.reconcile_batch_v3", "--db", a.db] + common
    thr_cmd = [sys.executable, "-m", "src.runners.threshold_batch_eval", "--db", a.db] + common + ["--pack", a.pack, "--pack-version", a.pack_version]
    rep_cmd = [sys.executable, "-m", "src.runners.report_pack", "--db", a.db] + common + ["--pack", a.pack, "--pack-version", a.pack_version, "--out-dir", a.out_dir, "--out-prefix", a.out_prefix]

    if a.overwrite:
        rec_cmd.append("--overwrite")
        thr_cmd.append("--overwrite")

    _run(rec_cmd)
    _run(thr_cmd)
    _run(rep_cmd)

if __name__ == "__main__":
    main()
