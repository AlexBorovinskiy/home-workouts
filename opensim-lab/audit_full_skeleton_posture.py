#!/usr/bin/env python3
"""Audit proportions and neutral stance of the existing multi-source skeleton.

This is a geometric consistency report, NOT a clinical postural assessment.
Do not silently rotate/resize individual segments to satisfy arbitrary
'ideal posture' values. All source original assembled frames are preserved.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET
import math

import numpy as np
from scipy.spatial import cKDTree


def array(value):
    return np.asarray(value, dtype=np.float64)

def read_vtp(b: bytes) -> np.ndarray:
    root=ET.fromstring(b)
    piece=root.find("./PolyData/Piece")
    if piece is None: raise ValueError("Missing VTP PolyData")
    da=piece.find("./Points/DataArray")
    if da is None or da.get("format","ascii").lower()!="ascii":
        raise ValueError("Expected native ASCII VTP point coordinates")
    v=np.fromstring(da.text or "",sep=" ",dtype=np.float64)
    if len(v)<9 or len(v)%3 or not np.isfinite(v).all():
        raise ValueError("Invalid native mesh point list")
    return v.reshape((-1,3))


def fhs_frame_matrix(frame):
    return np.column_stack(frame["basisColumns"])


def fhs_world(vertices,frame,mesh):
    return (vertices*array(mesh["scaleFactors"])) @ fhs_frame_matrix(frame).T + array(frame["origin"])


def raj_world(vertices,frame,mesh,reg):
    p=vertices*array(mesh["scale"])
    p=p@array(frame["rotation"]).T+array(frame["positionM"])
    return p@reg["R"].T*reg["s"]+reg["t"]


def masi_world(vertices,frame,reg,cervical_scale=.88875):
    # Browser neckRoot is inverse(FHS -> MASI), and neckScaffold scales
    # about the registered MASI C7/T1 landmark.
    p=vertices*array(frame["scale"])
    p=p@array(frame["rotation"]).T+array(frame["position"])
    p=reg["anchor"]+cervical_scale*(p-reg["anchor"])
    return (p-reg["t"])@np.linalg.inv(reg["R"]).T


def masi_point(point,reg,s=.88875):
    p=reg["anchor"]+s*(array(point)-reg["anchor"])
    return np.linalg.solve(reg["R"],p-reg["t"])


def bounds(pts):
    return {"minM":np.min(pts,axis=0).round(6).tolist(),
            "maxM":np.max(pts,axis=0).round(6).tolist(),
            "spanMm":((np.max(pts,axis=0)-np.min(pts,axis=0))*1000).round(3).tolist()}


def mm(x):
    return round(float(x)*1000,3)

def dist(a,b):
    return float(np.linalg.norm(array(a)-array(b)))

def point(v):
    return array(v).round(7).tolist()

def nearest_cloud(a,b):
    da=cKDTree(b).query(a,workers=-1)[0]
    db=cKDTree(a).query(b,workers=-1)[0]
    return {
       "minimumMm":mm(min(np.min(da),np.min(db))),
       "sourceToTargetMedianMm":mm(np.median(da)),
       "targetToSourceMedianMm":mm(np.median(db)),
       "sourceToTargetP10Mm":mm(np.percentile(da,10)),
       "targetToSourceP10Mm":mm(np.percentile(db,10)),
       "note":"Vertex-to-vertex separation is not a joint contact or cartilage-thickness measurement.",
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--fhs-zip",type=Path,required=True)
    ap.add_argument("--fhs-frames",type=Path,required=True)
    ap.add_argument("--raj-frames",type=Path,required=True)
    ap.add_argument("--masi-frames",type=Path,required=True)
    ap.add_argument("--masi-upper",type=Path,required=True)
    ap.add_argument("--neck-registration",type=Path,required=True)
    ap.add_argument("--raj-geometry",type=Path,required=True)
    ap.add_argument("--masi-geometry",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()

    f=json.loads(args.fhs_frames.read_text())
    r=json.loads(args.raj_frames.read_text())
    n=json.loads(args.masi_frames.read_text())
    u=json.loads(args.masi_upper.read_text())
    m=json.loads(args.neck_registration.read_text())
    if f["kind"]!="fhs-opensim-body-frames-v1" or r["schema"]!="rajagopal-lower-limbs-native-4.6-v1":
        raise ValueError("Wrong native author frame exports")
    if m["schema"]!="c7-t1-masi-fhs-registration-candidate-v1":
        raise ValueError("Wrong diagnostic neck registration")
    pF=array(f["bodyFrames"]["pelvis"]["origin"])
    pR=array(r["sourcePelvisFrame"]["positionM"])
    Rf=fhs_frame_matrix(f["bodyFrames"]["pelvis"])
    Rr=array(r["sourcePelvisFrame"]["rotation"])
    Rp=Rf@Rr.T
    s=float(r["visualInitialization"]["uniformScale"])
    t=pF-s*Rp@pR
    rajReg={"s":s,"R":Rp,"t":t}
    residual=dist(pF,s*Rp@pR+t)
    if residual>1e-7:raise AssertionError("Rajagopal-FHS pelvis origin mismatch")
    neckReg={"R":array(m["rotationMatrix"]),"t":array(m["translationM"]),
             "anchor":array(m["masiAnchorM"])}
    neckResidual=dist(masi_point(m["masiAnchorM"],neckReg),m["fhsAnchorM"])
    if neckResidual>1e-6:raise AssertionError("MASI neck anchor mismatch")

    archiveBase=f["archiveRelativeOsimPath"].split("/Male/")[0]+"/Geometry/"
    fgeom={}
    with zipfile.ZipFile(args.fhs_zip) as z:
        for body in ["pelvis","sacrum","thoracic1","thoracic12","lumbar5"]:
            clouds=[]
            for mesh in f["anatomyMeshes"][body]:
                v=read_vtp(z.read(archiveBase+mesh["file"]))
                clouds.append(fhs_world(v,f["bodyFrames"][body],mesh))
            fgeom[body]=np.vstack(clouds)

    raj_geom={}
    for body,meshes in r["bodyMeshes"].items():
        clouds=[]
        for mesh in meshes:
            v=read_vtp((args.raj_geometry/mesh["file"]).read_bytes())
            clouds.append(raj_world(v,r["bodyFrames"][body],mesh,rajReg))
        raj_geom[body]=np.vstack(clouds)
    # The Rajagopal source pelvis meshes are attached to a single pelvis body.
    sourceP=r["sourcePelvisFrame"]
    raj_pelvis={}
    for side in ["r","l"]:
        v=read_vtp((args.raj_geometry/(side+"_pelvis.vtp")).read_bytes())
        raj_pelvis[side]=raj_world(v,sourceP,{"scale":[1,1,1]},rajReg)

    masi_geom={}
    for name in ["skull","cerv1","cerv7","torso"]:
        frame=n["bodyFrames"][name]
        v=read_vtp((args.masi_geometry/frame["file"]).read_bytes())
        masi_geom[name]=masi_world(v,frame,neckReg)
    jaw=u["bodyFrames"]["jaw"]
    masi_geom["jaw"]=masi_world(read_vtp((args.masi_geometry/jaw["file"]).read_bytes()),jaw,neckReg)
    allGeom={**{"fhs_"+k:v for k,v in fgeom.items()},
             **{"raj_"+k:v for k,v in raj_geom.items()},
             **{"masi_"+k:v for k,v in masi_geom.items()}}
    cloud=np.vstack(list(allGeom.values()))
    bb=bounds(cloud)
    shoulderR=array(f["bodyFrames"]["humerus_R"]["origin"])
    shoulderL=array(f["bodyFrames"]["humerus_L"]["origin"])
    t1=array(f["bodyFrames"]["thoracic1"]["origin"])
    t12=array(f["bodyFrames"]["thoracic12"]["origin"])
    C7=masi_point(n["bodyFrames"]["cerv7"]["position"],neckReg)
    C1=masi_point(n["bodyFrames"]["cerv1"]["position"],neckReg)
    skullFrame=masi_point(n["bodyFrames"]["skull"]["position"],neckReg)
    skullVisualCentre=(np.min(masi_geom["skull"],axis=0)+np.max(masi_geom["skull"],axis=0))/2
    skullVisualCentreMean=np.mean(masi_geom["skull"],axis=0)
    hip={}
    for side in ["r","l"]:
        hipSource=array(r["jointWorldPoints"]["hip_"+side]["parentPoint"])
        hipWorld=s*Rp@hipSource+t
        femur=raj_geom["femur_"+side]
        pelvisF=fgeom["pelvis"]
        leftRightHip=hipWorld[2]
        hip[side]={
          "sourceHipJointCenterM":point(hipSource),
          "transformedHipJointCenterM":point(hipWorld),
          "pelvisFHSAtSource":nearest_cloud(femur,pelvisF),
          "femurToSourceRajPelvis":nearest_cloud(femur,raj_pelvis[side]),
          "RajPelvisToFHSPelvis":nearest_cloud(raj_pelvis[side],pelvisF),
          "rajSourcePelvisBoundingBox":bounds(raj_pelvis[side]),
          "hipHeightToHeelCentreMm":mm(hipWorld[1]-np.mean(raj_geom["calcn_"+side],axis=0)[1]),
          "medialSideCoordinateM":round(float(leftRightHip),6),
        }

    # Median sole/bottom-to-top height and landmark ratios, no clinical thresholds.
    feet=np.vstack([raj_geom["calcn_r"],raj_geom["calcn_l"],
                    raj_geom["toes_r"],raj_geom["toes_l"]])
    soleY=np.min(feet[:,1])
    headTopY=np.max(np.vstack([masi_geom["skull"],masi_geom["jaw"]])[:,1])
    height=headTopY-soleY
    shoulderWidth=dist(shoulderR,shoulderL)
    hipWidth=dist(hip["r"]["transformedHipJointCenterM"],
                  hip["l"]["transformedHipJointCenterM"])
    headToC7=float(skullVisualCentre[0]-C7[0])
    pelvisToT1X=float(t1[0]-pF[0])
    feetLR={}
    for side in ["r","l"]:
        verts=np.vstack([raj_geom["calcn_"+side],raj_geom["toes_"+side]])
        feetLR[side]={"bottomY":round(float(np.min(verts[:,1])),6),
                      "topY":round(float(np.max(verts[:,1])),6),
                      "bounds":bounds(verts)}

    measurements={
      "fullSceneGeometryBoundingBox":bb,
      "visibleSkeletonTopToFootBottomMm":mm(height),
      "distanceFromT1ToPelvisOriginMm":mm(dist(t1,pF)),
      "T1AnteriorOffsetFromPelvisOriginMm":mm(pelvisToT1X),
      "headMeshVisualCentreAnteriorOffsetFromC7Mm":mm(headToC7),
      "skullFrameAnteriorOffsetFromT1Mm":mm(skullFrame[0]-t1[0]),
      "skullMeshVisualCentreAnteriorOffsetFromT1Mm":mm(skullVisualCentre[0]-t1[0]),
      "skullMeshMeanAnteriorOffsetFromT1Mm":mm(skullVisualCentreMean[0]-t1[0]),
      "skullVisualCentreToPelvisAnteriorMm":mm(skullVisualCentre[0]-pF[0]),
      "shoulderJointFrameWidthMm":mm(shoulderWidth),
      "hipJointFrameWidthMm":mm(hipWidth),
      "shoulderToHipWidthRatio":round(shoulderWidth/hipWidth,4),
      "T1ToT12VerticalMm":mm(t1[1]-t12[1]),
      "C1ToC7VerticalMm":mm(C1[1]-C7[1]),
      "pelvisYFromGroundSoleMm":mm(pF[1]-soleY),
      "headTopYFromGroundSoleMm":mm(height),
      "legHipJointToHeelMm":{side:hip[side]["hipHeightToHeelCentreMm"] for side in ["r","l"]},
      "hipY":{side:hip[side]["transformedHipJointCenterM"][1] for side in ["r","l"]},
      "footBottomYSymmetryMm":mm(abs(feetLR["r"]["bottomY"]-feetLR["l"]["bottomY"])),
      "leftRightLegLengthsDifferenceMm":abs(hip["r"]["hipHeightToHeelCentreMm"]-hip["l"]["hipHeightToHeelCentreMm"]),
    }
    flags={
       "legLeftRightSymmetryOk":measurements["footBottomYSymmetryMm"]<2
                                and measurements["leftRightLegLengthsDifferenceMm"]<2,
       "anatomicalPelvisHipJoinValidated":False,
       "anatomicalCervicalJoinValidated":False,
       "neutralPostureValidated":False,
       "referenceHealthyAnthropometryCompared":False,
    }
    result={
      "schema":"full-skeleton-posture-surface-audit-v1",
      "sources":{
         "fhs":"https://zenodo.org/records/18259702",
         "masi":"https://doi.org/10.6084/m9.figshare.4249808.v2",
         "aah":"https://github.com/nishbo/ms_arm_and_hand",
         "rajagopal":"https://github.com/opensim-org/opensim-models/tree/master/Models/Rajagopal"
      },
      "summary":{
        "purpose":"Coordinate-based 3D neutral stance and surface alignment diagnosis",
        "diagnosticNotClinical":True,
        "noSourceAnatomyModified":True,
        "neckRegistrationResidualMm":mm(neckResidual),
        "pelvisFrameRegistrationResidualMm":mm(residual),
        "measuredXCoordinateConvention":"OpenSim +X forward, +Y up; anterior-offset sign uses frame conventions",
      },
      "measuredLandmarkFrames":{
        "FHS_pelvis":point(pF),"FHS_T1":point(t1),"FHS_T12":point(t12),
        "MASI_C7_registered":point(C7),
        "MASI_C1_registered":point(C1),
        "MASI_skull_frame_registered":point(skullFrame),
        "MASI_skull_geometry_centre":point(skullVisualCentre),
        "FHS_shoulders":{"right":point(shoulderR),"left":point(shoulderL)},
      },
      "measurements":measurements,
      "hipSurfaceCompatibility":hip,
      "footGeometry":feetLR,
      "flags":flags,
      "limitations":[
        "Bone mesh nearest-vertex distances are not joint-space distances or cartilage measurements",
        "The skull centre is a bounding-box proxy, not a clinically measured external auditory meatus or head COM",
        "The FHS pelvis and Rajagopal hips have been matched by bone-frame origins and a trial scale, not calibrated anatomical hip centres",
        "The reference FHS spine may represent a particular source pose; its kyphotic curvature is not independently adjusted",
        "No medical posture diagnosis, exercise safety assessment, muscle force model, contact dynamics or validation",
        "Do not change bone placements until cross-source fit is measured and approved by visual source comparison",
      ]
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("FULL_SKELETON_POSTURE_AUDIT",json.dumps({
      "heightMm":measurements["visibleSkeletonTopToFootBottomMm"],
      "T1AnteriorOffsetFromPelvisMm":measurements["T1AnteriorOffsetFromPelvisOriginMm"],
      "skullOffsetFromT1Mm":measurements["skullMeshVisualCentreAnteriorOffsetFromT1Mm"],
      "footBottomSymmetryMm":measurements["footBottomYSymmetryMm"],
      "pelvisFemurVsFHSMinimumMm":{s:v["pelvisFHSAtSource"]["minimumMm"] for s,v in hip.items()},
      "pelvisMeshRajVsFHSMinimumMm":{s:v["RajPelvisToFHSPelvis"]["minimumMm"] for s,v in hip.items()},
    },ensure_ascii=False))
if __name__=="__main__":
    main()
