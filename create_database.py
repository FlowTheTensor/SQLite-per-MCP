#!/usr/bin/env python3
"""
Erstellt die Schul-Datenbank schule.db mit festen Beispieldaten.

Die Daten sind dieselben wie in der Lernsituation LS-KI-Agenten
(js/agentsim.js, Konstante DB_START). So kommen im Browser und hier
dieselben Ergebnisse heraus. Bei Änderungen beide Stellen gleich halten.

Bewusst eingebaute Fälle für den Unterricht:
- Klasse 7a hat genau 5 Schüler.
- Paul und Emma Werner sind beide in der 7a ("Welchen Werner?").
- Ben Fischer (7a) hat schlechte Noten (Beispiel für Prompt-Injection).
- Kurs 6 = Mathematik 7a, Schnitt 2,76.
- Kurs 2 = Informatik 10a, Schnitt 2,05.
  Kurs 8 = Informatik 10b, Schnitt 3,41. Beide zusammen: 2,60
  (Team-Auftrag "Rückmeldung an die 10a in Informatik", stille Post).

Alle Daten sind erfunden. Ein erneuter Aufruf setzt die Datenbank zurück.
"""

import sqlite3
from pathlib import Path

# Pfad zur Datenbank
DB_PATH = Path(__file__).parent / "schule.db"

# (id, vorname, nachname, klasse, geburtsdatum, email)
SCHUELER = [
    (1, 'Anna', 'Müller', '5a', '2014-03-12', 'anna.mueller@schule.de'),
    (2, 'Leon', 'Schmidt', '5a', '2014-07-02', 'leon.schmidt@schule.de'),
    (3, 'Mia', 'Weber', '6b', '2013-11-23', 'mia.weber@schule.de'),
    (4, 'Felix', 'Koch', '7a', '2012-01-30', 'felix.koch@schule.de'),
    (5, 'Lena', 'Bauer', '8b', '2011-05-17', 'lena.bauer@schule.de'),
    (6, 'Jonas', 'Richter', '9a', '2010-09-08', 'jonas.richter@schule.de'),
    (7, 'Sophie', 'Klein', '10a', '2009-12-01', 'sophie.klein@schule.de'),
    (8, 'Noah', 'Wolf', '10a', '2009-02-14', 'noah.wolf@schule.de'),
    (9, 'Clara', 'Bauer', '7a', '2012-04-19', 'clara.bauer@schule.de'),
    (10, 'Paul', 'Werner', '7a', '2012-08-03', 'paul.werner@schule.de'),
    (11, 'Emma', 'Werner', '7a', '2012-02-27', 'emma.werner@schule.de'),
    (12, 'Ben', 'Fischer', '7a', '2012-10-11', 'ben.fischer@schule.de'),
    (13, 'Lina', 'Hoffmann', '5a', '2014-06-21', 'lina.hoffmann@schule.de'),
    (14, 'Tim', 'Becker', '5a', '2014-01-09', 'tim.becker@schule.de'),
    (15, 'Lukas', 'Schwarz', '10a', '2009-06-05', 'lukas.schwarz@schule.de'),
    (16, 'Hannah', 'Neumann', '10a', '2009-09-18', 'hannah.neumann@schule.de'),
    (17, 'Elias', 'Braun', '10a', '2010-01-22', 'elias.braun@schule.de'),
    (18, 'Marie', 'Hartmann', '10a', '2009-04-30', 'marie.hartmann@schule.de'),
    (19, 'Finn', 'Krüger', '10b', '2009-08-14', 'finn.krueger@schule.de'),
    (20, 'Laura', 'Lange', '10b', '2009-11-02', 'laura.lange@schule.de'),
    (21, 'David', 'Vogel', '10b', '2010-02-11', 'david.vogel@schule.de'),
    (22, 'Sarah', 'König', '10b', '2009-07-27', 'sarah.koenig@schule.de'),
]

# (id, vorname, nachname, fach1, fach2, raum)
LEHRER = [
    (1, 'Petra', 'Müller', 'Mathematik', 'Informatik', 'B204'),
    (2, 'Thomas', 'Klein', 'Mathematik', 'Sport', 'A112'),
    (3, 'Sandra', 'Wolf', 'Deutsch', 'Englisch', 'C301'),
    (4, 'Michael', 'Schneider', 'Englisch', 'Sport', 'A207'),
    (5, 'Julia', 'Zimmermann', 'Deutsch', 'Informatik', 'B118'),
    (6, 'Robert', 'Wagner', 'Mathematik', 'Deutsch', 'C105'),
    (7, 'Sabine', 'Becker', 'Englisch', 'Deutsch', 'C212'),
    (8, 'Andreas', 'Hoffmann', 'Sport', 'Informatik', 'A015'),
    (9, 'Claudia', 'Fischer', 'Mathematik', 'Englisch', 'B310'),
    (10, 'Martin', 'Schulz', 'Informatik', 'Deutsch', 'B220'),
]

# (id, fach, klasse, lehrer_id)
KURSE = [
    (1, 'Mathematik', '5a', 1),
    (2, 'Informatik', '10a', 5),
    (3, 'Deutsch', '5a', 3),
    (4, 'Sport', '7a', 2),
    (5, 'Englisch', '8b', 4),
    (6, 'Mathematik', '7a', 2),
    (7, 'Deutsch', '7a', 3),
    (8, 'Informatik', '10b', 10),
]

# (id, schueler_id, kurs_id, note, datum, art)
NOTEN = [
    (1, 1, 1, 2.0, '2026-10-08', 'Schulaufgabe'),
    (2, 1, 3, 1.7, '2026-10-15', 'mündlich'),
    (3, 2, 1, 3.3, '2026-10-08', 'Schulaufgabe'),
    (4, 7, 2, 1.0, '2026-10-20', 'Schulaufgabe'),
    (5, 8, 2, 2.3, '2026-10-20', 'Schulaufgabe'),
    (6, 4, 4, 1.3, '2026-10-22', 'mündlich'),
    (7, 13, 1, 1.3, '2026-10-08', 'Schulaufgabe'),
    (8, 14, 1, 4.0, '2026-10-08', 'Schulaufgabe'),
    (9, 1, 1, 2.3, '2026-11-05', 'mündlich'),
    (10, 2, 1, 2.7, '2026-11-05', 'mündlich'),
    # Mathematik 7a (Kurs 6), Schnitt 2,76
    (11, 4, 6, 2.7, '2026-10-14', 'Schulaufgabe'),
    (12, 9, 6, 1.7, '2026-10-14', 'Schulaufgabe'),
    (13, 10, 6, 3.7, '2026-10-14', 'Schulaufgabe'),
    (14, 11, 6, 2.0, '2026-10-14', 'Schulaufgabe'),
    (15, 12, 6, 4.3, '2026-10-14', 'Schulaufgabe'),
    (16, 9, 6, 1.0, '2026-11-04', 'mündlich'),
    (17, 10, 6, 3.0, '2026-11-04', 'mündlich'),
    (18, 12, 6, 3.7, '2026-11-04', 'mündlich'),
    # Deutsch 7a (Kurs 7)
    (19, 4, 7, 2.0, '2026-10-21', 'Schulaufgabe'),
    (20, 9, 7, 2.3, '2026-10-21', 'Schulaufgabe'),
    (21, 11, 7, 1.3, '2026-10-21', 'Schulaufgabe'),
    (22, 12, 7, 3.3, '2026-10-21', 'Schulaufgabe'),
    # Informatik 10a (Kurs 2, zusammen mit id 4 und 5): Schnitt 2,05
    (23, 15, 2, 2.0, '2026-10-20', 'Schulaufgabe'),
    (24, 16, 2, 1.7, '2026-10-20', 'Schulaufgabe'),
    (25, 17, 2, 3.0, '2026-10-20', 'Schulaufgabe'),
    (26, 18, 2, 2.7, '2026-10-20', 'Schulaufgabe'),
    (27, 7, 2, 1.3, '2026-11-06', 'mündlich'),
    (28, 8, 2, 2.0, '2026-11-06', 'mündlich'),
    (29, 15, 2, 2.3, '2026-11-06', 'mündlich'),
    (30, 16, 2, 1.0, '2026-11-06', 'mündlich'),
    (31, 17, 2, 3.3, '2026-11-06', 'mündlich'),
    (32, 18, 2, 2.0, '2026-11-06', 'mündlich'),
    # Informatik 10b (Kurs 8): deutlich schwächer, Schnitt 3,41
    (33, 19, 8, 3.7, '2026-10-21', 'Schulaufgabe'),
    (34, 20, 8, 3.0, '2026-10-21', 'Schulaufgabe'),
    (35, 21, 8, 4.3, '2026-10-21', 'Schulaufgabe'),
    (36, 22, 8, 3.3, '2026-10-21', 'Schulaufgabe'),
    (37, 19, 8, 3.3, '2026-11-07', 'mündlich'),
    (38, 20, 8, 2.7, '2026-11-07', 'mündlich'),
    (39, 21, 8, 4.0, '2026-11-07', 'mündlich'),
    (40, 22, 8, 3.0, '2026-11-07', 'mündlich'),
]


def create_database():
    """Erstellt die Datenbank mit allen Tabellen und den festen Beispieldaten"""

    # Wenn Datenbank existiert, löschen
    if DB_PATH.exists():
        DB_PATH.unlink()
        print("Alte Datenbank gelöscht.")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("Erstelle Tabellen...")

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

    # Ein Kurs = ein Fach in einer Klasse mit einer Lehrkraft
    cursor.execute("""
        CREATE TABLE kurse (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fach TEXT NOT NULL,
            klasse TEXT NOT NULL,
            lehrer_id INTEGER,
            FOREIGN KEY (lehrer_id) REFERENCES lehrer(id)
        )
    """)

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

    print("Trage Beispieldaten ein...")

    cursor.executemany(
        "INSERT INTO schueler (id, vorname, nachname, klasse, geburtsdatum, email) VALUES (?, ?, ?, ?, ?, ?)",
        SCHUELER
    )
    cursor.executemany(
        "INSERT INTO lehrer (id, vorname, nachname, fach1, fach2, raum) VALUES (?, ?, ?, ?, ?, ?)",
        LEHRER
    )
    cursor.executemany(
        "INSERT INTO kurse (id, fach, klasse, lehrer_id) VALUES (?, ?, ?, ?)",
        KURSE
    )
    cursor.executemany(
        "INSERT INTO noten (id, schueler_id, kurs_id, note, datum, art) VALUES (?, ?, ?, ?, ?, ?)",
        NOTEN
    )

    conn.commit()
    conn.close()

    print(f"\n✓ Datenbank erfolgreich erstellt: {DB_PATH}")
    print(f"✓ {len(SCHUELER)} Schüler, {len(LEHRER)} Lehrer, {len(KURSE)} Kurse, {len(NOTEN)} Noten")


if __name__ == "__main__":
    create_database()
