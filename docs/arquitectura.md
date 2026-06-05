# Arquitectura

El proyecto separa **lógica** (Python) de **orquestación** (n8n / cron). El mismo
código funciona como script suelto o como pieza de un workflow automatizado.

```
                 ┌──────────────────────────────────────────┐
                 │              ORQUESTACIÓN                  │
                 │   n8n Schedule Trigger  ó  cron del SO     │
                 └───────────────────┬──────────────────────┘
                                     │ ejecuta cada X horas
                                     ▼
        ┌────────────────────────────────────────────────────┐
        │                  src/main.py (Python)               │
        │  1. Lee config.json (productos + umbral)            │
        │  2. Descarga cada página (requests)                 │
        │  3. Extrae el precio (BeautifulSoup + selector CSS) │
        │  4. Compara contra umbral y contra el último precio │
        │     guardado en data/state.json                     │
        └───────────────┬───────────────────┬─────────────────┘
                        │                   │
            --json (n8n decide)      standalone (Python avisa)
                        │                   │
                        ▼                   ▼
              n8n: IF alert → Telegram   API de Telegram (requests)
```

## Decisiones de diseño

- **`--json` vs standalone:** el script puede avisar él mismo (standalone, ideal
  con cron) o solo imprimir resultados en JSON para que n8n decida el canal
  (Telegram, email, Slack…). Una sola base de código, dos modos de uso.
- **`state.json`:** guarda el último precio visto por URL. Permite distinguir
  "está por debajo del umbral" de "acaba de bajar respecto a la última vez".
- **Selector CSS configurable:** cada tienda marca el precio distinto, así que el
  selector vive en `config.json` y no hay que tocar código para añadir productos.
- **Modo `--demo`:** datos simulados para poder probar y grabar la demo sin
  depender de una tienda real ni de su HTML.

## Límites conocidos

- El scraping depende del HTML de cada tienda; si cambia su maquetación, hay que
  actualizar el `css_selector`. Sitios con precio cargado por JavaScript
  necesitarían Playwright/Selenium (posible mejora del roadmap).
