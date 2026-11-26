# Neutral stance audit — v0.8 (26 November 2026)

## Completed checks
The native OpenSim v0.8 export (run 45407502408, neutral frame of pronation) was independently compared with original FHS and MASI body frames from inventory run 45364940962. All measured values are recorded in neutral-stance-audit.json.

- Bilateral hip-to-ankle sagittal inclination: 0.457°; hip–knee–ankle segment-axis deviation: 0.580°. These are geometric proxies, not clinical joint angles.
- The original internal positions and orientations of the lumbar/thoracic and cervical/cranial blocks are preserved within export rounding (position differences <0.002 mm).
- All six foot mesh files were examined using their native body transforms. Both feet have identical minimum height. The lowest vertices on the forefoot/toe meshes are 2.30 mm below the lowest vertices of the hindfoot/midfoot meshes.
- The lowest skeletal vertex is at y=-0.914104 m. The visible skull reaches y=0.812397 m, giving an approximate mesh extent of 1.72650 m, not human stature. The skull geometry is the same surrogate already used in the viewer.
- The apparent sagittal rotation of the pelvis frame (-14.01°) is NOT clinical pelvic tilt. The differences of vertebral body-frame angles (L5/L1 32.18°, T12/T1 -20.84°, C7/C2 approximately zero) are NOT Cobb angles. In MASI the neutral cervical body frame axes are almost parallel even though the vertebral geometry is curved.

## Decision
Keep v0.8 as the working kinematic baseline; no new anatomical corrections are justified by these tests alone. Do not scale to 1.82 m using skull-to-foot extent as though it were measured skin stature.

Remaining acceptance gates: identify superior/inferior vertebral endplate landmarks, actual S1 superior endplate and hip-center midpoint, occipital/head landmarks, and physical plantar contact. Measure true sagittal parameters using the definitions in the literature, not arbitrary body axes. Direct inspection of original FHS vertebral meshes was blocked by the archive download in this runtime; no endplate or L5/S1 contact conclusion is claimed. Heterogeneous donor masses and absence of foot contact geometry prevent credible dynamic balance validation. The report is a completed limited audit, not certification of anatomical correctness.

## Scientific references
- Normative sagittal alignment, systematic review: https://pubmed.ncbi.nlm.nih.gov/40407040/
- MEANS healthy adult reference cohort: https://pubmed.ncbi.nlm.nih.gov/35797462/
- Standing alignment and force-plate gravity line: https://pmc.ncbi.nlm.nih.gov/articles/PMC5382592/
- Endplate-based measurement definitions: https://pmc.ncbi.nlm.nih.gov/articles/PMC12514220/
- FHS model source: https://zenodo.org/records/18259702
