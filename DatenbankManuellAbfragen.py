import sqlite3

conn = sqlite3.connect("schule.db")
cursor = conn.cursor()

# Abfrage ausführen
cursor.execute("SELECT * FROM schueler LIMIT 10")

# Alle Zeilen holen
rows = cursor.fetchall()

# Spaltennamen aus dem Cursor
spalten = [description[0] for description in cursor.description]
print(spalten)

# Ergebnisse ausgeben
for row in rows:
    print(row)

conn.close()