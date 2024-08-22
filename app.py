import streamlit as st
import pandas as pd
import geopandas as gpd
import numpy as np
import altair as alt
import plotly.express as px
from datetime import datetime, timedelta
from shapely.geometry import Point
import random

#######################
# Configuración de la página
st.set_page_config("Tablero Dashboard de Reportes en Gustavo A. Madero",
    page_icon="🚧",
    layout="wide",
    initial_sidebar_state="expanded")

alt.themes.enable("dark")

#######################
# Cargar y generar datos
@st.cache_data
def cargar_shapefile():
    return gpd.read_file("poligonos_colonias_cdmx.shp")

gdf = cargar_shapefile()
gdf_gustavo = gdf[gdf['alc'].str.contains("Gustavo A. Madero", case=False, na=False)]

# Generar datos de reportes por servicio
def generar_puntos_por_servicio(gdf, servicios, num_puntos):
    puntos_por_servicio = []
    for servicio in servicios:
        for _, row in gdf.iterrows():
            poly = row['geometry']
            for _ in range(num_puntos):
                minx, miny, maxx, maxy = poly.bounds
                while True:
                    p = Point(random.uniform(minx, maxx), random.uniform(miny, maxy))
                    if poly.contains(p):
                        puntos_por_servicio.append({
                            'colonia': row['colonia'],
                            'servicio': servicio,
                            'estado': random.choice(["En proceso", "Resuelto", "Pendiente"]),
                            'fecha_reporte': datetime.now() - timedelta(days=random.randint(0, 30)),
                            'geometry': p,
                            'coordenadas': f"({p.x:.5f}, {p.y:.5f})"
                        })
                        break
    return pd.DataFrame(puntos_por_servicio)

# Definir los servicios
servicios = ["Fugas de Agua", "Incendios", "Fugas de Gas", "Delitos", "Baches", "Inundaciones", "Corte de Electricidad"]

# Generar puntos de reporte en las colonias para cada servicio
df_reportes = generar_puntos_por_servicio(gdf_gustavo, servicios, num_puntos=5)

# Agregar la columna 'num_reportes' al GeoDataFrame `gdf_gustavo` basada en los reportes generados
reporte_count = df_reportes.groupby('colonia').size().reset_index(name='num_reportes')
gdf_gustavo = gdf_gustavo.merge(reporte_count, on='colonia', how='left')
gdf_gustavo['num_reportes'].fillna(0, inplace=True)  # Rellenar valores NaN con 0

#######################
# Sidebar
with st.sidebar:
    st.title('🚧 Dashboard de Servicios en GAM')
    
    servicio_list = list(df_reportes['servicio'].unique())
    selected_servicio = st.selectbox('Selecciona el tipo de Servicio', servicio_list)

    estado_resolucion = st.selectbox("Selecciona el estado de resolución", ["Todos", "En proceso", "Resuelto", "Pendiente"])

    # Mapeo de nombres descriptivos para los temas de color
    color_theme_options = {
        "Fugas de Agua": 'blues',
        "Incendios": 'inferno',
        "Fugas de Gas": 'greens',
        "Delitos": 'magma',
        "Baches": 'reds',
        "Inundaciones": 'turbo',
        "Corte de Electricidad": 'viridis'
    }

    # Asignar el esquema de color al servicio seleccionado
    selected_color_theme = color_theme_options[selected_servicio]

    # Filtrar los puntos según el servicio y el estado de resolución seleccionado
    df_selected_servicio = df_reportes[df_reportes['servicio'] == selected_servicio]
    
    if estado_resolucion != "Todos":
        df_selected_servicio = df_selected_servicio[df_selected_servicio['estado'] == estado_resolucion]

#######################
# Indicadores clave (KPIs)
total_reportes = df_selected_servicio.shape[0]
num_resueltos = len(df_selected_servicio[df_selected_servicio['estado'] == 'Resuelto'])
num_pendientes = len(df_selected_servicio[df_selected_servicio['estado'] == 'Pendiente'])
num_en_proceso = len(df_selected_servicio[df_selected_servicio['estado'] == 'En proceso'])

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total de Reportes", total_reportes)
col2.metric("Reportes Resueltos", num_resueltos)
col3.metric("Reportes Pendientes", num_pendientes)
col4.metric("Reportes en Proceso", num_en_proceso)

#######################
# Funciones para los gráficos

# Mapa coroplético con puntos de reporte para cada servicio optimizado para rendimiento
def make_choropleth_with_service_points(input_df, gdf_gustavo, input_color_theme):
    if len(input_df) == 0:
        st.warning("No hay datos para el servicio y estado seleccionados.")
        return None
    
    # Crear mapa coroplético de las colonias
    choropleth = px.choropleth(
        gdf_gustavo, 
        geojson=gdf_gustavo.geometry.__geo_interface__, 
        locations=gdf_gustavo.index, 
        color='num_reportes', 
        color_continuous_scale=input_color_theme,
        range_color=(0, max(gdf_gustavo['num_reportes'])),
        labels={'num_reportes':'Número de Reportes'}
    )
    
    # Añadir puntos de reporte específicos para el servicio seleccionado sin leyenda
    for _, row in input_df.iterrows():
        choropleth.add_scattergeo(
            lon=[row['geometry'].x],
            lat=[row['geometry'].y],
            text=f"Reporte: {row['colonia']} - {row['estado']} - {row['servicio']}",
            mode='markers',
            marker=dict(color='black', size=6),
            showlegend=False  # Esto elimina las leyendas de los puntos
        )

    # Mejorar aspecto visual
    choropleth.update_geos(fitbounds="locations", visible=False)
    choropleth.update_layout(
        template='plotly_dark',
        mapbox_style="open-street-map",
        plot_bgcolor='rgba(0, 0, 0, 0)',
        paper_bgcolor='rgba(0, 0, 0, 0)',
        margin=dict(l=0, r=0, t=0, b=0),
        height=450  # Aumenta el tamaño del mapa sin amontonar lo demás
    )
    return choropleth

# Mapa de calor
def make_heatmap(input_df, input_y, input_x, input_color, input_color_theme):
    if len(input_df) == 0:
        return None

    heatmap = alt.Chart(input_df).mark_rect().encode(
            y=alt.Y(f'{input_y}:O', axis=alt.Axis(title="", titleFontSize=18, titlePadding=15, titleFontWeight=900)),
            x=alt.X(f'{input_x}:O', axis=alt.Axis(title="", titleFontSize=18, titlePadding=15, titleFontWeight=900)),
            color=alt.Color(f'max({input_color}):Q',
                             legend=None,
                             scale=alt.Scale(scheme=input_color_theme)),
            stroke=alt.value('black'),
            strokeWidth=alt.value(0.25),
        ).properties(width=900).configure_axis(
        labelFontSize=12,
        titleFontSize=12
        ) 
    return heatmap

#######################
# Dashboard Main Panel
col = st.columns((1.5, 5, 2), gap='medium')  # Aumentamos el ancho del mapa

with col[0]:
    st.markdown(f'#### Resumen de Reportes por Estado para {selected_servicio}')

    reportes_por_estado = df_selected_servicio.groupby('estado')['geometry'].count().reset_index(name='num_reportes')

    if not reportes_por_estado.empty:
        for _, row in reportes_por_estado.iterrows():
            st.metric(label=row['estado'], value=row['num_reportes'])
    else:
        st.metric(label="N/A", value="0")

with col[1]:
    st.markdown(f'#### Mapa de Reportes de {selected_servicio}')
    
    choropleth = make_choropleth_with_service_points(df_selected_servicio, gdf_gustavo, selected_color_theme)
    if choropleth:
        st.plotly_chart(choropleth, use_container_width=True)
    
    heatmap = make_heatmap(df_reportes, 'colonia', 'estado', 'geometry', selected_color_theme)
    if heatmap:
        st.altair_chart(heatmap, use_container_width=True)
    

with col[2]:
    st.markdown('#### Detalle de Reportes por Servicio y Estado')
    
    if not df_selected_servicio.empty:
        st.dataframe(df_selected_servicio[['colonia', 'estado', 'fecha_reporte', 'coordenadas']],
                     hide_index=True,
                     width=None
                     )
    
    with st.expander('Acerca de los Datos', expanded=True):
        st.write(f'''
            - Datos generados aleatoriamente para representar reportes de {selected_servicio} en la alcaldía Gustavo A. Madero.
            - :orange[**Resumen por Estado**]: distribución de reportes en diferentes estados (Resuelto, Pendiente, En proceso).
            - :orange[**Mapa de Reportes**]: muestra la concentración de reportes por colonia y la ubicación exacta de cada reporte.
            ''')
