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
    'TURTLE_THRESHOLD': 1500,
    'X_BONUS': 4000,
    'DANGER_ZONE': 200000,
    'ESCAPE_PENALTY': 100000,
    'PASILLO_PENALTY': 120000,
    'BORDE_PENALTY': 50000,
    'COLA_TRAPPED': 30000,
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

def clasificar_comida(comida_raw):
    asteriscos, nums = [], {}
    for c, x, y in comida_raw:
        if c == '*': asteriscos.append((x, y))
        else: nums[int(c)] = (x, y)
        
    c_buena, c_mala = [], set()
    valor_comida = 1 
    for d, pos in nums.items():
        if ((d - 2) % 9 + 1) in nums:
            c_mala.add(pos)
        else:
            c_buena.append(pos)
            valor_comida = d 
    return asteriscos + c_buena, c_mala, valor_comida

def encontrar_siguiente_digito(comida_raw):
    """Encuentra el siguiente dígito a comer según la secuencia 1-9."""
    nums = {}
    for c, x, y in comida_raw:
        if c != '*':
            nums[int(c)] = (x, y)
    
    if not nums:
        return None
    
    if len(nums) == 1:
        return list(nums.values())[0]
    
    for d in range(1, 10):
        pred = d - 1 if d > 1 else 9
        if pred not in nums and d in nums:
            return nums[d]
    
    return None

def escanear_tablero(filas, dic_acciones):
    for y, fila in enumerate(filas):
        for x, char in enumerate(fila):
            func = dic_acciones.get(char)
            if func: func(x, y)

def analizar_tablero(filas, mi_lado):
    cuerpo, cab_en, comida_raw = [], [], []
    cuerp_en, paredes = set(), set()
    cabeza, pickups = [], []
    
    mi_cuerpo = mi_lado.lower()
    enemigo = list({'A', 'B'} - {mi_lado})[0]
    enemigo_cuerpo = enemigo.lower()

    dic_acciones = {
        mi_lado: lambda x, y: cabeza.append((x, y)),
        mi_cuerpo: lambda x, y: cuerpo.append((x, y)),
        '|': lambda x, y: paredes.add((x, y)),
        '-': lambda x, y: paredes.add((x, y)),
        '#': lambda x, y: paredes.add((x, y)), 
        'X': lambda x, y: pickups.append((x, y)), 
        enemigo: lambda x, y: (cab_en.append((x, y)), cuerp_en.add((x, y))),
        enemigo_cuerpo: lambda x, y: cuerp_en.add((x, y))
    }
    
    for char in "123456789*":
        dic_acciones[char] = lambda x, y, c=char: comida_raw.append((c, x, y))

    escanear_tablero(filas, dic_acciones)
    
    comida, comida_mala, valor_comida = clasificar_comida(comida_raw)
    paredes.update(comida_mala)

    cab_res = cabeza[0] if cabeza else None
    return cab_res, cuerpo, cab_en, cuerp_en, comida, paredes, pickups, valor_comida, comida_raw

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

def hay_escape(sig_pos, obs_sim, zonas, an, al, min_espacio=8):
    esp = calcular_espacio_libre(sig_pos, obs_sim, zonas, an, al, an * al)
    return esp >= min_espacio

def score_neto_por_movimiento(sig_pos, objetivo, d_obj, mi_pts, riv_pts, mi_mult, valor_obj, es_x=False):
    if objetivo is None:
        return 0
    
    if es_x:
        score_futuro = 50 * (mi_mult + 1) - (50 * mi_mult)
        return max(0, score_futuro * 10 - d_obj * 2)
    
    if valor_obj > 0:
        score_futuro = valor_obj * 100 * mi_mult
        score_neto = score_futuro - (d_obj * 5)
        return max(0, score_neto)
    
    return 0

def evaluar_movimiento_mark3(sig_pos, cab_ia, kwargs_eval):
    an, al, obs_tot, zonas, e_seg, cola, cab_en, cuerp_en, comida, esp_bef, mi_pts, riv_pts, cx, cy, f_dist, pickups, mi_mult, valor_comida, comida_raw = kwargs_eval
    area_total = an * al
    
    espacio = calcular_espacio_libre(sig_pos, obs_tot, zonas, an, al, area_total)
    if espacio < 6:
        return -CONFIG['ESCAPE_PENALTY']
    
    obs_sim = set(obs_tot) | {sig_pos}
    if es_pasillo(sig_pos[0], sig_pos[1], an, al, obs_sim):
        return -CONFIG['PASILLO_PENALTY']
    
    dist_rival = f_dist(sig_pos)
    if dist_rival <= 4 and es_borde(sig_pos[0], sig_pos[1], an, al):
        return -CONFIG['BORDE_PENALTY']
    
    if cola and not hay_camino_a_objetivo(sig_pos, cola, obs_tot, an, al):
        return -CONFIG['COLA_TRAPPED']
    
    pts = 0
    pts += espacio * 12
    
    if mi_pts - riv_pts > 500 and es_pasillo(sig_pos[0], sig_pos[1], an, al, obs_sim):
        pts -= 50000
    
    len_yo = len(cuerp_en) if cuerp_en else 1
    len_rival = max(3, len(cuerp_en) // max(1, len(cab_en)))
    
    if mi_pts - riv_pts < -500:
        pts += espacio * 5
        pts -= dist_rival * 2 if dist_rival > 0 else -2000
    elif mi_pts - riv_pts > 1000:
        area = calcular_espacio_libre(sig_pos, obs_sim, zonas, an, al, area_total)
        for cab, antes in esp_bef.items():
            despues = calcular_espacio_libre(cab, obs_sim, zonas, an, al, an * al)
            esp_red = max(0, antes - despues)
            if esp_red > 8:
                pts += esp_red * CONFIG['SPACE_KILL_FACTOR']
    
    siguiente_digit = encontrar_siguiente_digito(comida_raw)
    mejor_obj = siguiente_digit or None
    mejor_score_neto = -9999
    mejor_d = 9999
    
    for comida_pos in comida:
        d = astar_distancia(sig_pos, comida_pos, obs_tot, an, al)
        score_neto = score_neto_por_movimiento(sig_pos, comida_pos, d, mi_pts, riv_pts, mi_mult, valor_comida)
        if score_neto > mejor_score_neto:
            mejor_score_neto = score_neto
            mejor_obj = comida_pos
            mejor_d = d
    
    for pickup_pos in pickups:
        d = astar_distancia(sig_pos, pickup_pos, obs_tot, an, al)
        score_neto = score_neto_por_movimiento(sig_pos, pickup_pos, d, mi_pts, riv_pts, mi_mult, 0, es_x=True)
        if score_neto > mejor_score_neto and mi_mult < 4:
            mejor_score_neto = score_neto
            mejor_obj = pickup_pos
            mejor_d = d
    
    if mejor_obj:
        esp_en_obj = calcular_espacio_libre(mejor_obj, obs_sim, zonas, an, al, an * al)
        if esp_en_obj >= 8:
            pts += max(0, 5000 - mejor_d * 50)
        else:
            pts -= 3000
    
    return pts

def mapear_espacios(cabezas, obs, zonas, an, al):
    return {c: calcular_espacio_libre(c, obs, zonas, an, al, an * al) for c in cabezas}

def f_dist_factory(cab_en):
    return lambda pos: min((abs(pos[0]-cx) + abs(pos[1]-cy) for cx, cy in cab_en), default=9999)

def obtener_movimiento_ia(board_string, mi_lado, mi_puntaje=0, rival_puntaje=0, mi_mult=1, game_id=None):
    filas = board_string.strip('\n').split('\n')
    cab, cuerpo, cab_en, cuerp_en, comida, paredes, pickups, valor_comida, comida_raw = analizar_tablero(filas, mi_lado)
    
    if not cab: return "UP"
    ancho, alto = len(filas[0]), len(filas)
    obs = set(cuerpo) | cuerp_en | paredes
    zonas = calcular_peligros(cab_en, ancho, alto)
    
    kwargs = (
        ancho, alto, obs, zonas, len(cuerpo) + 3, encontrar_cola(cuerpo, cab), 
        cab_en, cuerp_en, comida, mapear_espacios(cab_en, obs, zonas, ancho, alto), 
        mi_puntaje, rival_puntaje, ancho//2, alto//2, f_dist_factory(cab_en),
        pickups, mi_mult, valor_comida, comida_raw
    )

    def get_pts(mov):
        nx, ny = cab[0] + mov[0], cab[1] + mov[1]
        if 0 <= nx < ancho and 0 <= ny < alto and (nx, ny) not in obs:
            return evaluar_movimiento_mark3((nx, ny), cab, kwargs)
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
    
def extraer_estado_jugador(data, side):
    p1, pts1 = data.get("player_1", "Jugador 1"), data.get("score_1", 0)
    p2, pts2 = data.get("player_2", "Jugador 2"), data.get("score_2", 0)
    m1, m2 = data.get("multiplier_1", 1), data.get("multiplier_2", 1)
    
    marcador = f"{p1}: {pts1} pts (x{m1}) | {p2}: {pts2} pts (x{m2})"
    
    if side == 'A':
        return pts1, pts2, m1, marcador
    return pts2, pts1, m2, marcador

async def handle_your_turn(websocket, data): # pragma: no cover
    game_id = data.get("game_id")
    side = data.get("side")
    board_string = data.get("board")
    
    mi_pts, riv_pts, mi_mult, marcador = extraer_estado_jugador(data, side)

    with games_lock:
        if active_games.get(game_id, {}).get("game_over", False): 
            return 
        active_games[game_id] = {"tablero": board_string, "marcador": marcador, "side": side, "game_over": False}
    
    mov = obtener_movimiento_ia(board_string, side, mi_pts, riv_pts, mi_mult, game_id)
    await send(websocket, "move", {"game_id": game_id, "turn_token": data.get("turn_token"), "direction": mov})

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
