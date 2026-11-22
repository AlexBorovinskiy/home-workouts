#!/usr/bin/env python3
"""Export OpenSim 4.6 original body coordinate frames, but NOT anatomy meshes.

This data is enough to place locally-loaded VTP geometries in a WebGL viewer.
The source geometries remain in the user's local FHS ZIP. No mesh is published.
"""
import argparse
import hashlib
import json
import pathlib
import xml.etree.ElementTree as ET

import opensim as osim

def vec3(v):
    return [round(float(v[i]),8) for i in range(3)]

def axes(rotation):
    # SimTK Rotation column vectors: local x/y/z expressed in Ground.
    # This avoids incorrectly approximating the orientation from joint positions.
    # SWIG may not expose Rotation.x()/y()/z(); inspect underlying methods.
    if not hasattr(rotation, "x"):
        print("ROTATION_AVAILABLE_METHODS", sorted(k for k in dir(rotation) if not k.startswith("_")))
    return [vec3(rotation.x()),vec3(rotation.y()),vec3(rotation.z())]

def export(filename,model_zip_path):
    model=osim.Model(str(filename))
    model.setUseVisualizer(False)
    state=model.initSystem()
    model.assemble(state)
    model.realizePosition(state)
    frames={}
    bodies=model.getBodySet()
    for i in range(bodies.getSize()):
        body=bodies.get(i)
        frame=body.getTransformInGround(state)
        frames[body.getName()] = {
            "origin": vec3(frame.p()),
            "basisColumns": axes(frame.R()),
        }
    root=ET.parse(filename).getroot()
    model_elt=root.find("Model")
    assert model_elt is not None
    meshes={}
    for body in model_elt.findall("./BodySet/objects/Body"):
        name=body.get("name")
        geometries=[]
        for mesh in body.findall("./attached_geometry/Mesh"):
            file_=(mesh.findtext("mesh_file") or "").strip()
            s=(mesh.findtext("scale_factors") or "1 1 1").split()
            sf=[float(v) for v in s]
            socket=(mesh.findtext("socket_frame") or "..").strip()
            if not file_:
                continue
            if socket!="..":
                # Do not guess extra PhysicalOffsetFrame transform. Force QA failure.
                raise ValueError(f"Unsupported mesh frame for {name}: {socket}")
            geometries.append({
                "file":file_,
                "scaleFactors":sf,
                "sourceBody":name,
                "socket":socket
            })
        if geometries:
            meshes[name]=geometries
    # No full-model personal medical/anthropometric data is published.
    return {
        "kind":"fhs-opensim-body-frames-v1",
        "sourceRecord":"https://zenodo.org/records/18259702",
        "archiveRelativeOsimPath":model_zip_path,
        "modelName":model_elt.get("name"),
        "engine":osim.GetVersionAndDate(),
        "unit":"m",
        "basis":"columns in ground frame (OpenSim ground x,y,z); use THREE.Matrix4.makeBasis",
        "licensing":"Geometry is NOT redistributed; user opens official dataset ZIP locally",
        "anatomyMeshes":meshes,
        "bodyFrames":frames,
        "note":"Visible C1-C7 skull, hand phalanges are rigidly attached; independent articulation is not implied",
    }

if __name__=="__main__":
    arg=argparse.ArgumentParser()
    arg.add_argument("--model",required=True)
    arg.add_argument("--archive-relative",required=True)
    arg.add_argument("--output",required=True)
    a=arg.parse_args()
    out=export(a.model,a.archive_relative)
    pathlib.Path(a.output).parent.mkdir(parents=True,exist_ok=True)
    pathlib.Path(a.output).write_text(json.dumps(out,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    assert "head_neck" in out["bodyFrames"] and "hand_R" in out["bodyFrames"]
    assert len(out["anatomyMeshes"]["head_neck"])>=8
    assert len(out["anatomyMeshes"]["hand_R"])>=25
    print("FHS_FRAME_INVENTORY",json.dumps({
        "bodyCount":len(out["bodyFrames"]),
        "meshCount":sum(map(len,out["anatomyMeshes"].values())),
        "headMeshes":len(out["anatomyMeshes"]["head_neck"]),
        "rightHandMeshes":len(out["anatomyMeshes"]["hand_R"]),
        "leftHandMeshes":len(out["anatomyMeshes"]["hand_L"]),
        "model":out["modelName"],
        "path":out["archiveRelativeOsimPath"],
        "headTransform":out["bodyFrames"]["head_neck"],
        "rightHandTransform":out["bodyFrames"]["hand_R"],
    },ensure_ascii=False))
    print("FHS_FRAMES_JSON",json.dumps(out,ensure_ascii=False,separators=(",",":")))
