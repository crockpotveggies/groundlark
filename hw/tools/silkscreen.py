"""Place the monochrome Groundlark mark as board graphics, without BOM parts."""
from pathlib import Path
import pcbnew as p
from kicad_support import v

ROOT = Path(__file__).resolve().parents[2]
LOGO_CENTER = (94.5, 100.7)
MODEL_CENTER = (94.5, 104.8)


def add_logo(board, center=LOGO_CENTER):
    footprint = p.FootprintLoad(str(ROOT / 'hw/shared/libraries/Groundlark.pretty'), 'Logo_Groundlark_7mm')
    if footprint is None:
        raise RuntimeError('Missing Groundlark silkscreen artwork')
    for previous in list(board.Groups()):
        if previous.GetName() == 'Groundlark silkscreen':
            for item in list(previous.GetItems()):
                previous.RemoveItem(item)
                board.Delete(item)
            board.Delete(previous)
    group = p.PCB_GROUP(board)
    group.SetName('Groundlark silkscreen')
    board.Add(group)
    for graphic in footprint.GraphicalItems():
        shape = p.PCB_SHAPE(board)
        shape.SetShape(p.SHAPE_T_POLY)
        shape.SetPolyShape(graphic.GetPolyShape())
        shape.SetFilled(True)
        shape.SetWidth(0)
        shape.SetLayer(p.F_SilkS)
        shape.Move(v(*center))
        board.Add(shape)
        group.AddItem(shape)
