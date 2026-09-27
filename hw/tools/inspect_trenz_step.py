from pathlib import Path
from OCP.STEPControl import STEPControl_Reader
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
root=Path(__file__).resolve().parents[2]
r=STEPControl_Reader();r.ReadFile(str(root/'hw/shared/models/trenz/STP-TE0712-03-No Variations.step'));r.TransferRoots()
e=TopExp_Explorer(r.OneShape(),TopAbs_SOLID);rows=[]
while e.More():
    b=Bnd_Box();BRepBndLib.Add_s(e.Current(),b);a=b.CornerMin().Coord();c=b.CornerMax().Coord();d=[c[i]-a[i] for i in range(3)];rows.append((d[0]*d[1]*d[2],a,c));e.Next()
for row in sorted(rows,reverse=True)[:14]:print(row)
