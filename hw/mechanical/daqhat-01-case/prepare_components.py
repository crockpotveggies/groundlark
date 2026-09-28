"""Tessellate detailed, attributed Pi reference CAD without editing board inputs."""
import gzip
import hashlib
import json
from pathlib import Path

import cadquery as cq
import numpy as np
import trimesh
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TDocStd import TDocStd_Document
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDF import TDF_LabelSequence
from OCP.XCAFDoc import XCAFDoc_DocumentTool, XCAFDoc_ColorSurf, XCAFDoc_ColorGen
from OCP.Quantity import Quantity_ColorRGBA

ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'hw/shared/models/raspberrypi4'
CACHE=ROOT/'.local/case'


def main():
    CACHE.mkdir(parents=True,exist_ok=True)
    raw=gzip.decompress((SOURCE/'raspberry-pi-4b.step.gz').read_bytes())
    provenance=json.loads((SOURCE/'provenance.json').read_text())
    assert hashlib.sha256(raw).hexdigest()==provenance['sha256']
    step=CACHE/'raspberry-pi-4b.step';step.write_bytes(raw)
    reader=STEPCAFControl_Reader();reader.SetColorMode(True);reader.SetNameMode(True)
    reader.ReadFile(str(step))
    doc=TDocStd_Document(TCollection_ExtendedString('pi4'));reader.Transfer(doc)
    shapes=XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    colors=XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
    roots=TDF_LabelSequence();shapes.GetFreeShapes(roots)
    solids=[]
    for i in range(1,roots.Length()+1):
        solids.extend(cq.Shape.cast(shapes.GetShape_s(roots.Value(i))).Solids())
    scene=trimesh.Scene();colored_faces=0;triangles=0
    # Source has X along board length, Y above PCB, Z from -56 to 0.
    # Physical frame: (X, -Z-56, Y). This is a proper rotation, det=+1.
    rotation=np.array([[1,0,0],[0,0,-1],[0,1,0]],float)
    assert np.linalg.det(rotation)==1
    for i,solid in enumerate(solids):
        chunks=[];bb=solid.BoundingBox()
        fallback=(.025,.24,.08,1) if i==0 else (.15,.16,.17,1)
        for face in solid.Faces():
            color=Quantity_ColorRGBA();rgba=fallback
            for shape in (face.wrapped,solid.wrapped):
                if any(colors.GetColor(shape,kind,color) for kind in (XCAFDoc_ColorSurf,XCAFDoc_ColorGen)):
                    rgb=color.GetRGB();rgba=(rgb.Red(),rgb.Green(),rgb.Blue(),color.Alpha());colored_faces+=1;break
            vertices,faces=face.tessellate(.015,.08)
            if not faces:continue
            xyz=np.array([v.toTuple() for v in vertices])@rotation.T+np.array([0,-56,0])
            # glTF is Y-up. Blender reverses this proper rotation on import.
            gltf=xyz[:,[0,2,1]]*np.array([1,1,-1])
            mesh=trimesh.Trimesh(vertices=gltf,faces=faces,process=False)
            mesh.visual.face_colors=np.tile(np.clip(np.array(rgba)*255,0,255).astype(np.uint8),(len(faces),1))
            chunks.append(mesh);triangles+=len(faces)
        scene.add_geometry(trimesh.util.concatenate(chunks),node_name=f'Pi4-component-{i:03d}')
    output=SOURCE/'raspberry-pi-4b.glb';output.write_bytes(scene.export(file_type='glb'))
    report=dict(solids=len(solids),triangles=triangles,colored_faces=colored_faces,
                source_sha256=provenance['sha256'],image_model_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                coordinate_transform={'source_to_physical':[[1,0,0,0],[0,0,-1,-56],[0,1,0,0],[0,0,0,1]],'determinant':1},
                physical_board_bounds_mm=[[0,-56,-1.7],[85,0,.1]],
                source='Community reference; independent official drawing checks control orientation and port placement.')
    (SOURCE/'mesh-provenance.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
