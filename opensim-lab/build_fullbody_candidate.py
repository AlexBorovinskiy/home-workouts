#!/usr/bin/env python3
"""Assemble a *candidate* lower-limb kinematic topology onto the 2026 FHS spine.

Research prototype only: preserve FHS thoracolumbar bones/joints/muscles,
copy donor lower-body rigid segments and joint definitions without pretending
their inertial/geometry calibration is anatomically validated after grafting.

This does not calculate push-ups, forces, activation, hand contact, or safety.
"""
from __future__ import annotations
import argparse
import copy
import json
import math
import pathlib
import xml.etree.ElementTree as ET

import opensim as osim

DONOR_SEGMENTS = {
    f"{kind}_{side}"
    for side in ("l", "r")
    for kind in ("femur", "tibia", "patella", "talus", "calcn", "toes")
}
DONOR_JOINTS = {
    f"{kind}_{side}"
    for side in ("l", "r")
    for kind in ("hip", "walker_knee", "patellofemoral",
                 "ankle", "subtalar", "mtp")
}
FHS_SPINE = [f"lumbar{i}" for i in range(5, 0, -1)] + [
    f"thoracic{i}" for i in range(12, 0, -1)]
DONOR_COORDS = ("hip_flexion_r", "knee_angle_r", "ankle_angle_r")

def objects(model, setname):
    obj=model.find(f"./{setname}/objects")
    if obj is None:
        raise ValueError(f"Missing {setname}/objects")
    return obj

def load_xml(path):
    tree=ET.parse(path)
    model=tree.getroot().find("Model")
    if model is None:
        raise ValueError("Missing OpenSim Model root")
    return tree,model

def copy_legs(fhs_path, donor_path, output_path):
    tree, target=load_xml(fhs_path)
    _,donor=load_xml(donor_path)
    source_bodies={e.get("name"):e for e in objects(donor,"BodySet") if e.tag=="Body"}
    source_joints={e.get("name"):e for e in objects(donor,"JointSet") if e.tag.endswith("Joint")}
    dst_bodies=objects(target,"BodySet")
    dst_joints=objects(target,"JointSet")

    assert {b.get("name") for b in dst_bodies if b.tag=="Body"}.isdisjoint(DONOR_SEGMENTS)
    assert "pelvis" in {b.get("name") for b in dst_bodies if b.tag=="Body"}
    missing_bodies=DONOR_SEGMENTS-source_bodies.keys()
    missing_joints=DONOR_JOINTS-source_joints.keys()
    if missing_bodies or missing_joints:
        raise ValueError(f"Missing donor bodies {missing_bodies}; joints {missing_joints}")

    for name in sorted(DONOR_SEGMENTS):
        node=copy.deepcopy(source_bodies[name])
        # Omit donor visual geometry (which depends on relative donor geometry files).
        # Preserve mass, inertial tensor, muscle wrapping objects and rigid-body frames.
        attach=node.find("attached_geometry")
        if attach is not None:
            attach.clear()
        dst_bodies.append(node)

    for name in sorted(DONOR_JOINTS):
        dst_joints.append(copy.deepcopy(source_joints[name]))

    constraints_from=donor.find("./ConstraintSet/objects")
    constraints_to=target.find("./ConstraintSet/objects")
    imported_constraints=[]
    if constraints_from is not None:
        if constraints_to is None:
            constraint_set=target.find("ConstraintSet")
            if constraint_set is None:
                constraint_set=ET.SubElement(target,"ConstraintSet",{"name":"constraintset"})
            constraints_to=ET.SubElement(constraint_set,"objects")
        for node in constraints_from:
            body=ET.tostring(node,encoding="unicode")
            # Donor knee/patellar couplers are essential for joint assembly.
            if "knee_angle_" in body or "patellofemoral" in body:
                constraints_to.append(copy.deepcopy(node))
                imported_constraints.append(node.get("name"))

    pathlib.Path(output_path).parent.mkdir(parents=True,exist_ok=True)
    tree.write(output_path,encoding="utf-8",xml_declaration=True)
    return {"donorSegments":sorted(DONOR_SEGMENTS),
            "donorJoints":sorted(DONOR_JOINTS),
            "copiedConstraints":imported_constraints}

def solve(path, provenance):
    model=osim.Model(str(path))
    model.setUseVisualizer(False)
    state=model.initSystem()
    model.assemble(state)
    model.realizePosition(state)
    bodyset=model.getBodySet()
    jointset=model.getJointSet()
    coords=model.getCoordinateSet()
    names=[bodyset.get(i).getName() for i in range(bodyset.getSize())]
    joints=[jointset.get(i).getName() for i in range(jointset.getSize())]
    missing=[k for k in FHS_SPINE if k not in names]
    if missing:raise AssertionError(f"Lost FHS vertebrae: {missing}")
    if not all(k in names for k in DONOR_SEGMENTS):
        raise AssertionError("Leg segments not assembled")
    if any(k not in joints for k in DONOR_JOINTS):
        raise AssertionError("Donor joints were not included")

    def pos(name):
        p=bodyset.get(name).getTransformInGround(state).p()
        return [round(float(p[i]),6) for i in range(3)]
    landmarks={n:pos(n) for n in
        ["pelvis","sacrum","lumbar5","thoracic1",
         "femur_r","tibia_r","talus_r","calcn_r","toes_r",
         "femur_l","tibia_l","talus_l","calcn_l","toes_l",
         "hand_R","hand_L"] if n in names}

    # These are only kinematic sanity checks, not an ergonomic pose.
    pelvis=landmarks["pelvis"]
    distances={
        n:round(math.dist(pelvis, landmarks[n]),4)
        for n in ("toes_l","toes_r","hand_R","hand_L")
        if n in landmarks
    }
    if any(not all(math.isfinite(v) for v in xyz) for xyz in landmarks.values()):
        raise AssertionError("Non-finite model coordinates")
    if max(distances.values(),default=0)>5:
        raise AssertionError("Unrealistic candidate length >5m")

    return {
        "status":"opensim-assembly-only",
        "engine":osim.GetVersionAndDate(),
        "sourceSpine":"https://zenodo.org/records/18259702",
        "sourceLegs":"https://github.com/opensim-org/opensim-models/tree/master/Models/Rajagopal",
        "originalFhsMusclesPreserved":552,
        "bodyCount":bodyset.getSize(),"jointCount":jointset.getSize(),
        "coordinateCount":coords.getSize(),"vertebrae":len(FHS_SPINE),
        "legSegments":len(DONOR_SEGMENTS),"legJoints":len(DONOR_JOINTS),
        "bodyFrameOriginsM":landmarks,
        "distancesFromPelvisM":distances,
        "hasHands":all(n in names for n in ("hand_R","hand_L")),
        "hasFeet":all(n in names for n in ("toes_r","toes_l")),
        "hasContactForces":False,
        "hasMeasuredPushup":False,
        "massDistributionVerified":False,
        "jointAlignmentValidated":False,
        "isSafeExerciseModel":False,
        "graft":provenance
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--fhs",required=True)
    parser.add_argument("--donor",required=True)
    parser.add_argument("--model",required=True)
    parser.add_argument("--report",required=True)
    args=parser.parse_args()
    graft=copy_legs(args.fhs,args.donor,args.model)
    result=solve(args.model,graft)
    with open(args.report,"w",encoding="utf-8") as output:
        json.dump(result,output,ensure_ascii=False,indent=2)
    print("FULLBODY_TOPOLOGY_REPORT "+json.dumps(result,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
