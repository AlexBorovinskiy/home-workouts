#!/usr/bin/env python3
"""Unvalidated *contact scaffolding* for FHS + Rajagopal full-body candidate.

Four sphere/ground pairs: palms and forefoot. Not a push-up pose, and not
an estimate of real pressures or appropriate injury risk. Contact locations,
radii, friction and stiffness are placeholder engineering parameters.
"""
import argparse
import json
import math
import pathlib

import opensim as osim

CONTACT_BODIES = {
    "right_palm": ("hand_R", 0.027),
    "left_palm": ("hand_L", 0.027),
    "right_forefoot": ("toes_r", 0.027),
    "left_forefoot": ("toes_l", 0.027),
}
def position(body,state):
    p=body.getTransformInGround(state).p()
    return [float(p[i]) for i in range(3)]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",required=True)
    ap.add_argument("--output",required=True)
    ap.add_argument("--report",required=True)
    args=ap.parse_args()

    model=osim.Model(args.source)
    model.setUseVisualizer(False)
    state=model.initSystem()
    model.realizePosition(state)
    bodies=model.getBodySet()
    initial={name:position(bodies.get(body),state)
             for name,(body,_) in CONTACT_BODIES.items()}
    # Upright floor near forefoot. This is not the ground plane of a push-up.
    floor_height=min(initial[n][1]-CONTACT_BODIES[n][1]
                     for n in ("right_forefoot","left_forefoot"))
    floor=osim.ContactHalfSpace(
        osim.Vec3(0,float(floor_height),0),
        osim.Vec3(0,0,-math.pi/2),
        model.getGround(),"research_floor")
    model.addContactGeometry(floor)

    named=[]
    for label,(body_name,radius) in CONTACT_BODIES.items():
        # DO NOT claim a sphere centred at the local body origin is the
        # measured palm/forefoot contact patch.
        sphere=osim.ContactSphere(
            radius,osim.Vec3(0,0,0),bodies.get(body_name),
            "candidate_sphere_"+label)
        model.addContactGeometry(sphere)
        force=osim.SmoothSphereHalfSpaceForce("candidate_contact_"+label,sphere,floor)
        # Explicit research-only provisional parameters; not calibrated.
        force.set_stiffness(1000000)
        force.set_dissipation(0.5)
        force.set_static_friction(0.7)
        force.set_dynamic_friction(0.5)
        force.set_viscous_friction(0.1)
        force.set_transition_velocity(0.2)
        model.addForce(force)
        named.append({"name":label,"body":body_name,"radiusM":radius,
                      "initialBodyOriginM":[round(x,6) for x in initial[label]]})

    # Reinitialize OpenSim after adding Geometry + Force objects.
    state=model.initSystem()
    model.assemble(state)
    model.realizeDynamics(state)
    pathlib.Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    model.printToXML(args.output)

    recorded=[]
    fs=model.getForceSet()
    for i in range(fs.getSize()):
        f=fs.get(i)
        if f.getName().startswith("candidate_contact_"):
            vals=f.getRecordValues(state)
            recorded.append({"name":f.getName(),"outputs":
                             [round(float(vals.get(k)),4) for k in range(vals.getSize())]})

    summary={
        "kind":"openSim-contact-scaffold-not-pushup",
        "engine":osim.GetVersionAndDate(),
        "hasFootBodies":True,
        "hasPalmBodies":True,
        "floorHeightM":round(floor_height,6),
        "contactGeometryCount":model.getContactGeometrySet().getSize(),
        "contactForceCount":len(recorded),
        "contacts":named,
        "contactRecords":recorded,
        "groundForcesNotCalibrated":True,
        "handAndToeContactPointsVerified":False,
        "plankPoseSolved":False,
        "movementMeasured":False,
        "loadAssessmentValidated":False,
        "purpose":"Validate four OpenSim-compliant sphere/half-space force connections, not estimate physiologic load"
    }
    assert summary["contactForceCount"]==4
    assert summary["contactGeometryCount"]>=5
    with open(args.report,"w",encoding="utf-8") as out:
        json.dump(summary,out,ensure_ascii=False,indent=2)
    print("FULLBODY_CONTACT_REPORT "+json.dumps(summary,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
