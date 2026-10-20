"""
Regresiones sacadas de las partidas reales (my_match 5, 6 y 7).

Cada fixture es un tablero donde la v3 hizo algo que le costó puntos:
  - choque       -> borra el puntaje, pierde la cola y se la regala al rival
  - bomba        -> la explosión borra el puntaje
  - digito_malo  -> -500

La propiedad que se verifica: el bot elige SIEMPRE la mejor categoría disponible
(ok < digito_malo < bomba < choque), usando un motor de reglas independiente del bot.
"""
import json
from pathlib import Path

import pytest

from run_v3 import (
    clasificar_comida,
    escanear_completo,
    mapear_espacios,
    calcular_peligros,
    obtener_movimiento_ia,
)

FIXTURES = json.loads((Path(__file__).parent / "fixtures_logs.json").read_text(encoding="utf-8"))
DIRS = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}
BOMBA_GRANDE, BOMBA_CHICA = "\U0001F4A3", "\U0001F9E8"
GRAVEDAD = {"ok": 0, "digito_malo": 1, "bomba": 2, "choque": 3}


def _obtener_cabeza(g, lado):
    return next((x, y) for y, fila in enumerate(g) for x, c in enumerate(fila) if c == lado)

def _es_fuera_de_limites_o_choque(g, nx, ny, ancho, alto):
    if not (0 <= nx < ancho and 0 <= ny < alto):
        return True
    return g[ny][nx] in "|#-ABab"

def _obtener_objetivo_comida(g):
    digitos = {int(c) for fila in g for c in fila if c in "123456789"}
    for d in digitos:
        if ((d - 2) % 9 + 1) not in digitos:
            return d
    return None

def _es_digito_erroneo(g, celda):
    if celda not in "123456789":
        return False
    objetivo = _obtener_objetivo_comida(g)
    return objetivo is None or int(celda) != objetivo

def _en_rango_de_bomba(celda, x, y, nx, ny):
    distancia = max(abs(x - nx), abs(y - ny))
    if celda == BOMBA_GRANDE and distancia <= 2:
        return True
    return celda == BOMBA_CHICA and distancia <= 1

def _es_zona_bomba(g, nx, ny):
    for y, fila in enumerate(g):
        for x, celda in enumerate(fila):
            if celda in (BOMBA_GRANDE, BOMBA_CHICA):
                if _en_rango_de_bomba(celda, x, y, nx, ny):
                    return True
    return False

def clasificar_destino(board, lado, mov):
    """Reglas del juego (v8) aplicadas a un movimiento, refactorizado a Clase A."""
    g = board.strip("\n").split("\n")
    alto, ancho = len(g), len(g[0])

    cabeza = _obtener_cabeza(g, lado)
    nx, ny = cabeza[0] + DIRS[mov][0], cabeza[1] + DIRS[mov][1]

    if _es_fuera_de_limites_o_choque(g, nx, ny, ancho, alto):
        return "choque"
        
    celda = g[ny][nx]
    
    if _es_digito_erroneo(g, celda):
        return "digito_malo"
        
    if _es_zona_bomba(g, nx, ny):
        return "bomba"
        
    return "ok"
@pytest.mark.parametrize(
    "fx", FIXTURES,
    ids=[f"p{f['partida']}-t{f['turno_global']}-{f['que_paso']}" for f in FIXTURES],
)
def test_no_repite_el_error_de_la_v3(fx):
    mov = obtener_movimiento_ia(fx["board"], fx["lado"], fx["puntaje"], fx["rival"], fx["mult"], "log")
    clases = {m: clasificar_destino(fx["board"], fx["lado"], m) for m in DIRS}
    mejor = min(clases.values(), key=GRAVEDAD.get)
    assert clases[mov] == mejor, f"eligió {mov} ({clases[mov]}) habiendo {mejor}: {clases}"


def _fixture(partida, puntaje):
    return next(f for f in FIXTURES if f["partida"] == partida and f["puntaje"] == puntaje)


def test_encerrado_prefiere_digito_malo_antes_que_chocar_partida5():
    """Perdió 8946 puntos y 8 segmentos chocando con su cuerpo cuando RIGHT sólo costaba -500."""
    fx = _fixture("5", 8946)
    assert obtener_movimiento_ia(fx["board"], fx["lado"], fx["puntaje"], fx["rival"], fx["mult"], "x") == "RIGHT"


def test_encerrado_no_repite_el_mismo_choque_partida6():
    """Espiral de -500 por turno (hasta -3000 y derrota) repitiendo el mismo choque."""
    fx = _fixture("6", 4365)
    assert obtener_movimiento_ia(fx["board"], fx["lado"], fx["puntaje"], fx["rival"], fx["mult"], "x") == "RIGHT"


def test_callejon_prefiere_movimiento_legal_a_la_pared():
    tablero = "\n".join(["|||||", "|A.B|", "|||||"])
    assert obtener_movimiento_ia(tablero, "A", 0, 0, 1, "t") == "RIGHT"


def test_todas_las_copias_de_un_digito_son_conocidas():
    raw = [("3", 1, 1), ("3", 5, 5), ("3", 9, 2), ("4", 2, 2), ("4", 7, 7)]
    buena, mala, valor = clasificar_comida(raw)
    assert sorted(buena) == [(1, 1), (5, 5), (9, 2)]
    assert mala == {(2, 2), (7, 7)}
    assert valor == 3


def _tablero_vacio(ancho=13, alto=9):
    g = [[" "] * ancho for _ in range(alto)]
    for y in range(alto):
        g[y][0] = g[y][-1] = "|"
    return g


def test_zonas_de_bomba_exactas():
    g = _tablero_vacio()
    g[3][4] = BOMBA_GRANDE  
    g[7][10] = BOMBA_CHICA  
    g[8][7] = "A"
    t = escanear_completo(["".join(f) for f in g], "A")
    assert len(t.zonas_bomba) == 25 + 9
    assert (6, 5) in t.zonas_bomba and (7, 3) not in t.zonas_bomba    
    assert (9, 6) in t.zonas_bomba and (8, 6) not in t.zonas_bomba      


def test_comida_de_cola_solo_la_de_mi_letra():
    g = _tablero_vacio()
    g[7][2], g[7][4], g[8][7] = "\u24b6", "\u24b7", "A"   
    t = escanear_completo(["".join(f) for f in g], "A")
    assert (2, 7) in t.comida         
    assert (4, 7) not in t.comida      


def test_espacio_del_enemigo_no_se_calcula_con_sus_propios_vecinos_bloqueados():
    filas = ["...........", "...........", "....B......", "...........", "......A....", "..........."]
    t = escanear_completo(filas, "A")
    obs = set(t.cuerpo) | t.cuerp_en | t.paredes
    con_zonas = mapear_espacios(t.cab_en, obs, calcular_peligros(t.cab_en, 11, 6), 11, 6)
    sin_zonas = mapear_espacios(t.cab_en, obs, frozenset(), 11, 6)
    assert con_zonas[(4, 2)] == 1    
    assert sin_zonas[(4, 2)] == 66
