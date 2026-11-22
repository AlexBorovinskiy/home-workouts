#!/usr/bin/env python3
"""OpenSim 4.6 spine body-frame diagnostic, NOT a prescribed exercise.

Inputs: subject-specific FHS OpenSim model supplied at run time.
Outputs: joint-controlled body positions (not simulated muscle forces).
No source subject meshes or .osim files are published.
"""
import argparse
import json
import math
import xml.etree.ElementTree as ET

import opensim as osim

LEVELS = ([f"lumbar{i}" for i in range(5, 0, -1)] +
          [f"thoracic{i}" for i in range(12, 0, -1)])
# The original FHS model combines the head and all cervical structures in ONE rigid body.
# Include its real OpenSim frame origin; this is not individual cervical vertebra geometry.
SUPPORT = ["sacrum", "head_neck", "sternum", "clavicle_R", "scapula_R",
           "humerus_R", "ulna_R", "radius_R", "hand_R",
           "clavicle_L", "scapula_L", "humerus_L",
           "ulna_L", "radius_L", "hand_L"]
CORE = LEVELS + SUPPORT
# Artificial small, identical coordinate increments only verify linkage.
# They do NOT represent healthy ROM, an exercise, or safe training technique.
CASES = [
    ("neutral", None, 0.0),
    ("flexion_diagnostic", "FE", 0.009),
    ("extension_diagnostic", "FE", -0.009),
    ("sidebend_diagnostic", "LB", 0.006),
    ("twist_diagnostic", "AR", 0.006),
]
COORDS = ([f"L5_S1_{a}" for a in ("FE", "LB", "AR")] +
          [f"L{i}_L{i+1}_{a}" for i in range(4, 0, -1)
           for a in ("FE", "LB", "AR")] +
          [f"T12_L1_{a}" for a in ("FE", "LB", "AR")] +
          [f"T{i}_T{i+1}_{a}" for i in range(11, 0, -1)
           for a in ("FE", "LB", "AR")])


def vec3(vec):
    return [round(float(vec[i]), 7) for i in range(3)]


def run(path):
    doc = ET.parse(path)
    raw = doc.getroot().find("Model")
    if raw is None:
        raise ValueError("Not an OpenSim model.")
    names = {b.get("name") for b in raw.findall("./BodySet/objects/Body")}
    missing = [b for b in LEVELS if b not in names]
    if missing:
        raise ValueError(f"Missing expected spine bodies: {missing}")
    actual_contact_forces = [
        c.tag for c in raw.findall("./ForceSet/objects/*")
        if "contact" in c.tag.lower() or "huntcrossley" in c.tag.lower()
        or "elasticfoundation" in c.tag.lower()
    ]
    contact_geometry = raw.findall(".//ContactGeometrySet/objects/*")
    has_feet = any(x.startswith(("calcn", "foot", "toes", "tibia", "femur"))
                   for x in names)

    model = osim.Model(str(path))
    model.setUseVisualizer(False)
    state = model.initSystem()
    all_coordinates = model.getCoordinateSet()
    baseline = {}
    for key in COORDS:
        try:
            baseline[key] = float(all_coordinates.get(key).getValue(state))
        except Exception as exc:
            raise ValueError(f"Missing coordinate {key}") from exc
    bones = model.getBodySet()

    frames = []
    for label, axis, delta in CASES:
        for key, initial in baseline.items():
            coordinate = all_coordinates.get(key)
            value = initial + (delta if (axis and key.endswith("_" + axis)) else 0.0)
            # Do not silently exceed scientific model coordinate ranges.
            if value < coordinate.getRangeMin() or value > coordinate.getRangeMax():
                raise ValueError(f"{label} out of source range: {key}={value}")
            coordinate.setValue(state, value, False)
        # Required: solve constraints; don't output unconstrained arbitrary transforms.
        model.assemble(state)
        model.realizePosition(state)
        locations = {}
        for key in CORE:
            if key in names:
                body = bones.get(key)
                transform = body.getTransformInGround(state)
                # Frame origins, not the vertices or muscle attachment points.
                locations[key] = vec3(transform.p())
        frames.append({"id": label, "deltaRadPerLevel": delta,
                       "axis": axis, "bodyFrameOriginsM": locations})

    # Validate that the actual OpenSim kinematic chain moves in the test.
    neutral = frames[0]["bodyFrameOriginsM"]
    nonzero = [
        math.dist(neutral[name], frame["bodyFrameOriginsM"][name])
        for frame in frames[1:] for name in LEVELS
    ]
    if not nonzero or max(nonzero) < 1e-5:
        raise AssertionError("OpenSim transform response was effectively zero.")

    result = {
        "kind": "opensim-native-kinematic-diagnostic",
        "source": "https://zenodo.org/records/18259702",
        "model": raw.get("name", ""),
        "opensimVersion": osim.GetVersionAndDate(),
        "units": "m",
        "bodyFrameOriginsNotCOM": True,
        "method": "OpenSim Model.initSystem, Coordinate.setValue, Model.assemble, realizePosition, Body.getTransformInGround",
        "diagnosticOnly": True,
        "noMeasuredMotion": True,
        "noMuscleForceComputation": True,
        "isPushup": False,
        "contactAudit": {
            "hasFeet": has_feet,
            "hasExternalHandGroundForces": bool(actual_contact_forces),
            "contactForceTypes": sorted(set(actual_contact_forces)),
            "contactGeometryCount": len(contact_geometry),
            "hasPalmPressureModelVerified": False
        },
        "spineLevels": LEVELS,
        "neckHeadResolution": "combined head_neck body; no separate C1-C7",
        "handResolution": "one rigid body per hand; no articulated finger segments",
        "frames": frames
    }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = run(args.model)
    with open(args.output, "w", encoding="utf-8") as dest:
        json.dump(result, dest, ensure_ascii=False, indent=2)
    print("NATIVE_SPINE_REPORT " + json.dumps(result, ensure_ascii=False, separators=(",", ":")))
