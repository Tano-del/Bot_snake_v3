---
trigger: always_on
description: Flujo obligatorio de validacion (Coverage >= 90%, Xenon A, Flake8, 5 peleas bot vs bot sin puntaje negativo) y subida automatica a GitHub.
---

# Reglas del Proyecto Bot_snake_v3

1. **Fuente oficial de reglas del juego:**
   - Consultar `https://codechallenge-snake-production.up.railway.app/how-to-play` para detectar nuevas versiones de reglas (`v10`, `v11`, etc.) y adaptar `run_v3.py`, `interfaz.py` y `test_bot.py`.

2. **Validaciones obligatorias antes de subir cambios a GitHub:**
   - **Cobertura de tests >= 90%:** Ejecutar `python -m pytest --cov=run_v3 --cov-report=term-missing --cov-fail-under=90`.
   - **Complejidad ciclomática Xenon grado A:** Ejecutar `python -m xenon --max-absolute A --max-modules A --max-average A .`. Todo bloque, función y módulo debe ser `A`.
   - **Linter Flake8:** Ejecutar `python -m flake8 .` sin ningún error ni advertencia.
   - **5 peleas Bot vs Bot sin puntaje negativo:** Ejecutar las 5 partidas de auto-enfrentamiento (`test_cinco_peleas_bot_vs_bot_sin_puntaje_negativo`). Si en alguna partida cualquiera de los dos bots termina con puntaje negativo (`< 0`), corregir la heurística/lógica antes de hacer commit/push.

3. **Subida directa a GitHub:**
   - Una vez aprobadas todas las validaciones anteriores, hacer `git add`, `git commit` y `git push origin main` automáticamente.
