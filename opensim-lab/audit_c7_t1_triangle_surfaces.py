#!/usr/bin/env python3
"""Surface geometry C7 MASI vs T1 FHS: diagnostics only.

Computes exact vertex-to-triangle (within numerical tolerance) proximity
and non-coplanar triangle edge intersections in the registered static pose.
No cartilage, facets, forces, CT landmarks, muscular attachments or dynamic
reliability can be inferred. Coplanar overlap and fully enclosed meshes are
not exhaustively detected by the edge-intersection algorithm.
"""
from __future__ import annotations
import argparse
import json
import pathlib
import xml.etree.ElementTree as ET
import zipfile

import numpy as np

SCALES = [1.0, .88875]


def load_vtp(data: bytes):
    root = ET.fromstring(data)
    piece = root.find("./PolyData/Piece")
    if piece is None:
        raise ValueError("VTP missing PolyData/Piece")
    pts = piece.find("./Points/DataArray")
    if pts is None or pts.get("format", "ascii").lower() != "ascii":
        raise ValueError("Expected ASCII VTP")
    v = np.fromstring(pts.text or "", sep=" ", dtype=np.float64).reshape((-1, 3))
    polys = piece.find("Polys")
    if polys is None:
        raise ValueError("Polys missing from VTP")
    arrays = polys.findall("DataArray")
    def get_array(name, fallback):
        arr = next((a for a in arrays if a.get("Name") == name), None)
        if arr is None:
            arr = arrays[fallback]
        if arr.get("format", "ascii").lower() != "ascii":
            raise ValueError("Expected ASCII face list")
        return np.fromstring(arr.text or "", sep=" ", dtype=np.int64)
    conn, offs = get_array("connectivity", 0), get_array("offsets", 1)
    if not len(v) or not len(offs) or offs[-1] != len(conn):
        raise ValueError("Invalid vertex count or polygon offsets")
    faces = []
    last = 0
    for end in offs:
        poly = conn[last:int(end)]
        if len(poly) < 3:
            raise ValueError("Degenerate polygon in VTP")
        for j in range(1, len(poly) - 1):
            faces.append([int(poly[0]), int(poly[j]), int(poly[j+1])])
        last = int(end)
    faces = np.array(faces, dtype=np.int64)
    if not len(faces) or np.min(faces) < 0 or np.max(faces) >= len(v):
        raise ValueError("Invalid triangulated indices")
    return v, faces


def transform_points(verts, R, position):
    return verts @ np.asarray(R, dtype=np.float64).T + np.asarray(position, dtype=np.float64)


def closest_to_triangles(query, vertices, faces):
    """Find exact closest points from mesh vertices to finite triangles.

    Projection-to-plane if within face; otherwise closest among 3 triangle
    segments. Returns minimum distance and sample nearest pair in metres.
    """
    triangles = vertices[faces]  # (F,3,3)
    aa, bb, cc = triangles[:,0,:], triangles[:,1,:], triangles[:,2,:]
    ab, ac = bb-aa, cc-aa
    face_norm = np.cross(ab, ac)
    n2 = np.einsum("ij,ij->i", face_norm, face_norm)
    good = n2 > 1e-23
    if not np.any(good):
        raise ValueError("All triangles degenerate")
    q = query[:,None,:]
    proj = q-aa[None,:,:]
    dot00 = np.einsum("ij,ij->i", ab, ab)
    dot01 = np.einsum("ij,ij->i", ab, ac)
    dot11 = np.einsum("ij,ij->i", ac, ac)
    dot20 = np.einsum("vfi,fi->vf", proj, ab)
    dot21 = np.einsum("vfi,fi->vf", proj, ac)
    denom = dot00*dot11-dot01*dot01
    safe_denom = np.where(good & (np.abs(denom)>1e-23), denom, 1.0)
    u = (dot11*dot20-dot01*dot21)/safe_denom
    v = (dot00*dot21-dot01*dot20)/safe_denom
    in_face = good[None,:] & (u>=-1e-10) & (v>=-1e-10) & (u+v<=1.0000000001)
    projected = aa[None,:,:]+u[:,:,None]*ab[None,:,:]+v[:,:,None]*ac[None,:,:]
    best = np.full((len(query),len(faces)), np.inf)
    best_points = np.zeros((len(query),len(faces),3), dtype=np.float64)
    face_dist = np.sum((q-projected)**2,axis=2)
    best = np.where(in_face,face_dist,best)
    best_points = np.where(in_face[:,:,None],projected,best_points)
    for start,end in ((aa,bb),(bb,cc),(cc,aa)):
        edge = end-start
        e2 = np.sum(edge*edge,axis=1)
        safe = np.where(e2>1e-23,e2,1.)
        ts = np.clip(np.einsum("vfi,fi->vf",q-start[None,:,:],edge)/safe[None,:],0.,1.)
        point = start[None,:,:]+ts[:,:,None]*edge[None,:,:]
        d2 = np.sum((q-point)**2,axis=2)
        mask = d2<best
        best = np.where(mask,d2,best)
        best_points = np.where(mask[:,:,None],point,best_points)
    flat = int(np.argmin(best))
    vi,fi=np.unravel_index(flat,best.shape)
    per_vertex=np.sqrt(np.min(best,axis=1))
    return {"minimumM":float(np.sqrt(best[vi,fi])),
            "near5mmVertices":int(np.count_nonzero(per_vertex<=.005)),
            "near2mmVertices":int(np.count_nonzero(per_vertex<=.002)),
            "queryVertex":int(vi),"targetFace":int(fi),
            "queryPositionM":query[vi].tolist(),
            "nearestSurfacePositionM":best_points[vi,fi].tolist()}


def edge_hits_triangle(p, q, a, b, c):
    """Möller–Trumbore segment/triangle hit in metres (non-coplanar)."""
    direction=q-p
    e1=b-a
    e2=c-a
    h=np.cross(direction,e2)
    determinant=float(np.dot(e1,h))
    if abs(determinant)<1e-13:
        return None
    inverse=1/determinant
    s=p-a
    u=inverse*float(np.dot(s,h))
    if u<-1e-9 or u>1+1e-9:
        return None
    k=np.cross(s,e1)
    v=inverse*float(np.dot(direction,k))
    if v<-1e-9 or u+v>1+1e-9:
        return None
    t=inverse*float(np.dot(e2,k))
    if t<-1e-9 or t>1+1e-9:
        return None
    return (p+t*direction).tolist()


def intersect_faces(vertices_a, faces_a, vertices_b, faces_b):
    """Broad-phase triangle AABB; then 6 segment-triangle tests per pair."""
    a=vertices_a[faces_a]
    b=vertices_b[faces_b]
    a_min,a_max=np.min(a,axis=1),np.max(a,axis=1)
    b_min,b_max=np.min(b,axis=1),np.max(b,axis=1)
    candidate=(np.all(a_min[:,None,:]<=b_max[None,:,:]+1e-10,axis=2)&
               np.all(b_min[None,:,:]<=a_max[:,None,:]+1e-10,axis=2))
    pairs=np.argwhere(candidate)
    hit_pairs=[]
    hit_points=[]
    for i,j in pairs:
        ta,tb=a[i],b[j]
        hit=None
        for k in range(3):
            hit=edge_hits_triangle(ta[k],ta[(k+1)%3],*tb)
            if hit is not None:
                break
        if hit is None:
            for k in range(3):
                hit=edge_hits_triangle(tb[k],tb[(k+1)%3],*ta)
                if hit is not None:
                    break
        if hit is not None:
            hit_pairs.append([int(i),int(j)])
            hit_points.append(hit)
    return {
        "aabbCandidateTrianglePairs":int(len(pairs)),
        "nonCoplanarEdgeIntersectingTrianglePairs":len(hit_pairs),
        "samplePairs":hit_pairs[:20],
        "samplePointsM":hit_points[:20],
        "limitation":"Intersection test does not fully detect coplanar triangle overlap, exact enclosed meshes, or volume penetration"
    }


def analyze(c7_local, c7_faces, t1_local, t1_faces, registration):
    joint=np.array(registration["jointConnections"]["masi"]["parentOriginM"],dtype=np.float64)
    c7frame=registration["masiC7Frame"]
    c7world=transform_points(c7_local,c7frame["rotation"],c7frame["positionM"])
    t1frame=registration["fhsVertebralFrames"]["thoracic1"]
    fhs_scale=np.array(registration["fhsT1Mesh"]["scale"],dtype=np.float64)
    t1world=transform_points(t1_local*fhs_scale,t1frame["registeredRotation"],t1frame["registeredPositionM"])
    out=[]
    for scale in SCALES:
        verts=(c7world-joint)*scale+joint
        from_c7=closest_to_triangles(verts,t1world,t1_faces)
        from_t1=closest_to_triangles(t1world,verts,c7_faces)
        contact=intersect_faces(verts,c7_faces,t1world,t1_faces)
        if from_c7["minimumM"]<=from_t1["minimumM"]:
            minimum=from_c7["minimumM"]
            sample={"c7PointM":from_c7["queryPositionM"],
                    "t1PointM":from_c7["nearestSurfacePositionM"]}
        else:
            minimum=from_t1["minimumM"]
            sample={"c7PointM":from_t1["nearestSurfacePositionM"],
                    "t1PointM":from_t1["queryPositionM"]}
        out.append({
            "c7VisualScale":scale,
            "vertexToTriangleMinMm":round(minimum*1000,5),
            "possibleSurfaceIntersection":bool(contact["nonCoplanarEdgeIntersectingTrianglePairs"]),
            "testedTriangleCounts":{"C7":int(len(c7_faces)),"T1":int(len(t1_faces))},
            "C7VerticesNearT1Within5mm":from_c7["near5mmVertices"],
            "T1VerticesNearC7Within5mm":from_t1["near5mmVertices"],
            "C7VerticesNearT1Within2mm":from_c7["near2mmVertices"],
            "T1VerticesNearC7Within2mm":from_t1["near2mmVertices"],
            "exampleClosestPositions":sample,
            "triangleIntersection":contact,
        })
    return {
       "schema":"C7T1-triangle-surface-diagnostic-v1",
       "sourceRegistration":"MASI/FHS native 4.6 C7–T1 joints, single-joint registration",
       "units":"metres in positions, millimetres in distances",
       "trials":out,
       "medicalInterpretation":"NOT verified facet joint contact; triangles are unannotated rendering meshes, cartilage/ligaments absent",
       "validatedAnatomicalLandmarks":False,
       "facetsSegmented":False,
       "jointKinematicsUpdated":False,
       "isValidatedHybrid":False,
       "methodLimitations":["Positive triangle intersections mean possible mesh self-penetration at this model pose; no anatomical facet inference",
          "Zero intersection count does NOT guarantee no overlap due to coplanar and containment cases",
          "Point-to-triangle minima are geometric nearest approaches anywhere on the vertebrae, not necessarily articulating surfaces",
          "Visual scaled trial is pivot-anchored, native OpenSim joint centers and masses not recalculated"],
    }


def main():
    parser=argparse.ArgumentParser()
    for k in ("registration","fhs-archive","masi-c7-vtp","output"):
        parser.add_argument("--"+k,required=True)
    args=parser.parse_args()
    reg=json.loads(pathlib.Path(args.registration).read_text())
    assert reg["schema"]=="masi-fhs-C7-T1-registration-diagnostic-v1"
    with zipfile.ZipFile(args.fhs_archive) as z:
        mesh=reg["fhsT1Mesh"]["file"]
        paths=[n for n in z.namelist() if n.endswith("/Geometry/"+mesh)]
        if len(paths)!=1:
            raise ValueError("Missing unique T1 VTP from scientific FHS archive")
        t1,t1faces=load_vtp(z.read(paths[0]))
    c7,c7faces=load_vtp(pathlib.Path(args.masi_c7_vtp).read_bytes())
    out=analyze(c7,c7faces,t1,t1faces,reg)
    target=pathlib.Path(args.output)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    for trial in out["trials"]:
        print("C7T1_TRIANGLE_SURFACE_RESULT",json.dumps({
            "scale":trial["c7VisualScale"],
            "nearSurfaceMm":trial["vertexToTriangleMinMm"],
            "intersectingTrianglePairs":trial["triangleIntersection"]["nonCoplanarEdgeIntersectingTrianglePairs"],
            "near5mmC7Vertices":trial["C7VerticesNearT1Within5mm"],
            "near5mmT1Vertices":trial["T1VerticesNearC7Within5mm"]
        }))


if __name__=="__main__":
    main()
