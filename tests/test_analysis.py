from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock
import pandas as pd
import pytest
from termico.analysis import Rules, analyze, payload
from termico.data import Dataset, parse_files, batch_catalog
from termico.ai import generate_report, Report, Finding
from termico.charts import figure

def fixture_data(minutes=21,pv=21,sp=20):
    times=pd.date_range('2026-11-01',periods=minutes+1,freq='min')
    def series(value): return pd.DataFrame({'time':times,'value':value})
    signals={'PV':series(pv),'SP':series(sp),'Retorno':series(40),'Fresco':series(60),
             'Batch':pd.DataFrame({'time':[times[0]],'value':['123']})}
    return Dataset(signals,pd.DataFrame(),'test',5),dict(batch='123',start=times[0],end=times[-1],closed=True)

def test_event_strictly_more_than_twenty_minutes():
    d,b=fixture_data(20)
    r=analyze(d,b,Rules())
    assert r['metrics']['thermal_events']==0
    d,b=fixture_data(21)
    r=analyze(d,b,Rules())
    assert r['metrics']['thermal_events']==1
    assert r['events'].iloc[0]['minutos']==pytest.approx(21)

def test_limits_inclusive_and_time_weighted_error():
    d,b=fixture_data(pv=20.8)
    r=analyze(d,b,Rules())
    assert r['metrics']['within_pct']==pytest.approx(100)
    assert r['metrics']['mae']==pytest.approx(.8)

def test_exact_threshold_crossing_duration():
    d,b=fixture_data(1)
    d.signals['PV']['value']=[20,24]
    r=analyze(d,b,Rules())
    assert r['metrics']['hot_minutes']==pytest.approx(.5)
    assert r['metrics']['within_pct']==pytest.approx(20)
    assert r['metrics']['mae']==pytest.approx(2)

def test_missing_pv_breaks_events_and_is_not_good_control():
    d,b=fixture_data(45)
    d.signals['PV']=d.signals['PV'].drop(index=range(15,31))
    r=analyze(d,b,Rules())
    assert r['metrics']['thermal_events']==0
    assert r['metrics']['unknown_hours']>0
    assert r['metrics']['within_pct']==0

def test_sp_not_retained_over_long_gap():
    d,b=fixture_data(60)
    d.signals['SP']=d.signals['SP'].iloc[[0]]
    r=analyze(d,b,Rules())
    assert r['metrics']['evaluable_hours']==pytest.approx(90/3600)
    assert r['metrics']['joint_coverage_pct']==pytest.approx(2.5)

def test_sp_zero_is_off_not_failure():
    d,b=fixture_data(sp=0)
    r=analyze(d,b,Rules())
    assert r['metrics']['within_pct'] is None
    assert r['metrics']['off_hours']==pytest.approx(21/60)
    assert r['events'].empty

def test_absolute_heat_even_when_within_relative_band():
    d,b=fixture_data(pv=22.2,sp=21.5)
    r=analyze(d,b,Rules())
    assert r['metrics']['within_pct']==pytest.approx(100)
    assert r['metrics']['hot_minutes']==pytest.approx(21)
    assert r['events'].iloc[0]['tipo']=='Sobre 22 °C'

def test_curtain_deviation_requires_both_feedback():
    d,b=fixture_data()
    d.signals['Fresco']['value']=80
    r=analyze(d,b,Rules())
    assert r['metrics']['curtain_bad_minutes']==pytest.approx(21)
    d.signals['Retorno']=d.signals['Retorno'].iloc[:0]
    r=analyze(d,b,Rules())
    assert r['metrics']['curtain_hours']==0

def test_data_parser_preserves_blank_batches_and_rejects_invalid():
    files=[]
    for role,tag,value in [('PV','PROM_SOBRE_N5,31','20,5'),('SP','00TT2004,29','20,0'),('Batch','NUM_BATCH_NAVE_5,10','123')]:
        text=f'header\n01-11-2026 0:00:00\t{value}\n01-11-2026 1:00:00\t{value}\n'
        if role=='Batch': text+='01-11-2026 0:30:00\t\n'
        else: text+='bad line\n'
        files.append((f'01_11_26 {tag}.dat',text.encode()))
    d=parse_files(files)
    assert d.signals['PV'].iloc[0].value==20.5
    assert len(d.issues)==3
    c=batch_catalog(d)
    assert c.iloc[0].end==pd.Timestamp('2026-11-01 00:30')
    assert not c.iloc[0].closed

def test_ai_uses_structured_response_no_raw_records_and_no_storage():
    d,b=fixture_data()
    evidence=payload(analyze(d,b,Rules()),[])
    assert 'raw' not in evidence and 'segments' not in evidence
    report=Report(resumen='Prueba de contrato, no respuesta real.',hallazgos=[Finding(titulo='Prueba',evidencia='Métrica',limite='Cobertura')],hipotesis=[],verificaciones=[],limitaciones=[])
    client=Mock()
    client.responses.parse.return_value=SimpleNamespace(output_parsed=report,usage=None)
    response=generate_report(evidence,'clave-ficticia','gpt-4.1-mini',client)
    assert response['contenido']['resumen']==report.resumen
    assert client.responses.parse.call_args.kwargs['store'] is False
    assert client.responses.parse.call_args.kwargs['text_format'] is Report

def test_missing_key_and_incomplete_output_not_fake_success():
    with pytest.raises(ValueError): generate_report({},'', 'model')
    client=Mock()
    client.responses.parse.return_value=SimpleNamespace(output_parsed=None)
    with pytest.raises(ValueError): generate_report({},'fake','model',client)

def test_chart_no_markers_and_gap_breaks():
    d,b=fixture_data(5)
    d.signals['PV']=d.signals['PV'].iloc[[0,-1]]
    fig=figure(d.signals,['PV','SP'],90,smooth=True,connect_gaps=False)
    assert fig.data[0].mode=='lines'
    assert None in fig.data[0].x

def test_real_batches():
    from pathlib import Path
    from termico.data import load_folder,manifest
    root=Path(__file__).resolve().parents[1]
    d=load_folder(manifest(str(root/'data/historicos')))
    c=batch_catalog(d)
    assert c.batch.tolist()==['26304','26310','26316']
    assert c['count'].tolist()==[5786,7029,2052]
    r=analyze(d,c[c.batch=='26310'].iloc[0],Rules())
    assert r['extrema']['PV']['max']==24.4
    assert 0<r['metrics']['joint_coverage_pct']<1
