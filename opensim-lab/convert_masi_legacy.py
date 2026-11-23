#!/usr/bin/env python3
"""In-memory XML name migration for published MASI OpenSim 3.2 -> 4.6 QA.

No anatomical positions, muscle parameters, frames, constraints or geometry are
manually modified. Preserve source unchanged in research downloads. This only
replaces OpenSim 4.6-forbidden characters from XML component attribute names
and updates literal XML text references.
"""
from __future__ import annotations
import argparse
import collections
import json
import pathlib
import re
import xml.etree.ElementTree as ET

FORBIDDEN=re.compile(r"[\*+/\s]")

def migrate(source,dest):
    tree=ET.parse(source)
    root=tree.getroot()
    named=collections.Counter(el.get("name") for el in root.iter() if el.get("name"))
    replacements={}
    for name in named:
        cleaned=FORBIDDEN.sub("_",name)
        if cleaned!=name:replacements[name]=cleaned
    if len(replacements.values())!=len(set(replacements.values())):
        raise AssertionError("Name collision after conversion")
    for el in root.iter():
        old=el.get("name")
        if old in replacements:el.set("name",replacements[old])
        for key,value in el.attrib.items():
            if key=="name":continue
            if value in replacements:el.set(key,replacements[value])
        if el.text:
            # In old OpenSim XML references may refer by name through text fields.
            # Replacing all literal occurrences is intentional, and reported.
            text=el.text
            for old,repl in sorted(replacements.items(),key=lambda p:-len(p[0])):
                if old in text:text=text.replace(old,repl)
            if text!=el.text:el.text=text
    pathlib.Path(dest).parent.mkdir(parents=True,exist_ok=True)
    tree.write(dest,encoding="utf-8",xml_declaration=True)
    return {"renamedCount":len(replacements),"someRenames":list(replacements.items())[:40],
            "remainingForbidden":[el.get("name") for el in root.iter() if el.get("name") and FORBIDDEN.search(el.get("name"))]}
if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    j=migrate(args.source,args.output)
    print("MASI_LEGACY_NAME_MIGRATION "+json.dumps(j,ensure_ascii=False,separators=(",",":")))
