"""Ejecuta comprobaciones locales reproducibles, sin llamadas a OpenAI."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import subprocess
import sys
import time
from termico.data import manifest,load_folder,batch_catalog
from termico.analysis import analyze,Rules,payload

ROOT=Path(__file__).resolve().parent
run=subprocess.run([sys.executable,'-m','pytest','-q'],cwd=ROOT,capture_output=True,text=True)
print(run.stdout)
if run.returncode:
    print(run.stderr)
    raise SystemExit(run.returncode)
t=time.perf_counter()
data=load_folder(manifest(str(ROOT/'data/historicos')))
load_seconds=time.perf_counter()-t
catalog=batch_catalog(data)
result=analyze(data,catalog[catalog.batch=='26310'].iloc[0],Rules())
evidence=payload(result,[])
raw_bytes=sum(len(df.to_json(date_format='iso').encode()) for df in result['raw'].values())
payload_bytes=len(json.dumps(evidence,ensure_ascii=False,allow_nan=False).encode())
record=dict(fecha=datetime.now(ZoneInfo('America/Santiago')).isoformat(),
    pruebas=run.stdout.strip(),archivos=data.files,
    batches=catalog[['batch','count']].to_dict('records'),
    metricas_batch_26310=result['metrics'],
    carga_local_segundos=load_seconds,
    optimizacion=dict(comparacion='JSON de todas las muestras del batch frente a resumen de evidencia enviado a IA',
                      json_muestras_bytes=raw_bytes,json_resumen_bytes=payload_bytes,
                      reduccion_bytes_pct=100*(1-payload_bytes/raw_bytes)),
    api_real='Pendiente de configurar y probar con la clave del usuario; contrato verificado con cliente simulado.')
folder=ROOT/'evidencia'; folder.mkdir(exist_ok=True)
(folder/'verificacion.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(record,ensure_ascii=False,indent=2))
