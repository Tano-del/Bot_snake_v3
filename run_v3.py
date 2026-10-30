import asyncio
from collections import deque
import heapq
import json
import sys
import threading
from typing import NamedTuple
import websockets

active_games = {}
games_lock = threading.Lock()


def get_all_games():
    with games_lock:
        return {
            game_id: data.copy() for game_id, data in active_games.items()
        }


CONFIG = {
    'APPLE_VALUE': 100,
    'KILL_VALUE': 1000,
    'TURN_POINT': 1,
    'APPLE_MULT': 25,
    'KILL_MULT': 15,
    'SPACE_KILL_FACTOR': 30,
    'TURTLE_THRESHOLD': 1000,
    'X_BONUS': 4000,
    'STAR_BONUS': 12000,
    'CUT_BONUS': 5000,
    'SHOOT_COST': 5000,
    'CRASH_COST': 20_000_000,
    'CRASH_COST_INV': 500_000,
    'MALA_COST': 2_500_000,
    'BOMB_MARGIN': 5_000_000,
}

RADIO_BOMBA = {'\U0001F4A3': 2, '\U0001F9E8': 1}
COMIDA_COLA = {'A': '\u24b6', 'B': '\u24b7'}
ESTRELLA = '\u2b50'

DIRECCIONES = [(0, -1), (0, 1), (-1, 0), (1, 0)]
NOMBRES_DIR = {
    (0, -1): "UP",
    (0, 1): "DOWN",
    (-1, 0): "LEFT",
    (1, 0): "RIGHT",
}


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
    estrellas: set = frozenset()
    mi_inv: bool = False
    riv_inv: bool = False
    inv_seguro: bool = False


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
    estrellas: set = frozenset()
    mi_inv: bool = False
    riv_inv: bool = False


def dentro_tablero(nx, ny, ancho, alto):
    return 0 <= nx < ancho and 0 <= ny < alto


def es_vec_valido(nx, ny, ancho, alto, obs, pel, vis):
    if not dentro_tablero(nx, ny, ancho, alto):
        return False
    sig = (nx, ny)
    return sig not in obs and sig not in pel and sig not in vis


def agregar_vecinos(x, y, ancho, alto, obs, pel, vis, cola):
    for dx, dy in DIRECCIONES:
        nx, ny = x + dx, y + dy
        if es_vec_valido(nx, ny, ancho, alto, obs, pel, vis):
            vis.add((nx, ny))
            cola.append((nx, ny))


def calcular_espacio_libre(
    start_pos, obstaculos, zonas_peligro, ancho, alto, limite
):
    visitados = {start_pos}
    cola = deque([start_pos])
    espacio = 0
    while cola and espacio < limite:
        x, y = cola.popleft()
        espacio += 1
        agregar_vecinos(
            x, y, ancho, alto, obstaculos, zonas_peligro, visitados, cola
        )
    return espacio


def heuristica_manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def contar_vecinos_cuerpo(segmento, cuerpo_set, cabeza):
    vecinos = 0
    for dx, dy in DIRECCIONES:
        vec = (segmento[0] + dx, segmento[1] + dy)
        if vec in cuerpo_set or vec == cabeza:
            vecinos += 1
    return vecinos


def encontrar_cola(cuerpo_propio, cabeza):
    if not cuerpo_propio:
        return None
    cuerpo_set = set(cuerpo_propio)
    for segmento in cuerpo_propio:
        if contar_vecinos_cuerpo(segmento, cuerpo_set, cabeza) == 1:
            return segmento
    return cuerpo_propio[-1]


def vecino_camino_ok(nx, ny, ancho, alto, obs, obj, vis):
    if not dentro_tablero(nx, ny, ancho, alto):
        return False
    sig = (nx, ny)
    if sig in vis:
        return False
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
        if pos == objetivo:
            return True
        expandir_camino(
            pos, ancho, alto, obstaculos, objetivo, visitados, cola
        )
    return False


def astar_vecino_ok(nx, ny, ancho, alto, obs):
    return dentro_tablero(nx, ny, ancho, alto) and (nx, ny) not in obs


def relajar_astar(sig, g, obj, vis, frontera, zonas):
    nuevo_g = g + (15 if sig in zonas else 1)
    if sig not in vis or nuevo_g < vis[sig]:
        vis[sig] = nuevo_g
        prioridad = nuevo_g + heuristica_manhattan(sig, obj)
        heapq.heappush(frontera, (prioridad, nuevo_g, sig))


def expandir_astar(pos, g, ancho, alto, obs, obj, vis, frontera, zonas):
    for dx, dy in DIRECCIONES:
        nx, ny = pos[0] + dx, pos[1] + dy
        if astar_vecino_ok(nx, ny, ancho, alto, obs):
            relajar_astar((nx, ny), g, obj, vis, frontera, zonas)


def astar_distancia(
    start_pos, objetivo, obstaculos, ancho, alto, zonas=frozenset()
):
    if start_pos == objetivo:
        return 0
    frontera = [(0, 0, start_pos)]
    visitados = {start_pos: 0}
    while frontera:
        _, g, pos = heapq.heappop(frontera)
        if pos == objetivo:
            return g
        if g <= visitados[pos]:
            expandir_astar(
                pos, g, ancho, alto, obstaculos,
                objetivo, visitados, frontera, zonas,
            )
    return 9999


def clasificar_comida(comida_raw):
    """Separa comida buena/mala. Cada digito puede tener varias copias."""
    asteriscos, nums = [], {}
    for c, x, y in comida_raw:
        if c == '*':
            asteriscos.append((x, y))
        else:
            nums.setdefault(int(c), []).append((x, y))

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
    return {
        (x, y): (1 if c == '*' else int(c))
        for c, x, y in comida_raw
        if (x, y) in buenas
    }


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
            if func:
                func(x, y)


def acciones_comida(comida_raw, bombas, estrellas, mi_lado):
    acciones = {
        c: (lambda x, y, c=c: comida_raw.append((c, x, y)))
        for c in "123456789*"
    }
    cola_ch = COMIDA_COLA[mi_lado]
    acciones[cola_ch] = lambda x, y: comida_raw.append(('*', x, y))
    acciones[ESTRELLA] = lambda x, y: (
        comida_raw.append(('*', x, y)),
        estrellas.add((x, y)),
    )
    for ch in RADIO_BOMBA:
        acciones[ch] = lambda x, y, ch=ch: bombas.append((ch, x, y))
    return acciones


def resolver_serpiente(pos_may, pos_min, inv_flag=False):
    es_inv = bool(inv_flag) or (len(pos_min) == 1 and len(pos_may) > 1)
    if es_inv:
        return pos_min, pos_may, True
    return pos_may, pos_min, False


def escanear_completo(filas, mi_lado, mi_inv=0, riv_inv=0):
    mi_may, mi_min, en_may, en_min = [], [], [], []
    comida_raw, bombas, pickups = [], [], []
    paredes, estrellas = set(), set()

    enemigo = 'B' if mi_lado == 'A' else 'A'
    dic_acciones = acciones_comida(comida_raw, bombas, estrellas, mi_lado)
    dic_acciones.update({
        mi_lado: lambda x, y: mi_may.append((x, y)),
        mi_lado.lower(): lambda x, y: mi_min.append((x, y)),
        '|': lambda x, y: paredes.add((x, y)),
        '-': lambda x, y: paredes.add((x, y)),
        '#': lambda x, y: paredes.add((x, y)),
        'X': lambda x, y: pickups.append((x, y)),
        enemigo: lambda x, y: en_may.append((x, y)),
        enemigo.lower(): lambda x, y: en_min.append((x, y)),
    })
    escanear_tablero(filas, dic_acciones)

    cabeza, cuerpo, soy_inv = resolver_serpiente(mi_may, mi_min, mi_inv > 0)
    cab_en, c_en_l, en_inv = resolver_serpiente(en_may, en_min, riv_inv > 0)
    cuerp_en = set(cab_en) | set(c_en_l)

    comida, malas, valor_comida = clasificar_comida(comida_raw)
    ancho, alto = len(filas[0]), len(filas)
    return Tablero(
        cabeza[0] if cabeza else None,
        cuerpo,
        cab_en,
        cuerp_en,
        comida,
        paredes,
        pickups,
        valor_comida,
        malas,
        calcular_zonas_bomba(bombas, ancho, alto),
        mapear_valores(comida_raw, comida),
        estrellas,
        soy_inv,
        en_inv,
        soy_inv and mi_inv != 1,
    )


def analizar_tablero(filas, mi_lado):
    """Interfaz historica (8 valores). Digitos malos se tratan como paredes."""
    t = escanear_completo(filas, mi_lado)
    return (
        t.cabeza,
        t.cuerpo,
        t.cab_en,
        t.cuerp_en,
        t.comida,
        t.paredes | t.malas,
        t.pickups,
        t.valor_comida,
    )


def calcular_peligros(cab_en, ancho, alto):
    zonas = set()
    for cx, cy in cab_en:
        for dx, dy in DIRECCIONES:
            if dentro_tablero(cx + dx, cy + dy, ancho, alto):
                zonas.add((cx + dx, cy + dy))
    return zonas


def contar_vecinos_libres(nx, ny, ancho, alto, obs_sim):
    libres = 0
    for vx, vy in DIRECCIONES:
        tx, ty = nx + vx, ny + vy
        if dentro_tablero(tx, ty, ancho, alto) and (tx, ty) not in obs_sim:
            libres += 1
    return libres


def es_pasillo(nx, ny, ancho, alto, obs_sim):
    return contar_vecinos_libres(nx, ny, ancho, alto, obs_sim) <= 2


def es_borde(nx, ny, ancho, alto):
    return nx in (0, ancho - 1) or ny in (0, alto - 1)


def evaluar_pasillo_borde(
    nx, ny, ancho, alto, obs_sim, cab_en, sig_pos, f_dist
):
    if not cab_en:
        return 0

    dist_cabeza = f_dist(sig_pos)
    en_pasillo = dist_cabeza <= 8 and es_pasillo(nx, ny, ancho, alto, obs_sim)
    en_borde = dist_cabeza <= 4 and es_borde(nx, ny, ancho, alto)
    return -60000 * int(en_pasillo) - 15000 * int(en_borde)


def evaluar_ofensiva(
    esp_before, obs_sim, zonas, an, al, est_len,
    sig_pos, comida, pickups, mi_mult, valor_comida,
):
    pts, esp_red, posible_kill = 0, 0, False
    for cab, antes in esp_before.items():
        despues = calcular_espacio_libre(cab, obs_sim, zonas, an, al, an * al)
        esp_red += max(0, antes - despues)
        posible_kill = posible_kill or (despues < est_len + 2)

    bono_kill = CONFIG['KILL_VALUE'] * CONFIG['KILL_MULT'] + 300
    pts += esp_red * CONFIG['SPACE_KILL_FACTOR']
    pts += bono_kill * int(posible_kill)
    pts += (valor_comida * 100 * mi_mult * CONFIG['APPLE_MULT']) * int(
        sig_pos in comida
    )
    pts += CONFIG['X_BONUS'] * int(sig_pos in pickups)
    return pts, posible_kill


def evaluar_tortuga(
    sig_pos, zonas, comida, area, mi_pts, riv_pts, dist_en, p_kill
):
    pts = 0
    if mi_pts - riv_pts >= CONFIG['TURTLE_THRESHOLD']:
        pts -= 700 * int(sig_pos in zonas)
        pts -= (CONFIG['APPLE_VALUE'] * 2) * int(sig_pos in comida)
        pts += area * 3

    if dist_en == 0:
        return pts - 6000

    pts_dist = -1200 if (dist_en == 1 and not p_kill) else (dist_en * 5)
    return pts + pts_dist


def bonus_distancia_manzana(sig_pos, d_manz, d_en_com, cx, cy):
    if d_manz < d_en_com:
        return max(0, 4000 - d_manz * 60)
    if d_manz == d_en_com:
        return max(0, 2000 - d_manz * 30)
    dist_centro = abs(sig_pos[0] - cx) + abs(sig_pos[1] - cy)
    return max(0, 200 - dist_centro * 8) - 1000


def evaluar_manzanas(sig_pos, obj, d_manz, d_en_com, cx, cy, esp):
    if obj:
        pts = bonus_distancia_manzana(sig_pos, d_manz, d_en_com, cx, cy)
        return pts + max(0, 1500 - d_manz * 40)
    dist_centro = abs(sig_pos[0] - cx) + abs(sig_pos[1] - cy)
    return esp * 3 - dist_centro * 3


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
    pts, p_kill = evaluar_ofensiva(
        c.esp_bef, obs_en, frozenset(), c.ancho, c.alto,
        est_len, sig_pos, c.comida, c.pickups, c.mi_mult, valor,
    )
    pts += CONFIG['STAR_BONUS'] * int(sig_pos in c.estrellas)
    pts += CONFIG['CUT_BONUS'] * int(c.mi_inv and sig_pos in c.cuerp_en)
    return pts, p_kill


def evaluar_objetivos(sig_pos, area, obs_sim, c):
    candidatos = (
        (astar_distancia(sig_pos, m, obs_sim, c.ancho, c.alto, c.zonas), m)
        for m in c.objetivos
    )
    mejor_d, mejor_obj = min(candidatos, default=(9999, None))
    d_en = c.d_en_manz.get(mejor_obj, 9999) if mejor_obj else 9999
    return evaluar_manzanas(
        sig_pos, mejor_obj, mejor_d, d_en, c.cx, c.cy, area
    )


def evaluar_movimiento(sig_pos, cab_ia, c):
    obs_sim = c.obs_ruta | {cab_ia}
    area = calcular_espacio_libre(
        sig_pos, obs_sim, c.zonas, c.ancho, c.alto, c.ancho * c.alto
    )
    camino_cola = bool(c.cola) and hay_camino_a_objetivo(
        sig_pos, c.cola, obs_sim, c.ancho, c.alto
    )

    pts = evaluar_supervivencia(sig_pos, area, camino_cola, c.e_seg, c.zonas)
    pts += evaluar_pasillo_borde(
        sig_pos[0], sig_pos[1], c.ancho, c.alto,
        c.obs_duro, c.cab_en, sig_pos, c.f_dist,
    )

    p_ofensiva, posible_kill = evaluar_ofensiva_ctx(sig_pos, cab_ia, c)
    pts += p_ofensiva
    pts += evaluar_tortuga(
        sig_pos, c.zonas, c.comida, area,
        c.mi_pts, c.riv_pts, c.f_dist(sig_pos), posible_kill,
    )
    return pts + evaluar_objetivos(sig_pos, area, obs_sim, c)


def costo_celda(sig, malas, zonas_bomba, mi_pts, mi_inv=False):
    if mi_inv:
        return 50 * int(sig in malas)
    costo = CONFIG['MALA_COST'] * int(sig in malas)
    if sig in zonas_bomba:
        costo += max(mi_pts, 500) + CONFIG['BOMB_MARGIN']
    return costo


def costo_choque(c):
    # Invencible: chocar no resta puntos, solo deja la snake en el lugar.
    return CONFIG['CRASH_COST_INV'] if c.mi_inv else CONFIG['CRASH_COST']


def puntuar_movimiento(mov, cab, c):
    nx, ny = cab[0] + mov[0], cab[1] + mov[1]
    if not dentro_tablero(nx, ny, c.ancho, c.alto) or (nx, ny) in c.obs_duro:
        return -costo_choque(c)
    sig = (nx, ny)
    pts = evaluar_movimiento(sig, cab, c)
    return pts - costo_celda(sig, c.malas, c.zonas_bomba, c.mi_pts, c.mi_inv)


def mapear_distancias(
    comida_y_pickups, cabezas, obs, an, al, zonas=frozenset()
):
    return {
        m: min(
            (astar_distancia(c, m, obs, an, al, zonas) for c in cabezas),
            default=9999,
        )
        for m in comida_y_pickups
    }


def mapear_espacios(cabezas, obs, zonas, an, al):
    return {
        c: calcular_espacio_libre(c, obs, zonas, an, al, an * al)
        for c in cabezas
    }


def f_dist_factory(cab_en):
    return lambda pos: min(
        (abs(pos[0] - cx) + abs(pos[1] - cy) for cx, cy in cab_en),
        default=9999,
    )


def obstaculos_segun_estado(t):
    # Solo se relajan las penalidades si quedan 2+ turnos de invencibilidad:
    # con 1 turno restante no sabemos si el turno actual sigue cubierto.
    en_bloquea = not (t.inv_seguro and len(t.cuerp_en) > 1)
    obs_en = t.cuerp_en if en_bloquea else set()
    obs_duro = set(t.cuerpo) | t.paredes | obs_en
    if t.inv_seguro:
        return obs_duro, obs_duro
    return obs_duro, obs_duro | t.malas | t.zonas_bomba


def construir_contexto(t, ancho, alto, mi_pts, riv_pts, mi_mult):
    obs_duro, obs_ruta = obstaculos_segun_estado(t)
    objetivos = t.comida + t.pickups
    peligros = (
        frozenset()
        if (t.inv_seguro and not t.riv_inv)
        else calcular_peligros(t.cab_en, ancho, alto)
    )
    return Contexto(
        ancho, alto, obs_duro, obs_ruta, t.malas, t.zonas_bomba,
        peligros, len(t.cuerpo) + 3,
        encontrar_cola(t.cuerpo, t.cabeza), t.cab_en, t.cuerp_en, t.comida,
        mapear_espacios(t.cab_en, obs_duro, frozenset(), ancho, alto),
        mi_pts, riv_pts, ancho // 2, alto // 2,
        mapear_distancias(objetivos, t.cab_en, obs_duro, ancho, alto),
        f_dist_factory(t.cab_en), t.pickups, objetivos, t.valores, mi_mult,
        t.estrellas, t.inv_seguro, t.riv_inv,
    )


def rayo_impacta_rival(cab, dx, dy, t, ancho, alto):
    for paso in range(1, 5):
        nx, ny = cab[0] + dx * paso, cab[1] + dy * paso
        if not dentro_tablero(nx, ny, ancho, alto) or (nx, ny) in t.paredes:
            return False
        if (nx, ny) in t.cuerp_en:
            return True
    return False


def conviene_disparar(t, mi_pts, mi_mult):
    if t.riv_inv or not t.cabeza:
        return False
    ganancia = len(t.cuerp_en) * 100 * mi_mult
    return mi_pts >= CONFIG['SHOOT_COST'] + 1000 and ganancia >= 3000


def direccion_disparo(t, ancho, alto, mi_pts, mi_mult):
    if not conviene_disparar(t, mi_pts, mi_mult):
        return None
    for dx, dy in DIRECCIONES:
        if rayo_impacta_rival(t.cabeza, dx, dy, t, ancho, alto):
            return NOMBRES_DIR[(dx, dy)]
    return None


def obtener_movimiento_ia(
    board_string, mi_lado, mi_puntaje=0, rival_puntaje=0,
    mi_mult=1, game_id=None, mi_inv=0, riv_inv=0,
):
    filas = board_string.strip('\n').split('\n')
    t = escanear_completo(filas, mi_lado, mi_inv, riv_inv)

    if not t.cabeza:
        return "UP"
    ctx = construir_contexto(
        t, len(filas[0]), len(filas), mi_puntaje, rival_puntaje, mi_mult
    )

    opciones = [
        (0, -1, "UP"), (0, 1, "DOWN"), (-1, 0, "LEFT"), (1, 0, "RIGHT")
    ]
    return max(opciones, key=lambda m: puntuar_movimiento(m, t.cabeza, ctx))[2]


def obtener_accion_ia(
    board_string, mi_lado, mi_puntaje=0, rival_puntaje=0,
    mi_mult=1, game_id=None, mi_inv=0, riv_inv=0,
):
    filas = board_string.strip('\n').split('\n')
    t = escanear_completo(filas, mi_lado, mi_inv, riv_inv)
    if not t.cabeza:
        return "move", "UP"
    ancho, alto = len(filas[0]), len(filas)
    disparo = direccion_disparo(t, ancho, alto, mi_puntaje, mi_mult)
    if disparo:
        return "shoot", disparo
    mov = obtener_movimiento_ia(
        board_string, mi_lado, mi_puntaje, rival_puntaje,
        mi_mult, game_id, mi_inv, riv_inv,
    )
    return "move", mov


async def send(websocket, action, data):  # pragma: no cover
    message = json.dumps({"action": action, "data": data})
    print(f"> Enviando: {message}")
    await websocket.send(message)


async def handle_challenge(websocket, data):  # pragma: no cover
    challenge_id = data.get("challenge_id")
    await send(websocket, "accept_challenge", {"challenge_id": challenge_id})


def extraer_invencibilidad(data, side):
    inv1 = data.get("invincible_1", 0)
    inv2 = data.get("invincible_2", 0)
    if side == 'A':
        return inv1, inv2
    return inv2, inv1


def extraer_estado_jugador(data, side):
    p1 = data.get("player_1", "Jugador 1")
    pts1 = data.get("score_1", 0)
    p2 = data.get("player_2", "Jugador 2")
    pts2 = data.get("score_2", 0)
    m1, m2 = data.get("multiplier_1", 1), data.get("multiplier_2", 1)

    marcador = f"{p1}: {pts1} pts (x{m1}) | {p2}: {pts2} pts (x{m2})"

    if side == 'A':
        return pts1, pts2, m1, marcador
    return pts2, pts1, m2, marcador


async def handle_your_turn(websocket, data):  # pragma: no cover
    game_id = data.get("game_id")
    side = data.get("side")
    board_string = data.get("board")

    mi_pts, riv_pts, mi_mult, marcador = extraer_estado_jugador(data, side)
    mi_inv, riv_inv = extraer_invencibilidad(data, side)

    with games_lock:
        if active_games.get(game_id, {}).get("game_over", False):
            return
        active_games[game_id] = {
            "tablero": board_string,
            "marcador": marcador,
            "side": side,
            "mi_inv": mi_inv,
            "riv_inv": riv_inv,
            "game_over": False,
        }

    accion, direccion = obtener_accion_ia(
        board_string, side, mi_pts, riv_pts, mi_mult, game_id, mi_inv, riv_inv
    )
    await send(
        websocket,
        accion,
        {
            "game_id": game_id,
            "turn_token": data.get("turn_token"),
            "direction": direccion,
        },
    )


def handle_game_over(data):  # pragma: no cover
    game_id = data.get("game_id")
    print(f"\n--- [!] Partida {game_id} terminada ---\n")
    with games_lock:
        active_games.pop(game_id, None)


async def process_event(websocket, message_str):  # pragma: no cover
    print(f"< Recibido: {message_str[:150]}...")
    try:
        message = json.loads(message_str)
        event, data = message.get("event"), message.get("data", {})
        eventos_handlers = {
            "challenge": lambda: handle_challenge(websocket, data),
            "your_turn": lambda: handle_your_turn(websocket, data),
            "game_over": lambda: handle_game_over(data),
        }
        handler = eventos_handlers.get(event)
        if handler:
            result = handler()
            if asyncio.iscoroutine(result):
                await result
    except json.JSONDecodeError:
        print("[X] Error JSON")
    except Exception as e:
        print(f"[X] Error: {e}")


async def play(websocket):  # pragma: no cover
    async for message in websocket:
        await process_event(websocket, message)


async def start(auth_token):  # pragma: no cover
    uri = f"wss://server.codechallenge.net.ar/ws?token={auth_token}"
    while True:
        try:
            print("\n[*] Conectando al servidor...")
            async with websockets.connect(uri) as websocket:
                print("[*] Conexion establecida exitosamente!")
                await play(websocket)
        except websockets.ConnectionClosed:
            await asyncio.sleep(3)
        except Exception as e:
            print(f"[X] Conexion caida: {e}")
            await asyncio.sleep(3)


if __name__ == "__main__":  # pragma: no cover
    if len(sys.argv) < 2:
        print("Uso: python run_v3.py <TU_TOKEN>")
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
        from interfaz import iniciar_interfaz_multitab
        iniciar_interfaz_multitab(get_all_games)
    except Exception as e:
        print(f"[!] Sin interfaz ({e}); el bot sigue jugando.")
    hilo_websocket.join()
