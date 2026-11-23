#!/usr/bin/env python3
"""Export REAL OpenSim 4.6 assembled AAH hand body frames for posed viewing.

Source: Sobinov et al. NCams/AAH MIT, Right/Left NoMuscles .osim.
Visual interpolation between export samples does NOT constitute OpenSim
dynamics, validated grip/contact, or muscle force simulation.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import opensim as osim

SAMPLES=13
FINGER_NAMES=(
 "cmc1_f_e","cmc1_opp","cmc1_ad_ab","mcp1_e_f","ip1_e_f",
 "mcp2_e_f","mcp2_ad_ab","pip2_e_f","dip2_e_f",
 "mcp3_e_f","mcp3_rd_ud","pip3_e_f","dip3_e_f",
 "mcp4_e_f","mcp4_ad_ab","pip4_e_f","dip4_e_f",
 "mcp5_e_f","mcp5_ad_ab","pip5_e_f","dip5_e_f",
)

def vec3(v):
    return [round(float(v[i]),9) for i in range(3)]
def mat3(R):
    return [[round(float(R.get(i,j)),9) for j in range(3)] for i in range(3)]
def body_transform(b,s):
    t=b.getTransformInGround(s)
    return {"p":vec3(t.p()),"R":mat3(t.R())}
def extract_visual_meshes(xml_path):
    root=ET.parse(xml_path).getroot()
    b=root.find("./Model/BodySet/objects")
    if b is None:raise ValueError("Missing OpenSim BodySet")
    meshes=[]
    for body in b.findall("Body"):
        name=body.get("name")
        for mesh in body.findall("./attached_geometry/Mesh"):
            f=(mesh.findtext("mesh_file") or "").strip()
            if not f:continue
            scale=[float(x) for x in (mesh.findtext("scale_factors") or "1 1 1").split()]
            parent=(mesh.findtext("socket_frame") or "..").strip()
            if parent!="..":raise ValueError(f"Unexpected AAH mesh socket {name}:{parent}")
            meshes.append({"body":name,"file":f,"scale":scale})
    return meshes

def bounded(coord,value):
    lower=float(coord.getRangeMin())
    upper=float(coord.getRangeMax())
    if lower>upper:raise AssertionError("Invalid OpenSim range "+coord.getName())
    return max(lower,min(upper,value))

def near_zero(coord):
    return bounded(coord,0.)

def target(coord,desired):
    # desired is a signed anatomical coordinate in radians. AAH authors'
    # flexion-extension convention is checked by original range and test QA.
    return bounded(coord,desired)

def finger_pose(side,kind):
    pref="ra" if side=="right" else "la"
    # Explicit experimental targets. NO claim of gripping an object.
    if kind=="straight":return {}
    if kind=="curl":
        deg={
            **{f"mcp{j}_e_f":62 for j in range(2,6)},
            **{f"pip{j}_e_f":82 for j in range(2,6)},
            **{f"dip{j}_e_f":54 for j in range(2,6)},
            "mcp1_e_f":25,"ip1_e_f":38,
            "cmc1_f_e":15,"cmc1_opp":20,"cmc1_ad_ab":10,
        }
    elif kind=="cylinder":
        deg={
            "mcp2_e_f":63,"pip2_e_f":69,"dip2_e_f":39,
            "mcp3_e_f":69,"pip3_e_f":76,"dip3_e_f":43,
            "mcp4_e_f":71,"pip4_e_f":78,"dip4_e_f":44,
            "mcp5_e_f":68,"pip5_e_f":71,"dip5_e_f":41,
            "mcp1_e_f":24,"ip1_e_f":25,
            "cmc1_f_e":18,"cmc1_opp":29,"cmc1_ad_ab":15,
        }
    else:raise ValueError(kind)
    return {f"{pref}_{k}":math.radians(v) for k,v in deg.items()}

def export_side(path,side):
    model=osim.Model(str(path))
    state=model.initSystem()
    model.assemble(state);model.realizePosition(state)
    bodyset=model.getBodySet()
    coords=model.getCoordinateSet()
    prefix="ra" if side=="right" else "la"
    mesh=extract_visual_meshes(path)
    body_names=sorted({v["body"] for v in mesh})
    missing=[b for b in body_names if not bodyset.contains(b)]
    if missing:raise ValueError("visual body absent "+repr(missing))
    # Independent thumb and all four long finger segments explicitly required
    required=[f"{prefix}_{name}" for name in FINGER_NAMES]
    for n in required:
        if not coords.contains(n):raise ValueError("missing finger DoF "+n)
    finger={n:coords.get(n) for n in required}
    ranges={n:{
       "minDeg":round(math.degrees(float(c.getRangeMin())),4),
       "maxDeg":round(math.degrees(float(c.getRangeMax())),4),
       "defaultDeg":round(math.degrees(float(c.getDefaultValue())),4)
    } for n,c in finger.items()}
    trajectories={}
    for kind in ("curl","cylinder"):
        steps=[]
        goal=finger_pose(side,kind)
        for i in range(SAMPLES):
            u=i/(SAMPLES-1)
            # smooth easing applied to OpenSim coordinate targets
            easing=u*u*(3-2*u)
            for n,c in finger.items():
                desired=target(c,goal[n]) if n in goal else near_zero(c)
                start=near_zero(c)
                c.setValue(state,start+(desired-start)*easing,False)
            model.assemble(state);model.realizePosition(state)
            positions={n:body_transform(bodyset.get(n),state) for n in body_names}
            angles={n:round(math.degrees(float(c.getValue(state))),5) for n,c in finger.items()}
            steps.append({"u":round(u,6),"frames":positions,"fingerDegrees":angles})
        trajectories[kind]=steps
    result={
      "schema":"AAH-hand-native-OpenSim-4.6-poses-v1",
      "sourceModel":model.getName(),"side":side,
      "sourceRepo":"https://github.com/nishbo/ms_arm_and_hand",
      "license":"MIT, original author attribution required",
      "engine":osim.GetVersionAndDate(),
      "modelStatus":"NoMuscles zero-mass inverse-kinematics model only",
      "displayMeshes":mesh,
      "bodyNames":body_names,
      "modelCounts":{
        "bodies":bodyset.getSize(),
        "joints":model.getJointSet().getSize(),
        "coordinateObjects":coords.getSize(),
        "muscles":model.getMuscles().getSize(),
        "displayedMeshes":len(mesh),
      },
      "fingerCoordinateRangesDeg":ranges,
      "trajectories":trajectories,
      "actualOpenSimAssemblyForEachSample":True,
      "sampleCount":SAMPLES,
      "warnings":[
        "Synthetically selected finger angle targets. Not measured hand-grip motion.",
        "OpenSim joint and dependent-coordinates assembly performed for each recorded sample; interpolation in browser is display only.",
        "No finger-to-object contact or collision optimization.",
        "No dynamic simulation, grip force, muscle forces, mass or inertia.",
        "No compatibility with FHS or MASI claimed, and no geometry fusion performed."
      ],
    }
    print("AAH_NATIVE_EXPORT",json.dumps({
       "side":side,
       "modelCounts":result["modelCounts"],
       "meshNames":[m["file"] for m in mesh],
       "ranges":ranges,
       "samplePreview":{
         label:{k:v for k,v in series[-1]["fingerDegrees"].items() if any(t in k for t in ("mcp2_e_f","pip2_e_f","dip2_e_f","cmc1_opp","mcp1_e_f"))}
         for label,series in trajectories.items()}
    },ensure_ascii=False))
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--right",type=Path,required=True)
    p.add_argument("--left",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    out={
        "schema":"AAH-bilateral-OpenSim-pose-export-v1",
        "source":"https://github.com/nishbo/ms_arm_and_hand",
        "license":"MIT",
        "right":export_side(a.right,"right"),
        "left":export_side(a.left,"left"),
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(out,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf8")
    print("AAH_COMPLETE",json.dumps({
        "bytes":a.out.stat().st_size,
        "sideMeshes":{s:len(out[s]["displayMeshes"]) for s in ("right","left")},
        "samples":out["right"]["sampleCount"]
    }))
if __name__=="__main__":main()
