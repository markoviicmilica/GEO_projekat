import os
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

@st.cache_data(ttl=300)
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

@st.cache_data(ttl=300)
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

@st.cache_data(ttl=300)
def load_opstine():
    conn = get_connection()
    query = """
        SELECT id, naziv, region, povrsina_km2, broj_stanovnika,
               ST_AsText(geom) as wkt
        FROM opstine
    """
    df = pd.read_sql(query, conn)
    conn.close()
    df['geometry'] = df['wkt'].apply(wkt.loads)
    gdf = gpd.GeoDataFrame(df, geometry='geometry', crs='EPSG:4326')
    return gdf

@st.cache_data(ttl=300)
def load_parcele():
    conn = get_connection()
    query = """
        SELECT s.id, s.naziv, s.tip_sume, s.povrsina_ha,
               o.naziv as opstina, ST_AsText(s.geom) as wkt
        FROM sumske_parcele s
        JOIN opstine o ON s.opstina_id = o.id
    """
    df = pd.read_sql(query, conn)
    conn.close()
    df['geometry'] = df['wkt'].apply(wkt.loads)
    gdf = gpd.GeoDataFrame(df, geometry='geometry', crs='EPSG:4326')
    return gdf

@st.cache_data(ttl=300)
def load_opozarena():
    conn = get_connection()
    query = """
        SELECT op.id, op.povrsina_ha, op.indeks_dnbr,
               p.datum_pocetka, ST_AsText(op.geom) as wkt
        FROM opozarena_podrucja op
        JOIN pozari p ON op.pozar_id = p.id
    """
    df = pd.read_sql(query, conn)
    conn.close()
    if 'datum_pocetka' in df.columns:
        df['datum_pocetka'] = df['datum_pocetka'].astype(str)
    df['geometry'] = df['wkt'].apply(wkt.loads)
    gdf = gpd.GeoDataFrame(df, geometry='geometry', crs='EPSG:4326')
    return gdf

st.title("🔥 Monitoring sumskih pozara")

if st.button("🔄 Osvezi podatke"):
    st.cache_data.clear()
    st.rerun()

st.markdown("---")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Statistika",
    "🗺 Mapa",
    "🤖 ML Detekcije",
    "⚙️ CRUD",
    "📈 Analize"
])

# Statistika
with tab1:
    st.header("Statistika požara")

    df_pozari    = load_pozari()
    df_detekcije = load_detekcije()
    gdf_opstine  = load_opstine()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Ukupno požara", len(df_pozari))
    with col2:
        st.metric("ML detekcije", len(df_detekcije))
    with col3:
        st.metric("Opštine", len(gdf_opstine))
    with col4:
        ukupna = df_pozari['povrsina_zahvacena_ha'].sum() if len(df_pozari) > 0 else 0
        st.metric("Ukupna površina (ha)", f"{ukupna:.1f}")

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Požari po opštinama")
        if len(df_pozari) > 0 and 'opstina' in df_pozari.columns:
            ppo = df_pozari['opstina'].value_counts().reset_index()
            ppo.columns = ['opstina', 'broj_pozara']
            fig = px.bar(ppo, x='opstina', y='broj_pozara',
                         color='opstina', title='Broj požara po opštinama')
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Intenzitet požara")
        if len(df_pozari) > 0 and 'intenzitet' in df_pozari.columns:
            ic = df_pozari['intenzitet'].value_counts().reset_index()
            ic.columns = ['intenzitet', 'broj']
            fig = px.pie(ic, values='broj', names='intenzitet',
                         title='Raspodela po intenzitetu')
            st.plotly_chart(fig, use_container_width=True)

# Mapa

with tab2:
    st.header("Interaktivna mapa")

    gdf_opstine   = load_opstine()
    gdf_parcele   = load_parcele()
    gdf_opozarena = load_opozarena()

    center_lat = 43.2
    center_lon = 22.5

    # Esri satelitska podloga
    m = folium.Map(location=[center_lat, center_lon], zoom_start=9, tiles=None)
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri World Imagery',
        name='Satelitska podloga',
        overlay=False,
        control=True
    ).add_to(m)
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
        attr='Esri Labels',
        name='Nazivi mesta',
        overlay=True,
        control=True
    ).add_to(m)

    folium.GeoJson(
        gdf_opstine,
        name='Opštine',
        style_function=lambda x: {
            'fillColor': 'transparent',
            'color': 'white',
            'weight': 2,
            'fillOpacity': 0
        },
        tooltip=folium.GeoJsonTooltip(
            fields=['naziv', 'region'],
            aliases=['Opština:', 'Region:']
        )
    ).add_to(m)

    if len(gdf_parcele) > 0:
        folium.GeoJson(
            gdf_parcele,
            name='Šumske parcele',
            style_function=lambda x: {
                'fillColor': '#2ecc71',
                'color': 'darkgreen',
                'weight': 1,
                'fillOpacity': 0.5
            },
            tooltip=folium.GeoJsonTooltip(
                fields=['naziv', 'tip_sume'],
                aliases=['Parcela:', 'Tip:']
            )
        ).add_to(m)

    if len(gdf_opozarena) > 0:
        folium.GeoJson(
            gdf_opozarena,
            name='Opožarena područja',
            style_function=lambda x: {
                'fillColor': '#e74c3c',
                'color': 'darkred',
                'weight': 2,
                'fillOpacity': 0.6
            },
            tooltip=folium.GeoJsonTooltip(
                fields=['id', 'povrsina_ha'],
                aliases=['ID:', 'Površina (ha):']
            )
        ).add_to(m)

    df_det = load_detekcije()
    if len(df_det) > 0:
        for idx, row in df_det.iterrows():
            try:
                lat        = float(row['lat'])
                lon        = float(row['lon'])
                confidence = float(row['confidence'])
                status     = row['status']
                napomena   = row['napomena'] if row['napomena'] and \
                             str(row['napomena']) not in ['nan', 'None', ''] \
                             else 'Nema napomene'

                popup_html = f"""
                <div style="font-family: Arial; font-size: 14px;">
                    <b>ID:</b> {row['id']}<br>
                    <b>Pouzdanost:</b> {confidence:.2f}<br>
                    <b>Status:</b> {status}<br>
                    <b>Napomena:</b> <span style="color:#e74c3c;font-weight:bold;">{napomena}</span>
                </div>
                """
                boja = 'red' if status in ['potvrđeno', 'potvrdeno'] else 'orange'
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=5,
                    color=boja,
                    fill=True,
                    fillColor=boja,
                    fillOpacity=0.8,
                    popup=folium.Popup(popup_html, max_width=300)
                ).add_to(m)
            except Exception:
                pass

    folium.LayerControl().add_to(m)
    folium_static(m, width=1000, height=600)
    st.caption("Crveni poligoni — opožarena područja | Zeleno — šumske parcele | Tačke — ML detekcije")


# ML Detekcije
with tab3:
    st.header("ML detekcije požara")

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
                min_value=0.0, max_value=1.0,
                value=0.5, step=0.05
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
                df_filtered, x='confidence', color='status',
                title='Distribucija pouzdanosti detekcija', nbins=20
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Nema detekcija u bazi.")

# CRUD

with tab4:
    st.header("CRUD operacije — Upravljanje detekcijama")

    # CREATE
    st.subheader("➕ Dodavanje nove detekcije")
    with st.expander("Dodaj novu detekciju"):
        col1, col2 = st.columns(2)
        with col1:
            nova_confidence = st.slider("Pouzdanost", 0.0, 1.0, 0.7, 0.01)
            novi_status = st.selectbox(
                "Status",
                options=['na čekanju', 'potvrđeno', 'lažna detekcija', 'potrebna provera']
            )
        with col2:
            nova_lat     = st.number_input("Latituda",  value=43.2, format="%.6f")
            nova_lon     = st.number_input("Longituda", value=22.5, format="%.6f")
            nova_napomena = st.text_area("Napomena", value="")

        if st.button("💾 Dodaj detekciju", type="primary"):
            conn = get_connection()
            cur  = conn.cursor()
            try:
                # IZMENA: upisuje i geom kao Point geometriju
                cur.execute("""
                    INSERT INTO ml_detekcije
                    (confidence, status, napomena, lat, lon,
                     datum_detekcije, geom)
                    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP,
                            ST_Buffer(
                                ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                                50
                            )::geometry)
                    RETURNING id
                """, (nova_confidence, novi_status, nova_napomena or None,
                      nova_lat, nova_lon, nova_lon, nova_lat))
                new_id = cur.fetchone()[0]
                conn.commit()
                st.success(f"✅ Nova detekcija dodata sa ID: {new_id}")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                conn.rollback()
                st.error(f"❌ Greška: {e}")
            finally:
                cur.close()
                conn.close()

    st.markdown("---")

    # UPDATE
    st.subheader("✏️ Izmena postojeće detekcije")
    df_detekcije = load_detekcije()

    if len(df_detekcije) > 0:
        selected_id = st.selectbox(
            "Izaberi detekciju za izmenu",
            options=df_detekcije['id'].tolist(),
            format_func=lambda x: f"ID {x} — Confidence: {df_detekcije[df_detekcije['id']==x]['confidence'].values[0]:.2f}"
        )

        if selected_id:
            row = df_detekcije[df_detekcije['id'] == selected_id].iloc[0]

            sve_opcije = ['na čekanju', 'potvrđeno', 'lažna detekcija', 'potrebna provera']
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
                    "Novi status", options=sve_opcije,
                    index=default_index, key="status_update"
                )
            with col2:
                trenutna_napomena = row['napomena'] \
                    if row['napomena'] and str(row['napomena']) not in ['nan', 'None'] \
                    else ""
                nova_napomena = st.text_area(
                    "Napomena", value=trenutna_napomena, key="napomena_update"
                )

            if st.button("💾 Sačuvaj promene", type="primary"):
                conn = get_connection()
                cur  = conn.cursor()
                try:
                    cur.execute("""
                        UPDATE ml_detekcije
                        SET status = %s, napomena = %s
                        WHERE id = %s
                    """, (novi_status, nova_napomena or None, int(selected_id)))
                    conn.commit()
                    if cur.rowcount == 0:
                        st.warning(f"⚠ ID {selected_id} nije pronađen")
                    else:
                        st.success(f"✅ Detekcija ID {selected_id} ažurirana!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    conn.rollback()
                    st.error(f"❌ Greška: {e}")
                finally:
                    cur.close()
                    conn.close()
    else:
        st.info("Nema detekcija za izmenu.")

    st.markdown("---")

    # DELETE
    st.subheader("🗑️ Brisanje detekcije")
    delete_id = st.number_input("ID detekcije za brisanje", min_value=1, step=1)
    if st.button("🗑 Obriši", type="secondary"):
        conn = get_connection()
        cur  = conn.cursor()
        try:
            cur.execute("DELETE FROM ml_detekcije WHERE id = %s", (int(delete_id),))
            conn.commit()
            if cur.rowcount == 0:
                st.warning(f"⚠ Detekcija ID {delete_id} nije pronađena")
            else:
                st.success(f"✅ Detekcija ID {delete_id} obrisana!")
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            conn.rollback()
            st.error(f"❌ Greška: {e}")
        finally:
            cur.close()
            conn.close()

#  Analize
with tab5:
    st.header("Prostorne analize")

    df_pozari    = load_pozari()
    df_detekcije = load_detekcije()

    if len(df_pozari) > 0:
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Površina požara po opštinama")
            if 'opstina' in df_pozari.columns:
                ppo = df_pozari.groupby('opstina')['povrsina_zahvacena_ha'].sum().reset_index()
                fig = px.bar(ppo, x='opstina', y='povrsina_zahvacena_ha',
                             title='Ukupna površina požara (ha)', color='opstina')
                st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Vatrogasci vs površina")
            if 'povrsina_zahvacena_ha' in df_pozari.columns and \
               'broj_angazovanih_vatrogasaca' in df_pozari.columns:
                fig = px.scatter(
                    df_pozari,
                    x='povrsina_zahvacena_ha',
                    y='broj_angazovanih_vatrogasaca',
                    title='Angažovani vatrogasci vs površina',
                    labels={
                        'povrsina_zahvacena_ha': 'Površina (ha)',
                        'broj_angazovanih_vatrogasaca': 'Broj vatrogasaca'
                    },
                    color='intenzitet' if 'intenzitet' in df_pozari.columns else None
                )
                st.plotly_chart(fig, use_container_width=True)

    if len(df_detekcije) > 0:
        st.subheader("Status ML detekcija")
        sc = df_detekcije['status'].value_counts().reset_index()
        sc.columns = ['status', 'broj']
        fig = px.pie(sc, values='broj', names='status',
                     title='Status ML detekcija')
        st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.caption("Projekat: Monitoring šumskih požara | PostgreSQL/PostGIS + Python + Streamlit")