"""Run the persistent station using a prebuilt descriptor."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'sw/pi'), str(ROOT/'sw/interfaces/python')]

if __name__ == '__main__':
    from groundlark.station import main
    main()
