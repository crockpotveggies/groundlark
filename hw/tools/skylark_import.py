"""Validate external SES placement against KiCad's DSN, then import copper.

KiCad 9 exports bottom-side DSN rotations in the mirrored Specctra convention.
The native snapshot uses KiCad angles. Normalize only after matching the original
DSN placement; never silently accept a moved or rotated router component.
"""
from pathlib import Path
import sexpdata as sx
import pcbnew as p
from project_paths import board_dir
from import_routes import child, children, main as import_copper

def main():
    folder=board_dir('skylark-usb');path=folder/'skylark-usb.ses'
    ses=sx.loads(path.read_text());dsn=sx.loads((folder/'skylark-usb.dsn').read_text().replace('(string_quote ")','(string_quote quote)').replace('[','__LB__').replace(']','__RB__'))
    if str(ses[1]).endswith('.native-full'):
        import_copper('skylark-usb');return
    def placements(tree):
        return {str(pl[1]):pl for c in children(child(tree,'placement'),'component') for pl in children(c,'place')}
    expected=placements(dsn);actual=placements(ses)
    assert set(expected)==set(actual)
    b=p.LoadBoard(str(folder/'skylark-usb.kicad_pcb'));fps={f.GetReference():f for f in b.GetFootprints()}
    # KiCad DSN declares explicit um coordinates; SES placement uses resolution.
    assert str(child(dsn,'unit')[1])=='um'
    sr=child(child(ses,'placement'),'resolution') if children(child(ses,'placement'),'resolution') else child(child(ses,'routes'),'resolution')
    assert str(sr[1])=='um'
    for ref,pl in actual.items():
        ep=expected[ref]
        assert str(ep[4])==str(pl[4])
        for i in (2,3):assert abs(float(ep[i])-float(pl[i])/float(sr[2]))<.101,(ref,ep,pl)
        assert abs((float(ep[5])-float(pl[5])+180)%360-180)<.001,(ref,ep,pl)
        pl[5]=fps[ref].GetOrientationDegrees()
    path.write_text(sx.dumps(ses)+'\n')
    import_copper('skylark-usb')

if __name__=='__main__':main()
