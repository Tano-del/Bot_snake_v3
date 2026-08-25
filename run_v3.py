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
    'APPLE_VALUE': 100, 'KILL_VALUE': 1000, 'TURN_POINT': 1,
    'APPLE_MULT': 25, 'KILL_MULT': 15, 'SPACE_KILL_FACTOR': 30,
    'TURTLE_THRESHOLD': 400,
}


def es_vec_valido(nx, ny, ancho, alto, obs, pel, vis):
    if not (0 <= nx < ancho and 0 <= ny < alto): return False
    sig = (nx, ny)
    return sig not in obs and sig not in pel and sig not in vis

def agregar_vecinos(x, y, ancho, alto, obs, pel, vis, cola):
    for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
        nx, ny = x + dx, y + dy
        if es_vec_valido(nx, ny, ancho, alto, obs, pel, vis):
            vis.add((nx, ny))
            cola.append((nx, ny))

def calcular_espacio_libre(start_pos, obstaculos, zonas_peligro, ancho, alto, limite):
    visitados = {start_pos}
    cola = deque([start_pos])
    espacio = 0
    while cola and espacio < limite:
        x, y = cola.popleft()
        espacio += 1
        agregar_vecinos(x, y, ancho, alto, obstaculos, zonas_peligro, visitados, cola)
    return espacio

def heuristica_manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

def contar_vecinos_cuerpo(segmento, cuerpo_set, cabeza):
    vecinos = 0
    for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
        vec = (segmento[0] + dx, segmento[1] + dy)
        if vec in cuerpo_set or vec == cabeza: vecinos += 1
    return vecinos

def encontrar_cola(cuerpo_propio, cabeza):
    if not cuerpo_propio: return None
    cuerpo_set = set(cuerpo_propio)
    for segmento in cuerpo_propio:
        if contar_vecinos_cuerpo(segmento, cuerpo_set, cabeza) == 1:
            return segmento
    return cuerpo_propio[-1]

def vecino_camino_ok(nx, ny, ancho, alto, obs, obj, vis):
    if not (0 <= nx < ancho and 0 <= ny < alto): return False
    sig = (nx, ny)
    if sig in vis: return False
    return sig == obj or sig not in obs

def expandir_camino(pos, ancho, alto, obs, obj, vis, cola):
    for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
        nx, ny = pos[0] + dx, pos[1] + dy
        if vecino_camino_ok(nx, ny, ancho, alto, obs, obj, vis):
            vis.add((nx, ny))
            cola.append((nx, ny))

def hay_camino_a_objetivo(start_pos, objetivo, obstaculos, ancho, alto):
    visitados = {start_pos}
    cola = deque([start_pos])
    while cola:
        pos = cola.popleft()
        if pos == objetivo: return True
        expandir_camino(pos, ancho, alto, obstaculos, objetivo, visitados, cola)
    return False

def astar_vecino_ok(nx, ny, ancho, alto, obs):
    return 0 <= nx < ancho and 0 <= ny < alto and (nx, ny) not in obs

def expandir_astar(pos, g, ancho, alto, obs, obj, vis, frontera):
    for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
        nx, ny = pos[0] + dx, pos[1] + dy
        sig = (nx, ny)
        if astar_vecino_ok(nx, ny, ancho, alto, obs):
            nuevo_g = g + 1
            if sig not in vis or nuevo_g < vis[sig]:
                vis[sig] = nuevo_g
                prioridad = nuevo_g + heuristica_manhattan(sig, obj)
                heapq.heappush(frontera, (prioridad, nuevo_g, sig))

def astar_distancia(start_pos, objetivo, obstaculos, ancho, alto):
    if start_pos == objetivo: return 0
    frontera = [(0, 0, start_pos)]
    visitados = {start_pos: 0}
    while frontera:
        f, g, pos = heapq.heappop(frontera)
        if pos == objetivo: return g
        expandir_astar(pos, g, ancho, alto, obstaculos, objetivo, visitados, frontera)
    return 9999 



def analizar_tablero(filas, mi_lado):
    cuerpo, cab_en, comida = [], [], []
    cuerp_en, paredes = set(), set()
    cabeza = []
    
    mi_cuerpo = mi_lado.lower()
    enemigo = list({'A', 'B'} - {mi_lado})[0]
    enemigo_cuerpo = enemigo.lower()

    dic_acciones = {
        mi_lado: lambda x, y: cabeza.append((x, y)),
        mi_cuerpo: lambda x, y: cuerpo.append((x, y)),
        '*': lambda x, y: comida.append((x, y)),
        '|': lambda x, y: paredes.add((x, y)),
        '-': lambda x, y: paredes.add((x, y)),
        enemigo: lambda x, y: (cab_en.append((x, y)), cuerp_en.add((x, y))),
        enemigo_cuerpo: lambda x, y: cuerp_en.add((x, y))
    }

    for y, fila in enumerate(filas):
        for x, char in enumerate(fila):
            func = dic_acciones.get(char)
            if func: func(x, y)

    return cabeza[0] if cabeza else None, cuerpo, cab_en, cuerp_en, comida, paredes

def calcular_peligros(cab_en, ancho, alto):
    zonas = set()
    for cx, cy in cab_en:
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            if 0 <= cx + dx < ancho and 0 <= cy + dy < alto:
                zonas.add((cx + dx, cy + dy))
    return zonas

def es_pasillo(nx, ny, ancho, alto, obs_sim):
    libres = sum(
        1 for vx, vy in [(0, -1), (0, 1), (-1, 0), (1, 0)]
        if 0 <= (nx + vx) < ancho and 0 <= (ny + vy) < alto and (nx + vx, ny + vy) not in obs_sim
    )
    return libres <= 2

def es_borde(nx, ny, ancho, alto):
    return nx in (0, ancho - 1) or ny in (0, alto - 1)

def evaluar_pasillo_borde(nx, ny, ancho, alto, obs_sim, cab_en, sig_pos, f_dist):
    if not cab_en or f_dist(sig_pos) > 4:
        return 0
    if es_borde(nx, ny, ancho, alto) or es_pasillo(nx, ny, ancho, alto, obs_sim):
        return -50000
    return 0

def evaluar_defensa(sig_pos, zonas, esp, esp_seguro, cola, obs, an, al):
    pts = -1400 if sig_pos in zonas else 0
    pts += esp * 8 if esp >= esp_seguro else -3200
    if cola and not hay_camino_a_objetivo(sig_pos, cola, obs, an, al): pts -= 4200
    return pts

def evaluar_ofensiva(esp_before, obs_sim, zonas, an, al, est_len, sig_pos, comida):
    pts, esp_red, posible_kill = 0, 0, False
    for cab, antes in esp_before.items():
        despues = calcular_espacio_libre(cab, obs_sim, zonas, an, al, 1000)
        esp_red += max(0, antes - despues)
        posible_kill = posible_kill or (despues < est_len + 2)

    pts += esp_red * CONFIG['SPACE_KILL_FACTOR']
    pts += (CONFIG['KILL_VALUE'] * CONFIG['KILL_MULT'] + 300) * int(posible_kill)
    pts += (CONFIG['APPLE_VALUE'] * CONFIG['APPLE_MULT']) * int(sig_pos in comida)
    
    return pts, posible_kill

def evaluar_tortuga(sig_pos, zonas, comida, area, mi_pts, riv_pts, dist_en, p_kill):
    pts = 0
    if mi_pts - riv_pts >= CONFIG['TURTLE_THRESHOLD']:
        pts -= 700 * int(sig_pos in zonas)
        pts -= (CONFIG['APPLE_VALUE'] * 2) * int(sig_pos in comida)
        pts += area * 3

    if dist_en == 0:
        return pts - 6000
    
    pts_dist = -1200 if (dist_en == 1 and not p_kill) else (dist_en * 5)
    return pts + pts_dist

def evaluar_manzanas(sig_pos, obj, d_manz, d_en_com, cx, cy, esp):
    pts = 0
    if obj:
        if d_manz < d_en_com: pts += max(0, 4000 - d_manz * 60)
        elif d_manz == d_en_com: pts += max(0, 2000 - d_manz * 30)
        else: pts += max(0, 200 - (abs(sig_pos[0]-cx) + abs(sig_pos[1]-cy)) * 8) - 1000
        pts += max(0, 1500 - d_manz * 40)
    else:
        pts += esp * 3 - (abs(sig_pos[0]-cx) + abs(sig_pos[1]-cy)) * 3
    return pts

def evaluar_movimiento(sig_pos, cab_ia, kwargs_eval):
    an, al, obs_tot, zonas, e_seg, cola, cab_en, cuerp_en, comida, esp_bef, mi_pts, riv_pts, cx, cy, d_en_manz, f_dist = kwargs_eval
    
    espacio = calcular_espacio_libre(sig_pos, obs_tot, zonas, an, al, 100)
    pts = evaluar_defensa(sig_pos, zonas, espacio, e_seg, cola, obs_tot, an, al)

    obs_sim = set(obs_tot) | {sig_pos}
    pts += evaluar_pasillo_borde(sig_pos[0], sig_pos[1], an, al, obs_sim, cab_en, sig_pos, f_dist)

    area = calcular_espacio_libre(sig_pos, obs_sim, zonas, an, al, 1000)
    pts += area * 5 if area >= e_seg else -1800

    est_len = max(3, len(cuerp_en) // max(1, len(cab_en)))
    p_ofensiva, posible_kill = evaluar_ofensiva(esp_bef, obs_sim, zonas, an, al, est_len, sig_pos, comida)
    pts += p_ofensiva

    pts += evaluar_tortuga(sig_pos, zonas, comida, area, mi_pts, riv_pts, f_dist(sig_pos), posible_kill)

    mejor_d, mejor_obj = min(((astar_distancia(sig_pos, m, obs_tot, an, al), m) for m in comida), default=(9999, None))
    d_en_comida = d_en_manz.get(mejor_obj, 9999) if mejor_obj else 9999
    pts += evaluar_manzanas(sig_pos, mejor_obj, mejor_d, d_en_comida, cx, cy, espacio)
    
    return pts

def mapear_distancias(comida, cabezas, obs, an, al):
    return {m: min((astar_distancia(c, m, obs, an, al) for c in cabezas), default=9999) for m in comida}

def mapear_espacios(cabezas, obs, zonas, an, al):
    return {c: calcular_espacio_libre(c, obs, zonas, an, al, 1000) for c in cabezas}

def f_dist_factory(cab_en):
    return lambda pos: min((abs(pos[0]-cx) + abs(pos[1]-cy) for cx, cy in cab_en), default=9999)

def obtener_movimiento_ia(board_string, mi_lado, mi_puntaje=0, rival_puntaje=0, game_id=None):
    filas = board_string.strip('\n').split('\n')
    cab, cuerpo, cab_en, cuerp_en, comida, paredes = analizar_tablero(filas, mi_lado)
    
    if not cab: return "UP"
    ancho, alto = len(filas[0]), len(filas)
    obs = set(cuerpo) | cuerp_en | paredes
    zonas = calcular_peligros(cab_en, ancho, alto)
    
    kwargs = (
        ancho, alto, obs, zonas, len(cuerpo) + 3, encontrar_cola(cuerpo, cab), 
        cab_en, cuerp_en, comida, mapear_espacios(cab_en, obs, zonas, ancho, alto), 
        mi_puntaje, rival_puntaje, ancho//2, alto//2, 
        mapear_distancias(comida, cab_en, obs, ancho, alto), f_dist_factory(cab_en)
    )

    def get_pts(mov):
        nx, ny = cab[0] + mov[0], cab[1] + mov[1]
        if 0 <= nx < ancho and 0 <= ny < alto and (nx, ny) not in obs:
            return evaluar_movimiento((nx, ny), cab, kwargs)
        return -999999

    opciones = [(0, -1, "UP"), (0, 1, "DOWN"), (-1, 0, "LEFT"), (1, 0, "RIGHT")]
    return max(opciones, key=get_pts)[2]



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
        if game_id in active_games and active_games[game_id].get("game_over"): return 
        active_games[game_id] = {"tablero": board_string, "marcador": marcador, "side": side, "game_over": False}
    
    mi_pts, riv_pts = (puntaje_1, puntaje_2) if side == 'A' else (puntaje_2, puntaje_1)
    mov = obtener_movimiento_ia(board_string, side, mi_pts, riv_pts, game_id)
    await send(websocket, "move", {"game_id": game_id, "turn_token": turn_token, "direction": mov})

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
            "game_over": lambda: handle_game_over(data)
        }
        handler = eventos_handlers.get(event)
        if handler:
            result = handler()
            if asyncio.iscoroutine(result): await result
    except json.JSONDecodeError: print("[X] Error JSON")
    except Exception as e: print(f"[X] Error: {e}")

async def play(websocket): # pragma: no cover
    async for message in websocket: await process_event(websocket, message)

async def start(auth_token): # pragma: no cover
    uri = f"wss://server.codechallenge.net.ar/ws?token={auth_token}"
    while True:
        try:
            print(f"\n[*] Conectando al servidor...")
            async with websockets.connect(uri) as websocket:
                print("[*] ¡Conexión establecida exitosamente!")
                await play(websocket)
        except websockets.ConnectionClosed:
            await asyncio.sleep(3)
        except Exception as e:
            await asyncio.sleep(3)

if __name__ == "__main__": # pragma: no cover
    if len(sys.argv) < 2:
        print("Uso: python run_v3.py <TU_TOKEN>")
        sys.exit(1)
    
    token = sys.argv[1]

    def run_asyncio_client():
        try: asyncio.run(start(token))
        except KeyboardInterrupt: pass

    hilo_websocket = threading.Thread(target=run_asyncio_client, daemon=True, name="WebSocketClient")
    hilo_websocket.start()
    
    try: iniciar_interfaz_multitab(get_all_games)
    except Exception:
        while True: pass
