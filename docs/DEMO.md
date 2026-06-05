# Cómo grabar la demo (lo que hará que este repo destaque)

Un GIF de 8-12 segundos vale más que mil líneas de README. Sigue esto:

## Opción rápida (sin tienda real) — modo demo

1. Abre una terminal en la carpeta del proyecto.
2. Ejecuta:
   ```bash
   python src/main.py --demo
   ```
3. Verás cómo detecta la bajada del "Teclado mecánico (demo)" y prepara la alerta.
4. Si tienes `.env` configurado con tu bot, la alerta llegará a tu Telegram de verdad.

## Grabar el GIF

- **Windows:** [ShareX](https://getsharex.com/) → grabar región → exportar a GIF.
- **Mac/Linux:** [Peek](https://github.com/phw/peek) o [Kap](https://getkap.co/).

### Plano ideal para el GIF
1. Terminal ejecutando `python src/main.py` mostrando el chequeo de precios.
2. Corte a tu Telegram recibiendo la alerta 🔻 con el nombre y el precio.

Guarda el GIF como `docs/demo.gif` y enlázalo en el README (ya hay un hueco preparado).

## Captura del workflow de n8n
Importa `workflow.json` en n8n, haz una captura del lienzo con los 4 nodos
conectados y guárdala como `docs/n8n-workflow.png`. Demuestra que sabes
orquestar, no solo programar.
