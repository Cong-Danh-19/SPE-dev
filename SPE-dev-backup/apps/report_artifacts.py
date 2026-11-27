"""Text artifacts that bind the submission to its audited results."""
import hashlib

REPORT_FILES = (
    *(f"design_E{i}_{suffix}" for i in range(1, 7) for suffix in ("raw.csv", "summary.csv", "manifest.json")),
    "report.html", "slo.csv", "tandem.csv", "verification.csv", "runtime_validation.csv",
    "e6_factorial.csv", "verification_followup_raw.csv",
)


def report_hashes(directory):
    # Git checkouts and CSV writers may use LF or CRLF for the same text.
    return {f: hashlib.sha256((directory / f).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            for f in REPORT_FILES}
