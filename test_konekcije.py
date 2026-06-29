import psycopg2

try:
    conn = psycopg2.connect(
        dbname="sumski_pozari_db",
        user="postgres",
        password="milica123",
        host="localhost",
        port="5432"
    )
    cur = conn.cursor()
    cur.execute("SELECT postgis_version();")
    version = cur.fetchone()
    print("✅ Konekcija uspešna!")
    print(f"📌 PostGIS verzija: {version[0]}")
    cur.close()
    conn.close()
except Exception as e:
    print(f"❌ Greška: {e}")