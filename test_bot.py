import pytest
from run_v3 import (
    heuristica_manhattan,
    calcular_espacio_libre,
    encontrar_cola,
    hay_camino_a_objetivo,
    astar_distancia,
    analizar_tablero,
    calcular_peligros,
    es_pasillo,
    mapear_distancias,
    mapear_espacios,
    obtener_movimiento_ia
)


def test_distancia_manhattan():
    assert heuristica_manhattan((0, 0), (3, 4)) == 7
    assert heuristica_manhattan((5, 5), (5, 5)) == 0

def test_astar_distancia():
    assert astar_distancia((0,0), (0,0), set(), 5, 5) == 0
    assert astar_distancia((0,0), (0,2), set(), 5, 5) == 2
    obstaculos = {(0, 1), (1, 0), (1, 1)}
    assert astar_distancia((0,0), (4,4), obstaculos, 5, 5) == 9999

def test_calcular_espacio_libre():
    obstaculos = {(1, 0), (1, 1)}
    zonas_peligro = {(2, 2)}
    espacio = calcular_espacio_libre((0, 0), obstaculos, zonas_peligro, 5, 5, 100)
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
    assert encontrar_cola([], cabeza) is None

@pytest.mark.parametrize(
    "cabezas_enemigas, filas, columnas, peligros_esperados",
    [
        ([(2, 2)], 5, 5, {(1, 2), (3, 2), (2, 1), (2, 3)}),
        ([(0, 0)], 5, 5, {(0, 1), (1, 0)}),
        ([(4, 2)], 5, 5, {(3, 2), (4, 1), (4, 3)}),
        ([(0, 0), (4, 4)], 5, 5, {(0, 1), (1, 0), (3, 4), (4, 3)}),
        ([], 5, 5, set())
    ]
)
def test_calcular_peligros(cabezas_enemigas, filas, columnas, peligros_esperados):
    peligros = calcular_peligros(cabezas_enemigas, filas, columnas)
    assert set(peligros) == peligros_esperados

def test_analizar_tablero_jugador():
    tablero = ["|A|", "-*-", "bB."]
    cab, cuerpo, _, _, _, _ = analizar_tablero(tablero, 'A')
    
    assert cab == (1, 0)
    assert cuerpo == []

def test_analizar_tablero_enemigo():
    tablero = ["|A|", "-*-", "bB."]
    _, _, cab_en, cuerp_en, _, _ = analizar_tablero(tablero, 'A')
    
    assert cab_en == [(1, 2)]
    assert cuerp_en == [(0, 2), (1, 2)]

def test_analizar_tablero_entorno():
    tablero = ["|A|", "-*-", "bB."]
    _, _, _, _, comida, paredes = analizar_tablero(tablero, 'A')
    
    assert comida == [(1, 1)]
    assert len(paredes) == 4

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
    tablero_vacio = "\n".join([
        ".......",
        "...*...",
        "....B.."
    ])
    mov = obtener_movimiento_ia(tablero_vacio, 'A', 0, 0, "test-1")
    assert mov == "UP" 

def test_ia_movimiento_basico():
    tablero = "\n".join([
        ".......",
        "...*...",
        "..Aaa..",
        ".......",
        "..b....",
        "..B....",
        "......."
    ])
    mov_a = obtener_movimiento_ia(tablero, 'A', 0, 0, "test-2")
    assert mov_a in ["UP", "DOWN", "LEFT", "RIGHT"]
    
    mov_b = obtener_movimiento_ia(tablero, 'B', 0, 0, "test-2")
    assert mov_b in ["UP", "DOWN", "LEFT", "RIGHT"]

def test_ia_movimiento_encerrado():
    tablero = "\n".join([
        "|-|....",
        "|A|....",
        "|.B....",
        "......."
    ])
    mov = obtener_movimiento_ia(tablero, 'A', 0, 0, "test-3")
    assert mov == "DOWN"

def test_ia_ataque_ofensivo():
    tablero = "\n".join([
        ".......",
        "....A..",
        "....B.|",
        "....b.|",
        "....b.|"
    ])
    mov = obtener_movimiento_ia(tablero, 'A', 0, 0, "test-4")
    assert mov in ["LEFT", "RIGHT", "UP"]

def test_ia_modo_tortuga():
    tablero = "\n".join([
        ".......",
        "...*...",
        "..A....",
        ".......",
        "....B..",
        "......."
    ])
    mov = obtener_movimiento_ia(tablero, 'A', 600, 0, "test-5")
    assert mov in ["UP", "DOWN", "LEFT", "RIGHT"]

def test_ia_evitar_peligro():
    tablero = "\n".join([
        ".......",
        "..A....",
        "..B....",
        "......."
    ])
    mov = obtener_movimiento_ia(tablero, 'A', 0, 0, "test-6")
    assert mov in ["UP", "LEFT", "RIGHT"]
