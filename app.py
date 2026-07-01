import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import folium_static
import psycopg2
import plotly.express as px
from shapely import wkt

st.set_page_config(
    page_title="Monitoring sumskih pozara",
    page_icon="🔥",
    layout="wide"
)

DB_CONFIG = {
    'dbname': 'sumski_pozari_db',
    'user': 'postgres',
    'password': 'milica123',
    'host': 'localhost',
    'port': '5432'
}

def get_connection():
    return psycopg2.connect(**DB_CONFIG)

@st.cache_data
def load_pozari():
    conn = get_connection()
    query = """
        SELECT p.id, p.datum_pocetka, p.datum_gasenja, 
               p.intenzitet, p.povrsina_zahvacena_ha,
               p.broj_angazovanih_vatrogasaca,
               s.naziv as parcela, o.naziv as opstina
        FROM pozari p
        LEFT JOIN sumske_parcele s ON p.parcela_id = s.id
        LEFT JOIN opstine o ON s.opstina_id = o.id
        ORDER BY p.datum_pocetka DESC
    """
    df = pd.read_sql(query, conn)
    conn.close()
    if 'datum_pocetka' in df.columns:
        df['datum_pocetka'] = df['datum_pocetka'].astype(str)
    if 'datum_gasenja' in df.columns:
        df['datum_gasenja'] = df['datum_gasenja'].astype(str)
    return df

@st.cache_data
def load_detekcije():
    conn = get_connection()
    query = """
        SELECT id, confidence, status, napomena,
               datum_detekcije, lon, lat
        FROM ml_detekcije
        ORDER BY confidence DESC
    """
    df = pd.read_sql(query, conn)
    conn.close()
    if 'datum_detekcije' in df.columns:
        df['datum_detekcije'] = df['datum_detekcije'].astype(str)
    return df

@st.cache_data
def load_opstine():
    conn = get_connection()
    query = """
        SELECT id, naziv, region, povrsina_km2, broj_stanovnika,
               ST_AsText(geom) as wkt
        FROM opstine
    """
    df = pd.read_sql(query, conn)
    df['geometry'] = df['wkt'].apply(wkt.loads)
    gdf = gpd.GeoDataFrame(df, geometry='geometry', crs='EPSG:4326')
    conn.close()
    return gdf

@st.cache_data
def load_parcele():
    conn = get_connection()
    query = """
        SELECT s.id, s.naziv, s.tip_sume, s.povrsina_ha,
               o.naziv as opstina, ST_AsText(s.geom) as wkt
        FROM sumske_parcele s
        JOIN opstine o ON s.opstina_id = o.id
    """
    df = pd.read_sql(query, conn)
    df['geometry'] = df['wkt'].apply(wkt.loads)
    gdf = gpd.GeoDataFrame(df, geometry='geometry', crs='EPSG:4326')
    conn.close()
    return gdf

@st.cache_data
def load_opozarena():
    conn = get_connection()
    query = """
        SELECT op.id, op.povrsina_ha, op.indeks_dnbr,
               p.datum_pocetka, ST_AsText(op.geom) as wkt
        FROM opozarena_podrucja op
        JOIN pozari p ON op.pozar_id = p.id
    """
    df = pd.read_sql(query, conn)
    if 'datum_pocetka' in df.columns:
        df['datum_pocetka'] = df['datum_pocetka'].astype(str)
    df['geometry'] = df['wkt'].apply(wkt.loads)
    gdf = gpd.GeoDataFrame(df, geometry='geometry', crs='EPSG:4326')
    conn.close()
    return gdf

st.title("Monitoring sumskih pozara")

if st.button("🔄 Osvezi podatke"):
    st.cache_data.clear()
    st.rerun()

st.markdown("---")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Statistika", 
    "Mapa", 
    "ML Detekcije", 
    "CRUD", 
    "Analize"
])

with tab1:
    st.header("Statistika")
    
    df_pozari = load_pozari()
    df_detekcije = load_detekcije()
    gdf_opstine = load_opstine()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Ukupno pozara", len(df_pozari))
    with col2:
        st.metric("ML detekcije", len(df_detekcije))
    with col3:
        st.metric("Opstine", len(gdf_opstine))
    with col4:
        ukupna_povrsina = df_pozari['povrsina_zahvacena_ha'].sum() if len(df_pozari) > 0 else 0
        st.metric("Ukupna povrsina (ha)", f"{ukupna_povrsina:.1f}")
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Pozari po opstinama")
        if len(df_pozari) > 0 and 'opstina' in df_pozari.columns:
            pozari_po_opstini = df_pozari['opstina'].value_counts().reset_index()
            pozari_po_opstini.columns = ['opstina', 'broj_pozara']
            fig = px.bar(pozari_po_opstini, x='opstina', y='broj_pozara',
                         color='opstina', title='Broj pozara po opstinama')
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Intenzitet pozara")
        if len(df_pozari) > 0 and 'intenzitet' in df_pozari.columns:
            intenzitet_count = df_pozari['intenzitet'].value_counts().reset_index()
            intenzitet_count.columns = ['intenzitet', 'broj']
            fig = px.pie(intenzitet_count, values='broj', names='intenzitet',
                         title='Raspodela po intenzitetu')
            st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.header("Interaktivna mapa")
    
    gdf_opstine = load_opstine()
    gdf_parcele = load_parcele()
    gdf_opozarena = load_opozarena()
    
    center_lat = 43.2
    center_lon = 22.5
    
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=9,
        tiles='OpenStreetMap'
    )
    
    folium.GeoJson(
        gdf_opstine,
        name='Opstine',
        style_function=lambda x: {
            'fillColor': 'lightblue',
            'color': 'blue',
            'weight': 2,
            'fillOpacity': 0.2
        },
        tooltip=folium.GeoJsonTooltip(
            fields=['naziv', 'region'],
            aliases=['Opstina:', 'Region:']
        )
    ).add_to(m)
    
    if len(gdf_parcele) > 0:
        folium.GeoJson(
            gdf_parcele,
            name='Sumske parcele',
            style_function=lambda x: {
                'fillColor': 'green',
                'color': 'darkgreen',
                'weight': 1,
                'fillOpacity': 0.5
            },
            tooltip=folium.GeoJsonTooltip(
                fields=['naziv', 'tip_sume'],
                aliases=['Parcele:', 'Tip:']
            )
        ).add_to(m)
    
    if len(gdf_opozarena) > 0:
        folium.GeoJson(
            gdf_opozarena,
            name='Opozarena podrucja',
            style_function=lambda x: {
                'fillColor': 'red',
                'color': 'darkred',
                'weight': 2,
                'fillOpacity': 0.6
            },
            tooltip=folium.GeoJsonTooltip(
                fields=['id', 'povrsina_ha'],
                aliases=['ID:', 'Povrsina (ha):']
            )
        ).add_to(m)
    
    df_det = load_detekcije()
    if len(df_det) > 0:
        for idx, row in df_det.iterrows():
            try:
                lat = float(row['lat'])
                lon = float(row['lon'])
                confidence = float(row['confidence'])
                status = row['status']
                napomena = row['napomena'] if row['napomena'] and str(row['napomena']) not in ['nan', 'None', ''] else 'Nema napomene'
                
                popup_html = f"""
                <div style="font-family: Arial; font-size: 14px;">
                    <b>ID:</b> {row['id']}<br>
                    <b>Pouzdanost:</b> {confidence:.2f}<br>
                    <b>Status:</b> {status}<br>
                    <b>Napomena:</b> <span style="color: #e74c3c; font-weight: bold;">{napomena}</span>
                </div>
                """
                
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=5,
                    color='red' if status in ['potvrđeno', 'potvrdeno'] else 'orange',
                    fill=True,
                    fillColor='red' if status in ['potvrđeno', 'potvrdeno'] else 'orange',
                    fillOpacity=0.8,
                    popup=folium.Popup(popup_html, max_width=300)
                ).add_to(m)
            except Exception as e:
                pass
    
    folium.LayerControl().add_to(m)
    folium_static(m, width=1000, height=600)
    
    st.caption("Crveni poligoni - opozarena podrucja | Zeleno - sumske parcele | Tacke - ML detekcije")

with tab3:
    st.header("ML detekcije pozara")
    
    df_detekcije = load_detekcije()
    
    if len(df_detekcije) > 0:
        col1, col2 = st.columns(2)
        
        with col1:
            status_filter = st.multiselect(
                "Filter po statusu",
                options=df_detekcije['status'].unique(),
                default=df_detekcije['status'].unique()
            )
        
        with col2:
            confidence_threshold = st.slider(
                "Minimalna pouzdanost",
                min_value=0.0,
                max_value=1.0,
                value=0.5,
                step=0.05
            )
        
        df_filtered = df_detekcije[
            (df_detekcije['status'].isin(status_filter)) &
            (df_detekcije['confidence'] >= confidence_threshold)
        ]
        
        st.metric("Prikazano detekcija", len(df_filtered))
        
        st.dataframe(
            df_filtered[['id', 'confidence', 'status', 'napomena', 'datum_detekcije']],
            use_container_width=True
        )
        
        if len(df_filtered) > 0:
            fig = px.histogram(
                df_filtered, 
                x='confidence',
                color='status',
                title='Distribucija pouzdanosti detekcija',
                nbins=20
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Nema detekcija u bazi.")

with tab4:
    st.header("CRUD operacije - Upravljanje detekcijama")
    
    st.subheader("📌 Dodavanje nove detekcije")
    
    with st.expander("➕ Dodaj novu detekciju"):
        col1, col2 = st.columns(2)
        
        with col1:
            nova_confidence = st.slider(
                "Pouzdanost",
                min_value=0.0,
                max_value=1.0,
                value=0.7,
                step=0.01
            )
            novi_status = st.selectbox(
                "Status",
                options=['potvrđeno', 'potvrdeno', 'lazna detekcija', 'na proveri', 'nepoznato']
            )
        
        with col2:
            nova_lat = st.number_input("Latituda", value=43.2, format="%.6f")
            nova_lon = st.number_input("Longituda", value=22.5, format="%.6f")
            nova_napomena = st.text_area("Napomena", value="")
        
        if st.button("💾 Dodaj detekciju", type="primary"):
            if nova_lat and nova_lon:
                conn = get_connection()
                cur = conn.cursor()
                try:
                    cur.execute("""
                        INSERT INTO ml_detekcije 
                        (confidence, status, napomena, lat, lon, datum_detekcije)
                        VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                        RETURNING id
                    """, (nova_confidence, novi_status, nova_napomena, nova_lat, nova_lon))
                    new_id = cur.fetchone()[0]
                    conn.commit()
                    st.success(f"✅ Nova detekcija dodata sa ID: {new_id}")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Greska: {e}")
                    conn.rollback()
                finally:
                    cur.close()
                    conn.close()
            else:
                st.warning("Unesi lat i lon!")
    
    st.markdown("---")
    
    st.subheader("✏️ Izmena postojeće detekcije")
    
    df_detekcije = load_detekcije()
    
    if len(df_detekcije) > 0:
        selected_id = st.selectbox(
            "Izaberi detekciju za izmenu",
            options=df_detekcije['id'].tolist(),
            format_func=lambda x: f"ID {x} - Confidence: {df_detekcije[df_detekcije['id']==x]['confidence'].values[0]:.2f}"
        )
        
        if selected_id:
            row = df_detekcije[df_detekcije['id'] == selected_id].iloc[0]
            
            sve_opcije = ['potvrđeno', 'potvrdeno', 'lazna detekcija', 'na proveri', 'nepoznato']
            
            trenutni_status = row['status']
            if trenutni_status not in sve_opcije:
                sve_opcije.append(trenutni_status)
            
            try:
                default_index = sve_opcije.index(trenutni_status)
            except ValueError:
                default_index = 0
            
            col1, col2 = st.columns(2)
            
            with col1:
                novi_status = st.selectbox(
                    "Novi status",
                    options=sve_opcije,
                    index=default_index,
                    key="status_update"
                )
            
            with col2:
                trenutna_napomena = row['napomena'] if row['napomena'] and str(row['napomena']) not in ['nan', 'None'] else ""
                nova_napomena = st.text_area("Napomena", value=trenutna_napomena, key="napomena_update")
            
            if st.button("Sacuvaj promene", type="primary"):
                conn = get_connection()
                cur = conn.cursor()
                try:
                    cur.execute("""
                        UPDATE ml_detekcije 
                        SET status = %s, napomena = %s
                        WHERE id = %s
                    """, (novi_status, nova_napomena, int(selected_id)))
                    conn.commit()
                    st.success(f"✅ Detekcija ID {selected_id} uspesno azurirana! Napomena: '{nova_napomena}'")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Greska: {e}")
                    conn.rollback()
                finally:
                    cur.close()
                    conn.close()
    else:
        st.info("Nema detekcija za izmenu.")
    
    st.markdown("---")
    
    st.subheader("🗑️ Brisanje detekcije")
    
    delete_id = st.number_input("ID detekcije za brisanje", min_value=1, step=1)
    if st.button("Obrisi", type="secondary"):
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM ml_detekcije WHERE id = %s", (int(delete_id),))
            conn.commit()
            st.success(f"✅ Detekcija ID {delete_id} obrisana!")
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            st.error(f"❌ Greska: {e}")
            conn.rollback()
        finally:
            cur.close()
            conn.close()

with tab5:
    st.header("Prostorne analize")
    
    df_pozari = load_pozari()
    df_detekcije = load_detekcije()
    
    if len(df_pozari) > 0:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Povrsina pozara po opstinama")
            if 'opstina' in df_pozari.columns:
                povrsina_po_opstini = df_pozari.groupby('opstina')['povrsina_zahvacena_ha'].sum().reset_index()
                fig = px.bar(povrsina_po_opstini, x='opstina', y='povrsina_zahvacena_ha',
                             title='Ukupna povrsina pozara (ha)',
                             color='opstina')
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("Broj vatrogasaca po pozaru")
            if 'povrsina_zahvacena_ha' in df_pozari.columns and 'broj_angazovanih_vatrogasaca' in df_pozari.columns:
                fig = px.scatter(df_pozari, x='povrsina_zahvacena_ha', y='broj_angazovanih_vatrogasaca',
                                 title='Angazovani vatrogasci vs povrsina',
                                 labels={'povrsina_zahvacena_ha': 'Povrsina (ha)',
                                         'broj_angazovanih_vatrogasaca': 'Broj vatrogasaca'},
                                 color='intenzitet' if 'intenzitet' in df_pozari.columns else None)
                st.plotly_chart(fig, use_container_width=True)
    
    if len(df_detekcije) > 0:
        st.subheader("Status detekcija")
        status_count = df_detekcije['status'].value_counts().reset_index()
        status_count.columns = ['status', 'broj']
        fig = px.pie(status_count, values='broj', names='status', title='Status ML detekcija')
        st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.caption("Projekat: Monitoring sumskih pozara | PostgreSQL/PostGIS + Python + Streamlit")