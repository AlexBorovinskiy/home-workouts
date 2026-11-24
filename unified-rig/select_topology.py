"""Select native mechanisms and check graph/constraint closure before registration."""
import json, pathlib, argparse, xml.etree.ElementTree as ET
def build(folder):
    modules={n:json.loads((folder/(n+'.json')).read_text()) for n in ('fhs','masi','legs','right','left')}
    selected=[]; constraints=[]; coords=set(); children=set()
    interfaces={'masi':('spine','thoracic1'),'right':('Thorax','sternum'),'left':('Thorax','sternum'),'legs':('pelvis','pelvis')}
    for n,d in modules.items():
        local=set()
        for j in d['joints']:
            c=j['child']
            keep= (not (c=='head_neck' or c.startswith(('clavicle_','scapula_','humerus_','ulna_','radius_','hand_','Abd'))) if n=='fhs' else
                   c.startswith('cerv') or c in ('skull','jaw') if n=='masi' else
                   c.startswith(('femur_','tibia_','patella_','talus_','calcn_','toes_')) if n=='legs' else c!='Thorax')
            if not keep: continue
            p=j['parent']
            if n in interfaces and p==interfaces[n][0]: p=interfaces[n][1]
            assert c not in children,c
            children.add(c)
            names={e.get('name') for e in ET.fromstring(j['native_xml']).findall('./coordinates/Coordinate')}
            assert not coords.intersection(names),coords.intersection(names)
            coords.update(names);local.update(names)
            selected.append({'source':n,'joint':j['name'],'parent':p,'child':c,'coordinates':sorted(names)})
        for s in d['constraints']:
            e=ET.fromstring(s)
            refs=set((e.findtext('independent_coordinate_names') or '').split()+ (e.findtext('dependent_coordinate_name') or '').split())
            if refs & local:
                assert refs<=local,(n,e.get('name'),refs-local)
                constraints.append({'source':n,'name':e.get('name'),'coordinates':sorted(refs)})
    reached={'ground'}
    pending=selected[:]
    while pending:
        ready=[j for j in pending if j['parent'] in reached]
        assert ready,('Disconnected or cyclic',pending)
        reached.update(j['child'] for j in ready)
        pending=[j for j in pending if j not in ready]
    return {'status':'topology-only; registration and combined OpenSim solve pending','joints':selected,'constraints':constraints,'counts':{'joints':len(selected),'coordinates':len(coords),'constraints':len(constraints)},'interfaces':interfaces,'source_hashes':{n:d['source_sha256'] for n,d in modules.items()}}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder',type=pathlib.Path);p.add_argument('out',type=pathlib.Path);a=p.parse_args()
    result=build(a.folder);a.out.write_text(json.dumps(result,indent=2));print(result['counts'])
