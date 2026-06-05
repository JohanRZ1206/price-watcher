"""
Price Watcher — monitor de precios con alertas por Telegram.

Lee una lista de productos desde config.json, consulta el precio actual de cada
uno mediante scraping y avisa por Telegram cuando el precio baja del umbral que
hayas fijado. Guarda el último precio visto para poder detectar bajadas reales.

Pensado para ejecutarse:
  - Standalone:  python src/main.py            (consulta y envía alertas)
  - Desde n8n:   python src/main.py --json      (imprime los resultados en JSON;
                                                  n8n decide a quién y cómo avisar)
  - Sin red:     python src/main.py --demo       (datos simulados para probar/grabar la demo)

Arquitectura: el scraping y la lógica viven en Python; la programación (cada X
horas) y la entrega del mensaje pueden delegarse a n8n o a cron. Así el mismo
código sirve para un script suelto o para un workflow de automatización.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# --- Dependencias externas con mensaje amigable si faltan -------------------
try:
    import requests
    from bs4 import BeautifulSoup
    from dotenv import load_dotenv
except ImportError as exc:  # pragma: no cover
    print(
        "Falta una dependencia. Instala todo con:\n"
        "    pip install -r requirements.txt\n"
        f"Detalle: {exc}",
        file=sys.stderr,
    )
    sys.exit(1)

# En Windows la consola suele usar cp1252 y rompe al imprimir emojis. Forzamos UTF-8.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

# --- Rutas del proyecto -----------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "config.json"
DATA_DIR = BASE_DIR / "data"
STATE_FILE = DATA_DIR / "state.json"

REQUEST_HEADERS = {
    # Algunos sitios bloquean peticiones sin User-Agent de navegador.
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


# --- Configuración y estado -------------------------------------------------
def load_config() -> dict:
    """Carga config.json (lista de productos a vigilar)."""
    if not CONFIG_FILE.exists():
        print(
            "No existe config.json. Copia config.example.json a config.json y "
            "ajusta tus productos.",
            file=sys.stderr,
        )
        sys.exit(1)
    with CONFIG_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def load_state() -> dict:
    """Devuelve el último precio visto por URL. Vacío en la primera ejecución."""
    if STATE_FILE.exists():
        with STATE_FILE.open(encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with STATE_FILE.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


# --- Parseo y scraping ------------------------------------------------------
def parse_price(text: str) -> float | None:
    """
    Convierte un texto de precio ('1.234,56 €', '$79.99', '79,99') a float.
    Detecta el separador decimal por la posición del último '.' o ','.
    """
    cleaned = re.sub(r"[^\d.,]", "", text)
    if not cleaned:
        return None
    if "," in cleaned and "." in cleaned:
        # El separador más a la derecha es el decimal.
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return None


def fetch_price(url: str, css_selector: str) -> float | None:
    """Descarga la página y extrae el precio con el selector CSS dado."""
    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"  ! No se pudo acceder a {url}: {exc}", file=sys.stderr)
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    node = soup.select_one(css_selector)
    if node is None:
        print(f"  ! Selector '{css_selector}' no encontró nada en {url}", file=sys.stderr)
        return None
    return parse_price(node.get_text(strip=True))


# --- Lógica principal -------------------------------------------------------
def check_products(config: dict, state: dict) -> list[dict]:
    """Consulta cada producto y devuelve una lista de resultados."""
    results = []
    for product in config.get("products", []):
        name = product["name"]
        url = product["url"]
        target = float(product["target_price"])
        currency = product.get("currency", "EUR")

        print(f"→ {name}")
        current = fetch_price(url, product["css_selector"])
        previous = state.get(url, {}).get("last_price")

        result = {
            "name": name,
            "url": url,
            "currency": currency,
            "current_price": current,
            "previous_price": previous,
            "target_price": target,
            "dropped": bool(current is not None and previous is not None and current < previous),
            "alert": bool(current is not None and current <= target),
            "checked_at": datetime.now().isoformat(timespec="seconds"),
        }
        results.append(result)

        if current is not None:
            state[url] = {"name": name, "last_price": current, "last_checked": result["checked_at"]}
            flag = "  ✅ ¡Por debajo del umbral!" if result["alert"] else ""
            print(f"  precio actual: {current} {currency} (umbral {target}){flag}")
    return results


def format_alert(result: dict) -> str:
    """Mensaje de Telegram en HTML para un producto que ha alcanzado el umbral."""
    return (
        f"🔻 <b>¡Bajada de precio!</b>\n\n"
        f"<b>{result['name']}</b>\n"
        f"Precio actual: <b>{result['current_price']} {result['currency']}</b>\n"
        f"Tu umbral: {result['target_price']} {result['currency']}\n"
        f'<a href="{result["url"]}">Ver producto →</a>'
    )


def send_telegram(token: str, chat_id: str, message: str) -> bool:
    """Envía un mensaje a través de la API del bot de Telegram."""
    api = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(
            api,
            data={"chat_id": chat_id, "text": message, "parse_mode": "HTML",
                  "disable_web_page_preview": False},
            timeout=15,
        )
        resp.raise_for_status()
        return True
    except requests.RequestException as exc:
        print(f"  ! Error enviando a Telegram: {exc}", file=sys.stderr)
        return False


def demo_results() -> list[dict]:
    """Resultados simulados para probar sin red ni configuración real."""
    now = datetime.now().isoformat(timespec="seconds")
    return [
        {"name": "Teclado mecánico (demo)", "url": "https://ejemplo.com/teclado",
         "currency": "EUR", "current_price": 64.99, "previous_price": 89.99,
         "target_price": 70.0, "dropped": True, "alert": True, "checked_at": now},
        {"name": "Monitor 27\" (demo)", "url": "https://ejemplo.com/monitor",
         "currency": "EUR", "current_price": 199.0, "previous_price": 199.0,
         "target_price": 150.0, "dropped": False, "alert": False, "checked_at": now},
    ]


def run(demo: bool, json_mode: bool) -> None:
    if demo:
        results = demo_results()
    else:
        config = load_config()
        state = load_state()
        results = check_products(config, state)
        save_state(state)

    # Modo JSON: imprime y termina (lo consume n8n o cualquier otro proceso).
    if json_mode:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    # Modo standalone: envía alerta por Telegram de cada producto en umbral.
    load_dotenv(BASE_DIR / ".env")
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    alerts = [r for r in results if r["alert"]]

    if not alerts:
        print("\nSin bajadas por debajo del umbral. Nada que avisar.")
        return

    if not (token and chat_id):
        print(
            "\nHay alertas pero falta TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID en .env. "
            "Las muestro por consola:\n",
            file=sys.stderr,
        )
        for r in alerts:
            print(format_alert(r).replace("<b>", "").replace("</b>", ""))
        return

    for r in alerts:
        if send_telegram(token, chat_id, format_alert(r)):
            print(f"\n📨 Alerta enviada por Telegram: {r['name']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor de precios con alertas por Telegram.")
    parser.add_argument("--json", action="store_true",
                        help="Imprime los resultados en JSON y no envía nada (para n8n).")
    parser.add_argument("--demo", action="store_true",
                        help="Usa datos simulados (sin red ni config).")
    args = parser.parse_args()
    run(demo=args.demo, json_mode=args.json)


if __name__ == "__main__":
    main()
