from pathlib import Path
import random
import subprocess
import sys

import pytest

from run_v3 import (
    CONFIG,
    ESTRELLA,
    active_games,
    analizar_tablero,
    astar_distancia,
    calcular_espacio_libre,
    calcular_peligros,
    clasificar_comida,
    construir_contexto,
    costo_choque,
    encontrar_cola,
    es_pasillo,
    escanear_completo,
    extraer_estado_jugador,
    extraer_invencibilidad,
    get_all_games,
    hay_camino_a_objetivo,
    heuristica_manhattan,
    mapear_distancias,
    mapear_espacios,
    obtener_accion_ia,
    obtener_movimiento_ia,
)

REPO_DIR = str(Path(__file__).parent)
VEC_DIR = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}


def test_calidad_codigo_xenon():
    """Verifica que todo el repositorio mantenga calificacion 'A' en Xenon."""
    comando = [
        sys.executable,
        "-m",
        "xenon",
        "--max-absolute",
        "A",
        "--max-modules",
        "A",
        "--max-average",
        "A",
        REPO_DIR,
    ]
    resultado = subprocess.run(comando, capture_output=True, text=True)
    msg = (
        f"El codigo bajo de 'A' en Xenon.\n"
        f"{resultado.stdout}\n{resultado.stderr}"
    )
    assert resultado.returncode == 0, msg


def test_calidad_codigo_flake8():
    """Verifica que todo el codigo pase el linter Flake8 sin errores."""
    comando = [sys.executable, "-m", "flake8", REPO_DIR]
    resultado = subprocess.run(comando, capture_output=True, text=True)
    msg = f"Flake8 detecto errores:\n{resultado.stdout}\n{resultado.stderr}"
    assert resultado.returncode == 0, msg


def test_get_all_games():
    active_games["g1"] = {"tablero": "A", "marcador": "m", "side": "A"}
    copia = get_all_games()
    assert "g1" in copia
    active_games.pop("g1", None)


def test_distancia_manhattan():
    assert heuristica_manhattan((0, 0), (3, 4)) == 7
    assert heuristica_manhattan((5, 5), (5, 5)) == 0


def test_astar_distancia():
    assert astar_distancia((0, 0), (0, 0), set(), 5, 5) == 0
    assert astar_distancia((0, 0), (0, 2), set(), 5, 5) == 2
    obstaculos = {(0, 1), (1, 0), (1, 1)}
    assert astar_distancia((0, 0), (4, 4), obstaculos, 5, 5) == 9999


def test_calcular_espacio_libre():
    obstaculos = {(1, 0), (1, 1)}
    zonas_peligro = {(2, 2)}
    espacio = calcular_espacio_libre(
        (0, 0), obstaculos, zonas_peligro, 5, 5, 100
    )
    assert 0 < espacio < 25
    espacio_limitado = calcular_espacio_libre((0, 0), set(), set(), 10, 10, 3)
    assert espacio_limitado == 3


def test_hay_camino_a_objetivo():
    obstaculos = {(1, 0), (1, 1), (1, 2), (1, 3), (1, 4)}
    assert not hay_camino_a_objetivo((0, 2), (3, 2), obstaculos, 5, 5)
    assert hay_camino_a_objetivo((0, 2), (3, 2), set(), 5, 5)


def test_es_pasillo():
    obs_sim = {(0, 1), (1, 0), (2, 1)}
    assert es_pasillo(1, 1, 5, 5, obs_sim) is True
    assert es_pasillo(2, 2, 5, 5, set()) is False


def test_encontrar_cola():
    cabeza = (2, 2)
    cuerpo = [(2, 3), (2, 4), (2, 5)]
    assert encontrar_cola(cuerpo, cabeza) == (2, 5)
    assert encontrar_cola([(2, 4), (4, 4)], cabeza) == (4, 4)
    assert encontrar_cola([], cabeza) is None


@pytest.mark.parametrize(
    "cabezas_enemigas, filas, columnas, peligros_esperados",
    [
        ([(2, 2)], 5, 5, {(1, 2), (3, 2), (2, 1), (2, 3)}),
        ([(0, 0)], 5, 5, {(0, 1), (1, 0)}),
        ([(4, 2)], 5, 5, {(3, 2), (4, 1), (4, 3)}),
        ([(0, 0), (4, 4)], 5, 5, {(0, 1), (1, 0), (3, 4), (4, 3)}),
        ([], 5, 5, set()),
    ],
)
def test_calcular_peligros(
    cabezas_enemigas, filas, columnas, peligros_esperados
):
    peligros = calcular_peligros(cabezas_enemigas, filas, columnas)
    assert set(peligros) == peligros_esperados


def test_analizar_tablero_jugador():
    tablero = ["|A|", "-X-", "bB#"]
    cab, cuerpo, _, _, _, _, _, _ = analizar_tablero(tablero, 'A')
    assert cab == (1, 0)
    assert cuerpo == []


def test_analizar_tablero_enemigo():
    tablero = ["|A|", "-*-", "bB."]
    _, _, cab_en, cuerp_en, _, _, _, _ = analizar_tablero(tablero, 'A')
    assert cab_en == [(1, 2)]
    assert cuerp_en == {(0, 2), (1, 2)}


def test_analizar_tablero_entorno():
    tablero = ["|A|", "-X-", "bB#"]
    _, _, _, _, _, paredes, pickups, _ = analizar_tablero(tablero, 'A')
    assert (1, 1) in pickups
    assert len(paredes) == 5


def test_clasificar_comida_buena():
    c_raw = [('*', 1, 1), ('3', 2, 2), ('4', 3, 3), ('1', 4, 4)]
    c_buena, _, _ = clasificar_comida(c_raw)
    assert len(c_buena) == 3
    assert set(c_buena) == {(1, 1), (2, 2), (4, 4)}


def test_clasificar_comida_mala_valor():
    c_raw = [('*', 1, 1), ('3', 2, 2), ('4', 3, 3), ('1', 4, 4)]
    _, c_mala, valor = clasificar_comida(c_raw)
    assert set(c_mala) == {(3, 3)}
    assert valor == 1


def test_mapeos():
    comida = [(0, 0)]
    cab_en = [(2, 2)]
    obs = {(1, 1)}
    zonas = set()
    dist_manz = mapear_distancias(comida, cab_en, obs, 5, 5)
    assert dist_manz[(0, 0)] == 4
    espacios = mapear_espacios(cab_en, obs, zonas, 5, 5)
    assert espacios[(2, 2)] > 0


def test_ia_sin_cabeza():
    tablero_vacio = "\n".join([".......", "...*...", "....B.."])
    mov = obtener_movimiento_ia(tablero_vacio, 'A', 0, 0, 1, "test-1")
    assert mov == "UP"
    assert obtener_accion_ia(tablero_vacio, 'A') == ("move", "UP")


def test_ia_movimiento_basico():
    tablero = "\n".join([
        ".......",
        "...*...",
        "..Aaa..",
        ".......",
        "..b....",
        "..B....",
        ".......",
    ])
    mov_a = obtener_movimiento_ia(tablero, 'A', 0, 0, 1, "test-2")
    assert mov_a in ["UP", "DOWN", "LEFT", "RIGHT"]
    mov_b = obtener_movimiento_ia(tablero, 'B', 0, 0, 1, "test-2")
    assert mov_b in ["UP", "DOWN", "LEFT", "RIGHT"]


def test_ia_movimiento_encerrado():
    tablero = "\n".join(["|-|....", "|A|....", "|.B....", "......."])
    mov = obtener_movimiento_ia(tablero, 'A', 0, 0, 1, "test-3")
    assert mov == "DOWN"


def test_ia_ataque_ofensivo():
    tablero = "\n".join([
        ".......",
        "....A..",
        "....B.|",
        "....b.|",
        "....b.|",
    ])
    mov = obtener_movimiento_ia(tablero, 'A', 0, 0, 1, "test-4")
    assert mov in ["LEFT", "RIGHT", "UP"]


def test_ia_modo_tortuga():
    tablero = "\n".join([
        ".......",
        "...*...",
        "..A....",
        ".......",
        "....B..",
        ".......",
    ])
    mov = obtener_movimiento_ia(tablero, 'A', 1500, 0, 1, "test-5")
    assert mov in ["UP", "DOWN", "LEFT", "RIGHT"]


def test_ia_evitar_peligro():
    tablero = "\n".join([".......", "..A....", "..B....", "......."])
    mov = obtener_movimiento_ia(tablero, 'A', 0, 0, 1, "test-6")
    assert mov in ["UP", "LEFT", "RIGHT"]


def test_ia_movimiento_nueva_regla():
    tablero = "\n".join([
        ".......",
        "...3...",
        "..A.4..",
        "...X...",
        "..b..#.",
        "..B....",
        ".......",
    ])
    mov_a = obtener_movimiento_ia(tablero, 'A', 0, 0, 1, "test-numeros")
    assert mov_a in ["UP", "DOWN", "LEFT", "RIGHT"]


def test_anal_tablero_elementos():
    filas = [
        ".......", "...3...", "..A.4..", "...X...",
        "..b..#.", "..B....", ".......",
    ]
    _, _, _, _, comida, paredes, _, _ = analizar_tablero(filas, 'A')
    assert (3, 1) in comida
    assert (4, 2) in paredes
    assert (5, 4) in paredes


def test_anal_tablero_pickups():
    filas = [
        ".......", "...3...", "..A.4..", "...X...",
        "..b..#.", "..B....", ".......",
    ]
    _, _, _, _, _, _, pickups, valor_comida = analizar_tablero(filas, 'A')
    assert (3, 3) in pickups
    assert valor_comida == 3


def test_extraer_estado_a():
    data = {
        "player_1": "Beto", "score_1": 1500, "multiplier_1": 3,
        "player_2": "Ana", "score_2": 200, "multiplier_2": 1,
        "invincible_1": 40, "invincible_2": 0,
    }
    mi_pts, riv_pts, mi_mult, marcador = extraer_estado_jugador(data, 'A')
    inv_a, inv_b = extraer_invencibilidad(data, 'A')
    assert (mi_pts, riv_pts, mi_mult) == (1500, 200, 3)
    assert "(x3)" in marcador
    assert (inv_a, inv_b) == (40, 0)


def test_extraer_estado_b():
    data = {
        "player_1": "Beto", "score_1": 1500, "multiplier_1": 3,
        "player_2": "Ana", "score_2": 200, "multiplier_2": 1,
        "invincible_1": 10, "invincible_2": 25,
    }
    mi_pts_b, riv_pts_b, mi_mult_b, _ = extraer_estado_jugador(data, 'B')
    inv_b, inv_a = extraer_invencibilidad(data, 'B')
    assert (mi_pts_b, riv_pts_b, mi_mult_b) == (200, 1500, 1)
    assert (inv_b, inv_a) == (25, 10)


def test_v10_estrella_e_invencibilidad_invertida():
    filas = [
        "|         |",
        f"|  AAAa{ESTRELLA}  |",
        "|         |",
        "|   bBB   |",
        "|         |",
    ]
    t = escanear_completo(filas, 'A')
    assert (t.mi_inv, t.riv_inv, t.cabeza) == (True, True, (6, 1))
    assert len(t.cuerpo) == 3 and (7, 1) in t.estrellas
    mov = obtener_movimiento_ia("\n".join(filas), 'A', 500, 500, 2, "v10", 30)
    assert mov == "RIGHT"


def test_v10_invencible_corta_al_rival():
    filas = [
        "|       |",
        "|  AAab |",
        "|     b |",
        "|     B |",
        "|       |",
    ]
    mov = obtener_movimiento_ia("\n".join(filas), 'A', 500, 500, 2, "cut", 25)
    assert mov == "RIGHT"


def test_v10_inv_seguro_y_costo_choque():
    filas = ["|  AAAa  |", "|   bBB  |"]
    t_seguro = escanear_completo(filas, 'A', mi_inv=2)
    t_ultimo = escanear_completo(filas, 'A', mi_inv=1)
    assert t_seguro.inv_seguro and not t_ultimo.inv_seguro
    ctx_inv = construir_contexto(t_seguro, 10, 2, 100, 100, 1)
    ctx_fin = construir_contexto(t_ultimo, 10, 2, 100, 100, 1)
    assert costo_choque(ctx_inv) == CONFIG['CRASH_COST_INV']
    assert costo_choque(ctx_fin) == CONFIG['CRASH_COST']


def test_v9_disparo_cuando_conviene():
    filas = [
        "|          |",
        "| aaA  bbbb|",
        "|         B|",
        "|     b    |",
        "|          |",
    ]
    accion, dir_tiro = obtener_accion_ia(
        "\n".join(filas), 'A', 8000, 1000, 6, "shoot-1", 0, 0
    )
    assert accion == "shoot"
    assert dir_tiro == "RIGHT"


def test_v9_no_dispara_si_rival_invencible_o_muro():
    filas = [
        "|          |",
        "| aaA #bbbb|",
        "|         B|",
        "|     b    |",
    ]
    accion, _ = obtener_accion_ia(
        "\n".join(filas), 'A', 8000, 1000, 6, "shoot-2", 0, 0
    )
    assert accion == "move"


def _zonas_prohibidas_bombas(bombas):
    prohibidas = set()
    for ch, bx, by in bombas:
        r = 2 if ch == '\U0001F4A3' else 1
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                prohibidas.add((bx + dx, by + dy))
    return prohibidas


def _render_serpiente(grid, cuerpo, letra, inv):
    cab_ch = letra.lower() if inv > 0 else letra
    cue_ch = letra if inv > 0 else letra.lower()
    grid[cuerpo[0][1]][cuerpo[0][0]] = cab_ch
    for x, y in cuerpo[1:]:
        grid[y][x] = cue_ch


def _crear_estado_simulacion(seed):
    rng = random.Random(seed)
    ancho, alto = 22, 20
    serp_a = [(4, 5), (3, 5), (2, 5)]
    serp_b = [(17, 14), (18, 14), (19, 14)]
    muros = {(10, y) for y in range(7, 13)}
    muros_ch = [('#', 10, y) for y in range(7, 13)]
    interior = {
        (x, y) for x in range(1, ancho - 1) for y in range(alto)
    } - muros
    bombas = [('\U0001F4A3', 10, 3), ('\U0001F9E8', 10, 16)]
    prohib = _zonas_prohibidas_bombas(bombas) | muros | set(serp_a + serp_b)
    return {
        "rng": rng, "ancho": ancho, "alto": alto,
        "a": serp_a, "b": serp_b, "muros": muros, "muros_ch": muros_ch,
        "interior": interior, "bombas": bombas, "prohib": prohib,
        "pts_a": 0, "pts_b": 0, "mult_a": 1, "mult_b": 1,
        "inv_a": 0, "inv_b": 0, "digito_actual": 1, "items": {},
    }


def _celdas_libres(est):
    ocupadas = set(est["a"] + est["b"]) | est["prohib"] | set(est["items"])
    return [
        (x, y)
        for y in range(1, est["alto"] - 1)
        for x in range(1, est["ancho"] - 1)
        if (x, y) not in ocupadas
    ]


def _asegurar_simbolo(est, simbolo, libres):
    if simbolo not in est["items"].values() and libres:
        pos = est["rng"].choice(libres)
        libres.remove(pos)
        est["items"][pos] = simbolo


def _poblar_items(est):
    libres = _celdas_libres(est)
    for offset in range(5):
        d = str((est["digito_actual"] - 1 + offset) % 9 + 1)
        _asegurar_simbolo(est, d, libres)
    _asegurar_simbolo(est, ESTRELLA, libres)
    _asegurar_simbolo(est, 'X', libres)


def _pintar_elementos(g, coleccion):
    for elem in coleccion:
        ch, x, y = elem
        g[y][x] = ch


def _crear_grilla_base(ancho, alto):
    g = [[' '] * ancho for _ in range(alto)]
    for y in range(alto):
        g[y][0] = g[y][-1] = '|'
    return g


def _pintar_mapa(g, mapa):
    for (x, y), ch in mapa.items():
        g[y][x] = ch


def _construir_board_str(est):
    _poblar_items(est)
    g = _crear_grilla_base(est["ancho"], est["alto"])
    _pintar_elementos(g, est["muros_ch"])
    _pintar_elementos(g, est["bombas"])
    _pintar_mapa(g, est["items"])
    _render_serpiente(g, est["a"], 'A', est["inv_a"])
    _render_serpiente(g, est["b"], 'B', est["inv_b"])
    return "\n".join(map("".join, g))


def _comer_digito_objetivo(est, pts_k, mult_k):
    obj_str = str(est["digito_actual"])
    est[pts_k] += est["digito_actual"] * 100 * est[mult_k]
    est["digito_actual"] = est["digito_actual"] % 9 + 1
    est["items"] = {k: v for k, v in est["items"].items() if v != obj_str}
    return True


def _aplicar_item_especial(est, item, pts_k, mult_k, inv_k):
    if item == 'X':
        est[pts_k] += 50
        est[mult_k] += 1
        return False
    if item == ESTRELLA:
        est[pts_k] += 100 * est[mult_k]
        est[inv_k] = 50
        return True
    if item and est[inv_k] == 0:
        est[pts_k] -= 500
    return False


def _aplicar_efectos_celda(est, clave_jug, sig):
    pts_k = f"pts_{clave_jug}"
    mult_k = f"mult_{clave_jug}"
    inv_k = f"inv_{clave_jug}"
    est[pts_k] += 1
    item = est["items"].pop(sig, None)
    if item == str(est["digito_actual"]):
        return _comer_digito_objetivo(est, pts_k, mult_k)
    return _aplicar_item_especial(est, item, pts_k, mult_k, inv_k)


def _es_choque_sim(est, sig, ocupadas):
    return sig not in est["interior"] or sig in ocupadas


def _penalizar_explosion_o_choque(est, pts_k, inv_k):
    if est[inv_k] == 0:
        est[pts_k] = 0 if est[pts_k] > 0 else est[pts_k] - 500


def _procesar_choque_sim(est, clave_jug, cuerpo, pts_k, inv_k):
    _penalizar_explosion_o_choque(est, pts_k, inv_k)
    if est[inv_k] == 0:
        est[clave_jug] = cuerpo[:3]


def _avanzar_cuerpo(cuerpo, sig, crece):
    if crece:
        return [sig] + cuerpo
    return [sig] + cuerpo[:-1]


def _mover_serpiente(est, clave_jug, mov):
    cuerpo = est[clave_jug]
    ocupadas = set(est["a"] + est["b"])
    dx, dy = VEC_DIR[mov]
    sig = (cuerpo[0][0] + dx, cuerpo[0][1] + dy)
    inv_k, pts_k = f"inv_{clave_jug}", f"pts_{clave_jug}"
    if _es_choque_sim(est, sig, ocupadas):
        _procesar_choque_sim(est, clave_jug, cuerpo, pts_k, inv_k)
        return
    crece = _aplicar_efectos_celda(est, clave_jug, sig)
    if sig in _zonas_prohibidas_bombas(est["bombas"]):
        _penalizar_explosion_o_choque(est, pts_k, inv_k)
    est[clave_jug] = _avanzar_cuerpo(cuerpo, sig, crece)
    est[inv_k] = max(0, est[inv_k] - 1)


def simular_partida_bot_vs_bot(seed, rondas=60):
    est = _crear_estado_simulacion(seed)
    for _ in range(rondas):
        b_a = _construir_board_str(est)
        mov_a = obtener_movimiento_ia(
            b_a, 'A', est["pts_a"], est["pts_b"],
            est["mult_a"], f"s{seed}", est["inv_a"], est["inv_b"],
        )
        _mover_serpiente(est, "a", mov_a)

        b_b = _construir_board_str(est)
        mov_b = obtener_movimiento_ia(
            b_b, 'B', est["pts_b"], est["pts_a"],
            est["mult_b"], f"s{seed}", est["inv_b"], est["inv_a"],
        )
        _mover_serpiente(est, "b", mov_b)
    return est["pts_a"], est["pts_b"]


@pytest.mark.parametrize("partida", [1, 2, 3, 4, 5])
def test_cinco_peleas_bot_vs_bot_sin_puntaje_negativo(partida):
    """El bot pelea contra si mismo 5 veces sin dar puntaje negativo."""
    pts_a, pts_b = simular_partida_bot_vs_bot(seed=partida * 17, rondas=60)
    assert pts_a >= 0, f"Partida {partida}: Bot A termino en {pts_a}"
    assert pts_b >= 0, f"Partida {partida}: Bot B termino en {pts_b}"
    assert pts_a + pts_b > 0
