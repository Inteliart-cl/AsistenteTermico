from __future__ import annotations

from dataclasses import dataclass, asdict
import numpy as np
import pandas as pd
from .data import Dataset

@dataclass(frozen=True)
class Rules:
    tolerance: float = 0.8
    event_minutes: float = 20.0
    critical_temperature: float = 22.0
    expected_seconds: float = 30.0
    gap_factor: float = 3.0
    curtain_tolerance: float = 5.0

    @property
    def max_gap(self):
        return self.expected_seconds * self.gap_factor

def _linear(frame, a, b, max_gap):
    """Linear interpolation only inside observed brackets no longer than max_gap."""
    n = len(a)
    if len(frame) < 2:
        return np.full(n, np.nan), np.full(n, np.nan)
    t = frame.time.astype('int64').to_numpy() / 1e9
    v = frame.value.to_numpy(dtype=float)
    mid = (a+b)/2
    i = np.searchsorted(t, mid, side='right') - 1
    j = np.clip(i, 0, len(t)-2)
    gap = t[j+1]-t[j]
    valid = (i>=0) & (i<len(t)-1) & (gap<=max_gap) & (a>=t[j]) & (b<=t[j+1])
    v0 = v[j] + (v[j+1]-v[j])*(a-t[j])/gap
    v1 = v[j] + (v[j+1]-v[j])*(b-t[j])/gap
    return np.where(valid,v0,np.nan), np.where(valid,v1,np.nan)

def _step(frame, a, b, max_gap):
    if frame.empty:
        return np.full(len(a),np.nan)
    t = frame.time.astype('int64').to_numpy()/1e9
    i = np.searchsorted(t,(a+b)/2,side='right')-1
    j = np.clip(i,0,len(t)-1)
    valid = (i>=0) & (b <= t[j]+max_gap)
    return np.where(valid,frame.value.to_numpy(dtype=float)[j],np.nan)

def _events(segments: pd.DataFrame, column: str, kind: str, minutes: float):
    events=[]
    current=None
    for row in segments.itertuples():
        active=bool(getattr(row,column))
        if active:
            if current is None:
                current=dict(tipo=kind,inicio=row.start,fin=row.end,segundos=row.seconds)
            elif current['fin']==row.start:
                current['fin']=row.end; current['segundos']+=row.seconds
            else:
                events.append(current)
                current=dict(tipo=kind,inicio=row.start,fin=row.end,segundos=row.seconds)
        elif current is not None:
            events.append(current); current=None
    if current is not None: events.append(current)
    for event in events:
        event['minutos']=event.pop('segundos')/60
        event['persistente']=event['minutos'] > minutes + 1e-8
        event['prioridad']='Alta' if kind=='Sobre 22 °C' else ('Media' if kind=='Sobre tolerancia' else 'Revisión')
    return events

def curtain_travel(frame: pd.DataFrame, max_gap: float, total_seconds: float) -> dict:
    # Distancia mínima observada: suma los movimientos entre registros cercanos.
    if len(frame) < 2:
        return {'meters': None, 'coverage_pct': 0.0, 'gaps': 0}
    elapsed = frame.time.diff().dt.total_seconds()
    delta = frame.value.diff().abs()
    valid = elapsed.gt(0) & elapsed.le(max_gap)
    return {
        'meters': float(delta[valid].sum()) / 100 if valid.any() else None,
        'coverage_pct': 100 * float(elapsed[valid].sum()) / total_seconds,
        'gaps': int(elapsed.gt(max_gap).sum()),
    }

def analyze(data: Dataset, batch, rules: Rules) -> dict:
    if rules.max_gap<=0 or rules.tolerance<0 or rules.event_minutes<0:
        raise ValueError('Las reglas de análisis no son válidas.')
    start,end=pd.Timestamp(batch['start']),pd.Timestamp(batch['end'])
    t0,t1=start.value/1e9,end.value/1e9
    if t1<=t0: raise ValueError('Intervalo de batch vacío.')
    points={t0,t1}
    for role in ('PV','SP','Fresco','Retorno'):
        frame=data.signals[role]
        t=frame.time.astype('int64').to_numpy()/1e9
        points.update(t[(t>t0)&(t<t1)].tolist())
        if role=='SP':
            expiry=t+rules.max_gap
            points.update(expiry[(expiry>t0)&(expiry<t1)].tolist())
    edges=np.array(sorted(points)); a,b=edges[:-1],edges[1:]
    pv0,pv1=_linear(data.signals['PV'],a,b,rules.max_gap)
    sp=_step(data.signals['SP'],a,b,rules.max_gap)
    f0,f1=_linear(data.signals['Fresco'],a,b,rules.max_gap)
    r0,r1=_linear(data.signals['Retorno'],a,b,rules.max_gap)
    # Split precisely at threshold crossings: durations do not depend on a resampling grid.
    crossings=[]
    for y0,y1,level in [(pv0-sp,pv1-sp,-rules.tolerance),(pv0-sp,pv1-sp,0),
                        (pv0-sp,pv1-sp,rules.tolerance),(pv0,pv1,rules.critical_temperature),
                        (f0+r0,f1+r1,100-rules.curtain_tolerance),
                        (f0+r0,f1+r1,100+rules.curtain_tolerance)]:
        mask=np.isfinite(y0)&np.isfinite(y1)&((y0-level)*(y1-level)<0)
        crossings.extend((a[mask]+(b[mask]-a[mask])*(level-y0[mask])/(y1[mask]-y0[mask])).tolist())
    if crossings:
        edges=np.unique(np.concatenate([edges,np.array(crossings)]))
        a,b=edges[:-1],edges[1:]
        pv0,pv1=_linear(data.signals['PV'],a,b,rules.max_gap)
        sp=_step(data.signals['SP'],a,b,rules.max_gap)
        f0,f1=_linear(data.signals['Fresco'],a,b,rules.max_gap)
        r0,r1=_linear(data.signals['Retorno'],a,b,rules.max_gap)
    seconds=b-a
    pv_ok=np.isfinite(pv0)&np.isfinite(pv1)
    off=np.isfinite(sp)&(sp==0)
    valid=pv_ok&np.isfinite(sp)&~off
    err0,err1=pv0-sp,pv1-sp
    err=(err0+err1)/2
    above=valid&(err>rules.tolerance+1e-9)
    below=valid&(err < -rules.tolerance-1e-9)
    within=valid&~above&~below
    hot=valid&((pv0+pv1)/2>rules.critical_temperature+1e-9)
    curtain_ok=np.isfinite(f0)&np.isfinite(f1)&np.isfinite(r0)&np.isfinite(r1)&np.isfinite(sp)&~off
    curtain_bad=curtain_ok&(np.abs((f0+f1+r0+r1)/2-100)>rules.curtain_tolerance+1e-9)
    segments=pd.DataFrame(dict(start=pd.to_datetime(a,unit='s'),end=pd.to_datetime(b,unit='s'),
        seconds=seconds,pv0=pv0,pv1=pv1,sp=sp,valid=valid,off=off,above=above,below=below,
        within=within,hot=hot,curtain_ok=curtain_ok,curtain_bad=curtain_bad))
    valid_seconds=float(seconds[valid].sum())
    off_seconds=float(seconds[off].sum())
    total=t1-t0
    raw={role:frame[(frame.time>=start)&(frame.time<end)] for role,frame in data.signals.items() if role!='Batch'}
    extrema={role:dict(count=len(frame),min=float(frame.value.min()) if len(frame) else None,
                      max=float(frame.value.max()) if len(frame) else None) for role,frame in raw.items()}
    mae=float(np.sum(seconds[valid]*(np.abs(err0[valid])+np.abs(err1[valid]))/2)/valid_seconds) if valid_seconds else None
    metrics=dict(total_hours=total/3600,evaluable_hours=valid_seconds/3600,
        pv_coverage_pct=100*float(seconds[pv_ok].sum())/total,
        joint_coverage_pct=100*valid_seconds/total, off_hours=off_seconds/3600,
        unknown_hours=max(0,total-valid_seconds-off_seconds)/3600,
        within_pct=100*float(seconds[within].sum())/valid_seconds if valid_seconds else None,
        above_hours=float(seconds[above].sum())/3600,
        below_hours=float(seconds[below].sum())/3600,
        above_pct_evaluable=100*float(seconds[above].sum())/valid_seconds if valid_seconds else None,
        below_pct_evaluable=100*float(seconds[below].sum())/valid_seconds if valid_seconds else None,
        outside_pct_evaluable=100*float(seconds[above|below].sum())/valid_seconds if valid_seconds else None,
        above_pct_batch=100*float(seconds[above].sum())/total if valid_seconds else None,
        below_pct_batch=100*float(seconds[below].sum())/total if valid_seconds else None,
        outside_pct_batch=100*float(seconds[above|below].sum())/total if valid_seconds else None,
        mae=mae,hot_minutes=float(seconds[hot].sum())/60,
        curtain_hours=float(seconds[curtain_ok].sum())/3600,
        curtain_bad_minutes=float(seconds[curtain_bad].sum())/60)
    for role in ('Fresco', 'Retorno'):
        travel = curtain_travel(raw[role], rules.max_gap, total)
        prefix = role.lower()
        metrics[f'{prefix}_travel_m'] = travel['meters']
        metrics[f'{prefix}_travel_coverage_pct'] = travel['coverage_pct']
        metrics[f'{prefix}_travel_gaps'] = travel['gaps']
    fresh = metrics['fresco_travel_m']
    returned = metrics['retorno_travel_m']
    metrics['curtain_travel_difference_m'] = abs(fresh - returned) if fresh is not None and returned is not None else None
    events=[]
    for col,kind in [('above','Sobre tolerancia'),('below','Bajo tolerancia'),('hot','Sobre 22 °C'),('curtain_bad','Cortinas fuera de complementariedad')]:
        events.extend(_events(segments,col,kind,rules.event_minutes))
    events=pd.DataFrame(events,columns=['tipo','inicio','fin','minutos','persistente','prioridad'])
    if not events.empty: events=events.sort_values('inicio').reset_index(drop=True)
    metrics['thermal_events']=int(events.loc[events.tipo.isin(['Sobre tolerancia','Bajo tolerancia']),'persistente'].sum())
    warnings=[]
    if metrics['joint_coverage_pct']<90:
        warnings.append('Cobertura conjunta PV/SP inferior al 90 %: los resultados describen solo los tramos evaluables, no el lote completo. El 90 % es una referencia informativa del proyecto.')
    if not batch['closed']: warnings.append('No se dispone de un cierre confirmado con el siguiente batch.')
    warnings.append('Cadencia y tolerancia de huecos son parámetros provisionales; confirmar el intervalo real del histórico.')
    return dict(batch=str(batch['batch']),start=start.isoformat(),end=end.isoformat(),
        closed=bool(batch['closed']),rules=asdict(rules),metrics=metrics,extrema=extrema,
        warnings=warnings,events=events,segments=segments,raw=raw,fingerprint=data.fingerprint)

def payload(result: dict, annotations: list) -> dict:
    events=result['events'].sort_values(['persistente','minutos'],ascending=False).head(20).copy()
    for col in ('inicio','fin'): events[col]=events[col].astype(str)
    return {key:result[key] for key in ['batch','start','end','closed','rules','metrics','extrema','warnings','fingerprint']} | {
        'eventos_mayores':events.to_dict('records'),'eventos_totales':len(result['events']),
        'anotaciones_usuario':annotations[:50],
        'metodo':'PV y feedback: interpolación lineal solo entre muestras separadas como máximo por max_gap. SP: retención acotada a max_gap. Huecos no se contabilizan. Duraciones estimadas; no son mediciones continuas.',
        'max_gap_segundos':result['rules']['expected_seconds']*result['rules']['gap_factor'],
        'metodo_recorrido': 'Cada punto porcentual equivale a 0,01 m. Se suman los cambios absolutos entre muestras consecutivas separadas por no más de max_gap, sin interpolar tramos faltantes. La diferencia absoluta compara dos recorridos observados con posible cobertura distinta.'}
