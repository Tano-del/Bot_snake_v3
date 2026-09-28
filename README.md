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

## Instalación

El proyecto requiere Python 3. Instala la dependencia de red ejecutando


pip install websockets==12.0




##  Uso

**1. Jugar en el servidor online (inicia el bot y la interfaz):**

python run_v3.py <TU_TOKEN>



