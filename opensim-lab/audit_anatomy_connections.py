#!/usr/bin/env python3
"""Independent spatial audit of source FHS skeleton (no corrective bone offsets).

Inspects the original archived VTP vertices and the model's fully assembled
OpenSim 4.6 frames. It does NOT prove medical/anatomical validity and must not
be used to estimate joint loading or declare an exercise safe.
"""
from __future__ import annotations
import argparse, json, re, zipfile, xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
import opensim as osim

def read_points(z, meshpath):
    piece=ET.fromstring(z.read(meshpath)).find("./PolyData/Piece")
    if piece is None: raise ValueError(f"VTP missing Piece {meshpath}")
    arr=piece.find("./Points/DataArray")
    if arr is None or arr.attrib.get("format")!="ascii": raise ValueError(f"Expected ASCII VTP {meshpath}")
    data=np.fromstring(arr.text or "",sep=" ",dtype=np.float64)
    if len(data)%3: raise ValueError(f"Invalid points {meshpath}")
    return data.reshape(-1,3)

def min_distance(a,b):
    if len(a)==0 or len(b)==0:return None
    best=np.inf
    for i in range(0,len(a),180):
        # Exact point-cloud separation, independent of 3D browser rendering.
        d2=((a[i:i+180,None,:]-b[None,:,:])**2).sum(axis=2)
        best=min(best,float(d2.min()))
    return round(best**.5*1000,2)

def audit(model_file, zip_file, model_in_zip):
    z=zipfile.ZipFile(zip_file)
    model=osim.Model(str(model_file))
    state=model.initSystem()
    model.assemble(state)
    model.realizePosition(state)
    root=ET.parse(model_file).getroot().find("Model")
    if root is None:raise ValueError("not OpenSim")
    prefix=model_in_zip.split("/Male/")[0]+"/Geometry/"
    bodies=model.getBodySet()
    positions={}
    meshes={}
    for b in root.findall("./BodySet/objects/Body"):
        name=b.get("name")
        frame=bodies.get(name).getTransformInGround(state)
        rot=np.array([[float(frame.R().get(i,j)) for j in range(3)] for i in range(3)])
        origin=np.array([float(frame.p()[i]) for i in range(3)])
        originals=b.findall(".//Mesh")
        verts=[]
        for obj in originals:
            fn=(obj.findtext("mesh_file") or "").strip()
            if not fn:continue
            if (obj.findtext("socket_frame") or "..").strip()!="..":
                raise ValueError(f"unhandled attachment {name}:{fn}")
            scale=np.fromstring(obj.findtext("scale_factors") or "1 1 1",sep=" ")
            if len(scale)!=3:raise ValueError(f"scale {name}:{fn}")
            points=read_points(z,prefix+fn)
            verts.append((points*scale)@rot.T+origin)
        if verts:meshes[name]=np.concatenate(verts,axis=0)
        positions[name]=origin.tolist()
    # As loaded in OpenSim, geometry is already associated with its source body.
    ribs=[]
    for i in range(1,13):
        for side in "RL":
            rib=f"rib{i}_{side}"; t=f"thoracic{i}"
            points=meshes[rib]
            # Nearest observed rib vertex to its own vertebra and to neighbours.
            candidates=[n for n in (f"thoracic{i-1}",t,f"thoracic{i+1}")
                        if n in meshes]
            d={n:min_distance(points,meshes[n]) for n in candidates}
            ribs.append({"rib":rib,"expectedVertebra":t,"nearestDistanceMm":d,
                         "ribFrameOriginM":[round(x,5) for x in positions[rib]]})
    shoulder=[]
    for side in "RL":
        pairs=[("sternum",f"clavicle_{side}"),
               (f"clavicle_{side}",f"scapula_{side}"),
               (f"scapula_{side}",f"humerus_{side}")]
        for a,b in pairs:shoulder.append({"from":a,"to":b,
                                           "meshMinDistanceMm":min_distance(meshes[a],meshes[b]),
                                           "bodyFrameDistanceMm":round(np.linalg.norm(np.array(positions[a])-positions[b])*1000,2)})
    links=[]
    for joint in root.findall("./JointSet/objects/*"):
        frames={}
        for f in joint.findall("./frames/*"):
            frames[f.attrib.get("name")]={
                "parentBody":(f.findtext("socket_parent") or "").split("/")[-1],
                "translationM":list(map(float,(f.findtext("translation") or "0 0 0").split()))
            }
        a=(joint.findtext("socket_parent_frame") or "").split("/")[-1]
        b=(joint.findtext("socket_child_frame") or "").split("/")[-1]
        src=frames.get(a,{}).get("parentBody",a)
        dst=frames.get(b,{}).get("parentBody",b)
        links.append({"joint":joint.get("name"),"kind":joint.tag,"parentBody":src,"childBody":dst,
                      "parentFrame":a,"childFrame":b,
                      "parentAttachmentLocalM":frames.get(a,{}).get("translationM"),
                      "childAttachmentLocalM":frames.get(b,{}).get("translationM")})
    result={"kind":"fhs-original-joint-connection-audit-v1",
       "sourceModel":model_in_zip,
       "method":"OpenSim body transforms plus original source VTP mesh vertices",
       "sourceArchive":"https://zenodo.org/records/18259702",
       "units":"mm",
       "ribs":ribs,"shoulder":shoulder,"jointLinks":links,
       "note":"Mesh minimum distances show approximate surface separation; they are not verified joint centres or cartilage. Source model constraints are not automatically proof of physiological accuracy.",
    }
    return result

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--model",required=True)
    ap.add_argument("--archive",required=True)
    ap.add_argument("--archive-relative",required=True)
    ap.add_argument("--output",required=True)
    args=ap.parse_args()
    report=audit(args.model,args.archive,args.archive_relative)
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print("FHS_CONNECTION_AUDIT",json.dumps({
       "links":len(report["jointLinks"]),
       "ribDistances":report["ribs"],
       "shoulderDistances":report["shoulder"],
       "ribParentLinks":[x for x in report["jointLinks"] if x["childBody"].lower().startswith("rib") or x["parentBody"].lower().startswith("rib")],
       "sternumParentLinks":[x for x in report["jointLinks"] if x["childBody"]=="sternum"],
    },ensure_ascii=False,separators=(",",":")))
