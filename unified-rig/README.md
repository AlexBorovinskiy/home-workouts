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
