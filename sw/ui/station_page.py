"""Deployed station view in the same NiceGUI app; acquisition lives elsewhere."""
from collections import deque
import json
import os
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from nicegui import ui, run


def request(route, value=None, binary=False):
    token=os.environ.get('GROUNDLARK_STATION_TOKEN','')
    if len(token)<32: raise ValueError('Station connection is not configured. Set GROUNDLARK_STATION_TOKEN on the UI service.')
    port=int(os.environ.get('GROUNDLARK_STATION_PORT','8765'))
    req=Request(f'http://127.0.0.1:{port}'+route,
                data=None if value is None else json.dumps(value,allow_nan=False).encode(),
                headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    try: response=urlopen(req,timeout=5)
    except HTTPError as exc:
        detail=exc.read(16384)
        try: reason=json.loads(detail)['error']
        except (ValueError,KeyError): reason=str(exc)
        raise ValueError(reason) from exc
    with response:
        data=response.read(64*1024*1024+1)
        if len(data)>64*1024*1024: raise ValueError('response exceeds bound')
        return data if binary else json.loads(data)


@ui.page('/station')
def station_page():
    traces={}
    busy=False
    inventory=()
    ui.dark_mode().enable()
    with ui.header().classes('items-center'):
        ui.label('Groundlark · Station').classes('text-xl')
        ui.link('Simulation and replay','/').classes('text-white')
    ui.label('Continuous acquisition is owned by the station service. Closing this page leaves it running.')
    error=ui.label().classes('text-red-400')
    connection_error=ui.label().classes('text-red-400')
    health=ui.label('Connecting…')
    storage=ui.label()
    cards=ui.column().classes('w-full')
    recording_options={}
    with ui.row().classes('items-center'):
        recordings=ui.select(recording_options,label='Completed recordings').classes('w-96')
        async def refresh_recordings():
            try:
                items=await run.io_bound(request,'/recordings')
                recordings.set_options({x['name']:f"{x['name']} · {x['bytes']/1024/1024:.2f} MiB"
                                        for x in items[-200:] if x['state']=='closed'})
            except Exception as exc: error.set_text(str(exc))
        ui.button('Refresh recordings',on_click=refresh_recordings)
        async def download():
            if not recordings.value: return
            try:
                data=await run.io_bound(request,'/recordings/'+recordings.value+'/data.ssrec',binary=True)
                ui.download(data,recordings.value+'.ssrec')
            except Exception as exc: error.set_text(str(exc))
        ui.button('Download SSREC',on_click=download)
    with ui.expansion('Station configuration').classes('w-full'):
        ui.label('Saving validates the configuration and restarts the station service. Capture is interrupted and a new session begins.')
        config=ui.textarea('Configuration JSON').classes('w-full').props('rows=12')
        async def load():
            try:
                config.set_value(json.dumps(await run.io_bound(request,'/configuration'),indent=2))
                error.set_text('')
            except Exception as exc:error.set_text(str(exc))
        async def save():
            try:
                await run.io_bound(request,'/configuration',json.loads(config.value))
                ui.notify('Configuration saved; station restarting')
            except Exception as exc:error.set_text(str(exc))
        with ui.row():
            ui.button('Load configuration',on_click=load)
            ui.button('Save and restart station',on_click=save)
    views={}
    async def control(name,enabled):
        try:await run.io_bound(request,'/control',dict(source=name,enabled=enabled))
        except Exception as exc:error.set_text(str(exc))
    async def update():
        nonlocal busy,inventory
        if busy:return
        busy=True
        try:
            status=await run.io_bound(request,'/status')
            connection_error.set_text('')
            health.set_text(f"{status['station_id']} · uptime {status['uptime_seconds']/3600:.2f} hours · physical qualification pending")
            disk=status['storage']
            storage.set_text(f"Storage {disk['recording_bytes']/1024**3:.2f} / {disk['budget_bytes']/1024**3:.2f} GiB · free {disk['free_bytes']/1024**3:.2f} GiB · interrupted sets {disk['interrupted']} · expired sets {disk['deleted_sets']}")
            current=tuple((s['name'],s['board'],s['mode']) for s in status['sources'])
            if current!=inventory:
                cards.clear();views.clear();traces.clear();inventory=current
            for source in status['sources']:
                name=source['name']
                if name not in views:
                    with cards:
                        with ui.card().classes('w-full'):
                            ui.label(f"{name} · {source['board']} · {source['mode'].upper()}").classes('text-lg')
                            label=ui.label()
                            rows=ui.table(columns=[dict(name=k,label=k.title(),field=k) for k in ('sensor','quality','value','age')],rows=[],row_key='sensor').classes('w-full')
                            chart=ui.echart({'animation':False,'xAxis':{'type':'category','data':[]},'yAxis':{'type':'value','name':'Raw ADC counts'},'series':[{'type':'line','data':[],'showSymbol':False}]}).classes('w-full h-48')
                            summary=ui.label()
                            alerts=ui.label().classes('text-amber-300 whitespace-pre-wrap')
                            with ui.row():
                                ui.button('Pause acquisition',on_click=lambda _,n=name:control(n,False))
                                ui.button('Resume acquisition',on_click=lambda _,n=name:control(n,True))
                            views[name]=(label,rows,chart,summary,alerts)
                            traces[name]=deque(maxlen=400)
                label,rows,chart,summary,alerts=views[name]
                label.set_text(f"{source['state']} · {source['samples']:,} samples · {source['missing']:,} missing · {source['known_dropped']:,} known dropped · {source['unknown_loss_batches']:,} batches with unknown loss · {source['restarts']} restarts · {source['error']}")
                rows.rows=[dict(sensor=sid,quality=p['quality'],value=str(p['primary']),age=f"{p['age_seconds']:.1f}s") for sid,p in source['latest'].items()];rows.update()
                point=source['latest'].get('9')
                chart.set_visibility(point is not None)
                if point:
                    key=(point['boot'],point['sequence'])
                    if not traces[name] or traces[name][-1][0]!=key:traces[name].append((key,point['primary'][0]))
                    chart.options['xAxis']['data']=[k[1] for k,v in traces[name]]
                    chart.options['series'][0]['data']=[v for k,v in traces[name]];chart.update()
                summary.set_text('Latest RSAM: '+json.dumps(source['summaries'][-1]) if source['summaries'] else 'No completed RSAM window')
                alerts.set_text('\n'.join(f"{e.get('sensor','Station')}: {e.get('detail','')}" for e in source['events'][-5:]))
        except Exception as exc:connection_error.set_text('Station unavailable: '+str(exc))
        finally:busy=False
    ui.timer(1,update)
    ui.timer(.1,refresh_recordings,once=True)
