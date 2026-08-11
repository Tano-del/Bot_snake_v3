# Snake Bot V3 - A* & Flood Fill

Bot cliente para un servidor de Snake multijugador. Utiliza una IA basada en algoritmos deterministas (A* y Flood Fill) para la toma de decisiones, e incluye herramientas de simulación y optimización local.

## Estrategia de la IA

El comportamiento del bot se define en `run_v3.py` mediante parámetros configurables y las siguientes lógicas:

* **A-Star (A*):** Búsqueda de rutas óptimas hacia la comida utilizando la heurística de distancia de Manhattan.
* **Control Espacial (Flood Fill):** Evaluación constante de las casillas transitables para evitar callejones sin salida.
* **Sensor Anti-Túneles:** Detección de corredores estrechos y bordes con enemigos cercanos, aplicando penalizaciones para prevenir encierros.
* **Modo Tortuga:** Comportamiento defensivo automático que se activa al obtener una ventaja considerable en el marcador.

## Estructura del Proyecto

* `run_v3.py`: Cliente asíncrono principal (WebSockets) y cerebro de la IA.
* `interfaz.py`: Monitor gráfico multi-pestaña construido con `tkinter` para ver las partidas en tiempo real.
* `simulator.py`: Simulador local para testear el rendimiento del bot sin conexión.
* `tournament.py`: Herramienta de Grid Search para optimizar los hiperparámetros de la IA enfrentando distintas variantes.

## Instalación

El proyecto requiere Python 3. Instala la dependencia de red ejecutando


pip install websockets==12.0




##  Uso

**1. Jugar en el servidor online (inicia el bot y la interfaz):**

python run_v3.py <TU_TOKEN>


**2. Ejecutar simulaciones locales:**

# Ejecutar 100 partidas de prueba a nivel local
python simulator.py 100


**3. Optimizar hiperparámetros (Torneo):**

# Enfrentar variantes (ej: 20 partidas por variante, guardando el top 10)
python tournament.py 20 10
