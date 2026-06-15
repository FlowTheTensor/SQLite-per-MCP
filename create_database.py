#!/usr/bin/env python3
"""
Initialisiert die Schul-Datenbank mit realistischen Beispieldaten
- Klassen 5-10 mit je ca. 17 Schülern (insgesamt ~100)
- Fächer: Deutsch, Englisch, Mathematik, Informatik, Sport
- Lehrer unterrichten 2 Fächer und maximal 4 Klassen
- Pro Fach: 2 Schulaufgaben + 3 mündliche Noten
"""

import sqlite3
import random
from pathlib import Path
from datetime import datetime, timedelta

# Pfad zur Datenbank
DB_PATH = Path(__file__).parent / "schule.db"

# Konstanten
KLASSEN = ['5a', '5b', '6a', '6b', '7a', '7b', '8a', '8b', '9a', '9b', '10a', '10b']
FAECHER = ['Deutsch', 'Englisch', 'Mathematik', 'Informatik', 'Sport']
SCHUELER_PRO_KLASSE = 17

# Vornamen für Schüler
VORNAMEN_M = ['Max', 'Leon', 'Paul', 'Felix', 'Jonas', 'Lukas', 'Tim', 'Noah', 'Ben', 'Tom',
              'Finn', 'Luca', 'David', 'Julian', 'Elias', 'Moritz', 'Jan', 'Nico', 'Simon']
VORNAMEN_W = ['Anna', 'Lisa', 'Emma', 'Mia', 'Sarah', 'Laura', 'Sophie', 'Lena', 'Julia', 'Hannah',
              'Lea', 'Marie', 'Emily', 'Paula', 'Lara', 'Nina', 'Clara', 'Amelie', 'Sophia']
NACHNAMEN = ['Müller', 'Schmidt', 'Schneider', 'Fischer', 'Weber', 'Meyer', 'Wagner', 'Becker',
             'Schulz', 'Hoffmann', 'Koch', 'Bauer', 'Richter', 'Klein', 'Wolf', 'Schröder',
             'Neumann', 'Schwarz', 'Zimmermann', 'Braun', 'Krüger', 'Hofmann', 'Hartmann',
             'Lange', 'Schmitt', 'Werner', 'Schmitz', 'Krause', 'Meier', 'Lehmann']

# Lehrer-Daten (Vorname, Nachname, Fach1, Fach2)
LEHRER_DATEN = [
    ('Petra', 'Müller', 'Mathematik', 'Informatik'),
    ('Thomas', 'Klein', 'Mathematik', 'Sport'),
    ('Sandra', 'Wolf', 'Deutsch', 'Englisch'),
    ('Michael', 'Schneider', 'Englisch', 'Sport'),
    ('Julia', 'Zimmermann', 'Deutsch', 'Informatik'),
    ('Robert', 'Wagner', 'Mathematik', 'Deutsch'),
    ('Sabine', 'Becker', 'Englisch', 'Deutsch'),
    ('Andreas', 'Hoffmann', 'Sport', 'Informatik'),
    ('Claudia', 'Fischer', 'Mathematik', 'Englisch'),
    ('Martin', 'Schulz', 'Informatik', 'Deutsch')
]

def generiere_geburtsdatum(klasse):
    """Generiert ein passendes Geburtsdatum basierend auf der Klassenstufe"""
    # Extrahiere die Klassenstufe (erste Zeichen bis zum Buchstaben)
    stufe = klasse.rstrip('ab')
    jahr_basis = {'5': 2014, '6': 2013, '7': 2012, '8': 2011, '9': 2010, '10': 2009}
    jahr = jahr_basis.get(stufe, 2010)  # Fallback auf 2010
    monat = random.randint(1, 12)
    tag = random.randint(1, 28)
    return f"{jahr}-{monat:02d}-{tag:02d}"

def generiere_note():
    """Generiert eine realistische Note (1.0 - 6.0)"""
    # Gewichtete Verteilung: mehr mittlere Noten
    noten_pool = [1.0, 1.3, 1.7, 2.0, 2.3, 2.7, 3.0, 3.3, 3.7, 4.0, 4.3, 4.7, 5.0, 5.3, 5.7, 6.0]
    gewichte = [2, 4, 6, 10, 12, 10, 12, 8, 8, 6, 4, 3, 2, 1, 1, 1]
    return random.choices(noten_pool, weights=gewichte)[0]

def generiere_datum(offset_tage_min, offset_tage_max):
    """Generiert ein Datum im aktuellen Schuljahr"""
    heute = datetime.now()
    offset = random.randint(offset_tage_min, offset_tage_max)
    datum = heute - timedelta(days=offset)
    return datum.strftime('%Y-%m-%d')

def create_database():
    """Erstellt die Datenbank mit allen Tabellen und realistischen Beispieldaten"""
    
    # Wenn Datenbank existiert, löschen
    if DB_PATH.exists():
        DB_PATH.unlink()
        print("Alte Datenbank gelöscht.")
    
    # Neue Datenbank erstellen
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("Erstelle Tabellen...")
    
    # Tabelle: Schueler
    cursor.execute("""
        CREATE TABLE schueler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vorname TEXT NOT NULL,
            nachname TEXT NOT NULL,
            klasse TEXT NOT NULL,
            geburtsdatum DATE,
            email TEXT
        )
    """)
    
    # Tabelle: Lehrer (mit fach1 und fach2)
    cursor.execute("""
        CREATE TABLE lehrer (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vorname TEXT NOT NULL,
            nachname TEXT NOT NULL,
            fach1 TEXT NOT NULL,
            fach2 TEXT NOT NULL,
            raum TEXT
        )
    """)
    
    # Tabelle: Kurse (Fach + Klasse + Lehrer)
    cursor.execute("""
        CREATE TABLE kurse (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fach TEXT NOT NULL,
            klasse TEXT NOT NULL,
            lehrer_id INTEGER,
            FOREIGN KEY (lehrer_id) REFERENCES lehrer(id)
        )
    """)
    
    # Tabelle: Noten
    cursor.execute("""
        CREATE TABLE noten (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schueler_id INTEGER NOT NULL,
            kurs_id INTEGER NOT NULL,
            note REAL NOT NULL,
            datum DATE,
            art TEXT,
            FOREIGN KEY (schueler_id) REFERENCES schueler(id),
            FOREIGN KEY (kurs_id) REFERENCES kurse(id)
        )
    """)
    
    print("Generiere Schüler...")
    
    # Schüler generieren
    schueler_data = []
    verwendete_namen = set()
    
    for klasse in KLASSEN:
        for i in range(SCHUELER_PRO_KLASSE):
            # Geschlecht zufällig wählen
            ist_maennlich = random.random() < 0.5
            vorname = random.choice(VORNAMEN_M if ist_maennlich else VORNAMEN_W)
            nachname = random.choice(NACHNAMEN)
            
            # Sicherstellen, dass der Name einzigartig ist
            name_key = f"{vorname}_{nachname}_{klasse}"
            counter = 1
            while name_key in verwendete_namen:
                nachname = random.choice(NACHNAMEN)
                name_key = f"{vorname}_{nachname}_{klasse}"
                counter += 1
                if counter > 10:  # Fallback
                    nachname = f"{nachname}{random.randint(1, 99)}"
                    name_key = f"{vorname}_{nachname}_{klasse}"
                    break
            
            verwendete_namen.add(name_key)
            
            geburtsdatum = generiere_geburtsdatum(klasse)
            email = f"{vorname.lower()}.{nachname.lower()}@schule.de"
            
            schueler_data.append((vorname, nachname, klasse, geburtsdatum, email))
    
    cursor.executemany(
        "INSERT INTO schueler (vorname, nachname, klasse, geburtsdatum, email) VALUES (?, ?, ?, ?, ?)",
        schueler_data
    )
    
    print("Erstelle Lehrer...")
    
    # Lehrer einfügen
    lehrer_data = []
    for vorname, nachname, fach1, fach2 in LEHRER_DATEN:
        raum = f"{random.choice(['A', 'B', 'C'])}{random.randint(101, 305)}"
        lehrer_data.append((vorname, nachname, fach1, fach2, raum))
    
    cursor.executemany(
        "INSERT INTO lehrer (vorname, nachname, fach1, fach2, raum) VALUES (?, ?, ?, ?, ?)",
        lehrer_data
    )
    
    print("Erstelle Kurse...")
    
    # Kurse erstellen (jede Klasse hat alle Fächer)
    # Jedem Lehrer max. 4 Klassen zuweisen
    kurs_data = []
    lehrer_klassen_count = {i: {fach: 0 for fach in FAECHER} for i in range(1, len(LEHRER_DATEN) + 1)}
    
    for klasse in KLASSEN:
        for fach in FAECHER:
            # Finde verfügbare Lehrer für dieses Fach
            verfuegbare_lehrer = []
            for idx, (_, _, fach1, fach2) in enumerate(LEHRER_DATEN, 1):
                if (fach == fach1 or fach == fach2) and lehrer_klassen_count[idx][fach] < 4:
                    verfuegbare_lehrer.append(idx)
            
            if verfuegbare_lehrer:
                lehrer_id = random.choice(verfuegbare_lehrer)
                lehrer_klassen_count[lehrer_id][fach] += 1
                kurs_data.append((fach, klasse, lehrer_id))
            else:
                # Fallback: nehme irgendeinen passenden Lehrer
                for idx, (_, _, fach1, fach2) in enumerate(LEHRER_DATEN, 1):
                    if fach == fach1 or fach == fach2:
                        kurs_data.append((fach, klasse, idx))
                        break
    
    cursor.executemany(
        "INSERT INTO kurse (fach, klasse, lehrer_id) VALUES (?, ?, ?)",
        kurs_data
    )
    
    print("Generiere Noten (dies kann einen Moment dauern)...")
    
    # Noten generieren
    # Hole alle Schüler und Kurse
    cursor.execute("SELECT id, klasse FROM schueler")
    schueler = cursor.fetchall()
    
    cursor.execute("SELECT id, fach, klasse FROM kurse")
    kurse = cursor.fetchall()
    
    noten_data = []
    
    # Für jeden Schüler
    for schueler_id, schueler_klasse in schueler:
        # Finde alle Kurse für diese Klasse
        klassen_kurse = [k for k in kurse if k[2] == schueler_klasse]
        
        for kurs_id, fach, _ in klassen_kurse:
            # 2 Schulaufgaben
            for i in range(2):
                note = generiere_note()
                datum = generiere_datum(10 + i * 40, 50 + i * 40)
                noten_data.append((schueler_id, kurs_id, note, datum, 'Schulaufgabe'))
            
            # 3 mündliche Noten
            for i in range(3):
                note = generiere_note()
                datum = generiere_datum(5 + i * 30, 25 + i * 30)
                noten_data.append((schueler_id, kurs_id, note, datum, 'mündlich'))
    
    cursor.executemany(
        "INSERT INTO noten (schueler_id, kurs_id, note, datum, art) VALUES (?, ?, ?, ?, ?)",
        noten_data
    )
    
    # Änderungen speichern
    conn.commit()
    conn.close()
    
    print(f"\n✓ Datenbank erfolgreich erstellt: {DB_PATH}")
    print(f"✓ {len(schueler_data)} Schüler hinzugefügt")
    print(f"✓ {len(lehrer_data)} Lehrer hinzugefügt")
    print(f"✓ {len(kurs_data)} Kurse hinzugefügt")
    print(f"✓ {len(noten_data)} Noten hinzugefügt")
    print(f"\nStatistik:")
    print(f"  - Klassen: {len(KLASSEN)}")
    print(f"  - Fächer: {len(FAECHER)}")
    print(f"  - Durchschnittliche Noten pro Schüler: {len(noten_data) // len(schueler_data)}")

if __name__ == "__main__":
    create_database()
