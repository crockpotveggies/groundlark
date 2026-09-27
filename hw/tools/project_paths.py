"""Product ownership and paths shared by hardware tools and the portable lab."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
PRODUCTS = {
    'groundlark-daqhat-01': 'groundlark-fpga-hat',
    'groundlark-hat': 'groundlark-coldfoot-hat',
    'groundlark-field-head': 'burrowlark-usb',
    'skylark-usb': 'skylark-usb',
}
TARGETS = {
    'trenz_hat': 'groundlark-daqhat-01',
    'hat': 'groundlark-hat',
    'field_head': 'groundlark-field-head',
    'skylark': 'skylark-usb',
}


def product_dir(board, root=ROOT):
    return root / 'hw' / PRODUCTS[board]


def board_dir(board, root=ROOT):
    return product_dir(board, root) / 'boards' / board


def compiled_dir(target, root=ROOT):
    return product_dir(TARGETS[target], root) / 'layout' / target


def placement_path(board, root=ROOT):
    return product_dir(board, root) / 'layout' / 'placement.json'


def load_layout(*boards, root=ROOT):
    """Read independent placement inputs without recreating a shared master file."""
    result = {}
    for board in boards or PRODUCTS:
        data = json.loads(placement_path(board, root).read_text())
        if set(data) != {board}:
            raise ValueError(f'Unexpected board in {placement_path(board, root)}')
        result.update(data)
    return result
