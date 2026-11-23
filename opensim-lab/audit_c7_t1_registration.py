#!/usr/bin/env python3
"""Quantitative C7–T1 registration *candidate* between original MASI and FHS.

Two distinct models are never fused here. A rigid transform maps the FHS
head-neck/T1 junction to MASI C7/spine junction, using the MASI spine and FHS
T1 body axes for orientation. This is a diagnostic initialization only:
body-frame axes are not verified anatomical landmarks, and exact joint-point
overlap alone does not prove physiological compatibility or muscle continuity.
"""
from __future__ import annotations
import argparse
import json
import math
import pathlib
import xml.etree.ElementTree as ET
import zipfile

import opensim as osim

FHS_SPINE = [f"thoracic{i}" for i in range(1,13)] + [f"lumbar{i}" for i in range(1,6)]

def xyz(v):
    return [float(v[i]) for i in range(3)]

def mat(rot):
    return [[float(rot.get(i,j)) for j in range(3)] for i in range(3)]

def mv(A,v):
    return [sum(A[i][j]*v[j] for j in range(3)) for i in range(3)]

def mm(A,B):
    return [[sum(A[i][k]*B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]

def tr(A):
    return [list(a) for a in zip(*A)]

def plus(a,b):
    return [x+y for x,y in zip(a,b)]

def minus(a,b):
    return [x-y for x,y in zip(a,b)]

def dmm(a,b):
    return math.dist(a,b)*1000.

def record(t):
    return {"positionM":xyz(t.p()),"rotation":mat(t.R())}

def base(frame):
    return frame.findBaseFrame().getName()

def links(model,state):
    result=[]
    joints=model.getJointSet()
    for i in range(joints.getSize()):
        j=joints.get(i)
        result.append({
            "name":j.getName(),
            "parent":base(j.getParentFrame()),
            "child":base(j.getChildFrame()),
            "parentOriginM":xyz(j.getParentFrame().getTransformInGround(state).p()),
            "childOriginM":xyz(j.getChildFrame().getTransformInGround(state).p()),
        })
    return result

def read_mesh_vtp(data):
    root=ET.fromstring(data)
    block=root.find("./PolyData/Piece/Points/DataArray")
    if block is None or block.get("format","ascii").lower()!="ascii":
        raise ValueError("FHS or MASI source geometry must be ASCII VTP")
    vals=list(map(float,(block.text or "").split()))
    if len(vals)%3 or not vals:
        raise ValueError("Invalid VTP vertices")
    return [vals[i:i+3] for i in range(0,len(vals),3)]

def mesh_descriptor(model_path,body_name):
    root=ET.parse(model_path).getroot().find("Model")
    body=next((b for b in root.findall("./BodySet/objects/Body") if b.get("name")==body_name),None)
    if body is None: raise ValueError("Body absent from source XML: "+body_name)
    found=[]
    for mesh in body.findall(".//Mesh"):
        name=(mesh.findtext("mesh_file") or "").strip()
        scale=[float(x) for x in (mesh.findtext("scale_factors") or "1 1 1").split()]
        socket=(mesh.findtext("socket_frame") or "..").strip()
        if name:found.append({"file":name,"scale":scale,"socket":socket})
    if len(found)!=1 or found[0]["socket"]!="..":
        raise ValueError("Unexpected FHS mesh attachment "+body_name+": "+repr(found))
    return found[0]

def bbox(vertices):
    return {"minM":[min(p[i] for p in vertices) for i in range(3)],
            "maxM":[max(p[i] for p in vertices) for i in range(3)]}

def audit(masi_path,fhs_path,archive_path,masi_c7_vtp):
    masi=osim.Model(str(masi_path)); ms=masi.initSystem(); masi.assemble(ms); masi.realizePosition(ms)
    fhs=osim.Model(str(fhs_path)); fs=fhs.initSystem();fhs.assemble(fs);fhs.realizePosition(fs)
    ml=links(masi,ms); fl=links(fhs,fs)
    mj=[v for v in ml if v["name"]=="auxt1jnt" and {v["parent"],v["child"]}=={"spine","cerv7"}]
    fj=[v for v in fl if {v["parent"],v["child"]}=={"thoracic1","head_neck"}]
    if len(mj)!=1 or len(fj)!=1:
        raise ValueError(f"Missing unambiguous neck–thorax joint: MASI={mj}; FHS candidates={[v for v in fl if 'thoracic1' in (v['parent'],v['child'])]}")
    mj=mj[0];fj=fj[0]
    if dmm(mj["parentOriginM"],mj["childOriginM"])>0.01 or dmm(fj["parentOriginM"],fj["childOriginM"])>0.01:
        raise ValueError("Unassembled neck-thoracic joint")
    mp=mj["parentOriginM"];fp=fj["parentOriginM"]
    f_t1=fhs.getBodySet().get("thoracic1").getTransformInGround(fs)
    m_spine=masi.getBodySet().get("spine").getTransformInGround(ms)
    R=mm(mat(m_spine.R()),tr(mat(f_t1.R())))
    t=minus(mp,mv(R,fp))
    if dmm(plus(mv(R,fp),t),mp)>1e-6:raise ValueError("Landmark registration error")
    fhs_frames={name:record(fhs.getBodySet().get(name).getTransformInGround(fs)) for name in FHS_SPINE}
    for frame in fhs_frames.values():
        frame["registeredPositionM"]=plus(mv(R,frame["positionM"]),t)
        frame["registeredRotation"]=mm(R,frame["rotation"])
    c7=masi.getBodySet().get("cerv7").getTransformInGround(ms)
    c7body=record(c7)
    fhs_desc=mesh_descriptor(fhs_path,"thoracic1")
    with zipfile.ZipFile(archive_path) as z:
        candidates=[k for k in z.namelist() if k.endswith("/Geometry/"+fhs_desc["file"])]
        if len(candidates)!=1:raise ValueError("Missing unique FHS T1 mesh: "+repr(candidates))
        fhs_verts=read_mesh_vtp(z.read(candidates[0]))
    c7_verts=read_mesh_vtp(pathlib.Path(masi_c7_vtp).read_bytes())
    Rf=fhs_frames["thoracic1"]["rotation"]; pf=fhs_frames["thoracic1"]["positionM"]
    f_world=[plus(mv(R,plus(mv(Rf,[p[i]*fhs_desc["scale"][i] for i in range(3)]),pf)),t) for p in fhs_verts]
    m_world=[plus(mv(c7body["rotation"],p),c7body["positionM"]) for p in c7_verts]
    # Vertex-to-vertex distance only, not exact surface-to-surface distance.
    mindist=min(dmm(a,b) for a in f_world for b in m_world)
    fbox=bbox(f_world);mbox=bbox(m_world)
    overlap_y=max(0,min(fbox["maxM"][1],mbox["maxM"][1])-max(fbox["minM"][1],mbox["minM"][1]))*1000
    vertical_gap=max(0,mbox["minM"][1]-fbox["maxM"][1])*1000
    t1center=[(fbox["minM"][i]+fbox["maxM"][i])/2 for i in range(3)]
    c7center=[(mbox["minM"][i]+mbox["maxM"][i])/2 for i in range(3)]
    m_orig=record(m_spine)
    return {
       "schema":"masi-fhs-C7-T1-registration-diagnostic-v1",
       "masiSourceDOI":"10.6084/m9.figshare.4249808.v2",
       "fhsSource":"https://zenodo.org/records/18259702",
       "fhsModelPath":"FHS_dataset_4.x - Copia/Male/Age4049/110_SizeScaled_CurvatureAdjust_MuscleAdjust.osim",
       "engine":osim.GetVersionAndDate(),
       "jointConnections":{
          "masi":mj,"fhs":fj,
          "MASIJointFrameMismatchMm":dmm(mj["parentOriginM"],mj["childOriginM"]),
          "FHSJointFrameMismatchMm":dmm(fj["parentOriginM"],fj["childOriginM"])},
       "registration":{
          "method":"Rigid transform; FHS head_neck–thoracic1 joint to MASI auxt1jnt, FHS T1 body axes to MASI spine body axes",
          "rotationMatrix":R,"translationM":t,"uniformScale":1,
          "anchorResidualMm":dmm(plus(mv(R,fp),t),mp),
          "verifiedAnatomicalFit":False,
          "verifiedMuscleOrDynamicCompatibility":False,
          "basisCaveat":"Rigid-body orientation is a modeling frame, not a measured corresponding T1 anatomical coordinate system"},
       "C7T1Geometry":{
          "MASIC7NativeWorldBoundsM":mbox,
          "FHST1RegisteredWorldBoundsM":fbox,
          "MASIC7MeshVertices":len(c7_verts),
          "FHST1MeshVertices":len(fhs_verts),
          "minVertexToVertexSeparationMm":round(mindist,4),
          "verticalBoundingBoxGapMm":round(vertical_gap,4),
          "verticalBoundingBoxOverlapMm":round(overlap_y,4),
          "boundingBoxCenterSpacingMm":round(dmm(t1center,c7center),4),
          "warning":"Vertex separation and bounding boxes do not measure intervertebral joint integrity, articular alignment, cartilage or physical collision"},
       "fhsVertebralFrames":fhs_frames,
       "masiC7Frame":c7body,
       "masiSpineFrame":m_orig,
       "fhsT1Mesh":fhs_desc,
       "notAValidatedHybridModel":True,
    }

def main():
    p=argparse.ArgumentParser()
    for name in ("masi","fhs","fhs-archive","masi-c7-vtp","output"):
        p.add_argument("--"+name,required=True)
    a=p.parse_args()
    report=audit(a.masi,a.fhs,a.fhs_archive,a.masi_c7_vtp)
    out=pathlib.Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print("MASI_FHS_C7_T1_REGISTRATION_AUDIT",json.dumps({
        "jointNames":{k:v["name"] for k,v in report["jointConnections"].items() if isinstance(v,dict)},
        "residualMm":report["registration"]["anchorResidualMm"],
        "surfaceProxy":report["C7T1Geometry"],
        "fhsVertebrae":len(report["fhsVertebralFrames"])},ensure_ascii=False))

if __name__=="__main__":
    main()
