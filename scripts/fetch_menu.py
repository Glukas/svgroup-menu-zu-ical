

from __future__ import annotations

import hashlib
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml
from bs4 import BeautifulSoup
from icalendar import Calendar, Event
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("sv_mensa_ical")

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "restaurants.yaml"
OUTPUT_DIR = ROOT / "docs"

# Wie viele Tage ab heute abgerufen werden sollen (Wochenenden werden automatisch übersprungen)
DAYS_AHEAD = 2

# Auf True setzen, um das gerenderte HTML zusätzlich in debug_page_{tag}.html zu speichern (hilfreich, falls sich die Struktur mal wieder ändert)
DEBUG_DUMP_HTML = False


class ParserError(Exception):
    """Wird geworfen, wenn die Seite nicht mehr dem erwarteten Format entspricht."""


@dataclass
class MenuEntry:
    day: date
    category: str | None
    dish: str
    description: str | None = None
    price: str | None = None  
    tags: list[str] = field(default_factory=list)

    def content_hash(self) -> str:
        raw = f"{self.day}|{self.category}|{self.dish}|{self.description}|{self.price}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def dedup_key(self) -> tuple:
        """Identifiziert inhaltlich identische Einträge (z.B. doppelte
        'Sihlou closed'-Meldungen), unabhängig von Preis/Tags."""
        return (self.category, self.dish, self.description)


def load_restaurants() -> list[dict]:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg["restaurants"]


def build_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--lang=de-CH")
    options.add_argument("--window-size=1400,2000")

    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def fetch_rendered_page(driver: webdriver.Chrome, url: str, debug_tag: str = "") -> str:
    """Rendert die Seite per Selenium (headless Chrome) und gibt den
    finalen (nach JS-Ausführung entstandenen) HTML-Inhalt zurück."""
    try:
        driver.set_page_load_timeout(30)
        driver.get(url)
       
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "app-category, app-menu-card"))
            )
        except Exception:
            log.warning("Timeout beim Warten auf app-category für %s", url)
        html = driver.page_source
    except Exception as e:
        raise ParserError(f"Fehler beim Laden von {url}: {e}") from e

    if DEBUG_DUMP_HTML:
        debug_path = ROOT / f"debug_page_{debug_tag}.html"
        debug_path.write_text(html, encoding="utf-8")
        log.info("Debug-HTML gespeichert unter %s", debug_path)

    return html


def extract_menu_entries(html: str, day: date) -> list[MenuEntry]:
  
    soup = BeautifulSoup(html, "html.parser")

    body_text = soup.get_text(" ", strip=True)
    if not body_text or len(body_text) < 50:
        raise ParserError(
            "Gerenderte Seite enthält (fast) keinen Text"
            "JS wurde vermutlich nicht vollständig geladen"
        )

    categories = soup.select("app-category")
    if not categories:
        raise ParserError(
            "Kein <app-category>-Element gefunden, Seitenstruktur hat sich "
            "vermutlich geändert. debug_page HTML prüfen."
        )

    entries: list[MenuEntry] = []

    for category_el in categories:
        header = category_el.select_one("h3.category-header")
        category_name = header.get_text(strip=True) if header else None

        for product in category_el.select("div.product-wrapper"):
            name_el = product.select_one(".name-column .legacy-text-xxl")
            if not name_el:
                continue

            teaser_el = product.select_one(".product-teaser")
            price_el = product.select_one(".price-column .price")

            price_text = None
            if price_el:
                price_text = price_el.get_text(strip=True).replace("\xa0", " ")

            tags = [
                (img.get("title") or img.get("alt") or "").strip()
                for img in product.select("app-product-custom-tag img")
            ]
            tags = [t for t in tags if t]

            entries.append(
                MenuEntry(
                    day=day,
                    category=category_name,
                    dish=name_el.get_text(strip=True),
                    description=teaser_el.get_text(strip=True) if teaser_el else None,
                    price=price_text,
                    tags=tags,
                )
            )

    if not entries:
       
        log.info("Keine Menüeinträge für %s gefunden (evtl. kein Betrieb an diesem Tag)", day)

    return entries


def deduplicate_entries(day_entries: list[MenuEntry]) -> list[MenuEntry]:
    """Entfernt inhaltlich identische Doppeleinträge (z.B. wenn die Seite
    dasselbe Gericht zweimal im DOM hat, wie bei 'Sihlou closed')."""
    seen: set[tuple] = set()
    deduped: list[MenuEntry] = []
    for e in day_entries:
        key = e.dedup_key()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(e)
    return deduped


def format_day_description(day_entries: list[MenuEntry]) -> str:
    """Formatiert die Menüs eines Tages ähnlich der Website: Kategorie als
    Überschrift, darunter Name / Beschreibung / Preis pro Gericht."""
    lines: list[str] = []
    last_category = object()  

    for i, e in enumerate(day_entries):
        if e.category != last_category:
            if i > 0:
                lines.append("")  
            if e.category:
                lines.append(e.category.upper())
                lines.append("-" * len(e.category))
            last_category = e.category

        lines.append(e.dish)
        if e.description:
            lines.append(e.description)
        if e.price:
            lines.append(e.price)
        if e.tags:
            lines.append(f"({', '.join(e.tags)})")
        lines.append("")  

    return "\n".join(lines).strip()


def build_ics(restaurant_name: str, entries: list[MenuEntry]) -> bytes:
    cal = Calendar()
    cal.add("prodid", f"-//SV Mensa Kalender//{restaurant_name}//DE")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", f"Mittagsmenü {restaurant_name}")

    cutoff = date.today() - timedelta(days=7)

    entries_by_day: dict[date, list[MenuEntry]] = {}
    for entry in entries:
        if entry.day < cutoff:
            continue
        entries_by_day.setdefault(entry.day, []).append(entry)

    for day, day_entries in sorted(entries_by_day.items()):
        day_entries = deduplicate_entries(day_entries)

        event = Event()
        content_hash = hashlib.sha256(
            "|".join(e.content_hash() for e in day_entries).encode()
        ).hexdigest()[:12]
        event.add("uid", f"{restaurant_name}-{day}-{content_hash}@sv-mensa-ical")
        event.add("summary", f"Mittagsmenü: {restaurant_name}")

        start = datetime.combine(day, datetime.min.time()).replace(hour=11, minute=30)
        event.add("dtstart", start)
        event.add("dtend", start + timedelta(minutes=90))
        event.add("dtstamp", datetime.now(timezone.utc))

        event.add("description", format_day_description(day_entries))
        event.add("location", restaurant_name)

        cal.add_component(event)

    return cal.to_ical()


def process_restaurant(driver: webdriver.Chrome, cfg: dict) -> bool:
    slug = cfg["slug"]
    name = cfg["name"]
    base_url = cfg["url"].rstrip("/")

    log.info("Verarbeite Restaurant %s (%s)", slug, name)

    all_entries: list[MenuEntry] = []
    today = date.today()

    for offset in range(DAYS_AHEAD):
        day = today + timedelta(days=offset)
        
        if day.weekday() >= 5:
            continue

        day_url = f"{base_url}/date/{day.isoformat()}"
        try:
            html = fetch_rendered_page(driver, day_url, debug_tag=f"{slug}_{day}")
            day_entries = extract_menu_entries(html, day)
            all_entries.extend(day_entries)
            log.info("  %s: %d Einträge", day, len(day_entries))
        except ParserError as e:
            log.warning("  %s: Parser-Fehler, übersprungen: %s", day, e)
            continue

    if not all_entries:
        log.error("Keine Einträge für %s über den gesamten Zeitraum gefunden", slug)
        return False

    OUTPUT_DIR.mkdir(exist_ok=True)
    ics_path = OUTPUT_DIR / f"{slug}.ics"
    ics_bytes = build_ics(name, all_entries)
    ics_path.write_bytes(ics_bytes)
    log.info("OK: %d Einträge total -> %s", len(all_entries), ics_path)
    return True


def main() -> int:
    restaurants = load_restaurants()
    ok = True

    driver = build_driver()
    try:
        for cfg in restaurants:
            success = process_restaurant(driver, cfg)
            ok = ok and success
    finally:
        driver.quit()

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
