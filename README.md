# 🔥 Monitoring šumskih požara - GIS projekat

Projekat za praćenje i analizu šumskih požara korišćenjem PostgreSQL/PostGIS, Python GIS alata i mašinskog učenja.

## 📋 Sadržaj

- [O projektu](#-o-projektu)
- [Tehnologije](#-tehnologije)
- [Struktura projekta](#-struktura-projekta)
- [Instalacija](#-instalacija)
- [Pokretanje](#-pokretanje)
- [Rezultati](#-rezultati)

## 🎯 O projektu

Projekat se sastoji iz tri dela:

### Deo 1 - Python SQL
- PostgreSQL/PostGIS baza sa 7 tabela
- CRUD operacije (Create, Read, Update, Delete)
- JOIN upiti sa WHERE filtriranjem

### Deo 2 - Python GEO
- Shapefile-ovi sa Geofabrika (Srbija)
- Interaktivna mapa sa Folium
- Overlay tehnike: Buffer, Union, Intersection, Clip
- Prostorni upiti: Within, Overlaps
- Raster podloga (Sentinel-2)

### Deo 3 - Python ML
- Detekcija požara na satelitskim snimcima (Random Forest)
- 512 detektovanih poligona
- Konverzija u vektorski format
- Upis u PostGIS bazu
- Izmena atributa kroz aplikaciju

## 🛠 Tehnologije

| Tehnologija | Namena |
|-------------|--------|
| PostgreSQL + PostGIS | Baza podataka sa prostornim funkcijama |
| Python | Programski jezik |
| psycopg2 | Konekcija ka bazi |
| GeoPandas | Rad sa prostornim podacima |
| Folium | Interaktivne mape |
| Scikit-learn | Mašinsko učenje |
| Rasterio | Rad sa satelitskim snimcima |
