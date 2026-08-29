ALTER TABLE facility_reports
  ADD COLUMN IF NOT EXISTS submitter_ip INET;

CREATE INDEX IF NOT EXISTS facility_reports_submitter_ip_created_idx
  ON facility_reports(submitter_ip, created_at DESC)
  WHERE submitter_ip IS NOT NULL;

COMMENT ON COLUMN facility_reports.submitter_ip IS
  'Network address used only for abuse controls; retained with the report retention period.';
