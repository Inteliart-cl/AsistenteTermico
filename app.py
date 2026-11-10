from __future__ import annotations

from pathlib import Path
from dataclasses import asdict
import hashlib
import json
import os
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from termico.data import TAGS, manifest, load_folder, load_zip, batch_catalog
from termico.analysis import Rules, analyze, payload
from termico.charts import figure
from termico.ai import generate_report, report_markdown
from termico.notes import load_notes, save_notes

ROOT=Path(__file__).resolve().parent
load_dotenv(ROOT/'.env',override=False)
st.set_page_config(page_title='Ingenio · Análisis térmico',page_icon=':material/thermostat:',layout='wide')

@st.cache_data(ttl=300,max_entries=4,show_spinner='Leyendo históricos…')
def folder_data(files): return load_folder(files)

@st.cache_data(ttl=300,max_entries=4,show_spinner='Leyendo archivo ZIP…')
def zip_data(blob): return load_zip(blob)

@st.cache_data(ttl=300,max_entries=12,show_spinner='Calculando cobertura y eventos…')
def calculate(fingerprint,batch_key,rules_tuple,_data,_batch):
    return analyze(_data,_batch,Rules(**dict(rules_tuple)))

def goto_ai():
    st.session_state['page']='Análisis con IA'
    st.session_state['generate_ai']=True

def fmt(value,unit='',digits=1):
    return 'No evaluable' if value is None else f'{value:.{digits}f}'.replace('.',',')+unit

def chart_pair(result,notes,window=None):
    with st.container(border=True):
        st.subheader('Temperatura medida y consigna')
        st.plotly_chart(figure(result['raw'],['PV','SP'],rules.max_gap,smooth,connect,
                              rules.critical_temperature,window,notes),width='stretch',
                        key='temp_chart',alt='Temperatura medida y consigna a lo largo del batch')
    with st.container(border=True):
        st.subheader('Apertura real de cortinas')
        st.plotly_chart(figure(result['raw'],['Retorno','Fresco'],rules.max_gap,smooth,connect,
                              rules.critical_temperature,window,notes),width='stretch',
                        key='curtain_chart',alt='Posiciones reales de las cortinas de retorno y aire fresco')
    if connect:
        st.caption('Las líneas unen registros para facilitar la lectura, incluso en huecos. Esa unión y el suavizado no se usan para calcular indicadores.')
    else:
        st.caption('Los huecos mayores al máximo permitido se muestran como cortes. El suavizado es solo visual.')

for key,default in {'page':'Resumen','generate_ai':False,'reports':{}}.items():
    if key not in st.session_state: st.session_state[key]=default

with st.sidebar:
    st.image(str(ROOT/'assets/logo.png'),width='stretch',alt='Ingenio Industrial')
    st.caption('Asistente de análisis térmico · Nave N5')
    with st.expander('Origen de los datos'):
        source=st.radio('Fuente',['Históricos incluidos','Carpeta local','Archivo ZIP'],key='source')
        folder=str(ROOT/'data/historicos')
        upload=None
        if source=='Carpeta local': folder=st.text_input('Carpeta con los .dat',key='data_folder')
        if source=='Archivo ZIP': upload=st.file_uploader('ZIP con carpetas de señales',type=['zip'],key='zip_upload')
        st.caption('Solo se leen .dat; los originales no se modifican.')

try:
    if source=='Archivo ZIP':
        if upload is None: st.info('Carga un ZIP para comenzar.'); st.stop()
        data=zip_data(upload.getvalue())
    else:
        data=folder_data(manifest(folder))
    catalog=batch_catalog(data)
except (ValueError,OSError) as exc:
    st.error(str(exc)); st.stop()

with st.sidebar:
    default_index=next((i for i,row in catalog.iterrows() if row.batch=='26310'),0)
    batch_key=st.selectbox('Batch',catalog.key.tolist(),index=default_index,key='batch_key',
        format_func=lambda key: f"{catalog.loc[catalog.key==key,'batch'].iloc[0]} · {catalog.loc[catalog.key==key,'start'].iloc[0]:%d/%m/%Y}")
    batch=catalog.loc[catalog.key==batch_key].iloc[0]
    st.caption(f"{batch.start:%d/%m %H:%M} → {batch.end:%d/%m %H:%M}")
    st.radio('Explorar',['Resumen','Eventos','Análisis con IA','Datos y validación'],key='page')
    with st.expander('Reglas de análisis'):
        st.caption('La cadencia real aún debe confirmarse. Se propone inicialmente 30 segundos y un hueco máximo de 90 segundos.')
        expected=st.number_input('Intervalo esperado del histórico (segundos)',min_value=1.0,max_value=3600.0,value=30.0,step=1.0,key='cadence')
        factor=st.number_input('Máximo de intervalos entre muestras',min_value=1.0,max_value=10.0,value=3.0,step=.5,key='gap_factor')
        tolerance=st.number_input('Tolerancia térmica (± °C)',min_value=0.0,max_value=10.0,value=.8,step=.1,key='tolerance')
        event_min=st.number_input('Persistencia: más de (minutos)',min_value=0.0,max_value=240.0,value=20.0,step=1.0,key='event_minutes')
        curtain_tol=st.number_input('Desviación de fresco + retorno (puntos %)',min_value=0.0,max_value=100.0,value=5.0,step=1.0,key='curtain_tolerance')
        st.caption('El margen de cortinas de 5 puntos porcentuales es provisional. Temperatura de especial atención: >22 °C.')
    with st.expander('Visualización'):
        smooth=st.toggle('Curvas suavizadas',value=True,key='smooth')
        connect=st.toggle('Unir registros en los huecos (solo visual)',value=True,key='connect')
    st.caption('Históricos locales · Sin conexión ni escritura al PLC')

rules=Rules(tolerance=tolerance,event_minutes=event_min,expected_seconds=expected,gap_factor=factor,curtain_tolerance=curtain_tol)
result=calculate(data.fingerprint,batch_key,tuple(asdict(rules).items()),data,batch)
try:
    notes=load_notes(ROOT/'local/anotaciones',batch_key)
except ValueError as exc:
    st.warning(str(exc)); notes=[]
evidence=payload(result,notes)
signature=hashlib.sha256(json.dumps(evidence,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
ai_report=st.session_state['reports'].get(signature)
m=result['metrics']

st.title('Control térmico del grano' if st.session_state.page=='Resumen' else st.session_state.page)
st.caption(f"Batch {batch.batch} · Nave N5 · {batch.start:%d/%m/%Y %H:%M} → {batch.end:%d/%m/%Y %H:%M} · Hora local del histórico")
if m['joint_coverage_pct']<90:
    st.warning(f"Cobertura conjunta PV/SP: {m['joint_coverage_pct']:.2f} %. Los indicadores describen solo {m['evaluable_hours']:.2f} h evaluables de {m['total_hours']:.2f} h. Los huecos no se consideran funcionamiento correcto.")
if not batch.closed: st.info('Batch parcial: no hay un cierre confirmado con la siguiente carga.')

page=st.session_state.page
if page=='Resumen':
    with st.container(horizontal=True):
        for role,label in [('PV','PV · temperatura medida'),('SP','SP · consigna'),('Retorno','Retorno · posición real'),('Fresco','Fresco · posición real')]:
            s=result['extrema'][role]; unit=' °C' if role in ('PV','SP') else ' %'
            value=fmt(s['min'])+' – '+fmt(s['max'])+unit if s['count'] else 'Sin datos'
            st.metric(label,value,border=True)
    chart_pair(result,notes)
    if result['extrema']['PV']['max'] is not None and result['extrema']['PV']['max']>22:
        st.warning(f"Se registró una temperatura de hasta {result['extrema']['PV']['max']:.1f} °C, superior a 22 °C. La duración solo puede estimarse donde existe cobertura válida.")
    with st.container(horizontal=True):
        st.metric('Dentro de tolerancia · tramo evaluable',fmt(m['within_pct'],' %'),border=True)
        st.metric('Error absoluto medio',fmt(m['mae'],' °C',2),border=True)
        st.metric('Eventos persistentes · tramo evaluable',str(m['thermal_events']),border=True)
        st.metric('Sobre 22 °C · tiempo evaluable',fmt(m['hot_minutes'],' min'),border=True)
    st.caption('Duraciones estimadas con interpolación local acotada. Un evento es persistente solo si supera estrictamente el tiempo definido; los huecos interrumpen la continuidad.')
    st.button('Analizar batch con IA',type='primary',on_click=goto_ai,key='analyze_batch',icon=':material/auto_awesome:')

elif page=='Eventos':
    st.caption('Se muestran también excursiones breves. Sobre 22 °C se destaca desde su primera observación evaluable.')
    persistent=st.toggle('Mostrar solo eventos persistentes',value=False,key='persistent_only')
    events=result['events']
    filtered=events[events.persistente] if persistent else events
    st.dataframe(filtered,hide_index=True,alt='Eventos calculados con inicio, fin, duración y prioridad')
    window=None
    if not filtered.empty:
        selected=st.selectbox('Evento para inspeccionar',filtered.index.tolist(),key='event_selected',
            format_func=lambda i:f"{events.loc[i,'tipo']} · {events.loc[i,'inicio']:%d/%m %H:%M} · {events.loc[i,'minutos']:.1f} min")
        row=events.loc[selected]
        window=(row.inicio,row.fin)
    else: st.info('No hay eventos con estos filtros. Revisa la cobertura antes de concluir que el lote no tuvo desviaciones.')
    chart_pair(result,notes,window)
    st.download_button('Descargar eventos CSV',events.to_csv(index=False).encode('utf-8-sig'),f'eventos_{batch.batch}.csv','text/csv',key='events_download')
    st.subheader('Anotaciones de volteos y contexto')
    st.caption('Las anotaciones se conservan localmente, contextualizan el análisis y no excluyen eventos ni alteran las métricas.')
    if notes: st.dataframe(pd.DataFrame(notes),hide_index=True,alt='Anotaciones manuales del batch')
    with st.form('annotation_form'):
        kind=st.selectbox('Tipo',['Volteo','Contexto operativo'],key='note_type')
        begin=st.text_input('Inicio · AAAA-MM-DD HH:MM',value=f'{batch.start:%Y-%m-%d %H:%M:%S}',key='note_start')
        finish=st.text_input('Fin · AAAA-MM-DD HH:MM',value=f'{batch.start:%Y-%m-%d %H:%M:%S}',key='note_end')
        comment=st.text_area('Descripción',max_chars=1000,key='note_text')
        save=st.form_submit_button('Guardar anotación',key='save_note')
    if save:
        try:
            a,b=pd.Timestamp(begin),pd.Timestamp(finish)
            if pd.isna(a) or pd.isna(b) or a.tzinfo or b.tzinfo or not batch.start<=a<b<=batch.end:
                raise ValueError('Usa horas locales y un intervalo válido dentro del batch, con fin posterior al inicio.')
            save_notes(ROOT/'local/anotaciones',batch_key,notes+[dict(tipo=kind,inicio=a.isoformat(),fin=b.isoformat(),descripcion=comment)])
            st.rerun()
        except (ValueError,OSError) as exc: st.error(str(exc))
    if notes:
        with st.expander('Eliminar una anotación'):
            idx=st.selectbox('Anotación',range(len(notes)),format_func=lambda i:f"{notes[i]['tipo']} · {notes[i]['inicio']}",key='delete_note_index')
            if st.button('Eliminar anotación seleccionada',key='delete_note'):
                save_notes(ROOT/'local/anotaciones',batch_key,[n for i,n in enumerate(notes) if i!=idx]); st.rerun()

elif page=='Análisis con IA':
    st.info('Se enviarán a OpenAI métricas, hasta 20 eventos y hasta 50 anotaciones del batch seleccionado. No se envían los archivos históricos completos. La solicitud utiliza tu cuenta de API.')
    with st.expander('Configuración de OpenAI',expanded=not bool(os.getenv('OPENAI_API_KEY'))):
        api_key=st.text_input('Clave de API · solo para esta sesión',type='password',key='api_key_input',
            help='También puedes configurar OPENAI_API_KEY en el archivo .env local.') or os.getenv('OPENAI_API_KEY','')
        model=st.text_input('Modelo',value=os.getenv('OPENAI_MODEL','gpt-4.1-mini'),key='model')
        st.caption('La clave no se guarda en los informes ni se incorpora a las descargas.')
    with st.expander('Ver evidencia que recibirá la IA'):
        st.json(evidence)
    request=st.button('Generar informe con OpenAI' if not ai_report else 'Volver a generar informe',type='primary',key='generate_report',disabled=not bool(api_key.strip()))
    auto_request=st.session_state.pop('generate_ai',False)
    if (request or auto_request) and api_key.strip():
        try:
            with st.spinner('OpenAI está preparando la interpretación del batch…'):
                ai_report=generate_report(evidence,api_key,model)
            st.session_state['reports'][signature]=ai_report
        except (ValueError,TypeError) as exc: st.error(str(exc))
    elif not api_key.strip(): st.info('Ingresa tu clave de API o configura el archivo .env para generar el informe.')
    if ai_report:
        content=ai_report['contenido']
        st.caption(f"Informe generado · {ai_report['modelo']} · {ai_report['generado']}")
        with st.container(border=True):
            st.subheader('Resumen del análisis'); st.markdown(content['resumen'])
        st.subheader('Hallazgos respaldados por los datos')
        for finding in content['hallazgos']:
            with st.container(border=True):
                st.markdown('**'+finding['titulo']+'**'); st.markdown(finding['evidencia']); st.caption(finding['limite'])
        left,right=st.columns(2)
        with left:
            st.subheader('Posibles explicaciones')
            for item in content['hipotesis']: st.markdown('- '+item)
        with right:
            st.subheader('Verificaciones recomendadas')
            for item in content['verificaciones']: st.markdown('- '+item)
        st.subheader('Limitaciones')
        for item in content['limitaciones']: st.markdown('- '+item)
    else: st.caption('Aún no hay un informe de IA para estos datos, reglas y anotaciones. No se muestran respuestas simuladas.')

else:
    st.subheader('Cobertura y trazabilidad')
    with st.container(horizontal=True):
        st.metric('Cobertura PV',fmt(m['pv_coverage_pct'],' %'),border=True)
        st.metric('Cobertura conjunta PV/SP',fmt(m['joint_coverage_pct'],' %'),border=True)
        st.metric('Apagado conocido',fmt(m['off_hours'],' h'),border=True)
        st.metric('Sin evaluación térmica',fmt(m['unknown_hours'],' h'),border=True)
    st.caption(f"Cortinas evaluables en operación: {m['curtain_hours']:.2f} h. Fuera de complementariedad: {m['curtain_bad_minutes']:.1f} min dentro de esa cobertura.")
    st.warning('Los intervalos de carga a carga incluyen operación y posibles períodos apagados. No equivalen automáticamente al tiempo de germinación.')
    st.markdown('**Método de cálculo**')
    st.markdown(evidence['metodo'])
    st.caption(f'Hueco máximo permitido: {rules.max_gap:g} segundos. Cadencia provisional: {rules.expected_seconds:g} segundos.')
    st.dataframe(pd.DataFrame([dict(variable=k,señal=v) for k,v in TAGS.items()]),hide_index=True,alt='Identificación de señales')
    stats=[]
    for role,frame in data.signals.items():
        delta=frame.time.diff().dt.total_seconds().dropna()
        stats.append(dict(señal=role,registros=len(frame),inicio=frame.time.min(),fin=frame.time.max(),
                          intervalo_mediano_s=float(delta.median()) if len(delta) else None,
                          hueco_máximo_s=float(delta.max()) if len(delta) else None))
    st.dataframe(pd.DataFrame(stats),hide_index=True,alt='Cobertura e intervalos observados por señal')
    st.subheader('Batches con temperatura disponible')
    st.dataframe(catalog.drop(columns=['key']),hide_index=True,alt='Batches disponibles y límites observados')
    st.subheader('Observaciones de importación')
    st.caption(f'{data.files} archivos .dat leídos. Huella SHA-256: {data.fingerprint}')
    st.dataframe(data.issues,hide_index=True,alt='Registros vacíos, inválidos o contradictorios encontrados')
    with st.expander('Registros originales del batch'):
        for role,frame in result['raw'].items():
            st.markdown('**'+role+'**'); st.dataframe(frame,hide_index=True,alt=f'Registros originales de {role}')

st.divider()
with st.container(horizontal=True):
    st.download_button('Descargar informe',report_markdown(evidence,ai_report),f'informe_batch_{batch.batch}.md','text/markdown',key='report_download')
    st.download_button('Descargar evidencia JSON',json.dumps(evidence,ensure_ascii=False,indent=2,allow_nan=False),f'evidencia_batch_{batch.batch}.json','application/json',key='evidence_download')
st.caption('Ingenio Industrial · Análisis histórico de apoyo a la revisión operativa · Sin cambios al control del proceso')
