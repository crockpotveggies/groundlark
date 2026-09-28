"""Render the current CAD stack with a dimensioned, conceptual Racotech element.

Run in WSL/Linux with KiCad 9 Python and xvfb-run. Source boards are read-only;
the temporary visualization board/model live in .local/readme-render. No
manufacturing files are created. The Pi/socket are the existing stack envelope;
geophone terminals and lead dressing are illustrative, not fit qualification.
"""
import hashlib
import json
import math
from pathlib import Path
import subprocess
import pcbnew as p
from assembly_fit import PI_TOP

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'hw/groundlark-fpga-hat/boards/groundlark-daqhat-01/pi-trenz-stack-concept.kicad_pcb'
CACHE=ROOT/'.local/readme-render'
OUTPUT=ROOT/'docs/images/groundlark-stack-geophone.png'


def cylinder(a,b,r,color):
    # Explicit mesh: KiCad's VRML importer does not render Cylinder primitives.
    # Board Y is down; VRML Y is up. Model origin is the board's (50,50).
    delta=[v-u for u,v in zip(a,b)]; length=math.sqrt(sum(v*v for v in delta))
    d=[v/length for v in delta]
    def cross(u,v):return (u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
    u=cross(d,(1,0,0) if abs(d[0])<.9 else (0,1,0))
    norm=math.sqrt(sum(v*v for v in u));u=[v/norm for v in u];v=cross(d,u)
    count=64;points=[];faces=[]
    for centre in (a,b):
        for i in range(count):
            theta=i*2*math.pi/count
            points.append(' '.join(f'{(centre[j]+r*(u[j]*math.cos(theta)+v[j]*math.sin(theta))-(50,-50,0)[j])/2.54:.7f}' for j in range(3)))
    for i in range(count):
        k=(i+1)%count;faces.append(f'{i} {k} {k+count} {i+count} -1')
    faces.extend([' '.join(map(str,reversed(range(count))))+' -1',
                  ' '.join(map(str,range(count,count*2)))+' -1'])
    return (f'Shape {{ appearance Appearance {{ material Material {{ diffuseColor {color} '
            f'specularColor 0.25 0.25 0.25 shininess 0.4 }} }} geometry IndexedFaceSet {{ '
            f'creaseAngle 0.5 coord Coordinate {{ point [ {", ".join(points)} ] }} '
            f'coordIndex [ {", ".join(faces)} ] }} }}\n')


def main():
    CACHE.mkdir(parents=True,exist_ok=True)
    native=SOURCE.with_name('groundlark-daqhat-01.kicad_pcb')
    model_dir=ROOT/'hw/shared/models'
    inputs=[SOURCE,native,ROOT/'hw/groundlark-fpga-hat/layout/placement.json',Path(__file__),
            model_dir/'trenz/STP-TE0712-03-No Variations.step',
            model_dir/'Pi4_stack_concept.wrl',model_dir/'Pi_Megastar_2x20.wrl',
            model_dir/'Trenz_spacers.wrl',model_dir/'LSHM_50_4mm.wrl',model_dir/'LSHM_30_4mm.wrl']
    digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    before={f.relative_to(ROOT).as_posix():digest(f) for f in inputs}
    b=p.LoadBoard(str(SOURCE))
    # Resolve paths for this temporary board, which is outside the native CAD folder.
    for fp in b.GetFootprints():
        models=list(fp.Models())
        fp.Models().clear()
        for model in models:
            model.m_Filename=model.m_Filename.replace('${KIPRJMOD}',str(SOURCE.parent))
            fp.Models().push_back(model)
    # RGI-4.5Hz nominal body: diameter 25.4 mm, height 33 mm; same bottom plane as Pi.
    x,y,z=22,-83,PI_TOP-1.6
    body=cylinder((x,y,z),(x,y,z+33),12.7,'0.48 0.40 0.23')
    body+=cylinder((x,y,z+32.8),(x,y,z+33.7),12.35,'0.04 0.045 0.05')
    body+=cylinder((x,y,z),(x,y,z+.65),12.9,'0.57 0.52 0.35')
    for dx,color in [(-5,'0.62 0.025 0.015'),(5,'0.025 0.028 0.035')]:
        body+=cylinder((x+dx,y,z+33.7),(x+dx,y,z+37.5),.65,'0.7 0.7 0.65')
        # Two separate wire leads into the existing J90 plug envelope.
        points=[(x+dx,y,z+37.5),(x+dx,-90,9),(32+dx,-101,11),
                (43+dx,-120,7),(64.19+dx*.381,-118,3.6),(64.19+dx*.381,-108.9,3.6)]
        # Catmull-Rom interpolation gives the illustrative flexible lead a smooth path.
        smooth=[];extended=[points[0],*points,points[-1]]
        for index in range(1,len(extended)-2):
            pa,pb,pc,pd=extended[index-1:index+3]
            for step in range(8):
                t=step/8
                smooth.append(tuple(.5*((2*pb[j])+(-pa[j]+pc[j])*t+
                    (2*pa[j]-5*pb[j]+4*pc[j]-pd[j])*t*t+
                    (-pa[j]+3*pb[j]-3*pc[j]+pd[j])*t*t*t) for j in range(3)))
        smooth.append(points[-1])
        for a,end in zip(smooth,smooth[1:]):body+=cylinder(a,end,.5,color)
    wrl=CACHE/'racotech-geophone-concept.wrl'
    wrl.write_text('#VRML V2.0 utf8\n# Nominal geophone and illustrative leads; not supplier CAD.\n'+body)
    fp=p.FOOTPRINT(b);fp.SetReference('MODEL_GEOPHONE');fp.SetValue('Visualization only')
    fp.SetPosition(p.VECTOR2I(p.FromMM(50),p.FromMM(50)))
    fp.Reference().SetVisible(False);fp.Value().SetVisible(False);b.Add(fp)
    model=p.FP_3DMODEL();model.m_Filename=str(wrl);model.m_Show=True;fp.Models().push_back(model)
    render_board=CACHE/'readme-stack.kicad_pcb';p.SaveBoard(str(render_board),b)
    command=['xvfb-run','-a','kicad-cli','pcb','render','--width','2000','--height','1200',
             '--quality','high','--background','opaque','--floor','--rotate','305,0,30',
             '--zoom','.70','--pan','-1.1,0,0','--light-camera','.65','-o',str(OUTPUT),str(render_board)]
    subprocess.run(command,check=True)
    assert all(digest(ROOT/name)==value for name,value in before.items()),'Render modified source'
    provenance=dict(source_sha256=before,image_sha256=digest(OUTPUT),
        renderer=subprocess.check_output(['kicad-cli','version'],text=True).strip(),
        scope='Current routed HAT and vendor Trenz STEP; conceptual Pi, socket, spacers, Racotech can and leads.',
        geophone_nominal_mm=dict(diameter=25.4,height=33),
        limitations='Selected 8.5 mm Megastar J1 and two 8.51 mm SSQ risers, 28.06 mm nominal gap. Horizontal 1803280 header. Geophone terminals and lead dressing are illustrative; no physical fit approval.')
    OUTPUT.with_suffix('.json').write_text(json.dumps(provenance,indent=2)+'\n')
    print(OUTPUT)


if __name__=='__main__':main()
