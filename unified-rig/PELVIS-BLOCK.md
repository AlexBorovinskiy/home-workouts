# Native Rajagopal pelvis experiment (v0.7)

## Verified inputs
- v0.6: OpenSim native inventory workflow 45364940962, six sequences, 186 frames.
- Both hip centers agree with native Rajagopal pelvis-local positions in the exported v0.6 frames (maximum residual below 0.001 mm).
- Hip-center separation: 154.52 mm; source local hip centers: (-0.056276, -0.07849, ±0.07726) m.
- Rajagopal model-specific pelvis geometry: r_pelvis.vtp, l_pelvis.vtp, sacrum.vtp, all with native unit scale and direct attachment to pelvis.
- FHS sacrum is an internal root frame; its visible bone is hidden in v0.7, not duplicated. FHS lumbar joints and mechanisms remain intact.

## Why no direct pivot transfer
The native Rajagopal aggregate back joint is at (-0.1007, 0.0815, 0) m in the pelvis frame. Equating it to the FHS L5/S1 joint center in v0.6 would move the pelvic subtree approximately 65.51 mm. Those two modeled pivots are not established anatomical homologues. This is a diagnostic comparison, not an accepted calibration.

## Experiment
fit_pelvis_block.py compares the original sacral surfaces under a rigid symmetry-preserving registration, alongside the original placement and pivot-only hypothesis. It changes only the pelvis-to-root weld. No scale, hip socket edit, or change to individual leg joints is permitted. verify_pelvis_block.py independently checks each native OpenSim output frame against the exact expected rigid subtree relocation.

The surface fit is a provisional registration. A low global surface discrepancy does not establish L5/S1 disc contact, sacroiliac biomechanics, standing alignment, or physiological ROM. Candidate is isolated from v0.6. No force, balance, or personalized anthropometry claim.

Viewer: pelvis.html, includes a pelvis/lumbar region and version comparison. Calibration output: pelvis-block.json and sequences-pelvis.json after successful native QA.

## Completed results (2026-11-24)
Native workflow 45377866490 completed surface fit and all 186 OpenSim frames; publication and browser QA completed in 45378281438. The three Rajagopal pelvic surfaces replace (not overlay) the FHS pelvis/sacrum. All 6 sequences preserved, independent rigid replay maximum residual 0.001215 mm, native hip center separation 154.52 mm. The browser comparison loaded all 134 objects and had no runtime errors.
- Donor-to-FHS sacral surface p95: 36.73 mm at original placement, 49.83 mm with pivot-only alignment, 9.75 mm with rigid surface fit.
- Residual between the aggregate back and L5/S1 model pivots: 27.20 mm after fit; this is NOT a measured physical disc gap.
- Fit introduces -14.01° sagittal rotation. In the neutral export the right hip-to-ankle angle from vertical changes 0.46° to 14.46°; the right heel frame moves posteriorly 221.75 mm. L5 is unchanged. No standing balance/contact solve has been done.
- Mobile screenshots confirm native femoral heads appear better seated relative to the pelvis; visual impression does not validate cartilage contact or L5–sacrum contact.

**Decision:** retain Rajagopal native pelvis/hip geometry; reject the experimental v0.7 neutral posture as a validated standing baseline. Preserve v0.6. Next test must use actual endplate landmarks and constrained neutral pose, not another unconstrained global surface fit. No anthropometric scaling yet.
