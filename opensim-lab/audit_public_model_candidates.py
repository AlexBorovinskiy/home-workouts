#!/usr/bin/env python3
"""Inventory public scientific .osim assets, no bone fusion or exercise synthesis.

Reports provenance, coordinate and joint counts, visual geometry references,
bilateral hand coverage, and actual OpenSim 4.6 initialization status.
Report does not establish anatomical compatibility among different models.
"""
from __future__ import annotations
import argparse
import collections
import json
from pathlib import Path
import xml.etree.ElementTree as ET

SOURCES = {
 "rajagopal2016":{
  "url":"https://github.com/opensim-org/opensim-models/blob/master/Models/Rajagopal/Rajagopal2016.osim",
  "scope":"public full-body model revised for OpenSim 4.5; locomotion focus",
  "role":"baseline for exercise kinematics, NOT detailed cervical/thoracic anatomy",
 },
 "rajagopal2023":{
  "url":"https://github.com/opensim-org/opensim-models/blob/master/Models/Rajagopal/RajagopalLaiUhlrich2023.osim",
  "scope":"improved high-flexion and passive muscle properties; lower-limb emphasis",
  "role":"practical full-body motion candidate, not independent spine or fingers",
 },
 "aah_right_nomuscles":{
  "url":"https://github.com/nishbo/ms_arm_and_hand/blob/main/AAH%20Model/RightArmAndHand_NoMuscles.osim",
  "scope":"right shoulder, upper limb and articulated hand; inverse kinematics only",
  "role":"finger and thumb geometry+kinematics candidate; do not infer grip forces",
 },
 "aah_left_nomuscles":{
  "url":"https://github.com/nishbo/ms_arm_and_hand/blob/main/AAH%20Model/LeftArmAndHand_NoMuscles.osim",
  "scope":"left shoulder, upper limb and articulated hand; inverse kinematics only",
  "role":"other-side hand reference; not a validated fused bilateral model",
 },
}


def names(nodes):
    return [n.get("name") for n in nodes if n.get("name")]


def basic(path):
    root=ET.parse(path).getroot()
    if root.tag!="OpenSimDocument":
        raise ValueError("not an OpenSim XML document")
    model=root.find("Model")
    if model is None:
        raise ValueError("Model absent")
    bodies=model.findall("./BodySet/objects/Body")
    joints=model.findall("./JointSet/objects/*")
    force_nodes=model.findall("./ForceSet/objects/*")
    meshes=model.findall(".//attached_geometry/Mesh")
    mesh_files=sorted(set((m.findtext("mesh_file") or "").strip() for m in meshes if (m.findtext("mesh_file") or "").strip()))
    mass_zero=sum(1 for b in bodies if (b.findtext("mass") or "") in ("0","0.0","0.0000000000000000"))
    coord_nodes=[node for node in model.findall(".//Coordinate") if node.get("name")]
    coordinate_names=sorted(set(n.get("name") for n in coord_nodes))
    joints_by_type=dict(sorted(collections.Counter(j.tag for j in joints).items()))
    force_by_type=dict(sorted(collections.Counter(f.tag for f in force_nodes).items()))
    return {
      "name":model.get("name"),
      "schemaVersion":root.get("Version"),
      "counts":{
        "bodies":len(bodies),
        "joints":len(joints),
        "coordinatesDeclaredInXML":len(coordinate_names),
        "forceObjects":len(force_nodes),
        "musclesByName":sum("Muscle" in f.tag for f in force_nodes),
        "zeroMassBodiesExactly":mass_zero,
        "attachedMeshInstances":len(meshes),
        "uniqueAttachedMeshFiles":len(mesh_files),
      },
      "jointTypes":joints_by_type,
      "forceTypes":force_by_type,
      "bodyNames":names(bodies),
      "coordinateNames":coordinate_names,
      "attachedMeshFiles":mesh_files,
      "warnings":["Native skeleton topology is NOT proof of a correctly rigged 3-D viewer",
                  "The model is an independent OpenSim file, NOT grafted to FHS or MASI"]
    }


def from_native(path):
    try:
        import opensim as osim
        m=osim.Model(str(path))
        s=m.initSystem()
        m.assemble(s)
        m.realizePosition(s)
        b=m.getBodySet()
        j=m.getJointSet()
        c=m.getCoordinateSet()
        muscles=m.getMuscles()
        return {"status":"assembled",
                "opensimVersion":osim.GetVersionAndDate(),
                "bodies":b.getSize(),
                "joints":j.getSize(),
                "coordinateCount":c.getSize(),
                "coordinateNames":[c.get(i).getName() for i in range(c.getSize())],
                "muscleCount":muscles.getSize()}
    except Exception as e:
        return {"status":"failed","errorClass":e.__class__.__name__,
                "error":str(e)[:1800]}


def inventory_finger_segments(report,side):
    """Heuristic names only, no claim all segment orientations are correct."""
    pref="RA" if side=="right" else "LA"
    body_names=report["bodyNames"]
    distal=[n for n in body_names if n.startswith(pref) and
            (n[-2:-1].lower()=="d" or "thumb" in n.lower())]
    digit_meshes=[f for f in report["attachedMeshFiles"] if any(x in f.lower() for x in
                   ("thumb","proxph","midph","distph","1mc","2mc","3mc","4mc","5mc"))]
    return {"digitMeshFileCount":len(digit_meshes),"digitMeshFiles":digit_meshes,
            "heuristicDistalBodyNames":distal,"fingerDegreeOfFreedomVerified":False}


def source_mesh_audit(record,tree_paths,kind):
    source=record["attachedMeshFiles"]
    if kind=="aah":
        valid={path.split("/")[-1] for path in tree_paths if path.startswith("AAH Model/Geometry/") and path.endswith(".vtp")}
    else:
        valid={path.split("/")[-1] for path in tree_paths
               if (path.startswith("Geometry/") or path.startswith("Models/Rajagopal/Geometry/")) and path.endswith(".vtp")}
    missing=[f for f in source if Path(f).name not in valid]
    return {
      "referencedFileCount":len(source),
      "availableInPublishedSourceRepo":len(source)-len(missing),
      "missingFromPublishedSourceRepo":missing,
      "checkMethod":"filename in the author-published repository tree; image loading and anatomical registration not verified"
    }


def main():
    p=argparse.ArgumentParser()
    for key in SOURCES:
        p.add_argument("--"+key.replace("_","-"),type=Path,required=True)
    p.add_argument("--aah-tree",type=Path,required=True)
    p.add_argument("--opensim-tree",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    trees={
     "aah":[v["path"] for v in json.loads(args.aah_tree.read_text())["tree"]],
     "rajagopal":[v["path"] for v in json.loads(args.opensim_tree.read_text())["tree"]],
    }
    results={}
    for key,source in SOURCES.items():
        path=getattr(args,key)
        obj=basic(path)
        obj["source"]=source
        obj["nativeOpenSim"]=from_native(path)
        obj["publishedMeshAvailability"]=source_mesh_audit(obj,trees,"aah" if key.startswith("aah") else "rajagopal")
        if key.startswith("aah"):
            obj["fingerAssessment"]=inventory_finger_segments(obj,"right" if "right" in key else "left")
        results[key]=obj
    out={
      "schema":"public-ready-models-audit-v1",
      "engine":"OpenSim 4.6 native state assembly + independent XML/geometry-source inspection",
      "results":results,
      "notMeasured":["motion quality under dumbbell loading","facets and surfaces in collision",
                     "cross-model graft compatibility","anatomical accuracy of 3-D grip pose"],
      "augmented2025":{
        "paper":"https://doi.org/10.1007/s10439-025-03762-7",
        "model":"https://simtk.org/projects/sports_model/",
        "downloadStatus":"authors say available for research use upon request; no OpenSim model file independently inspected",
        "paperReportedCounts":{"rigidBodies":29,"dof":48,"muscleTendonUnits":80},
        "spine":"two joint neck representation, not separately articulated C1-C7",
      },
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    for k,v in results.items():
        print("READY_MODEL_INVENTORY",json.dumps({
            "model":k,"counts":v["counts"],
            "native":v["nativeOpenSim"],
            "meshes":v["publishedMeshAvailability"],
            "hand":v.get("fingerAssessment",{}).get("digitMeshFileCount")
        },ensure_ascii=False))
    print("READY_MODELS_REPORT",str(args.output))


if __name__=="__main__":
    main()
