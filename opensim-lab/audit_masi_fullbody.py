#!/usr/bin/env python3
"""Audit the complete authors' MASI body in native OpenSim 4.6.

No geometry retargeting, no MASI/FHS fusion and no exercise safety claims.
Produces body/world transforms for a separately validated viewer.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import xml.etree.ElementTree as ET

import opensim as osim
from test_masi_kinematics import run as test_kinematics

DOI = "10.6084/m9.figshare.4249808.v2"
REQUIRED_NECK = [f"cerv{i}" for i in range(1, 8)]
REQUIRED_UPPER = ["skull", "torso", "rscapula", "lscapula", "rclavicle", "lclavicle", "humerus_r", "humerus_l"]


def xyz(vector):
    return [round(float(vector[i]), 9) for i in range(3)]


def transform(body, state):
    t = body.getTransformInGround(state)
    return {
        "positionM": xyz(t.p()),
        "rotation": [[round(float(t.R().get(r, c)), 9) for c in range(3)] for r in range(3)],
        "massKg": round(float(body.getMass()), 6),
    }


def frame_name(joint, side):
    try:
        frame = joint.getParentFrame() if side == "parent" else joint.getChildFrame()
        try:
            return frame.findBaseFrame().getName()
        except Exception:
            return frame.getName()
    except Exception:
        return None


def source_visuals(path):
    """Record source-attached meshes; filenames do NOT imply loaded anatomy."""
    model = ET.parse(path).getroot().find("Model")
    if model is None:
        raise ValueError("Not an OpenSim model")
    out = {}
    for b in model.findall("./BodySet/objects/Body"):
        files = []
        for d in b.findall(".//DisplayGeometry"):
            filename = d.findtext("geometry_file")
            if filename:
                files.append({
                    "file": filename.strip(),
                    "localTransform": (d.findtext("transform") or "").strip(),
                    "localScale": (d.findtext("scale_factors") or "").strip(),
                })
        if files:
            out[b.get("name")] = files
    return out


def audit(model_path):
    model = osim.Model(str(model_path))
    state = model.initSystem()
    model.assemble(state)
    model.realizePosition(state)
    bset, jset, cset = model.getBodySet(), model.getJointSet(), model.getCoordinateSet()
    frames = {bset.get(i).getName(): transform(bset.get(i), state) for i in range(bset.getSize())}
    names = set(frames)
    missing_neck = sorted(set(REQUIRED_NECK) - names)
    missing_upper = sorted(set(REQUIRED_UPPER) - names)
    if missing_neck or missing_upper:
        raise AssertionError(f"Unexpected MASI inventory: missing neck={missing_neck}; upper={missing_upper}")
    joints = []
    for i in range(jset.getSize()):
        j = jset.get(i)
        joints.append({"name": j.getName(), "type": j.getConcreteClassName(),
                       "parentBody": frame_name(j, "parent"), "childBody": frame_name(j, "child")})
    cervical_y = [frames[n]["positionM"][1] for n in REQUIRED_NECK]
    ordered_neck = all(a > b for a, b in zip(cervical_y, cervical_y[1:]))
    kine = test_kinematics(str(model_path))
    return {
        "schema": "MASI-fullbody-native-OpenSim-4.6-audit-v1",
        "sourceDOI": DOI,
        "sourceModel": "Authors' MASI 2017, name-only migration for OpenSim 4.6",
        "engine": osim.GetVersionAndDate(),
        "counts": {"bodies": bset.getSize(), "joints": jset.getSize(),
                   "coordinates": cset.getSize(), "muscles": model.getMuscles().getSize()},
        "bodies": frames, "joints": joints,
        "coordinateNames": [cset.get(i).getName() for i in range(cset.getSize())],
        "visualMeshesReferencedBySource": source_visuals(model_path),
        "checks": {
            "sevenSeparateCervicalBodies": len(REQUIRED_NECK) == 7 and not missing_neck,
            "cervicalBodyOriginsOrderedVertically": ordered_neck,
            "relativeCervicalMotionObservedInTrial": kine["hasNonrigidCervicalKinematics"],
            "relativeScapularMotionObservedInTrial": kine["hasScapulothoracicMotion"],
            "allRequiredUpperBodySegmentsPresent": not missing_upper,
            "neckToFhsInterchangeValidated": False,
            "pushupOrDumbbellExerciseValidated": False,
            "individualFingerArticulationValidated": False,
        },
        "researchKinematics": {
            "testedCoordinates": [x["coordinate"] for x in kine["individualTests"] if "error" not in x],
            "failedTrialCoordinates": [x["coordinate"] for x in kine["individualTests"] if "error" in x],
        },
        "limitations": [
            "Body-frame origins are not joint centers or visible bone vertices",
            "A source mesh filename does not establish correctly rendered anatomy",
            "Independent cervical and scapular control is not demonstrated by coupled relative motion",
            "This is the original MASI assembly, not a MASI/FHS fused model",
            "No dynamic loads, contacts, muscle recruitment, exercise poses or safety were validated",
        ],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    result = audit(args.model)
    out = pathlib.Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("MASI_FULLBODY_AUDIT", json.dumps({"counts": result["counts"], "checks": result["checks"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
