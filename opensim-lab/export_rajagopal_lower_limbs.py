#!/usr/bin/env python3
"""Export original OpenSim 4.6 Rajagopal 2023 lower limbs for FHS visual assembly.

Source meshes and joint poses remain intact in a separate model. The
inter-model pelvis registration is a reversible VISUALIZATION INITIALIZATION,
not a fused musculoskeletal model or a validated anatomical hip fit.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import opensim as osim

LEG_BODIES=(
    "femur_r","tibia_r","patella_r","talus_r","calcn_r","toes_r",
    "femur_l","tibia_l","patella_l","talus_l","calcn_l","toes_l"
)
EXPECTED={
    "femur_r": ["r_femur.vtp"],
    "tibia_r": ["r_tibia.vtp","r_fibula.vtp"],
    "patella_r": ["r_patella.vtp"],
    "talus_r": ["r_talus.vtp"],
    "calcn_r": ["r_foot.vtp"],
    "toes_r": ["r_bofoot.vtp"],
    "femur_l": ["l_femur.vtp"],
    "tibia_l": ["l_tibia.vtp","l_fibula.vtp"],
    "patella_l": ["l_patella.vtp"],
    "talus_l": ["l_talus.vtp"],
    "calcn_l": ["l_foot.vtp"],
    "toes_l": ["l_bofoot.vtp"],
}
def vec3(v):
    return [float(v[i]) for i in range(3)]
def m3(v):
    return [[float(v.get(i,j)) for j in range(3)] for i in range(3)]
def frame(obj,state):
    t=obj.getTransformInGround(state)
    return {"positionM":vec3(t.p()),"rotation":m3(t.R())}
def extract_osim_meshes(path):
    root=ET.parse(path).getroot().find("Model")
    assert root is not None
    by_body={}
    for body in root.findall("./BodySet/objects/Body"):
        name=body.get("name")
        if name not in LEG_BODIES:continue
        found=[]
        for mesh in body.findall("./attached_geometry/Mesh"):
            file=(mesh.findtext("mesh_file") or "").strip()
            if not file:continue
            scale=[float(x) for x in (mesh.findtext("scale_factors") or "1 1 1").split()]
            socket=(mesh.findtext("socket_frame") or "").strip()
            if socket!="..":raise ValueError(f"Unexpected mesh socket: {name}:{socket}")
            if len(scale)!=3:raise ValueError("Non-XYZ scale")
            found.append({"file":file,"body":name,"scale":scale})
        if sorted(x["file"] for x in found)!=sorted(EXPECTED[name]):
            raise ValueError(f"Unexpected meshes {name}: {found}")
        by_body[name]=found
    if set(by_body)!=set(LEG_BODIES):raise ValueError("Missing lower limb body in XML")
    return by_body
def verify_FHS(fhs):
    if fhs.get("kind")!="fhs-opensim-body-frames-v1":raise ValueError("Wrong FHS frame export")
    p=fhs["bodyFrames"]["pelvis"]
    arr=fhs["anatomyMeshes"]["pelvis"]
    scale=arr[0]["scaleFactors"]
    if len(arr)!=2 or any(x["scaleFactors"]!=scale for x in arr):
        raise ValueError("FHS pelvis visual mesh scales disagree")
    if max(scale)-min(scale)>1e-7 or not (.5<scale[0]<1.2):
        raise ValueError("Unexpected FHS pelvis source scale")
    return float(scale[0]),p
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--rajagopal-osim",type=Path,required=True)
    ap.add_argument("--fhs-frames",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    a=ap.parse_args()
    fhs=json.loads(a.fhs_frames.read_text(encoding="utf-8"))
    s_factor,fhs_pelvis=verify_FHS(fhs)
    model=osim.Model(str(a.rajagopal_osim))
    state=model.initSystem()
    model.assemble(state)
    model.realizePosition(state)
    bodies=model.getBodySet()
    allframes={b:frame(bodies.get(b),state) for b in ["pelvis",*LEG_BODIES]}
    mesh=extract_osim_meshes(a.rajagopal_osim)
    jointset=model.getJointSet()
    found={}
    for name in ["hip_r","hip_l","knee_r","knee_l","ankle_r","ankle_l","subtalar_r","subtalar_l","mtp_r","mtp_l"]:
        if not jointset.contains(name):
            raise ValueError("Missing Rajagopal leg joint "+name)
        joint=jointset.get(name)
        found[name]={
          "parentFrameName":joint.getParentFrame().getName(),
          "childFrameName":joint.getChildFrame().getName(),
          "parentPoint":vec3(joint.getParentFrame().getTransformInGround(state).p()),
          "childPoint":vec3(joint.getChildFrame().getTransformInGround(state).p()),
        }
        if math.dist(found[name]["parentPoint"],found[name]["childPoint"])>.001:
            raise ValueError(f"Rajagopal joint {name} not assembled")
    coordinates={}
    coordset=model.getCoordinateSet()
    for i in range(coordset.getSize()):
        c=coordset.get(i)
        if c.getName().startswith(("hip_","knee_","ankle_","subtalar_","mtp_","pelvis_")):
            coordinates[c.getName()]=float(c.getValue(state))
    source={
      "model":"RajagopalLaiUhlrich2023",
      "osim":"https://github.com/opensim-org/opensim-models/blob/master/Models/Rajagopal/RajagopalLaiUhlrich2023.osim",
      "geometryBase":"https://raw.githubusercontent.com/opensim-org/opensim-models/master/Geometry/",
      "licenseCaveat":"Review the author repository's license terms before third-party redistribution; meshes are loaded directly from their source",
    }
    data={
      "schema":"rajagopal-lower-limbs-native-4.6-v1",
      "source":source,
      "engine":osim.GetVersionAndDate(),
      "sourcePose":"OpenSim assembled source model default coordinates",
      "sourcePelvisFrame":allframes["pelvis"],
      "bodyFrames":{n:allframes[n] for n in LEG_BODIES},
      "bodyMeshes":mesh,
      "jointWorldPoints":found,
      "sourceCoordinateValues":coordinates,
      "fhsTargetPelvisFrame":fhs_pelvis,
      "visualInitialization":{
        "method":"FHS pelvis BODY ORIGIN AND AXES matched to Rajagopal pelvis, trial uniform scale from FHS pelvis visual geometry",
        "uniformScale":s_factor,
        "sourceOfTrialScale":"FHS pelvic right and left visual mesh scale, not an independently measured cross-model landmark fit",
        "anatomicallyValidated":False,
        "hipCentersValidatedAgainstFhs":False,
        "footGroundContactValidated":False,
      },
      "geometryCounts":{
        "bodyCount":len(LEG_BODIES),
        "meshCount":sum(len(m) for m in mesh.values()),
        "perSide":{"r":sum(len(v) for k,v in mesh.items() if k.endswith("_r")),
                   "l":sum(len(v) for k,v in mesh.items() if k.endswith("_l"))},
      },
      "limitations":[
        "FHS contains no hip-joint calibration or independent leg data; pelvis registration is only a pose and scale starting point",
        "Rajagopal forefoot/toes are one aggregate toe body per side, not individually articulated toe phalanges",
        "No thigh-muscle compatibility, joint dynamics, or collision validation after combining with FHS/MASI/AAH",
        "The user can switch off the Rajagopal lower limbs without changing FHS or AAH source models",
      ],
    }
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("RAJAGOPAL_LEGS_NATIVE_EXPORT",json.dumps({
        "meshCounts":data["geometryCounts"],"pelvis":allframes["pelvis"],
        "sourceHeel":{s:allframes[f"calcn_{s}"]["positionM"] for s in ("r","l")},
        "sourceToes":{s:allframes[f"toes_{s}"]["positionM"] for s in ("r","l")},
        "hipCenters":{k:v["parentPoint"] for k,v in found.items() if k.startswith("hip_")},
        "scale":s_factor
    },ensure_ascii=False))
if __name__=="__main__":
    main()
