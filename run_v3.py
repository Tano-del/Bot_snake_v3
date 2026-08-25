import asyncio
import websockets
import json
import sys
from collections import deque
import threading
import heapq

from interfaz import iniciar_interfaz_multitab

active_games = {}
games_lock = threading.Lock()

def get_all_games():
    with games_lock:
        return {game_id: data.copy() for game_id, data in active_games.items()}


CONFIG = {
    'APPLE_VALUE': 100,
    'KILL_VALUE': 1000,
    'TURN_POINT': 1,
    'APPLE_MULT': 25,
    'KILL_MULT': 15,
    'SPACE_KILL_FACTOR': 30,
    'TURTLE_THRESHOLD': 400,
}


def calcular_espacio_libre(start_pos, obstaculos, zonas_peligro, ancho, alto, limite):
    visitados = {start_pos}
    cola = deque([start_pos])
    espacio = 0
    while cola and espacio < limite:
        x, y = cola.popleft()
        espacio += 1
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            nx, ny = x + dx, y + dy
            siguiente = (nx, ny)
            if 0 <= nx < ancho and 0 <= ny < alto:
                if siguiente not in obstaculos and siguiente not in zonas_peligro and siguiente not in visitados:
                    visitados.add(siguiente)
                    cola.append(siguiente)
    return espacio

def heuristica_manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

def encontrar_cola(cuerpo_propio, cabeza):
    if not cuerpo_propio:
        return None
    cuerpo_set = set(cuerpo_propio)
    for segmento in cuerpo_propio:
        vecinos = 0
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            vecino = (segmento[0] + dx, segmento[1] + dy)
            if vecino in cuerpo_set or vecino == cabeza:
                vecinos += 1
        if vecinos == 1:
            return segmento
    return cuerpo_propio[-1]

def hay_camino_a_objetivo(start_pos, objetivo, obstaculos, ancho, alto):
    visitados = {start_pos}
    cola = deque([start_pos])
    while cola:
        pos = cola.popleft()
        if pos == objetivo:
            return True
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            nx, ny = pos[0] + dx, pos[1] + dy
            siguiente = (nx, ny)
            if 0 <= nx < ancho and 0 <= ny < alto and siguiente not in visitados:
                if siguiente == objetivo or siguiente not in obstaculos:
                    visitados.add(siguiente)
                    cola.append(siguiente)
    return False

def astar_distancia(start_pos, objetivo, obstaculos, ancho, alto):
    if start_pos == objetivo: return 0
    
    frontera = []
    heapq.heappush(frontera, (0, 0, start_pos))
    visitados = {start_pos: 0}
    
    while frontera:
        f, g, pos = heapq.heappop(frontera)
        if pos == objetivo:
            return g
            
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            nx, ny = pos[0] + dx, pos[1] + dy
            sig = (nx, ny)
            if 0 <= nx < ancho and 0 <= ny < alto and sig not in obstaculos:
                nuevo_costo_g = g + 1
                if sig not in visitados or nuevo_costo_g < visitados[sig]:
                    visitados[sig] = nuevo_costo_g
                    prioridad_f = nuevo_costo_g + heuristica_manhattan(sig, objetivo)
                    heapq.heappush(frontera, (prioridad_f, nuevo_costo_g, sig))
    return 9999 

def analizar_tablero(filas, mi_lado):
    mi_cuerpo_char = mi_lado.lower()
    cuerpo_propio, cuerpos_enemigos, cabezas_enemigas = [], set(), []
    comida, paredes, cabeza = [], set(), None
    
    for y, fila in enumerate(filas):
        for x, char in enumerate(fila):
            if char == mi_lado: cabeza = (x, y)
            elif char == mi_cuerpo_char: cuerpo_propio.append((x, y))
            elif char in ['A', 'B'] and char != mi_lado:
                cabezas_enemigas.append((x, y))
                cuerpos_enemigos.add((x, y))
            elif char in ['a', 'b'] and char != mi_cuerpo_char:
                cuerpos_enemigos.add((x, y))
            elif char == '*': comida.append((x, y))
            elif char in ['|', '-']: paredes.add((x, y))
            
    return cabeza, cuerpo_propio, cabezas_enemigas, cuerpos_enemigos, comida, paredes

def calcular_peligros(cabezas_enemigas, ancho, alto):
    zonas_peligro = set()
    for cx, cy in cabezas_enemigas:
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < ancho and 0 <= ny < alto:
                zonas_peligro.add((nx, ny))
    return zonas_peligro

def evaluar_pasillo_borde(nx, ny, ancho, alto, obstaculos_sim, cabezas_enemigas, siguiente_pos, func_distancia):
    es_borde = (nx == 0 or nx == ancho - 1 or ny == 0 or ny == alto - 1)
    
    casilleros_libres = sum(
        1 for vx, vy in [(0, -1), (0, 1), (-1, 0), (1, 0)]
        if 0 <= (nx + vx) < ancho and 0 <= (ny + vy) < alto and (nx + vx, ny + vy) not in obstaculos_sim
    )
                
    es_pasillo = casilleros_libres <= 2

    if (es_borde or es_pasillo) and cabezas_enemigas:
        if func_distancia(siguiente_pos) <= 4:
            return -50000 
    return 0

def evaluar_movimiento(siguiente_pos, cabeza_ia, kwargs_eval):
    
    (ancho, alto, obstaculos_totales, zonas_peligro, espacio_seguro, 
     cola, cabezas_enemigas, cuerpos_enemigos, comida, espacio_enemigo_before,
     mi_puntaje, rival_puntaje, centro_x, centro_y, dist_enemigo_manzanas, func_distancia) = kwargs_eval

    puntaje_mov = 0
    if siguiente_pos in zonas_peligro: puntaje_mov -= 1400
        
    espacio = calcular_espacio_libre(siguiente_pos, obstaculos_totales, zonas_peligro, ancho, alto, 100)
    
    if espacio < espacio_seguro: puntaje_mov -= 3200
    else: puntaje_mov += espacio * 8

    if cola and not hay_camino_a_objetivo(siguiente_pos, cola, obstaculos_totales, ancho, alto):
        puntaje_mov -= 4200

    obstaculos_sim = set(obstaculos_totales)
    obstaculos_sim.add(siguiente_pos)


    puntaje_mov += evaluar_pasillo_borde(siguiente_pos[0], siguiente_pos[1], ancho, alto, obstaculos_sim, cabezas_enemigas, siguiente_pos, func_distancia)

    self_area = calcular_espacio_libre(siguiente_pos, obstaculos_sim, zonas_peligro, ancho, alto, 1000)
    if self_area < espacio_seguro: puntaje_mov -= 1800
    else: puntaje_mov += self_area * 5

   
    espacio_reducido = 0
    enemigo_posible_kill = False
    est_len_enemigo = max(3, len(cuerpos_enemigos) // max(1, len(cabezas_enemigas)))
    
    for cab_en, antes in espacio_enemigo_before.items():
        despues = calcular_espacio_libre(cab_en, obstaculos_sim, zonas_peligro, ancho, alto, 1000)
        espacio_reducido += max(0, antes - despues)
        if despues < est_len_enemigo + 2:
            enemigo_posible_kill = True

    if espacio_reducido > 0: puntaje_mov += espacio_reducido * CONFIG['SPACE_KILL_FACTOR']
    if enemigo_posible_kill: puntaje_mov += CONFIG['KILL_VALUE'] * CONFIG['KILL_MULT'] + 300
    if siguiente_pos in comida: puntaje_mov += CONFIG['APPLE_VALUE'] * CONFIG['APPLE_MULT']

    
    if mi_puntaje - rival_puntaje >= CONFIG['TURTLE_THRESHOLD']:
        puntaje_mov -= 700 * (1 if siguiente_pos in zonas_peligro else 0)
        if siguiente_pos in comida: puntaje_mov -= CONFIG['APPLE_VALUE'] * 2
        puntaje_mov += self_area * 3

   
    dist_enemigo = func_distancia(siguiente_pos)
    if dist_enemigo == 0: puntaje_mov -= 6000
    elif dist_enemigo == 1 and not enemigo_posible_kill: puntaje_mov -= 1200
    else: puntaje_mov += dist_enemigo * 5
        
    
    dist_manzana = 9999
    objetivo = None
    for manzana in comida:
        dist = astar_distancia(siguiente_pos, manzana, obstaculos_totales, ancho, alto)
        if dist < dist_manzana:
            dist_manzana = dist
            objetivo = manzana
            
    if objetivo:
        dist_enemigo_comida = dist_enemigo_manzanas.get(objetivo, 9999)
        if dist_manzana < dist_enemigo_comida: puntaje_mov += max(0, 4000 - dist_manzana * 60)
        elif dist_manzana == dist_enemigo_comida: puntaje_mov += max(0, 2000 - dist_manzana * 30)
        else:
            puntaje_mov -= 1000 
            dist_centro = abs(siguiente_pos[0] - centro_x) + abs(siguiente_pos[1] - centro_y)
            puntaje_mov += max(0, 200 - dist_centro * 8)
        puntaje_mov += max(0, 1500 - dist_manzana * 40)
    else:
        dist_centro = abs(siguiente_pos[0] - centro_x) + abs(siguiente_pos[1] - centro_y)
        puntaje_mov += espacio * 3
        puntaje_mov -= dist_centro * 3

    return puntaje_mov


def obtener_movimiento_ia(board_string, mi_lado, mi_puntaje=0, rival_puntaje=0, game_id=None):
    filas = board_string.strip('\n').split('\n')
    cabeza, cuerpo_propio, cabezas_enemigas, cuerpos_enemigos, comida, paredes = analizar_tablero(filas, mi_lado)

    if not cabeza: return "UP"

    ancho = len(filas[0]) if filas else 0
    alto = len(filas)
    centro_x, centro_y = ancho // 2, alto // 2 
    
    obstaculos_totales = set(cuerpo_propio) | cuerpos_enemigos | paredes
    zonas_peligro = calcular_peligros(cabezas_enemigas, ancho, alto)

    espacio_seguro_minimo = len(cuerpo_propio) + 3 
    
    distancia_enemigo_manzana = {}
    for manzana in comida:
        min_dist = 9999
        for cab_en in cabezas_enemigas:
            dist = astar_distancia(cab_en, manzana, obstaculos_totales, ancho, alto)
            if dist < min_dist: min_dist = dist
        distancia_enemigo_manzana[manzana] = min_dist

    cola = encontrar_cola(cuerpo_propio, cabeza)

    espacio_enemigo_before = {
        cab_en: calcular_espacio_libre(cab_en, obstaculos_totales, zonas_peligro, ancho, alto, 1000)
        for cab_en in cabezas_enemigas
    }

    def distancia_a_cabeza_enemiga(pos):
        if not cabezas_enemigas: return 9999
        return min(abs(pos[0] - cx) + abs(pos[1] - cy) for cx, cy in cabezas_enemigas)

    mejor_accion = "UP"
    max_puntaje = -999999
    
    kwargs_eval = (
        ancho, alto, obstaculos_totales, zonas_peligro, espacio_seguro_minimo, 
        cola, cabezas_enemigas, cuerpos_enemigos, comida, espacio_enemigo_before,
        mi_puntaje, rival_puntaje, centro_x, centro_y, distancia_enemigo_manzana, distancia_a_cabeza_enemiga
    )
    
    for dx, dy, accion in [(0, -1, "UP"), (0, 1, "DOWN"), (-1, 0, "LEFT"), (1, 0, "RIGHT")]:
        nx, ny = cabeza[0] + dx, cabeza[1] + dy
        siguiente_pos = (nx, ny)
        
        if not (0 <= nx < ancho and 0 <= ny < alto): continue
        if siguiente_pos in obstaculos_totales: continue
        
        puntaje_movimiento = evaluar_movimiento(siguiente_pos, cabeza, kwargs_eval)

        if puntaje_movimiento > max_puntaje:
            max_puntaje = puntaje_movimiento
            mejor_accion = accion

    return mejor_accion


async def send(websocket, action, data): # pragma: no cover
    message = json.dumps({"action": action, "data": data})
    print(f"> Enviando: {message}")
    await websocket.send(message)

async def handle_challenge(websocket, data): # pragma: no cover
    challenge_id = data.get("challenge_id")
    await send(websocket, "accept_challenge", {"challenge_id": challenge_id})

async def handle_your_turn(websocket, data): # pragma: no cover
    game_id = data.get("game_id")
    turn_token = data.get("turn_token")
    board_string = data.get("board")
    side = data.get("side") 
    
    jugador_1, puntaje_1 = data.get("player_1", "Jugador 1"), data.get("score_1", 0)
    jugador_2, puntaje_2 = data.get("player_2", "Jugador 2"), data.get("score_2", 0)
    marcador = f"{jugador_1}: {puntaje_1} pts  |  {jugador_2}: {puntaje_2} pts"

    with games_lock:
        if game_id in active_games and active_games[game_id].get("game_over"):
            return 
        active_games[game_id] = {
            "tablero": board_string, "marcador": marcador,
            "side": side, "game_over": False
        }
    
    mi_puntaje, rival_puntaje = (puntaje_1, puntaje_2) if side == 'A' else (puntaje_2, puntaje_1)
    movimiento = obtener_movimiento_ia(board_string, side, mi_puntaje, rival_puntaje, game_id)
    
    await send(websocket, "move", {
        "game_id": game_id, "turn_token": turn_token, "direction": movimiento 
    })

def handle_game_over(data): # pragma: no cover
    game_id = data.get("game_id")
    print(f"\n--- [!] Partida {game_id} terminada ---\n")
    with games_lock:
        if game_id in active_games:
            active_games[game_id]["game_over"] = True
            active_games[game_id]["marcador"] = f"GAME OVER | {active_games[game_id]['marcador']}"

async def process_event(websocket, message_str): # pragma: no cover
    print(f"< Recibido: {message_str[:150]}...")
    try:
        message = json.loads(message_str)
        event, data = message.get("event"), message.get("data", {})

        eventos_handlers = {
            "challenge": lambda: handle_challenge(websocket, data),
            "your_turn": lambda: handle_your_turn(websocket, data),
            "game_over": lambda: handle_game_over(data),
            "list_users": lambda: None,
            "update_user_list": lambda: None
        }

        handler = eventos_handlers.get(event)
        if handler:
            result = handler()
            if asyncio.iscoroutine(result):
                await result

    except json.JSONDecodeError:
        print("[X] Error: El servidor no envió un JSON válido.")
    except Exception as e:
        print(f"[X] Error procesando el evento: {e}")


async def play(websocket): # pragma: no cover
    async for message in websocket:
        await process_event(websocket, message)

async def start(auth_token): # pragma: no cover
    uri = "wss://server.codechallenge.net.ar/ws?token={}".format(auth_token)
    while True:
        try:
            print(f"\n[*] Conectando al servidor con V3 parcheada (Modular)...")
            async with websockets.connect(uri) as websocket:
                print("[*] ¡Conexión establecida exitosamente!")
                await play(websocket)
        except websockets.ConnectionClosed:
            print("[!] Conexión cerrada. Reintentando...")
            await asyncio.sleep(3)
        except Exception as e:
            print(f"[X] Error de conexión: {e}. Reintentando...")
            await asyncio.sleep(3)

if __name__ == "__main__": # pragma: no cover
    if len(sys.argv) < 2:
        print("Uso: python run.py <TU_TOKEN>")
        sys.exit(1)
    
    token = sys.argv[1]

    def run_asyncio_client():
        try:
            asyncio.run(start(token))
        except KeyboardInterrupt:
            pass

    hilo_websocket = threading.Thread(
        target=run_asyncio_client, daemon=True, name="WebSocketClient"
    )
    hilo_websocket.start()
    
    try:
        iniciar_interfaz_multitab(get_all_games)
    except KeyboardInterrupt:
        print("\n[*] Interfaz detenida manualmente.")
    finally:
        print("\n[*] Saliendo...")
