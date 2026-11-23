#!/usr/bin/env python3
"""Audit original MASI 2017 full-body OpenSim model in OpenSim 4.6.

Author-provided original: Figshare 4249808 version 2, file id 6929198.
For now validates original as standalone scientific model, NOT mixed with FHS,
NOT automatically suitable for exercises and NOT visually 'corrected' by hand.
"""
import json
import argparse
import pathlib
import re
import traceback
import xml.etree.ElementTree as ET

SOURCE="https://ndownloader.figshare.com/files/6929198"

def xml_inventory(path):
    root=ET.parse(path).getroot()
    model=root.find("Model")
    if model is None:raise ValueError("Missing OpenSim Model root")
    body_items=model.findall("./BodySet/objects/Body")
    joint_objects=list(model.findall("./JointSet/objects/*"))
    muscles=list(model.findall("./ForceSet/objects/*"))
    meshes=model.findall(".//Mesh")
    geom_files=sorted(set(v.text.strip() for v in model.findall(".//mesh_file") if v.text and v.text.strip()))
    important=[n.get("name") for n in body_items if re.search(r"cerv|neck|skull|head|scap|clav|humer|tib|fem|torso|thorax|pelvis|rib",n.get("name",""),re.I)]
    linklist=[]
    for joint in joint_objects:
        linklist.append({"name":joint.get("name"),"type":joint.tag,
          "socketParentFrame":joint.findtext("socket_parent_frame"),
          "socketChildFrame":joint.findtext("socket_child_frame"),
          "legacyParentBody":joint.findtext("parent_body"),
          "legacyChildBody":joint.findtext("child_body"),
          "coordinates":[e.get("name") for e in joint.findall("./coordinates/Coordinate")]})
    return {"modelName":model.get("name"),"opensimDocumentVersion":root.get("Version"),
      "bodyCountXml":len(body_items),"bodyNames":[b.get("name") for b in body_items],
      "candidateNeckAndLimbBodies":important,
      "jointCountXml":len(joint_objects),"joints":linklist,
      "forceObjectsXml":len(muscles),"meshCount":len(meshes),
      "referencedMeshFiles":geom_files,
      "sourceFileSizeBytes":pathlib.Path(path).stat().st_size}

def native_test(path):
    try:
        import opensim as osim
        model=osim.Model(str(path))
        state=model.initSystem()
        model.assemble(state)
        model.realizePosition(state)
        bset=model.getBodySet()
        jointset=model.getJointSet()
        coords=model.getCoordinateSet()
        cervical=[]
        for i in range(bset.getSize()):
            body=bset.get(i)
            n=body.getName()
            if re.search(r"(?:cerv|^C[1-7]$|^C[1-7]_|_C[1-7]|^neck)",n,re.I):
                p=body.getTransformInGround(state).p()
                cervical.append({"name":n,"bodyOriginM":[round(float(p[k]),7) for k in range(3)]})
        return {"initialized":True,"version":osim.GetVersionAndDate(),
                "nativeBodies":bset.getSize(),"nativeJoints":jointset.getSize(),
                "nativeCoordinates":coords.getSize(),"nativeCervicalBodies":cervical,
                "nativeCoordinateNames":[coords.get(i).getName() for i in range(coords.getSize())]}
    except Exception as e:
        return {"initialized":False,"error":str(e),"tracebackTail":traceback.format_exc()[-4500:]}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--model",required=True)
    ap.add_argument("--output",required=True)
    args=ap.parse_args()
    xml=xml_inventory(args.model)
    native=native_test(args.model)
    result={"sourceModel":"MASI v2 by Cazzola et al 2017",
       "source":SOURCE,"publisher":"Figshare","doi":"10.6084/m9.figshare.4249808.v2",
       "license":"MIT (publisher metadata)","xml":xml,"native":native,
       "fhsReplaced":False,
       "limits":"Anatomical fidelity of visible bones and dynamics not established by XML parse or initSystem alone"}
    pathlib.Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    pathlib.Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print("MASI_NATIVE_AUDIT "+json.dumps({
      "xml":{k:v for k,v in xml.items() if k!="joints" and k!="bodyNames"},
      "jointsRelevant":[x for x in xml["joints"] if re.search(r"cerv|c[0-7]|neck|scap|clav|should|head",x["name"] or "",re.I)],
      "native":native,
      "fhsReplaced":False},ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":main()
