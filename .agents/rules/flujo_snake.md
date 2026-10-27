---
trigger: always_on
description: Flujo obligatorio de validacion (Coverage >= 90%, Xenon A, Flake8, y 5 peleas en vivo entre lucaisgro y V2 en codechallenge.net.ar sin puntaje negativo) antes de cada commit/push a GitHub.
---

# Reglas del Proyecto Bot_snake_v3

1. **Fuente oficial de reglas del juego:**
   - Consultar `https://codechallenge-snake-production.up.railway.app/how-to-play` para detectar nuevas versiones de reglas (`v10`, `v11`, etc.) y adaptar `run_v3.py`, `interfaz.py` y `test_bot.py`.

2. **Validaciones estáticas y de tests obligatorias antes de hacer commit/push:**
   - **Cobertura de tests >= 90%:** Ejecutar `python -m pytest --cov=run_v3 --cov-report=term-missing --cov-fail-under=90`.
   - **Complejidad ciclomática Xenon grado A:** Ejecutar `python -m xenon --max-absolute A --max-modules A --max-average A .`. Todo bloque, función y módulo debe ser `A`.
   - **Linter Flake8:** Ejecutar `python -m flake8 .` sin ningún error ni advertencia.

3. **5 peleas en el servidor en vivo (`https://codechallenge.net.ar/`) antes de hacer commit/push:**
   - Leer los tokens de prueba locales desde `.tokens_test.json` (`lucaisgro` y `V2`).
   - Conectar ambos bots simultáneamente a `wss://server.codechallenge.net.ar/ws?token=<TOKEN>` ejecutando la lógica actual de `run_v3.py`.
   - Usar las herramientas del navegador (**Chrome DevTools MCP** en `https://codechallenge.net.ar/`) para enfrentar a `lucaisgro` contra `V2` **5 veces**.
   - Verificar en los resultados de las 5 partidas que ningún bot termine con puntaje negativo (`score < 0`). Si en alguna partida da puntaje negativo, corregir `run_v3.py` y volver a probar las 5 partidas antes de hacer commit.

4. **Subida directa a GitHub:**
   - Únicamente cuando pasen el coverage >= 90%, Xenon A, Flake8 y las 5 partidas sin puntaje negativo, hacer `git add`, `git commit` y `git push origin main`.
