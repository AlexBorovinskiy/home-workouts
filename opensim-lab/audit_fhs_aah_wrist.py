#!/usr/bin/env python3
"""Quantify compatibility of FHS skeleton + NCams/AAH articulated hand.

This audit is deliberately distinct from a validated musculoskeletal graft.
Uses FHS hand_R/L as a rigid base and AAH lunate as the moving hand anchor.
Only source/pose-matched homologous carpal mesh geometry can justify an initial
registration. Never alter anatomical bone shapes or scale to 'look right'.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET
import numpy as np

HOMOLOGOUS=["lunate","scaphoid","capitate","trapezium","2mc","2proxph","2distph"]
def load_vertices(raw):
    root=ET.fromstring(raw)
    el=root.find("./PolyData/Piece/Points/DataArray")
    if el is None or el.get("format","ascii").lower()!="ascii":
        raise ValueError("Expected ASCII VTP")
    arr=np.fromstring(el.text or "",sep=" ",dtype=np.float64)
    if not len(arr) or len(arr)%3:raise ValueError("Malformed VTP points")
    return arr.reshape((-1,3))
def world_from_local(verts,frame,scale):
    R=np.stack(frame["basisColumns"],axis=1)
    return (verts*np.asarray(scale))@R.T+np.asarray(frame["origin"])
def world_aah(verts,frame,scale):
    return (verts*np.asarray(scale))@np.asarray(frame["R"]).T+np.asarray(frame["p"])
def aah_registration(fhs_hand,neutral_lunate,scale):
    Ra=np.asarray(neutral_lunate["R"],dtype=float)
    Rf=np.stack(fhs_hand["basisColumns"],axis=1)
    R=Rf@Ra.T
    t=np.asarray(fhs_hand["origin"])-scale*(R@np.asarray(neutral_lunate["p"]))
    return R,t
def transform(points,R,t,scale):
    return scale*points@R.T+t
def bounds(points):
    size=(np.max(points,axis=0)-np.min(points,axis=0))*1000
    return np.round(size,5).tolist()
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--fhs-zip",type=Path,required=True)
    ap.add_argument("--fhs-frames",type=Path,required=True)
    ap.add_argument("--aah-poses",type=Path,required=True)
    ap.add_argument("--aah-geometry",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    fhs=json.loads(args.fhs_frames.read_text())
    aah=json.loads(args.aah_poses.read_text())
    source=fhs["archiveRelativeOsimPath"]
    pfx=source[:source.rfind("/Male/")]+"/Geometry/"
    sides={}
    with zipfile.ZipFile(args.fhs_zip) as z:
        for side in ("right","left"):
            r=side=="right";S="R" if r else "L";P="RA" if r else "LA";suffix="" if r else "_l"
            frame=fhs["bodyFrames"]["hand_"+S]
            hand_mesh={Path(x["file"]).name:x for x in fhs["anatomyMeshes"]["hand_"+S]}
            pose=aah[side]["trajectories"]["curl"][0]["frames"]
            m={Path(x["file"]).name:x for x in aah[side]["displayMeshes"]}
            anchor=pose[P+"3L"]
            ratios=[]
            for file in (["lunate"+suffix+".vtp","scaphoid"+suffix+".vtp","capitate"+suffix+".vtp"]):
                if file not in hand_mesh:raise ValueError("No FHS homologous bone "+file)
                ratios.append(hand_mesh[file]["scaleFactors"])
            scale=float(np.median(np.asarray(ratios)))
            R,t=aah_registration(frame,anchor,scale)
            meshes={}
            for bone in HOMOLOGOUS:
                name=bone+suffix+".vtp"
                if name not in hand_mesh or name not in m:raise ValueError("Missing homologous source "+name)
                fv=load_vertices(z.read(pfx+name))
                av=load_vertices((args.aah_geometry/name).read_bytes())
                is_same=fv.shape==av.shape
                max_raw=float(np.max(np.linalg.norm(fv-av,axis=1))*1000) if is_same else None
                mesh_aah=m[name]
                aframe=pose[mesh_aah["body"]]
                a_world=world_aah(av,aframe,mesh_aah["scale"])
                mapped=transform(a_world,R,t,scale)
                f_world=world_from_local(fv,frame,hand_mesh[name]["scaleFactors"])
                if is_same:
                    delta=np.linalg.norm(mapped-f_world,axis=1)*1000
                    rms=float(np.sqrt(np.mean(delta*delta)))
                    mx=float(np.max(delta))
                else:rms=mx=None
                meshes[name]={
                    "sourceVertices":len(av),
                    "homologousSequenceSame":bool(is_same and max_raw<.005),
                    "maximumRawVertexDifferenceMm":None if max_raw is None else round(max_raw,6),
                    "poseRegisteredRmsMm":None if rms is None else round(rms,5),
                    "poseRegisteredMaxMm":None if mx is None else round(mx,5),
                    "fhsMeshScale":hand_mesh[name]["scaleFactors"],
                    "aahMeshScale":mesh_aah["scale"],
                    "aahBody":mesh_aah["body"],
                    "aahSourceBoundsMm":bounds(av),
                    "fhsSourceBoundsMm":bounds(fv),
                }
            sides[side]={
                "wristAnchor":"lunate and FHS hand body frame, not measured joint point",
                "globalScale":scale,
                "registrationRotation":np.round(R,9).tolist(),
                "registrationTranslationM":np.round(t,9).tolist(),
                "anchorMismatchMm":round(float(np.linalg.norm(transform(np.asarray(anchor["p"])[None,:],R,t,scale)[0]-np.asarray(frame["origin"]))*1000),8),
                "sourceMeshComparisons":meshes,
                "allHomologousRawMeshesIdentical":all(v["homologousSequenceSame"] for v in meshes.values()),
                "rmsHomologousFhsVsAahAfterRegistrationMm":round(math.sqrt(sum(v["poseRegisteredRmsMm"]**2 for v in meshes.values() if v["poseRegisteredRmsMm"] is not None)/len(meshes)),5),
                "anatomicalJointFitValidated":False,
            }
    result={
      "schema":"FHS-AAH-wrist-homology-audit-v1",
      "sourceFHS":"https://zenodo.org/records/18259702",
      "sourceAAH":"https://github.com/nishbo/ms_arm_and_hand",
      "sides":sides,
      "warnings":[
        "A homologous lunate mesh/pose provides a registration initialization only; the wrist joint axes are not independently validated",
        "AAH mesh and FHS mesh local positions may use different definitions, compare multiple bones before any graft",
        "Relative bone orientations and wrist dynamics in animated poses are not yet validated",
        "No altered FHS .osim or AAH .osim and no exercise mechanics validated"
      ]
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    for side,v in sides.items():
        print("FHS_AAH_WRIST_HOMOLOGY",json.dumps({"side":side,"scale":v["globalScale"],
          "sameMeshes":v["allHomologousRawMeshesIdentical"],
          "rmsMm":v["rmsHomologousFhsVsAahAfterRegistrationMm"],
          "meshes":{k:{x:d[x] for x in ("homologousSequenceSame","maximumRawVertexDifferenceMm","poseRegisteredRmsMm")} for k,d in v["sourceMeshComparisons"].items()}},ensure_ascii=False))
if __name__=="__main__":main()
