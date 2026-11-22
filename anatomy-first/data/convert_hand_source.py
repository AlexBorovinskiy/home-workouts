#!/usr/bin/env python3
"""Inspect and separate exact research STL mesh using shared vertices, not guessed shapes.

Source: HegdeUSA/Hand_template/3D_model_of_segmented_bones.zip
The source's anatomical labels are NOT inferred here. Distinct connected
components receive neutral segment_N names pending osteological validation.
"""
from __future__ import annotations
import sys,zipfile,struct,hashlib,json,pathlib
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

def convert(archive_path: str, output_dir: str) -> dict:
    source=pathlib.Path(archive_path)
    output=pathlib.Path(output_dir);output.mkdir(parents=True,exist_ok=True)
    original=source.read_bytes()
    source_hash=hashlib.sha256(original).hexdigest()
    with zipfile.ZipFile(source) as z:
        files=[n for n in z.namelist() if n.lower().endswith('.stl')]
        if len(files)!=1: raise ValueError(f'Expected exactly one STL in source ZIP, got {files}')
        raw=z.read(files[0])
    face_count=struct.unpack_from('<I',raw,80)[0]
    if len(raw)!=84+50*face_count:
        raise ValueError('Invalid binary STL length')
    dtype=np.dtype([('normal','<f4',(3,)),('vertices','<f4',(3,3)),('attribute','<u2')])
    triangles=np.frombuffer(raw, dtype=dtype, count=face_count,offset=84)
    source_vertices=np.ascontiguousarray(triangles['vertices']).reshape(-1,3)
    if not np.isfinite(source_vertices).all():
        raise ValueError('Non-finite STL coordinates')
    verts,inverse=np.unique(source_vertices,axis=0,return_inverse=True)
    faces=inverse.reshape(-1,3).astype(np.int32,copy=False)
    n=len(verts)
    edges=np.concatenate((faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]),axis=0)
    rows=edges[:,0];cols=edges[:,1]
    graph=coo_matrix((np.ones(len(edges),dtype=np.uint8),(rows,cols)),shape=(n,n)).tocsr()
    num,labels=connected_components(graph,directed=False)
    del graph,edges,rows,cols
    # Every triangle belongs to the component of its first vertex.
    tri_labels=labels[faces[:,0]]
    counts=np.bincount(tri_labels,minlength=num)
    ordering=np.argsort(counts)[::-1]
    global_bounds=np.array([verts.min(axis=0),verts.max(axis=0)])
    scale=.001 if np.max(global_bounds[1]-global_bounds[0])>1 else 1.
    center=np.mean(global_bounds,axis=0)
    report={
        'source':'https://github.com/HegdeUSA/Hand_template',
        'source_archive':'3D_model_of_segmented_bones.zip',
        'sha256':source_hash,
        'triangles':int(face_count),
        'unique_vertices':int(n),
        'connected_components':int(num),
        'component_sizes_desc':[int(counts[x]) for x in ordering[:80]],
        'bounds_original':global_bounds.tolist(),
        'units_heuristic':'mm_to_m' if scale==.001 else 'kept_original',
        'segments':[],
        'anatomical_names_validated':False
    }
    # A component is not an anatomically verified bone.
    min_triangles=100
    chosen=[int(i) for i in ordering if counts[i]>=min_triangles]
    report['substantial_components']=len(chosen)
    report['remaining_small_components']=int(num-len(chosen))
    report['faces_in_substantial_components']=int(sum(counts[i] for i in chosen))
    (output/'inspection.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
    print('COMPONENT_AUDIT',json.dumps({k:report[k] for k in ['triangles','unique_vertices','connected_components','substantial_components','component_sizes_desc','bounds_original']}))
    if not 15<=len(chosen)<=120:
        return report
    import trimesh
    scene=trimesh.Scene()
    palette=['#e4d7b8','#cfbd9a','#eadfca','#c7b5a3','#b5c8bc']
    for number,component_id in enumerate(chosen,1):
        selected=faces[tri_labels==component_id]
        unique_idxs,remap=np.unique(selected,return_inverse=True)
        local_faces=remap.reshape(-1,3)
        xyz=(verts[unique_idxs]-center)*scale
        mesh=trimesh.Trimesh(vertices=xyz,faces=local_faces,process=False)
        # Keep only source vertices/faces. No smoothing or geometric invention.
        rgb=tuple(bytes.fromhex(palette[(number-1)%len(palette)].lstrip('#')))
        mesh.visual.face_colors=np.array([*rgb,255],dtype=np.uint8)
        name=f'segment_{number:02d}_unlabeled'
        scene.add_geometry(mesh,node_name=name,geom_name=name)
        report['segments'].append({
            'id':name,'triangles':int(len(local_faces)),
            'bounds_m':mesh.bounds.round(6).tolist(),
            'centroid_m':mesh.centroid.round(6).tolist()
        })
    glb=scene.export(file_type='glb')
    (output/'research-hand-segments.glb').write_bytes(glb)
    report['glb_size_bytes']=len(glb)
    report['glb_sha256']=hashlib.sha256(glb).hexdigest()
    (output/'inspection.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
    print('GLB_REPORT',json.dumps({'segments':len(report['segments']),'bytes':len(glb),'sha256':report['glb_sha256']}))
    return report

if __name__=='__main__':
    if len(sys.argv)!=3: raise SystemExit('usage: convert_hand_source.py SOURCE.zip OUT_DIR')
    convert(sys.argv[1],sys.argv[2])
