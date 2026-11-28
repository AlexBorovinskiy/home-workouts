# Unified Human Rig — v0.1
Status: native mechanism inventory, not yet a unified moving model.
Goal: exercise visualization, target stature 1.82 m; no mesh or muscle binding until kinematics passes.
Canonical world: right-handed, +X anterior, +Y superior, +Z subject right; metres and radians.
Sources: FHS thoracolumbar spine/ribs and pelvis; MASI C1–C7/head; bilateral AAH shoulder/arm/hand; Rajagopal 2023 legs.
Each module must preserve native joint frames, coordinate functions and constraints. Do not count coordinates as independent DOF.
Interfaces: pelvis to legs; T1 to cervical chain; thorax to each AAH shoulder girdle. Each interface requires explicit rigid registration and calibrated scale, verified with independent landmarks. No duplicate joints or independent motion on both sides of an interface.
Foot individual toes remain unresolved (Rajagopal has grouped toes).
Stages:
1. Native mechanism inventory (extract_native.py; workflow unified-rig.yml).
2. Map source topology and constraint dependencies; select one owner per joint.
3. Assemble mesh-free OpenSim candidate; verify connectivity, coordinate ranges, coupled constraints, neutral and perturbed poses.
4. Viewer with body-frame markers, actual joint-frame markers and local axes separately labeled.
5. Validate neck, scapular motion, pronation, finger closure, squat and push-up pose against references. Contact constraints require separate calibration.
6. Only then bind anatomical meshes. No muscle force claims from kinematics.
Rejected: MakeHuman 53-bone rig as final basis; arbitrary offsets to fix single exercise; pose interpolation as substitute for native joint mechanisms.
Existing experiments are preserved.

## Audit the published pose exports

From the repository root, run the pose audit with Python and NumPy. The
checked-in calibration report supplies the two original FHS sternoclavicular
target points. A native FHS inventory from `extract_native.py` can provide the
same reference points.

```sh
python unified-rig/audit_pose_exports.py unified-rig/sequences-head-neck.json \
  unified-rig/calibration.json /tmp/head-neck-pose-audit.json
```

The arm report measures the unsigned change from the first frame in the
relative rotation of two bones. In the v1.0 head and neck export, the curl
changes the humeroulnar rotation by about 95° per side and holds the
radioulnar rotation fixed within the precision of the exported matrices. The
separate pronation diagnostic changes the radioulnar rotation by about 90°
per side. The grip and curl diagnostics move all three thumb joints. The
angles describe motion in these synthetic sequences. A clinical joint
coordinate system is required to resolve the rotations into anatomical
components. Assessment of opposition and equipment grip also requires the
relative positions of the thumb pad, fingers and handle surfaces.

Use [the ISB joint coordinate system recommendations](https://doi.org/10.1016/j.jbiomech.2004.05.042)
for shoulder, elbow, wrist and hand axes. The
[hand MRI reconstruction](../anatomy-first/REAL-HAND-SOURCE.md) documents a
separate geometry reference for the wrist and thumb. For stature, measure
from the support plane to the crown of the outer surface in neutral stance.
See the [neutral stance audit](NEUTRAL-STANCE-AUDIT.md) for the limitations of
the current skeletal extent.
