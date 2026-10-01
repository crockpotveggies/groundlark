"""Compile a validated, explicitly selected battery policy into a C header."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'pi'))
from groundlark.power_config import load_policy


def header(document):
    policy=load_policy(document)
    if policy is None: return 'static const power_policy board_policy={.enabled=false};\n'
    values=dict(shutdown_mv=round(policy.shutdown_v*1000),restart_mv=round(policy.restart_v*1000))
    for field in ('shutdown_confirm','restart_confirm','shutdown_timeout','minimum_off'):
        values[field+'_ms']=round(getattr(policy,field+'_s')*1000)
    return 'static const power_policy board_policy={.enabled=true,'+','.join(f'.{k}={v}' for k,v in values.items())+'};\n'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('configuration',type=Path);p.add_argument('output',type=Path)
    args=p.parse_args();data=header(json.loads(args.configuration.read_text()))
    with args.output.open('x') as stream:stream.write(data)
