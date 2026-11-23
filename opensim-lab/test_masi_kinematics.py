#!/usr/bin/env python3
"""Native OpenSim 4.6 kinematics audit of authors' MASI, NOT exercise simulation.

Loads name-only migrated MASI. Tests whether cervical bones move in a coupled
but non-rigid arrangement and scapula moves relative to thorax. Distances and
matrix deltas are diagnostic, not clinically validated angles/forces.
"""
from __future__ import annotations
import argparse
import json
import math
import pathlib
import opensim as osim

BODIES=("torso","cerv7","cerv6","cerv5","cerv4","cerv3","cerv2","cerv1","skull","rscapula","rclavicle","humerus_r")
TRIALS=("pitch1","pitch2","roll1","roll2","yaw1","yaw2","rollRSCA","pitchRSCA","yawRSCA","arm_flex_r")

def frame_values(body,state):
    t=body.getTransformInGround(state)
    return {"xyz":[float(t.p()[i]) for i in range(3)],
            "rot":[[float(t.R().get(i,j)) for j in range(3)] for i in range(3)]}

def transpose(m):return [[m[j][i] for j in range(3)] for i in range(3)]
def mmul(a,b):return [[sum(a[i][k]*b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
def relative_rot(a,b):return mmul(transpose(a["rot"]),b["rot"])
def relative_world_distance(a,b):
    return math.dist(a["xyz"],b["xyz"])*1000
def matrix_diff(a,b):return math.sqrt(sum((a[i][j]-b[i][j])**2 for i in range(3) for j in range(3)))

def grab(model,state):
    bset=model.getBodySet()
    return {n:frame_values(bset.get(n),state) for n in BODIES if bset.contains(n)}

def diff_relative(before,after,reference,moving):
    b0,a0=before[reference],before[moving]
    b1,a1=after[reference],after[moving]
    r0,r1=relative_rot(b0,a0),relative_rot(b1,a1)
    d0=[a0["xyz"][i]-b0["xyz"][i] for i in range(3)]
    d1=[a1["xyz"][i]-b1["xyz"][i] for i in range(3)]
    return {"changeRelativeOriginMm":round(math.dist(d0,d1)*1000,4),
            "changeRelativeOrientationMatrixNorm":round(matrix_diff(r0,r1),6)}

def run(filename):
    model=osim.Model(str(filename))
    state=model.initSystem()
    model.assemble(state)
    model.realizePosition(state)
    baseline=grab(model,state)
    if any(n not in baseline for n in BODIES):
        raise AssertionError("Missing MASI body "+str(set(BODIES)-set(baseline)))
    coords=model.getCoordinateSet()
    named={coords.get(i).getName() for i in range(coords.getSize())}
    tests=[]
    for name in TRIALS:
        if name not in named:continue
        state=model.initSystem()
        model.assemble(state)
        q=coords.get(name)
        original=float(q.getValue(state))
        lo,hi=float(q.getRangeMin()),float(q.getRangeMax())
        step=.06 if (original+.06)<=hi else -.06
        if not (lo<=original+step<=hi):continue
        try:
            q.setValue(state,original+step,False)
            model.assemble(state)
            model.realizePosition(state)
            after=grab(model,state)
            tests.append({"coordinate":name,"stepRad":step,
                "neckC1VsC7":diff_relative(baseline,after,"cerv7","cerv1"),
                "neckC1VsTorso":diff_relative(baseline,after,"torso","cerv1"),
                "skullVsC1":diff_relative(baseline,after,"cerv1","skull"),
                "scapulaVsTorso":diff_relative(baseline,after,"torso","rscapula"),
                "humerusVsScapula":diff_relative(baseline,after,"rscapula","humerus_r")})
        except Exception as ex:
            tests.append({"coordinate":name,"error":str(ex)})
    neck_independent=any(x.get("neckC1VsC7",{}).get("changeRelativeOrientationMatrixNorm",0)>1e-4 for x in tests)
    scapula_independent=any(x.get("scapulaVsTorso",{}).get("changeRelativeOrientationMatrixNorm",0)>1e-4 for x in tests)
    return {
        "kind":"native-MASI-OpenSim-4.6-kinematic-test",
        "engine":osim.GetVersionAndDate(),
        "source":"https://doi.org/10.6084/m9.figshare.4249808.v2",
        "cervicalBodyPositionsM":{n:baseline[n]["xyz"] for n in BODIES if n.startswith("cerv")},
        "sourcePoseFrames":baseline,"individualTests":tests,
        "hasNonrigidCervicalKinematics":neck_independent,
        "hasScapulothoracicMotion":scapula_independent,
        "limitations":{
            "independentCervicalControlVerified":False,
            "independentScapulaControlVerified":False,
            "isOriginalAnatomyInBrowser":False,
            "accuratePushupJointAngles":False,
            "collisionForcesVerified":False,
            "fhsSpineReplaced":False,
            "poseChanges": "Test-only small selected generalized-coordinate offsets; not biomechanical exercise recordings"},
    }

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--model",required=True)
    parser.add_argument("--output",required=True)
    a=parser.parse_args()
    report=run(a.model)
    pathlib.Path(a.output).parent.mkdir(parents=True,exist_ok=True)
    pathlib.Path(a.output).write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print("MASI_KINEMATICS_AUDIT "+json.dumps(report,ensure_ascii=False,separators=(",",":")))
