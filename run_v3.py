import asyncio
import websockets
import json
import sys
from collections import deque
import threading
import heapq
from typing import NamedTuple

active_games = {}
games_lock = threading.Lock()

def get_all_games():
    with games_lock:
        return {game_id: data.copy() for game_id, data in active_games.items()}

CONFIG = {
    'APPLE_VALUE': 100, 'KILL_VALUE': 1000, 'TURN_POINT': 1,
    'APPLE_MULT': 25, 'KILL_MULT': 15, 'SPACE_KILL_FACTOR': 30,
    'TURTLE_THRESHOLD': 1000,
    'X_BONUS': 4000,
    'CRASH_COST': 10_000_000,  
    'MALA_COST': 6000,         
    'BOMB_MARGIN': 3000,       
}

# Radio de explosión por tipo de bomba (distancia de Chebyshev a la cabeza)
RADIO_BOMBA = {'\U0001F4A3': 2, '\U0001F9E8': 1}   # 💣 grande, 🧨 chica
COMIDA_COLA = {'A': '\u24b6', 'B': '\u24b7'}       # Ⓐ / Ⓑ: sólo la come el dueño de la letra

DIRECCIONES = [(0, -1), (0, 1), (-1, 0), (1, 0)]


class Tablero(NamedTuple):
    cabeza: tuple
    cuerpo: list
    cab_en: list
    cuerp_en: set
    comida: list
    paredes: set
    pickups: list
    valor_comida: int
    malas: set          
    zonas_bomba: set    
    valores: dict      


class Contexto(NamedTuple):
    ancho: int
    alto: int
    obs_duro: set      
    obs_ruta: set       
    malas: set
    zonas_bomba: set
    zonas: set          
    e_seg: int
    cola: tuple
    cab_en: list
    cuerp_en: set
    comida: list
    esp_bef: dict
    mi_pts: int
    riv_pts: int
    cx: int
    cy: int
    d_en_manz: dict
    f_dist: object
    pickups: list
    objetivos: list
    valores: dict
    mi_mult: int


def es_vec_valido(nx, ny, ancho, alto, obs, pel, vis):
    if not (0 <= nx < ancho and 0 <= ny < alto): return False
    sig = (nx, ny)
    return sig not in obs and sig not in pel and sig not in vis

def agregar_vecinos(x, y, ancho, alto, obs, pel, vis, cola):
    for dx, dy in DIRECCIONES:
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
    for dx, dy in DIRECCIONES:
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
    for dx, dy in DIRECCIONES:
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

def relajar_astar(sig, g, obj, vis, frontera, zonas):
    nuevo_g = g + (15 if sig in zonas else 1)
    if sig not in vis or nuevo_g < vis[sig]:
        vis[sig] = nuevo_g
        heapq.heappush(frontera, (nuevo_g + heuristica_manhattan(sig, obj), nuevo_g, sig))

def expandir_astar(pos, g, ancho, alto, obs, obj, vis, frontera, zonas):
    for dx, dy in DIRECCIONES:
        nx, ny = pos[0] + dx, pos[1] + dy
        if astar_vecino_ok(nx, ny, ancho, alto, obs):
            relajar_astar((nx, ny), g, obj, vis, frontera, zonas)

def astar_distancia(start_pos, objetivo, obstaculos, ancho, alto, zonas=frozenset()):
    if start_pos == objetivo: return 0
    frontera = [(0, 0, start_pos)]
    visitados = {start_pos: 0}
    while frontera:
        f, g, pos = heapq.heappop(frontera)
        if pos == objetivo: return g
        if g > visitados[pos]: continue  
        expandir_astar(pos, g, ancho, alto, obstaculos, objetivo, visitados, frontera, zonas)
    return 9999

def clasificar_comida(comida_raw):
    """Separa comida buena/mala. Cada dígito puede tener varias copias (desde v6)."""
    asteriscos, nums = [], {}
    for c, x, y in comida_raw:
        if c == '*': asteriscos.append((x, y))
        else: nums.setdefault(int(c), []).append((x, y))

    c_buena, c_mala = [], set()
    valor_comida = 1
    for d, posiciones in nums.items():
        if ((d - 2) % 9 + 1) in nums:
            c_mala.update(posiciones)
        else:
            c_buena.extend(posiciones)
            valor_comida = d
    return asteriscos + c_buena, c_mala, valor_comida

def mapear_valores(comida_raw, comida):
    buenas = set(comida)
    return {(x, y): (1 if c == '*' else int(c)) for c, x, y in comida_raw if (x, y) in buenas}

def zona_bomba(bx, by, radio, ancho, alto):
    xs = range(max(0, bx - radio), min(ancho, bx + radio + 1))
    ys = range(max(0, by - radio), min(alto, by + radio + 1))
    return {(x, y) for x in xs for y in ys}

def calcular_zonas_bomba(bombas, ancho, alto):
    zonas = set()
    for ch, bx, by in bombas:
        zonas |= zona_bomba(bx, by, RADIO_BOMBA[ch], ancho, alto)
    return zonas

def escanear_tablero(filas, dic_acciones):
    for y, fila in enumerate(filas):
        for x, char in enumerate(fila):
            func = dic_acciones.get(char)
            if func: func(x, y)

def acciones_comida(comida_raw, bombas, mi_lado):
    acciones = {c: (lambda x, y, c=c: comida_raw.append((c, x, y))) for c in "123456789*"}
    acciones[COMIDA_COLA[mi_lado]] = lambda x, y: comida_raw.append(('*', x, y))
    for ch in RADIO_BOMBA:
        acciones[ch] = lambda x, y, ch=ch: bombas.append((ch, x, y))
    return acciones

def escanear_completo(filas, mi_lado):
    cuerpo, cab_en, comida_raw, bombas = [], [], [], []
    cuerp_en, paredes = set(), set()
    cabeza, pickups = [], []

    enemigo = list({'A', 'B'} - {mi_lado})[0]

    dic_acciones = acciones_comida(comida_raw, bombas, mi_lado)
    dic_acciones.update({
        mi_lado: lambda x, y: cabeza.append((x, y)),
        mi_lado.lower(): lambda x, y: cuerpo.append((x, y)),
        '|': lambda x, y: paredes.add((x, y)),
        '-': lambda x, y: paredes.add((x, y)),
        '#': lambda x, y: paredes.add((x, y)),
        'X': lambda x, y: pickups.append((x, y)),
        enemigo: lambda x, y: (cab_en.append((x, y)), cuerp_en.add((x, y))),
        enemigo.lower(): lambda x, y: cuerp_en.add((x, y)),
    })
    escanear_tablero(filas, dic_acciones)

    comida, malas, valor_comida = clasificar_comida(comida_raw)
    ancho, alto = len(filas[0]), len(filas)
    return Tablero(
        cabeza[0] if cabeza else None, cuerpo, cab_en, cuerp_en, comida, paredes,
        pickups, valor_comida, malas, calcular_zonas_bomba(bombas, ancho, alto),
        mapear_valores(comida_raw, comida)
    )

def analizar_tablero(filas, mi_lado):
    """Interfaz histórica (8 valores). Los dígitos malos se tratan como paredes."""
    t = escanear_completo(filas, mi_lado)
    return (t.cabeza, t.cuerpo, t.cab_en, t.cuerp_en, t.comida,
            t.paredes | t.malas, t.pickups, t.valor_comida)

def calcular_peligros(cab_en, ancho, alto):
    zonas = set()
    for cx, cy in cab_en:
        for dx, dy in DIRECCIONES:
            if 0 <= cx + dx < ancho and 0 <= cy + dy < alto:
                zonas.add((cx + dx, cy + dy))
    return zonas

def es_pasillo(nx, ny, ancho, alto, obs_sim):
    libres = sum(
        1 for vx, vy in DIRECCIONES
        if 0 <= (nx + vx) < ancho and 0 <= (ny + vy) < alto and (nx + vx, ny + vy) not in obs_sim
    )
    return libres <= 2

def es_borde(nx, ny, ancho, alto):
    return nx in (0, ancho - 1) or ny in (0, alto - 1)

def evaluar_pasillo_borde(nx, ny, ancho, alto, obs_sim, cab_en, sig_pos, f_dist):
    if not cab_en:
        return 0

    dist_cabeza = f_dist(sig_pos)
    pts_pasillo = -60000 * int(dist_cabeza <= 8 and es_pasillo(nx, ny, ancho, alto, obs_sim))
    pts_borde = -15000 * int(dist_cabeza <= 4 and es_borde(nx, ny, ancho, alto))

    return pts_pasillo + pts_borde

def evaluar_ofensiva(esp_before, obs_sim, zonas, an, al, est_len, sig_pos, comida, pickups, mi_mult, valor_comida):
    pts, esp_red, posible_kill = 0, 0, False
    for cab, antes in esp_before.items():
        despues = calcular_espacio_libre(cab, obs_sim, zonas, an, al, an * al)
        esp_red += max(0, antes - despues)
        posible_kill = posible_kill or (despues < est_len + 2)

    pts += esp_red * CONFIG['SPACE_KILL_FACTOR']
    pts += (CONFIG['KILL_VALUE'] * CONFIG['KILL_MULT'] + 300) * int(posible_kill)
    pts += (valor_comida * 100 * mi_mult * CONFIG['APPLE_MULT']) * int(sig_pos in comida)
    pts += CONFIG['X_BONUS'] * int(sig_pos in pickups)

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

def evaluar_supervivencia(sig_pos, area, camino_cola, e_seg, zonas):
    pts = -900000 * int(sig_pos in zonas)   
    if camino_cola:
        return pts + area * 2               
    if area < e_seg:
        return pts - 900000                 
    return pts + area * 8

def evaluar_ofensiva_ctx(sig_pos, cab_ia, c):
    obs_en = c.obs_duro | {sig_pos, cab_ia}
    est_len = max(3, len(c.cuerp_en) // max(1, len(c.cab_en)))
    valor = c.valores.get(sig_pos, 1)
    return evaluar_ofensiva(c.esp_bef, obs_en, frozenset(), c.ancho, c.alto,
                            est_len, sig_pos, c.comida, c.pickups, c.mi_mult, valor)

def evaluar_objetivos(sig_pos, area, obs_sim, c):
    candidatos = ((astar_distancia(sig_pos, m, obs_sim, c.ancho, c.alto, c.zonas), m) for m in c.objetivos)
    mejor_d, mejor_obj = min(candidatos, default=(9999, None))
    d_en = c.d_en_manz.get(mejor_obj, 9999) if mejor_obj else 9999
    return evaluar_manzanas(sig_pos, mejor_obj, mejor_d, d_en, c.cx, c.cy, area)

def evaluar_movimiento(sig_pos, cab_ia, c):
    obs_sim = c.obs_ruta | {cab_ia}   
    area = calcular_espacio_libre(sig_pos, obs_sim, c.zonas, c.ancho, c.alto, c.ancho * c.alto)
    camino_cola = bool(c.cola) and hay_camino_a_objetivo(sig_pos, c.cola, obs_sim, c.ancho, c.alto)

    pts = evaluar_supervivencia(sig_pos, area, camino_cola, c.e_seg, c.zonas)
    pts += evaluar_pasillo_borde(sig_pos[0], sig_pos[1], c.ancho, c.alto, c.obs_duro, c.cab_en, sig_pos, c.f_dist)

    p_ofensiva, posible_kill = evaluar_ofensiva_ctx(sig_pos, cab_ia, c)
    pts += p_ofensiva
    pts += evaluar_tortuga(sig_pos, c.zonas, c.comida, area, c.mi_pts, c.riv_pts, c.f_dist(sig_pos), posible_kill)
    return pts + evaluar_objetivos(sig_pos, area, obs_sim, c)

def costo_celda(sig, malas, zonas_bomba, mi_pts):
    costo = CONFIG['MALA_COST'] * int(sig in malas)
    if sig in zonas_bomba:
        costo += max(mi_pts, 500) + CONFIG['BOMB_MARGIN']
    return costo

def puntuar_movimiento(mov, cab, c):
    nx, ny = cab[0] + mov[0], cab[1] + mov[1]
    if not (0 <= nx < c.ancho and 0 <= ny < c.alto) or (nx, ny) in c.obs_duro:
        return -CONFIG['CRASH_COST']   
    sig = (nx, ny)
    return evaluar_movimiento(sig, cab, c) - costo_celda(sig, c.malas, c.zonas_bomba, c.mi_pts)

def mapear_distancias(comida_y_pickups, cabezas, obs, an, al, zonas=frozenset()):
    return {m: min((astar_distancia(c, m, obs, an, al, zonas) for c in cabezas), default=9999) for m in comida_y_pickups}

def mapear_espacios(cabezas, obs, zonas, an, al):
    return {c: calcular_espacio_libre(c, obs, zonas, an, al, an * al) for c in cabezas}

def f_dist_factory(cab_en):
    return lambda pos: min((abs(pos[0]-cx) + abs(pos[1]-cy) for cx, cy in cab_en), default=9999)

def construir_contexto(t, ancho, alto, mi_pts, riv_pts, mi_mult):
    obs_duro = set(t.cuerpo) | t.cuerp_en | t.paredes
    obs_ruta = obs_duro | t.malas | t.zonas_bomba
    objetivos = t.comida + t.pickups
    return Contexto(
        ancho, alto, obs_duro, obs_ruta, t.malas, t.zonas_bomba,
        calcular_peligros(t.cab_en, ancho, alto), len(t.cuerpo) + 3,
        encontrar_cola(t.cuerpo, t.cabeza), t.cab_en, t.cuerp_en, t.comida,
        mapear_espacios(t.cab_en, obs_duro, frozenset(), ancho, alto),
        mi_pts, riv_pts, ancho // 2, alto // 2,
        mapear_distancias(objetivos, t.cab_en, obs_duro, ancho, alto),
        f_dist_factory(t.cab_en), t.pickups, objetivos, t.valores, mi_mult
    )

def obtener_movimiento_ia(board_string, mi_lado, mi_puntaje=0, rival_puntaje=0, mi_mult=1, game_id=None):
    filas = board_string.strip('\n').split('\n')
    t = escanear_completo(filas, mi_lado)

    if not t.cabeza: return "UP"
    ctx = construir_contexto(t, len(filas[0]), len(filas), mi_puntaje, rival_puntaje, mi_mult)

    opciones = [(0, -1, "UP"), (0, 1, "DOWN"), (-1, 0, "LEFT"), (1, 0, "RIGHT")]
    return max(opciones, key=lambda m: puntuar_movimiento(m, t.cabeza, ctx))[2]

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
        active_games.pop(game_id, None)

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
            print(f"[X] Conexión caída: {e}")
            await asyncio.sleep(3)

if __name__ == "__main__": # pragma: no cover
    if len(sys.argv) < 2:
        print("Uso: python run_v4.py <TU_TOKEN>")
        sys.exit(1)

    token = sys.argv[1]

    def run_asyncio_client():
        try: asyncio.run(start(token))
        except KeyboardInterrupt: pass

    hilo_websocket = threading.Thread(target=run_asyncio_client, daemon=True, name="WebSocketClient")
    hilo_websocket.start()

    try:
        from interfaz import iniciar_interfaz_multitab  # import tardío: los tests no necesitan tkinter
        iniciar_interfaz_multitab(get_all_games)
    except Exception as e:
        print(f"[!] Sin interfaz ({e}); el bot sigue jugando.")
    hilo_websocket.join()  
