#!/usr/bin/env python3
"""Research compatibility test: independent source AAH upper-limb kinematics.

AAH has its own thorax, clavicle, scapula, humerus and hand. Test it in isolation
before attempting to retarget joints to the FHS spine. AAH does NOT contain
calibrated inertial data and may not be used to estimate exercise forces.
"""
import argparse, json, math
from pathlib import Path
import opensim as osim

def xyz(x):
    return [round(float(x[i]),7) for i in range(3)]

def pose(model,state):
    model.realizePosition(state)
    bodies=model.getBodySet()
    output={}
    for name in ("Thorax","RA_clavicle","RA_scapula","RA1H","RA4M1","RA5P1","RA6D1"):
        if not bodies.contains(name): continue
        trans=bodies.get(name).getTransformInGround(state)
        output[name]={"origin":xyz(trans.p()),
                      "rotation":[[round(float(trans.R().get(i,j)),7) for j in range(3)] for i in range(3)]}
    return output

def delta(before,after,key):
    a,b=before[key],after[key]
    t=math.dist(a["origin"],b["origin"])
    r=sum((a["rotation"][i][j]-b["rotation"][i][j])**2 for i in range(3) for j in range(3))**.5
    return {"translationMm":round(t*1000,3),"rotationMatrixDelta":round(r,7)}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--model",required=True);p.add_argument("--output",required=True);p.add_argument("--side",default="right")
    args=p.parse_args()
    model=osim.Model(args.model)
    model.setUseVisualizer(False)
    state=model.initSystem()
    model.assemble(state)
    baseline=pose(model,state)
    coords=model.getCoordinateSet()
    names=[coords.get(i).getName() for i in range(coords.getSize())]
    tested=[]
    for coord_name,adjust in (("ra_sh_elv",0.18),("ra_cmc1_opp",0.15)):
        if coord_name not in names:
            raise ValueError("Missing intended native AAH coordinate: "+coord_name)
        q=coords.get(coord_name)
        initial=float(q.getValue(state))
        target=initial+adjust
        if not (q.getRangeMin()<=target<=q.getRangeMax()):
            raise ValueError("Out of documented range: "+coord_name)
        q.setValue(state,target,False)
        model.assemble(state)
        updated=pose(model,state)
        tested.append({"changedCoordinate":coord_name,"deltaRad":adjust,
                       "scapula":delta(baseline,updated,"RA_scapula"),
                       "clavicle":delta(baseline,updated,"RA_clavicle"),
                       "humerus":delta(baseline,updated,"RA1H"),
                       "thumbProximal":delta(baseline,updated,"RA4M1"),
                       "thumbDistal":delta(baseline,updated,"RA6D1")})
        q.setValue(state,initial,False)
        model.assemble(state)
    shoulder=next(x for x in tested if x["changedCoordinate"]=="ra_sh_elv")
    thumb=next(x for x in tested if x["changedCoordinate"]=="ra_cmc1_opp")
    assert (shoulder["scapula"]["translationMm"]>.01 or
            shoulder["scapula"]["rotationMatrixDelta"]>1e-5), "Scapula did not move in shoulder test"
    assert (thumb["thumbProximal"]["translationMm"]>.01 or
            thumb["thumbProximal"]["rotationMatrixDelta"]>1e-5), "Thumb did not move in opposition test"
    report={"kind":"AAH-isolated-native-opensim-kinematic-compatibility",
            "model":args.side,"engine":osim.GetVersionAndDate(),
            "source":"https://github.com/nishbo/ms_arm_and_hand",
            "licence":"MIT with required attribution; see original LICENSE.txt",
            "coordinates":len(names),"movingScapulaVerified":True,"opposableThumbKinematicsVerified":True,
            "poseSamples":tested,"limitations":{
             "fhsSpineRetargeted":False,
             "independentScapularDOFs":False,
             "scapularMovement": "coupled to humeral/shoulder coordinates through OpenSim constraints",
             "inertialPropertiesIncluded":False,
             "muscleLoadSimulationVerified":False,
             "pushUpBiomechanicsValidated":False
            }}
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print("AAH_NATIVE_TEST "+json.dumps(report,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":main()
