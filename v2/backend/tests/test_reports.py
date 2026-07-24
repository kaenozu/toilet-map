"""Facility-report deduplication tests."""

from app.reports import ReportPayload, ReportType, report_fingerprint


def test_report_fingerprint_is_stable_for_same_day() -> None:
    payload = ReportPayload(ReportType.BROKEN, "  便器が故障  ")
    assert report_fingerprint(10, payload, day="2026-07-23") == report_fingerprint(
        10,
        ReportPayload(ReportType.BROKEN, "便器が故障"),
        day="2026-07-23",
    )


def test_report_fingerprint_changes_by_facility() -> None:
    payload = ReportPayload(ReportType.CLOSED)
    assert report_fingerprint(10, payload, day="2026-07-23") != report_fingerprint(
        11, payload, day="2026-07-23"
    )
