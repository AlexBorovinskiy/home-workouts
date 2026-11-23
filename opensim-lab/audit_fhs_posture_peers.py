#!/usr/bin/env python3
"""Compare neutral-looking sagittal frames across FHS source age/sex peers.

These are subject-specific OpenSim source models, not normative posture.
No healthy posture or ideal curvature is inferred from a dataset median.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import tempfile
import zipfile

import numpy as np
import opensim as osim

GROUP="/Male/Age4049/"
CURRENT="110_SizeScaled_CurvatureAdjust_MuscleAdjust.osim"
BODIES=("pelvis","thoracic1","thoracic12","thoracic6","lumbar1","lumbar5","head_neck")

def v(p):return np.array([float(p[i]) for i in range(3)])
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--zip",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    records=[];fail=[]
    with zipfile.ZipFile(args.zip) as z:
        models=sorted(x for x in z.namelist() if GROUP in x and x.endswith(".osim"))
        if len(models)<10:raise ValueError("Insufficient FHS original age cohort")
        with tempfile.TemporaryDirectory() as t:
            for k,member in enumerate(models):
                path=Path(t)/(f"fhs_{k}.osim")
                path.write_bytes(z.read(member))
                try:
                    model=osim.Model(str(path))
                    state=model.initSystem()
                    model.assemble(state);model.realizePosition(state)
                    b=model.getBodySet()
                    pos={name:v(b.get(name).getTransformInGround(state).p()) for name in BODIES}
                    t1=pos["thoracic1"];t12=pos["thoracic12"];pelvis=pos["pelvis"];l1=pos["lumbar1"];l5=pos["lumbar5"]
                    if t1[1]<=t12[1] or l1[1]<=l5[1]:raise ValueError("Non-upright model source frame")
                    record={
                        "model":member.split("/")[-1],
                        "pathInFHSArchive":member,
                        "T1AnteriorToPelvisMm":round(float((t1[0]-pelvis[0])*1000),3),
                        "T1AnteriorToT12Mm":round(float((t1[0]-t12[0])*1000),3),
                        "T1T12VerticalMm":round(float((t1[1]-t12[1])*1000),3),
                        "thoracicSagittalChordAngleFromVerticalDeg":
                            round(float(math.degrees(math.atan2(t1[0]-t12[0],t1[1]-t12[1]))),3),
                        "lumbarSagittalChordAngleFromVerticalDeg":
                            round(float(math.degrees(math.atan2(l1[0]-l5[0],l1[1]-l5[1]))),3),
                        "pelvisXmm":round(float(pelvis[0]*1000),3),
                        "source": "Original FHS OpenSim 4.x model, Model.assemble() body frames",
                    }
                    records.append(record)
                    print("FHS_PEER",record["model"],record["T1AnteriorToPelvisMm"],
                          record["thoracicSagittalChordAngleFromVerticalDeg"])
                except Exception as e:
                    fail.append({"model":member,"error":str(e)[:400]})
    if not any(x["model"]==CURRENT for x in records):raise ValueError("Current FHS subject missing")
    metrics=["T1AnteriorToPelvisMm","thoracicSagittalChordAngleFromVerticalDeg",
             "lumbarSagittalChordAngleFromVerticalDeg"]
    current=next(v for v in records if v["model"]==CURRENT)
    distribution={}
    for key in metrics:
        arr=np.array([x[key] for x in records],dtype=float)
        val=current[key]
        distribution[key]={
            "n":len(records),
            "min":round(float(arr.min()),3),
            "p10":round(float(np.percentile(arr,10)),3),
            "p25":round(float(np.percentile(arr,25)),3),
            "median":round(float(np.median(arr)),3),
            "p75":round(float(np.percentile(arr,75)),3),
            "p90":round(float(np.percentile(arr,90)),3),
            "max":round(float(arr.max()),3),
            "currentValue":val,
            "currentPercentileRank":round(float(100*(np.sum(arr<val)+.5*np.sum(arr==val))/len(arr)),1),
            "unit":"mm" if key.endswith("Mm") else "degrees",
        }
    # Proximity to cohort medians is NOT a "healthy" or posture correctness score.
    med={k:distribution[k]["median"] for k in metrics}
    mad={k:max(1,1.4826*np.median(np.abs(np.array([r[k] for r in records])-med[k]))) for k in metrics}
    ordered=sorted(records,key=lambda r:sum(((r[k]-med[k])/mad[k])**2 for k in metrics))
    out={
       "schema":"fhs-age-4049-male-source-sagittal-cohort-v1",
       "scientificSource":"https://zenodo.org/records/18259702",
       "sourceCohort":"Male/Age4049 from FHS ZIP, all available 25 individual models",
       "subjectModelsAnalyzed":len(records),
       "failedModels":fail,
       "currentModel":current,
       "sourceSpinalFrameDistributions":distribution,
       "closestToCohortMedians":[{"model":r["model"],
         "T1AnteriorToPelvisMm":r["T1AnteriorToPelvisMm"],
         "thoracicSagittalChordAngleFromVerticalDeg":r["thoracicSagittalChordAngleFromVerticalDeg"],
         "lumbarSagittalChordAngleFromVerticalDeg":r["lumbarSagittalChordAngleFromVerticalDeg"]} for r in ordered[:6]],
       "allSubjects":records,
       "clinicalNormalitySupported":False,
       "modelReplacementRecommendedAutomatically":False,
       "warnings":[
         "Cohort median does not mean clinically neutral spine or healthy spinal curvature",
         "Only age/sex peer FHS models compared, not whole-population normative data",
         "Sagittal chord angle between vertebral body frames is not a radiographic Cobb angle",
         "Source FHS body frames only; no human posture photos or measured clinical landmarks",
         "No changes to the current scene or original muscle attachments are authorized by these measures",
       ],
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("FHS_GROUP_COMPARISON",json.dumps({
       "sampleSize":len(records),"errors":len(fail),
       "current":current,
       "ranks":{k:v["currentPercentileRank"] for k,v in distribution.items()},
       "peerMedian":{k:v["median"] for k,v in distribution.items()},
       "candidateByMedian":out["closestToCohortMedians"][:3]},ensure_ascii=False))
if __name__=="__main__":main()
