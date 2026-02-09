from src.storage.sqlite_store_thresholds import ThresholdStore
from src.reporting.report_pack import ReportConfig, build_report

def test_report_pack_empty(tmp_path):
    db = tmp_path / "t.db"
    store = ThresholdStore(str(db))
    rep = build_report(store, ReportConfig())
    assert rep["schema"].startswith("report_pack")
    assert isinstance(rep["summary"], dict)
    assert isinstance(rep["rows"], list)
