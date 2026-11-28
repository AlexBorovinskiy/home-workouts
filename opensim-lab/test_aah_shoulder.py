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

def pose(model,state,prefix):
    model.realizePosition(state)
    bodies=model.getBodySet()
    output={}
    for name in ("Thorax", *(prefix+suffix for suffix in ("_clavicle","_scapula","1H","4M1","5P1","6D1"))):
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
    p.add_argument("--model",required=True);p.add_argument("--output",required=True);p.add_argument("--side",choices=("right","left"),default="right")
    args=p.parse_args()
    prefix="RA" if args.side=="right" else "LA"
    shoulder_coordinate=prefix.lower()+"_sh_elv"
    thumb_coordinate=prefix.lower()+"_cmc1_opp"
    model=osim.Model(args.model)
    model.setUseVisualizer(False)
    state=model.initSystem()
    model.assemble(state)
    baseline=pose(model,state,prefix)
    coords=model.getCoordinateSet()
    names=[coords.get(i).getName() for i in range(coords.getSize())]
    tested=[]
    for coord_name,adjust in ((shoulder_coordinate,0.18),(thumb_coordinate,0.15)):
        if coord_name not in names:
            raise ValueError("Missing intended native AAH coordinate: "+coord_name)
        q=coords.get(coord_name)
        initial=float(q.getValue(state))
        target=initial+adjust
        if not (q.getRangeMin()<=target<=q.getRangeMax()):
            raise ValueError("Out of documented range: "+coord_name)
        q.setValue(state,target,False)
        model.assemble(state)
        updated=pose(model,state,prefix)
        tested.append({"changedCoordinate":coord_name,"deltaRad":adjust,
                       "scapula":delta(baseline,updated,prefix+"_scapula"),
                       "clavicle":delta(baseline,updated,prefix+"_clavicle"),
                       "humerus":delta(baseline,updated,prefix+"1H"),
                       "thumbProximal":delta(baseline,updated,prefix+"4M1"),
                       "thumbDistal":delta(baseline,updated,prefix+"6D1")})
        q.setValue(state,initial,False)
        model.assemble(state)
    shoulder,thumb=tested
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
