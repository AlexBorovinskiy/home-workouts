"""Multi-coordinate diagnostic trajectories, native OpenSim at every frame.
Targets are synthetic, not measured exercises or contact-constrained motion.
"""
import argparse, pathlib, math, json, xml.etree.ElementTree as ET
import numpy as np
import opensim as osim

def main():
    p=argparse.ArgumentParser();p.add_argument('model',type=pathlib.Path);p.add_argument('out',type=pathlib.Path);a=p.parse_args()
    m=osim.Model(str(a.model));initial=m.initSystem();m.assemble(initial);m.realizePosition(initial)
    js=m.getJointSet();cs=m.getCoordinateSet();bs=m.getBodySet()
    names=[js.get(i).getName() for i in range(js.getSize())]
    bodies=[bs.get(i).getName() for i in range(bs.getSize())]
    dependent={e.text.strip() for e in ET.parse(a.model).getroot().find('Model').findall('./ConstraintSet/objects/*/dependent_coordinate_name') if e.text}
    def snapshot(s):
        def pt(f):
            t=f.getTransformInGround(s);return [round(float(t.p()[k]),6) for k in range(3)]
        return {'points':[pt(js.get(i).getChildFrame()) for i in range(js.getSize())],
                'bodies':[pt(bs.get(i)) for i in range(bs.getSize())],
                'rotations':[[[round(float(bs.get(i).getTransformInGround(s).R().get(k,l)),7) for l in range(3)] for k in range(3)] for i in range(bs.getSize())]}
    def target(name,degrees):
        q=cs.get(name)
        assert not q.getLocked(initial) and name not in dependent,name
        start=float(q.getValue(initial));goal=math.radians(degrees)
        lo,hi=float(q.getRangeMin()),float(q.getRangeMax())
        goal=min(hi,max(lo,goal))
        return q,start,goal
    both=lambda suffix,deg:{side+'_'+suffix:deg for side in ('ra','la')}
    grip={}
    for side in ('ra','la'):
        for i in range(2,6):
            for j,v in [('mcp',62),('pip',82),('dip',54)]:grip[f'{side}_{j}{i}_e_f']=v
        for k,v in [('mcp1_e_f',25),('ip1_e_f',38),('cmc1_f_e',15),('cmc1_opp',20),('cmc1_ad_ab',10)]:grip[side+'_'+k]=v
    pronation={}
    for side in ('ra','la'):
        q=cs.get(side+'_wr_sup_pro');v=float(q.getValue(initial))
        end=max([float(q.getRangeMin()),float(q.getRangeMax())],key=lambda x:abs(x-v))
        pronation[q.getName()]=math.degrees(end)
    plans=[
        ('pronation','Поворот предплечий (пронация / супинация)',pronation),
        ('arms','Подъём обеих рук',both('sh_elv',85)),
        ('curl','Сгибание обеих рук',{**both('el_e_f',95),**both('wr_sup_pro',0),**grip}),
        ('grip','Сжатие обеих кистей',grip),
        ('legs','Сгибание ног (без опоры)',{f'{q}_{s}':v for s in ('r','l') for q,v in [('hip_flexion',45),('knee_angle',65),('ankle_angle',10)]}),
        ('combined','Одновременное движение рук и ног',{**both('sh_elv',55),**both('el_e_f',75),**{f'{q}_{s}':v for s in ('r','l') for q,v in [('hip_flexion',30),('knee_angle',45)]}}),
    ]
    baseline=snapshot(initial);out=[];rejected=[]
    for ident,label,plan in plans:
        try:
            qs={n:target(n,v) for n,v in plan.items()}
            qs={n:t for n,t in qs.items() if abs(t[2]-t[1])>1e-4}
            assert len(qs)>=2
            frames=[]
            for i in range(31):
                u=(1-math.cos(math.pi*i/30))/2
                s=osim.State(initial)
                desired={n:b+(g-b)*u for n,(_,b,g) in qs.items()}
                for n,(q,_,_) in qs.items():q.setValue(s,desired[n],False)
                m.assemble(s);m.realizePosition(s)
                err=max(abs(float(q.getValue(s))-desired[n]) for n,(q,_,_) in qs.items())
                assert err<1e-4,(ident,i,err)
                snap=snapshot(s)
                assert np.isfinite(snap['points']).all() and np.isfinite(snap['bodies']).all()
                snap['u']=u;snap['errorRad']=err;frames.append(snap)
            shift=float(np.max(np.linalg.norm(np.array(frames[-1]['points'])-np.array(baseline['points']),axis=1)))
            assert shift>.001
            if ident=='pronation':
                for side in ('RA','LA'):
                    ui,ri=bodies.index(side+'2U'),bodies.index(side+'2R')
                    def rel(f):return np.array(f['rotations'][ui]).T@np.array(f['rotations'][ri])
                    change=np.linalg.norm(rel(frames[0])-rel(frames[-1]))
                    assert change>.1, (side,'no relative radius rotation',change)
            out.append({'id':ident,'label':label,'targets':{n:{'start':b,'end':g} for n,(_,b,g) in qs.items()},'frames':frames,'maxShiftM':shift})
        except Exception as e:rejected.append({'id':ident,'reason':str(e)})
    assert len(out)>=2 and any(x['id']=='pronation' for x in out),rejected
    result={'schema':'native-coordinated-diagnostics-v1','jointNames':names,'bodyNames':bodies,'sequences':out,'rejected':rejected,'limitations':'Synthetic diagnostic targets; no floor contact, balance, load, or anatomical registration validation.'}
    a.out.write_text(json.dumps(result,separators=(',',':'),ensure_ascii=False,allow_nan=False))
    print('COORDINATED_QA',[(x['id'],len(x['targets']),len(x['frames'])) for x in out], 'REJECTED',rejected)
if __name__=='__main__':main()
