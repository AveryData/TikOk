# printagenda

Project name is **printagenda**. The repo is `AveryData/TikOk` (legacy
folder name `TikOk/`, app code in `briefing/`) but everything
user-facing — Cloud Run service, GCS buckets, NFC tag, etc. — should
be named with `printagenda` going forward, not `daily-briefing` or
`record-of-our-day`.

When suggesting resource names in new commands, default to
`printagenda` / `printagenda-health` / etc. unless something already
exists with the old name, in which case offer the rename and let the
user decide.
