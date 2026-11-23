#!/usr/bin/env python3
"""Compare homologous cervical geometry across MASI (Neck6D VTP) and FHS source ZIP.

This compares SOURCE MESHES before pose differences. It does NOT infer
anatomical validity, surface correspondence, cervical joint axes or injury risk.
A temporary uniformly scaled MASI head/neck is evaluated in the C7–T1
registered position, but is never written into an OpenSim model.
"""
from __future__ import annotations
import argparse
import json
import math
import pathlib
import xml.etree.ElementTree as ET
import zipfile

CERVICAL = {f"cerv{i}": f"cerv{i}.vtp" for i in range(1, 7)}
CERVICAL.update({"cerv7":"rotatedcerv7.vtp","skull":"skull.vtp"})
def points(xml_bytes: bytes) -> list[list[float]]:
    root=ET.fromstring(xml_bytes)
    block=root.find("./PolyData/Piece/Points/DataArray")
    if block is None or block.get("format","ascii").lower()!="ascii":
        raise ValueError("Source must contain ASCII VTP points")
    raw=[float(x) for x in (block.text or "").split()]
    if len(raw)==0 or len(raw)%3:
        raise ValueError("Empty/malformed source vertices")
    return [raw[i:i+3] for i in range(0,len(raw),3)]
def body_scale(model_path):
    model=ET.parse(model_path).getroot().find("Model")
    body=next((b for b in model.findall("./BodySet/objects/Body") if b.get("name")=="head_neck"),None)
    if body is None: raise ValueError("FHS head_neck body missing")
    result={}
    for m in body.findall(".//Mesh"):
        file_name=m.findtext("mesh_file")
        if file_name:
            result[file_name.strip()] = [float(x) for x in (m.findtext("scale_factors") or "1 1 1").split()]
    return result
def bounds(points):
    return {
        "minM":[min(v[i] for v in points) for i in range(3)],
        "maxM":[max(v[i] for v in points) for i in range(3)],
        "sizeMm":[round((max(v[i] for v in points)-min(v[i] for v in points))*1000,4) for i in range(3)]
    }
def matvec(R,p):
    return [sum(R[i][k]*p[k] for k in range(3)) for i in range(3)]
def add(p,q):
    return [a+b for a,b in zip(p,q)]
def sub(p,q):
    return [a-b for a,b in zip(p,q)]
def mul(p,factor):
    return [a*factor for a in p]
def dmm(p,q):
    return math.dist(p,q)*1000
def evaluate_geometry(vtp,registration,fhs_t1_world,scale):
    frame=registration["masiC7Frame"]
    pivot=registration["jointConnections"]["masi"]["parentOriginM"]
    c7_original=[add(matvec(frame["rotation"],p),frame["positionM"]) for p in vtp]
    c7_scaled=[add(pivot,mul(sub(v,pivot),scale)) for v in c7_original]
    minimum=min(dmm(a,b) for a in c7_scaled for b in fhs_t1_world)
    c7_bounds=bounds(c7_scaled)
    t1_bounds=bounds(fhs_t1_world)
    return {
        "trialNeckUniformScale":round(scale,7),
        "C7WorldBounds":c7_bounds,
        "T1WorldBounds":t1_bounds,
        "C7T1NearestVertexMm":round(minimum,4),
        "verticalBBoxGapMm":round(max(0,c7_bounds["minM"][1]-t1_bounds["maxM"][1])*1000,4),
        "verticalBBoxOverlapMm":round(max(0,min(c7_bounds["maxM"][1],t1_bounds["maxM"][1])-max(c7_bounds["minM"][1],t1_bounds["minM"][1]))*1000,4),
    }
def run(archive,model,masi_dir,registration):
    j=json.loads(pathlib.Path(registration).read_text())
    if j["schema"]!="masi-fhs-C7-T1-registration-diagnostic-v1":
        raise ValueError("Wrong registration version")
    fscale=body_scale(model)
    output=[]
    with zipfile.ZipFile(archive) as z:
        files={item.split("/")[-1]:item for item in z.namelist() if "/Geometry/" in item}
        for id,filename in CERVICAL.items():
            if filename not in files or filename not in fscale:raise ValueError("Missing cervical mesh "+filename)
            f=points(z.read(files[filename]))
            m=points((pathlib.Path(masi_dir)/filename).read_bytes())
            same_order=len(f)==len(m)
            # Correct source-level point positions are compared BEFORE the FHS scale,
            # not using the FHS head_neck body transforms (which overlap vertebrae).
            max_dev = max((dmm(a,b) for a,b in zip(f,m)),default=math.inf) if same_order else math.inf
            same_geometry=same_order and max_dev<.005
            scale=fscale[filename]
            output.append({
                "segment":id,"sourceMeshFile":filename,
                "masiVertices":len(m),"fhsVertices":len(f),
                "sameRawVertexSequenceWithin5Microns":same_geometry,
                "maxRawVertexDeviationMm":round(max_dev,5) if math.isfinite(max_dev) else None,
                "fhsSourceScaleXYZ":scale,"masiSourceScaleXYZ":[1,1,1],
                "masiRawVertexBoundsMm":bounds(m)["sizeMm"],
                "fhsScaledRawVertexBoundsMm":bounds([[a*scale[k] for k,a in enumerate(p)] for p in f])["sizeMm"],
                "limitation":"FHS cervical geometry is attached to one rigid head_neck body; its apparent original C1-C7 arrangement is invalid"
            })
        t1file=j["fhsT1Mesh"]["file"]
        fhsT1=points(z.read(files[t1file]))
    t1=j["fhsVertebralFrames"]["thoracic1"]
    t1world=[add(matvec(t1["registeredRotation"],[p[i]*j["fhsT1Mesh"]["scale"][i] for i in range(3)]),t1["registeredPositionM"]) for p in fhsT1]
    c7=points((pathlib.Path(masi_dir)/CERVICAL["cerv7"]).read_bytes())
    common=[row["fhsSourceScaleXYZ"] for row in output]
    all_uniform=all(max(s)-min(s)<1e-7 for s in common)
    uniform=common[0][0] if all_uniform and all(abs(s[0]-common[0][0])<1e-7 for s in common) else None
    trials=[1.0]+([uniform] if uniform is not None and abs(uniform-1)>1e-7 else [])
    trials=trials+[.95,.92] if not any(abs(s-.95)<1e-9 for s in trials) else trials
    return {
        "schema":"MASI-FHS-cervical-source-scale-audit-v1",
        "origin":"FHS scientific source ZIP + MASI Neck6D geometry + native OpenSim joint registration",
        "sourceCervicalComparison":output,
        "allHomologousMeshesShareUniformFhsScale":uniform is not None,
        "observedFhsCervicalScale":uniform,
        "homologousSourceGeometryIdentical":all(x["sameRawVertexSequenceWithin5Microns"] for x in output),
        "trialRigidJointAnchoredUniformScales":[evaluate_geometry(c7,j,t1world,s) for s in trials],
        "recommendedAction":"No permanent scale correction: this is a source mesh audit and a visualization-only uniform-scaling experiment, not an anatomically calibrated hybrid.",
        "anatomicalLandmarksExplicitlySegmented":False,
        "articularFacetsValidated":False,
        "muscleAttachmentAndKinematicsRevalidatedAfterScaling":False,
        "warning":"Model scale differences do not imply every adjacent vertebral pair has matching shape. Scaling around C7-T1 does not update native OpenSim joint frames/inertia/forces."
    }
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for key in ["fhs-archive","fhs-model","masi-geometry-dir","registration","output"]:
        p.add_argument("--"+key,required=True)
    a=p.parse_args()
    d=run(a.fhs_archive,a.fhs_model,a.masi_geometry_dir,a.registration)
    target=pathlib.Path(a.output);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(d,ensure_ascii=False,indent=2))
    print("CERVICAL_HOMOLOGOUS_SCALE_AUDIT",json.dumps({
        "identicalMeshes":d["homologousSourceGeometryIdentical"],
        "fhsScale":d["observedFhsCervicalScale"],
        "rows":[{"segment":r["segment"],"meshDiffMm":r["maxRawVertexDeviationMm"],"same":r["sameRawVertexSequenceWithin5Microns"]} for r in d["sourceCervicalComparison"]],
        "trials":[{"scale":t["trialNeckUniformScale"],"closestMm":t["C7T1NearestVertexMm"],"verticalOverlapMm":t["verticalBBoxOverlapMm"]} for t in d["trialRigidJointAnchoredUniformScales"]]
    },ensure_ascii=False))
