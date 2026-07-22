# SV Gastronomie Mensa Kalender

Dieses Repository erzeugt automatisch iCalendar-Dateien (`.ics`) mit den täglichen Mittagsmenüs von [sv-gastronomie.ch](https://sv-gastronomie.ch)-Restaurants.

**Nicht mit der SV Group verbunden.** Dies ist ein unabhängiges, inoffizielles Projekt, das öffentlich sichtbare Menüdaten von der sv-gastronomie.ch-Website ausliest. Es wird nicht von der SV Group oder der SV (Schweiz) AG unterstützt, gesponsert oder ist in irgendeiner Form mit ihr verbunden.

## Dateien

* `scripts/fetch_menu.py` - Hauptscript, das die SV-Gastronomie-Menüseite rendert (per headless Chrome, da es sich um eine JavaScript-Single-Page-App handelt) und die Kalenderdateien erzeugt
* `config/restaurants.yaml` - Liste der konfigurierten Restaurants (hier anpassen, um eigene hinzuzufügen)
* `docs/*.ics` - Generierte iCalendar-Dateien, eine pro konfiguriertem Restaurant (täglich aktualisiert)
* `requirements.txt` - Python-Abhängigkeiten

## Verwendung

### Kalender abonnieren

Sobald GitHub Pages in einem Fork aktiviert ist, ist jedes konfigurierte Restaurant erreichbar unter:

```
https://<dein-username>.github.io/<repo-name>/<slug>.ics
```

Diese URL als **Kalender-Abo** (nicht als Download!) in deiner Kalender-App hinzufügen:

- **Google Calendar:** Einstellungen → Kalender hinzufügen → Per URL
- **Apple Kalender:** Ablage/Kalender Icon → Hinzufügen → Neues Kalenderabo
- **Outlook:** [Outlook - Calendar hinzufügen](https://outlook.office.com/calendar/addcalendar) dann Kalender hinzufügen → Aus dem Internet abonnieren

Wenn du dieses Repository direkt benutzen möchtest (Im Moment Wert zu Accenture Restaurant gesetzt) : 

```
https://glukas.github.io/svgroup-menu-zu-ical/docs/accenture-zuerich-sihlcity.ics
```

### Manuell ausführen

```
pip install -r requirements.txt
python scripts/fetch_menu.py
```

Voraussetzung: Google Chrome ist lokal installiert (der passende ChromeDriver wird automatisch heruntergeladen).

## Automatisierung

Die Kalender werden täglich automatisch über GitHub Actions aktualisiert. Der Workflow:

1. Rendert die konfigurierten sv-gastronomie.ch-Menüseiten per headless Chrome
2. Extrahiert die aktuellen Menüeinträge für jeden verfügbaren Tag
3. Erzeugt aktualisierte `.ics`-Dateien in `docs/`
4. Committet und pusht die Änderungen ins Repository

## Datenquelle

Die Menüdaten werden direkt aus dem gerenderten HTML der `https://sv-gastronomie.ch/menu/...`-Seiten ausgelesen. Es gibt keine öffentliche API für diese Daten, daher wird die Seite so gerendert, wie es ein echter Browser tun würde (Selenium + headless Chrome).

## Eigenes Restaurant gewünscht? Forken!

Dieses Repo ist so gebaut, dass du es forken und mit einer einfachen Config-Änderung auf jedes beliebige SV-Gastronomie-Restaurant umstellen kannst - keine Programmierkenntnisse nötig.

### 1. Dieses Repository forken

Oben rechts auf **Fork** klicken.

### 2. Den Menü-Link deines Restaurants holen

1. Auf [sv-gastronomie.ch](https://sv-gastronomie.ch) gehen
2. Bei **Standort** deinen gewünschten Standort auswählen
3. Bei **Menüplan** (direkt darunter) den gewünschten Menüplan auswählen
4. Auf **OK** klicken
5. Die URL aus der Adresszeile deines Browsers kopieren - das ist der direkte Menü-Link deines Restaurants

### 3. `config/restaurants.yaml` anpassen

```yaml
restaurants:
  - slug: mein-restaurant         # frei wählbar, wird Teil der .ics-URL - nur Kleinbuchstaben und Bindestriche
    name: "Mein Restaurant Name"  # erscheint als Kalendername und im Termin
    url: "https://sv-gastronomie.ch/menu/..."   # der in Schritt 2 kopierte Link
```

Du kannst beliebig viele Restaurants hinzufügen, indem du weitere Einträge ergänzt. Um eines vorübergehend zu pausieren (z.B. bei Betriebsferien), einfach mit `#` auskommentieren statt löschen.

### 4. GitHub Pages aktivieren

In deinem Fork: **Settings → Pages → Source: Deploy from a branch → Branch: `main`, Ordner: `/docs`**.

### 5. Workflow einmal manuell ausführen

**Actions → Update Menu → Run workflow** - danach erscheint deine `.ics`-Datei bzw. deine Dateien in `docs/` und ist unter der URL aus dem Abschnitt "Kalender abonnieren" oben erreichbar.

Fertig - ab jetzt kümmert sich der tägliche Cron-Job automatisch um den Rest.

## Bekannte Einschränkungen

- Es werden nur Tage abgerufen, die die Website selbst bereits veröffentlicht hat (in der Regel die aktuelle Woche) - weiter in der Zukunft liegende Menüs gibt es schlicht noch nicht.
- Wochenenden werden übersprungen.
- Restaurants in Betriebsferien liefern keine Einträge, bis sie wieder öffnen - in der Zwischenzeit einfach in `restaurants.yaml` auskommentieren.

## Lizenz

MIT
