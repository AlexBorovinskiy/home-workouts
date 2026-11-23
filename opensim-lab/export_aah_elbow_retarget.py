#!/usr/bin/env python3
"""AAH/OpenSim 4.6 source arm rig positions, elbow flexion only.

Exports per-body rigid poses for a right arm that is later retargeted, NOT
joint locations or a validated fit of the separate Écorché anatomy atlas.
"""
import argparse
import json
import math
from pathlib import Path

import opensim as osim

ARM_BODIES=("RA1H","RA2U","RA2R","RA3L","RA3S","RA3P","RA3Q","RA3C","RA3T","RA3O","RA3H",
            "RA4M1","RA4M2","RA4M3","RA4M4","RA4M5",
            "RA5P1","RA6D1",
            "RA5P2","RA6M2","RA7D2","RA5P3","RA6M3","RA7D3",
            "RA5P4","RA6M4","RA7D4","RA5P5","RA6M5","RA7D5")
DEGREES=(0,15,30,45,60,75,90,105,120)

def read_body(body,state):
    t=body.getTransformInGround(state)
    rot=t.R()
    return {"p":[round(float(t.p()[i]),9) for i in range(3)],
            "R":[[round(float(rot.get(i,j)),9) for j in range(3)] for i in range(3)]}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--model",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    model=osim.Model(str(args.model))
    state=model.initSystem()
    model.assemble(state)
    crd=model.getCoordinateSet().get("ra_el_e_f")
    bodies=model.getBodySet()
    if any(not bodies.contains(x) for x in ARM_BODIES):raise ValueError("AAH model missing anatomical body")
    lo=float(crd.getRangeMin())
    hi=float(crd.getRangeMax())
    print("SOURCE_ELBOW_DEG_RANGE",math.degrees(lo),math.degrees(hi))
    angles=tuple(x for x in DEGREES if math.radians(x)>=lo-1e-8 and math.radians(x)<=hi+1e-8)
    if len(angles)<4 or max(angles)<75:raise ValueError("Original coordinate angle range insufficient")
    data=[]
    for angle in angles:
        crd.setValue(state,math.radians(angle),False)
        model.assemble(state)
        model.realizePosition(state)
        actual=math.degrees(float(crd.getValue(state)))
        if abs(actual-angle)>1e-4:raise ValueError(f"Elbow cannot reach {angle}deg: {actual}")
        frames={name:read_body(bodies.get(name),state) for name in ARM_BODIES}
        data.append({"elbowFlexionDeg":angle,"frames":frames})
    from numpy.linalg import norm
    import numpy as np
    wristShift=float(norm(np.array(data[-1]["frames"]["RA3L"]["p"])-np.array(data[0]["frames"]["RA3L"]["p"])))
    if wristShift<.1:raise ValueError("Elbow not moving wrist in source OpenSim model")
    dataOut={
      "schema":"AAH-OpenSim46-elbow-source-poses-v1",
      "source":"https://github.com/nishbo/ms_arm_and_hand/blob/main/AAH%20Model/RightArmAndHand_NoMuscles.osim",
      "license":"MIT",
      "engine":osim.GetVersionAndDate(),
      "coordinate":"ra_el_e_f",
      "degrees":list(angles),
      "bodyNames":list(ARM_BODIES),
      "samples":data,
      "wristCenterMovementM":round(wristShift,7),
      "musclesSimulated":False,"contactSimulated":False,
      "warnings":["The original source rig is validated only within its AAH model coordinate frames.",
                  "No atlas-to-AAH retargeting is pre-validated.",
                  "Elbow/finger motions combined in browser are approximations; only the elbow samples and earlier finger samples were assembled by OpenSim.",
                  "This is a kinematic visualization, not force or exercise mechanics."]
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(dataOut,ensure_ascii=False,separators=(",",":"))+"\n")
    print("AAH_SOURCE_ELBOW_EXPORTED",json.dumps({"degrees":angles,"wristMovementM":wristShift,"bones":len(ARM_BODIES)}))

if __name__=="__main__":
    main()
