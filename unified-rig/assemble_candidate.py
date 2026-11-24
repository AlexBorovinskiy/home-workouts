"""Build a mesh-free native OpenSim candidate from selected joint definitions.
Registration is provisional: align donor base frames to target base frames.
No claim of anthropometric or anatomical calibration.
"""
import argparse, pathlib, json, copy, xml.etree.ElementTree as ET
import opensim as osim
from select_topology import build

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--inventory',type=pathlib.Path,required=True)
    p.add_argument('--out',type=pathlib.Path,required=True)
    p.add_argument('sources',nargs='+')
    a=p.parse_args()
    sources={n:ET.parse(pathlib.Path(v).with_suffix('.normalized.osim')).getroot().find('Model') for n,v in (x.split('=',1) for x in a.sources)}
    topo=build(a.inventory)
    root=ET.Element('OpenSimDocument',Version='40600')
    m=ET.SubElement(root,'Model',name='UnifiedRigCandidate')
    sets={k:ET.SubElement(ET.SubElement(m,k),'objects') for k in ('BodySet','JointSet','ConstraintSet')}
    interfaces=topo['interfaces']
    for j in topo['joints']:
        src=sources[j['source']]
        body=copy.deepcopy(next(e for e in src.findall('./BodySet/objects/Body') if e.get('name')==j['child']))
        # Keep inertial placeholders strictly for position realization.
        for tag in ('attached_geometry','WrapObjectSet','components'):
            for e in body.findall(tag): body.remove(e)
        mass=body.find('mass')
        if mass is not None and float(mass.text)<=0: mass.text='0.001'
        sets['BodySet'].append(body)
        joint=copy.deepcopy(next(e for e in src.findall('./JointSet/objects/*') if e.get('name')==j['joint']))
        if j['source'] in interfaces:
            old,new=interfaces[j['source']]
            if old!=new:
                for e in joint.iter():
                    if e.tag.startswith('socket_') and e.text and e.text.strip()=='/bodyset/'+old:
                        e.text='/bodyset/'+new
        sets['JointSet'].append(joint)
    for c in topo['constraints']:
        sets['ConstraintSet'].append(copy.deepcopy(next(e for e in sources[c['source']].findall('./ConstraintSet/objects/*') if e.get('name')==c['name'])))
    a.out.mkdir(parents=True,exist_ok=True)
    path=a.out/'candidate.osim'
    ET.ElementTree(root).write(path,encoding='utf-8',xml_declaration=True)
    model=osim.Model(str(path))
    state=model.initSystem()
    model.assemble(state)
    model.realizePosition(state)
    def pos(f):
        t=f.getTransformInGround(state)
        return [float(t.p()[i]) for i in range(3)]
    js=model.getJointSet()
    result={'status':'native position assembly only; interface registration provisional','joints':[
        {'name':js.get(i).getName(),'parent':pos(js.get(i).getParentFrame()),'child':pos(js.get(i).getChildFrame())} for i in range(js.getSize())],
        'counts':topo['counts'],'anatomicallyValidated':False,'targetHeightCalibrated':False}
    assert js.getSize()==topo['counts']['joints']
    (a.out/'candidate-report.json').write_text(json.dumps(result,indent=2,allow_nan=False))
    print('UNIFIED_POSITION_ASSEMBLY',result['counts'])
if __name__=='__main__': main()
