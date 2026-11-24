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
