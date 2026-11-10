from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

COLORS={'PV':'#2169CE','SP':'#DB8B24','Retorno':'#7753C7','Fresco':'#0C998C'}

def figure(raw: dict, roles: list[str], max_gap: float, smooth=True, connect_gaps=False,
           critical=22, event_window=None, annotations=None):
    fig=go.Figure()
    for role in roles:
        frame=raw[role]
        x,y=[],[]
        previous=None
        # Smooth each contiguous display section only. Original samples are used in calculations.
        for row in frame.itertuples():
            if previous is not None and (row.time-previous).total_seconds()>max_gap and not connect_gaps:
                x.append(None); y.append(None)
            x.append(row.time); y.append(row.value); previous=row.time
        fig.add_trace(go.Scatter(x=x,y=y,mode='lines',name=role,
            line=dict(color=COLORS[role],width=1.25,shape='spline' if smooth and role!='SP' else 'hv',
                      smoothing=0.35 if smooth and role!='SP' else 0),
            connectgaps=False,hovertemplate='%{x|%d/%m %H:%M:%S}<br>%{y:.2f}<extra>'+role+'</extra>'))
    if 'PV' in roles:
        fig.add_hline(y=critical,line_dash='dot',line_color='#CC7A61',line_width=1,
                      annotation_text=f'Atención: {critical:g} °C',annotation_position='top left')
    if event_window:
        fig.add_vrect(x0=event_window[0],x1=event_window[1],fillcolor='#F5BE68',opacity=.18,line_width=0)
    for note in annotations or []:
        fig.add_vrect(x0=note['inicio'],x1=note['fin'],fillcolor='#88B9C8',opacity=.15,line_width=0)
    fig.update_layout(height=310,margin=dict(l=15,r=15,t=10,b=10),paper_bgcolor='white',plot_bgcolor='white',
        font=dict(family='Segoe UI, sans-serif',color='#26334A'),hovermode='x unified',
        legend=dict(orientation='h',y=1.13,x=1,xanchor='right'),
        xaxis=dict(gridcolor='#EDF0F5',title=None),
        yaxis=dict(gridcolor='#E7EBF1',title='°C' if 'PV' in roles else 'Apertura (%)'))
    if 'Fresco' in roles: fig.update_yaxes(range=[0,100])
    return fig
