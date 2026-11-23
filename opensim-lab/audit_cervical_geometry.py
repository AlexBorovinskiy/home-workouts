#!/usr/bin/env python3
"""Audit all original FHS cervical bone meshes C1-C7 in OpenSim 4.6.

Read the original untouched VTP vertices from the scientific ZIP, scale by
each source Mesh.scale_factors, and transform by the *native* OpenSim body
TransformInGround. Report world-space bounds of each cervical mesh, T1 and
skull; do not invent/shift geometry or claim independent cervical motion.
"""
import argparse, json, math, pathlib, re, zipfile
import xml.etree.ElementTree as ET
import numpy as np
import opensim as osim

CERVICAL = ["cerv1.vtp","cerv2.vtp","cerv3.vtp","cerv4.vtp",
            "cerv5.vtp","cerv6.vtp","rotatedcerv7.vtp"]

def points_from_zip(z, path):
    root=ET.fromstring(z.read(path))
    piece=root.find("./PolyData/Piece")
    if piece is None:raise ValueError("Missing PolyData Piece: "+path)
    d=piece.find("./Points/DataArray")
    if d is None or d.attrib.get("format")!="ascii":raise ValueError("Non ASCII points "+path)
    values=np.fromstring(d.text or "",sep=" ",dtype=np.float64)
    if values.size%3 or values.size<9 or not np.isfinite(values).all():
        raise ValueError("Invalid points in "+path)
    return values.reshape((-1,3))

def native_transform(model,state,body_name):
    t=model.getBodySet().get(body_name).getTransformInGround(state)
    origin=np.array([float(t.p()[i]) for i in range(3)])
    rotation=np.array([[float(t.R().get(i,j)) for j in range(3)] for i in range(3)])
    assert np.allclose(rotation.T@rotation,np.eye(3),atol=2e-5)
    return origin,rotation

def mins_mm(a,b):
    best=1e20
    for i in range(0,len(a),180):
        best=min(best,float(np.sum((a[i:i+180,None,:]-b[None,:,:])**2,axis=2).min()))
    return round(math.sqrt(best)*1000,2)

def record(p,name,filename):
    a=p.min(axis=0); b=p.max(axis=0); center=(a+b)/2
    return {"id":name,"file":filename,"vertices":len(p),
            "minM":[round(x,6) for x in a.tolist()],
            "maxM":[round(x,6) for x in b.tolist()],
            "centerM":[round(x,6) for x in center.tolist()],
            "sizeMm":[round(x*1000,2) for x in (b-a).tolist()]}

def run(model_path,zip_path,path_inside):
    model=osim.Model(model_path)
    state=model.initSystem();model.assemble(state);model.realizePosition(state)
    with zipfile.ZipFile(zip_path) as z:
        xml=ET.fromstring(z.read(path_inside)).find("Model")
        if xml is None:raise ValueError("Missing original OpenSim model")
        geomdir=path_inside.split("/Male/")[0]+"/Geometry/"
        bybody={}
        for el in xml.findall("./BodySet/objects/Body"):
            name=el.attrib["name"]
            bybody[name]={}
            for mesh in el.findall(".//Mesh"):
                filename=(mesh.findtext("mesh_file") or "").strip()
                if not filename:continue
                if (mesh.findtext("socket_frame") or "..").strip()!="..":
                    raise ValueError("Unsupported socket for "+filename)
                scale=np.fromstring(mesh.findtext("scale_factors") or "1 1 1",sep=" ")
                if len(scale)!=3:raise ValueError("Invalid scale "+filename)
                origin,rotation=native_transform(model,state,name)
                p=(points_from_zip(z,geomdir+filename)*scale)@rotation.T+origin
                bybody[name][filename]=p
        head=bybody["head_neck"]
        expected=set(CERVICAL+["skull.vtp","jaw.vtp"])
        assert set(head)==expected,(set(head)^expected)
        t1=bybody["thoracic1"]["thoracic1_s.vtp"]
        cerv={}
        for i in range(1,8):
            filename=f"cerv{i}.vtp" if i<7 else "rotatedcerv7.vtp"
            cerv["C"+str(i)]=record(head[filename],"C"+str(i),filename)
        ordering=sorted(cerv,key=lambda k:-cerv[k]["centerM"][1])
        neighbours={}
        for i in range(1,8):
            me="C"+str(i)
            nextmesh= t1 if i==7 else head[f"cerv{i+1}.vtp" if i+1<7 else "rotatedcerv7.vtp"]
            fn=cerv[me]["file"]
            neighbours[me]={"next":("T1" if i==7 else "C"+str(i+1)),
                            "closestVertexMm":mins_mm(head[fn],nextmesh)}
        skull=head["skull.vtp"]
        c7=head["rotatedcerv7.vtp"]
        result={
            "kind":"FHS-native-cervical-VTP-geometry-audit-v1",
            "source":"https://zenodo.org/records/18259702",
            "subjectPath":path_inside,
            "unit":"m (positions); mm (distances and size)",
            "method":"Original VTP ASCII vertices * per-Mesh scale_factors, OpenSim Body.getTransformInGround native 4.6",
            "cervical":cerv,
            "skull":record(skull,"skull","skull.vtp"),
            "jaw":record(head["jaw.vtp"],"jaw","jaw.vtp"),
            "T1":record(t1,"T1","thoracic1_s.vtp"),
            "craniocaudalOrderByBoundingBoxCenter":ordering,
            "C1VsSkullMm":mins_mm(head["cerv1.vtp"],skull),
            "C7VsT1Mm":mins_mm(c7,t1),
            "adjacentSurfaceDistances":neighbours,
            "sameRigidBody":"head_neck",
            "independentCervicalJoints":False,
            "anatomicalValidation":False,
            "note":"Mesh surfaces are preexisting, but all C1-C7 share head_neck rigid transform; visual placement does not establish physiological cervical mechanics."
        }
    if len(cerv)!=7:raise AssertionError("Not seven cervical meshes")
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--model",required=True);p.add_argument("--archive",required=True)
    p.add_argument("--archive-relative",required=True);p.add_argument("--output",required=True)
    args=p.parse_args()
    result=run(args.model,args.archive,args.archive_relative)
    pathlib.Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    pathlib.Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print("FHS_CERVICAL_AUDIT "+json.dumps(result,ensure_ascii=False,separators=(",",":")))
