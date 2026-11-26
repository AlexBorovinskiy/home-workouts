# Vertebral endplate audit, v0.8 — 2026-11-26

Completed runs: [initial](https://github.com/AlexBorovinskiy/home-workouts/actions/runs/45769416404), [refined](https://github.com/AlexBorovinskiy/home-workouts/actions/runs/45769647059). Exact FHS archive checksum checked. No rig/mesh transforms edited.

## Method and results
- Original FHS surfaces, Rajagopal sacrum, and MyoHub surrogate cervical meshes as rendered by the existing viewer; 26 meshes, no loading failures.
- Vertical ray intersection on three nested patches around actual joint centers, checking coverage, planar residual and sensitivity to patch radius. These are geometric candidates, not expert-segmented endplates.
- Initial: 32 of 46 individual surfaces stable (7/10 lumbar, 19/24 thoracic, 6/11 cervical, 0/1 native sacrum). Both sides stable at 12/23 interfaces.
- Refined search: sagittal offsets -18 to +18 mm, step 3 mm, three nested radii. 17 additional candidate pairs across 10 of 11 initially unresolved interfaces; 22/23 have at least one geometrically stable pair. Visual sagittal projection reviewed: many patches now lie on plausible anterior vertebral body faces. This is not clinical acceptance.
- L5/S1: zero stable pairs in the expanded search; the two bone surfaces do not yield a reliable corresponding patch under the current method. Do not report disc clearance or sacral slope. This is the remaining localization priority; an algorithm failure does not establish a physical gap or collision.
- Among stable candidate pairs, vertical center clearance is positive (minimum 2.30 mm), but this does not rule out other surface overlaps and is not cartilage/disc thickness.

## Preliminary sagittal angles
- C2–C7 inferior-endplate slope difference: 22.08° (initial), 22.35–22.54° using refined C2 patches and initial C7 patch. Cervical mesh identity relative to original MASI remains unverified. Do not force a population mean.
- T4 superior to T12 inferior: 18.28°; MEANS cohort mean 37.4 ± 10.9° (PMID 35797648). Possible shallow thoracic curve; no correction based on a population mean alone.
- T1 superior to T12 inferior: 25.10–26.59° with refined T1 patches. Not equivalent to T4–T12.
- L1–S1: withheld because native S1 candidate was not resolved.
- Sagittal differences here are unsigned plane-slope estimates, not formal clinical signed Cobb measurements.

## Decision
Keep v0.8 intact. Prioritize native sacral superior endplate and L5 inferior endplate: explicit anatomical surface selection (sagittal and coronal cross-sections, not another blind whole-surface fit), paired surface clearance and attachment check, then compare with donor baseline. Only after that decide whether to adjust L5/S1 or distribute thoracic curvature through existing native coordinates. No scaling to 182 cm and no muscle binding yet.

References: [MEANS thoracic values](https://pubmed.ncbi.nlm.nih.gov/35797648/), [regional angle definitions](https://pmc.ncbi.nlm.nih.gov/articles/PMC7788366/), [cervical variability](https://pubmed.ncbi.nlm.nih.gov/33027127/). The complete raw reports and diagnostic images are attached to the runs above; workflow artifact retention is 14 days.
