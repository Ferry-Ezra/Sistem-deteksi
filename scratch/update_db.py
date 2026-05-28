import MySQLdb

try:
    conn = MySQLdb.connect(
        host="localhost",
        user="root",
        passwd="",
        db="tugas_akhir"
    )
    cursor = conn.cursor()
    
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN alamat TEXT")
        print("Kolom alamat ditambahkan.")
    except Exception as e:
        print("alamat:", e)
        
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN latitude VARCHAR(50)")
        print("Kolom latitude ditambahkan.")
    except Exception as e:
        print("latitude:", e)
        
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN longitude VARCHAR(50)")
        print("Kolom longitude ditambahkan.")
    except Exception as e:
        print("longitude:", e)

    conn.commit()
    cursor.close()
    conn.close()
    print("Selesai update DB.")
except Exception as e:
    print("Error:", e)
