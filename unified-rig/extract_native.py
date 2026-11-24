"""Extract native joint mechanisms without meshes or invented axes."""
import argparse, json, pathlib, hashlib, xml.etree.ElementTree as ET
import opensim as osim

def extract(path):
    model=osim.Model(str(path))
    state=model.initSystem()
    model.assemble(state)
    model.realizePosition(state)
    normalized=path.with_suffix('.normalized.osim')
    model.printToXML(str(normalized))
    root=ET.parse(normalized).getroot().find('Model')
    def xml(e): return ET.tostring(e,encoding='unicode')
    def transform(frame):
        t=frame.getTransformInGround(state)
        return {'p':[float(t.p()[i]) for i in range(3)],
                'R':[[float(t.R().get(i,j)) for j in range(3)] for i in range(3)]}
    joints=model.getJointSet()
    coords=model.getCoordinateSet()
    result={'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'model':model.getName(),'units':'m, rad','joints':[],
            'coordinates':[], 'constraints':[], 'bodies':[]}
    definitions={e.get('name'):e for e in root.findall('./JointSet/objects/*')}
    for i in range(joints.getSize()):
        j=joints.get(i)
        p,c=j.getParentFrame(),j.getChildFrame()
        result['joints'].append({'name':j.getName(),'type':j.getConcreteClassName(),
            'parent':p.findBaseFrame().getName(),'child':c.findBaseFrame().getName(),
            'parent_world':transform(p),'child_world':transform(c),
            'native_xml':xml(definitions[j.getName()])})
    for i in range(coords.getSize()):
        q=coords.get(i)
        result['coordinates'].append({'name':q.getName(),'default':q.getDefaultValue(),
            'range':[q.getRangeMin(),q.getRangeMax()],
            'locked':bool(q.getLocked(state)), 'clamped':bool(q.getClamped(state))})
    bodies=model.getBodySet()
    for i in range(bodies.getSize()):
        b=bodies.get(i)
        result['bodies'].append({'name':b.getName(),'world':transform(b)})
    result['constraints']=[xml(e) for e in root.findall('./ConstraintSet/objects/*')]
    result['counts']={k:len(result[k]) for k in ('bodies','joints','coordinates','constraints')}
    assert result['counts']['joints']>0
    assert len({j['name'] for j in result['joints']})==len(result['joints'])
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--out',required=True,type=pathlib.Path)
    p.add_argument('sources',nargs='+')
    a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    for entry in a.sources:
        name,path=entry.split('=',1)
        d=extract(pathlib.Path(path))
        (a.out/(name+'.json')).write_text(json.dumps(d,indent=2,allow_nan=False))
        print(name,d['counts'])
