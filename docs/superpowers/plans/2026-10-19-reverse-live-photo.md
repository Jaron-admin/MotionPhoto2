# Reverse Live Photo implementation plan

Goal: Add conservative Google Motion Photo → Apple Live Photo conversion to the existing Chinese app, reusing the licensed Python timed-metadata writer.
Architecture: Python detection, lossless photo metadata editing, bounded QuickTime remux, transactional pair output; GUI only selects direction and invokes CLI.
Tech stack: Python, lxml, ExifTool, tkinter; FFmpeg and Swift are test tools only.
Spec: docs/superpowers/specs/2026-10-19-reverse-live-photo-design.md

## Global Constraints

- Never alter input files or overwrite output; no media reencoding or Apple APIs in production.
- Support only validated Google JPG/HEIC + nonfragmented H.264/HEVC, optional AAC. Reject unsupported containers explicitly.
- Preserve standard photo metadata and source audio/video bytes. Preserve third-party Apache license and attribution.
- Existing forward regression tests stay green. A real Pixel sample and Photos playback remain a separate acceptance gate.
- Reuse the clean dedicated feature checkout, per the host preference to reuse suitable checkouts. Do not merge or publish a release.

## Review Focus

Review untrusted media sizes/offsets, extended boxes and integer limits, B-frame/edit-list timing, image auxiliary content, symlink/output collisions, partial publication/cancellation, CLI option interactions, bundle dependency inclusion, and accidental release paths. Confirm limitations are surfaced rather than silently discarding media.

### Task 1: Prove and adapt minimal Live Photo resources

Files: reverse/quicktime.py, reverse/iso_bmff.py, reverse/photo.py, tests/test_reverse_media.py, tests/verify_live_photo.swift, LICENSES/Apache-2.0.txt, THIRD_PARTY_NOTICES.md.
Interfaces: write_live_mov(source, output, identifier, timestamp_us) returns selected presentation time; write_live_photo(source, output, identifier) preserves compressed image and standard metadata.
1. Use native Apple output as independent control; record actual callbacks and metadata. Do not mistake degraded preview for final recognition.
2. Write tests for shared ID, preserved image/video data, timestamp bounds, malformed and unsupported movie layouts, then run them.
   Expected: missing reverse implementation fails.
3. Adapt the upstream metadata construction and implement validation, real MOV brand and preserved metadata.
4. Run `.venv/bin/python -m unittest tests.test_reverse_media -v` and Apple test harness.
   Expected: tests pass; Apple final result is reported accurately, including any unresolved environment limitation.
5. Commit reviewed media module and test evidence.

### Task 2: Detect Motion Photos and publish pairs safely

Files: reverse/detect.py, reverse/convert.py, tests/test_reverse.py.
Interfaces: detect(path) gives bounded image/video ranges and timestamp; convert_file returns structured status; convert_directory continues after per-file errors.
Consumes Task 1 writer APIs.
1. Write tests for current/legacy JPG and HEIC, namespace variants, malformed offsets/directories, ordinary photos, no-clobber, rollback, source hashes, times and recursive directory exclusion.
2. Run `.venv/bin/python -m unittest tests.test_reverse -v`.
   Expected: fail before implementation.
3. Implement bounded detection, temporary files and transactional no-overwrite output.
4. Rerun tests. Expected: all pass.
5. Commit conversion core.

### Task 3: Integrate CLI and Chinese direction controls

Files: motionphoto2.py, mac_gui.py, tests/test_reverse_cli.py, build-mac-app.spec.
Consumes Task 2 result statuses and conversion entry points.
1. Test CLI reverse directory/single-file paths, invalid combinations, process exit codes, GUI argument building and direction default path preservation.
2. Run tests before code. Expected: fail for absent reverse mode.
3. Implement direction switch, translated progress/results, forward-only option disabling; ensure stopping cleans temporary outputs.
4. Run `.venv/bin/python tests/run_tests.py` and GUI smoke test.
   Expected: old and new tests pass, one pre-existing XMP expected failure remains.
5. Commit integration.

### Task 4: Build validation, documentation and final review

Files: .github/workflows/build-mac-zh.yml, .github/workflows/test.yml, docs/TESTING.md, README_zh.md, docs/ROADMAP.md, design evidence.
1. Enable PR build checks and guard Release publication behind an explicit dispatch input; include reverse package in bundle.
2. Run full tests, compile checks and build where available. Expected: checks pass; unavailable manual Pixel acceptance is stated explicitly.
3. Request one fresh whole-branch code review; fix important findings with reproducing tests.
4. Push a stacked stage-1 PR targeting stage-0 branch, attach it, verify GitHub Actions without publishing.
   Expected: passing checks and downloadable test build, or precisely documented external blocker.
