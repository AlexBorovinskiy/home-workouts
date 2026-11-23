#!/usr/bin/env python3
"""Inspect original Cazzola et al. MASI v2 research archive without modifying FHS.

Publisher source: https://doi.org/10.6084/m9.figshare.4249808.v2
This first step only inventories Figshare datasets and their archive contents.
No published mesh or model is copied to our site until license and native
OpenSim compatibility are verified.
"""
from __future__ import annotations
import json
import os
import pathlib
import urllib.request
import zipfile
import tempfile

ARTICLE_ID=4249808
VERSION=2
API=f"https://api.figshare.com/v2/articles/{ARTICLE_ID}/versions/{VERSION}"
OUT=pathlib.Path(os.environ.get("MASI_REPORT_PATH","/tmp/masi-inventory.json"))
MAX_DOWNLOAD_MB=int(os.environ.get("MASI_DOWNLOAD_LIMIT_MB","200"))

def get_json(url):
    req=urllib.request.Request(url,headers={"User-Agent":"home-workouts-OpenSim-research/1.0","Accept":"application/json"})
    with urllib.request.urlopen(req, timeout=55) as response:
        return json.load(response)

def get_zip_entries(item):
    url=item["download_url"]
    if item["size"]>MAX_DOWNLOAD_MB*1024*1024:
        return {"status":"not-downloaded-over-limit","limitMb":MAX_DOWNLOAD_MB}
    with tempfile.NamedTemporaryFile(suffix=pathlib.Path(item["name"]).suffix or ".bin") as tmp:
        req=urllib.request.Request(url,headers={"User-Agent":"home-workouts-OpenSim-research/1.0"})
        with urllib.request.urlopen(req,timeout=130) as response:
            while True:
                chunk=response.read(1024*1024)
                if not chunk:break
                tmp.write(chunk)
        tmp.flush()
        if not zipfile.is_zipfile(tmp.name):
            return {"status":"not-zip-file","sizeBytes":os.stat(tmp.name).st_size}
        with zipfile.ZipFile(tmp.name) as archive:
            infos=[dict(name=x.filename,size=x.file_size) for x in archive.infolist() if not x.is_dir()]
        kinds={ext:sum(1 for x in infos if x["name"].lower().endswith(ext))
               for ext in (".osim",".vtp",".obj",".stl",".wrl",".mot",".trc",".xml")}
        return {"status":"zip-inventoried","totalEntries":len(infos),
                "kinds":kinds,"relevantFiles":[x for x in infos if
                 x["name"].lower().endswith((".osim",".vtp",".obj",".stl",".wrl",".mot",".trc",".xml"))][:100],
                "sampleOtherFiles":infos[:35]}

def main():
    try:
        data=get_json(API)
        endpoint=API
    except Exception as e:
        print("MASI_VERSION_API_WARNING",repr(e))
        endpoint=f"https://api.figshare.com/v2/articles/{ARTICLE_ID}"
        data=get_json(endpoint)
    files=data.get("files",[])
    if not files:files=get_json(f"https://api.figshare.com/v2/articles/{ARTICLE_ID}/versions/{VERSION}/files")
    report={"researchModel":"MASI","publisher":"Figshare",
      "doi":"10.6084/m9.figshare.4249808.v2",
      "articleId":ARTICLE_ID,"version":VERSION,"apiEndpoint":endpoint,
      "title":data.get("title"),"license":data.get("license"),
      "files":[{"id":f.get("id"),"name":f.get("name"),"size":f.get("size"),
                "download_url":f.get("download_url"),"is_link_only":f.get("is_link_only")}
               for f in files],
      "archives":[],"nativeOpenSimLoaded":False,
      "FHSmodelModified":False,
      "notes":"Source inventory only; no anatomical correctness, model compatibility or right to redistribute implied."}
    for item in files:
        if item["name"].lower().endswith((".zip",".7z",".rar")):
            record=get_zip_entries(item) if item["name"].lower().endswith(".zip") else {"status":"unsupported-archive-type"}
            report["archives"].append({"file":item["name"],"inspection":record})
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print("MASI_DATASET_INVENTORY "+json.dumps(report,ensure_ascii=False,separators=(",",":")))
if __name__=="__main__":
    main()
