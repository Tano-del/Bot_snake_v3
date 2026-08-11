import pytest
from run_v3 import (
    heuristica_manhattan,
    calcular_espacio_libre,
    encontrar_cola,
    hay_camino_a_objetivo,
    astar_distancia,
    obtener_movimiento_ia
)

def test_distancia_manhattan():
    assert heuristica_manhattan((0, 0), (3, 4)) == 7
    assert heuristica_manhattan((5, 5), (5, 5)) == 0

def test_calcular_espacio_libre():
    obstaculos = {(1, 0), (1, 1)}
    zonas_peligro = {(2, 2)}
    espacio = calcular_espacio_libre((0, 0), obstaculos, zonas_peligro, 5, 5, 100)
    assert espacio > 0
    assert espacio < 25

def test_encontrar_cola():
    cabeza = (2, 2)
    cuerpo = [(2, 3), (2, 4), (2, 5)]
    assert encontrar_cola(cuerpo, cabeza) == (2, 5)
    assert encontrar_cola([], cabeza) is None

def test_hay_camino_a_objetivo():
    obstaculos = {(1, 0), (1, 1), (1, 2), (1, 3), (1, 4)}
    assert not hay_camino_a_objetivo((0, 2), (3, 2), obstaculos, 5, 5)
    assert hay_camino_a_objetivo((0, 2), (3, 2), set(), 5, 5)

def test_astar_distancia():
    assert astar_distancia((0,0), (0,0), set(), 5, 5) == 0
    assert astar_distancia((0,0), (0,2), set(), 5, 5) == 2
    obstaculos = {(0, 1), (1, 0), (1, 1)}
    assert astar_distancia((0,0), (4,4), obstaculos, 5, 5) == 9999

def test_obtener_movimiento_ia():
    tablero = (
        ".......\n"
        "...*...\n"
        "..Aaa..\n"
        ".......\n"
        "..b....\n"
        "..B....\n"
        ".......\n"
    )
    movimiento = obtener_movimiento_ia(tablero, 'A', 0, 0, "test-id")
    assert movimiento in ["UP", "DOWN", "LEFT", "RIGHT"]
    
    movimiento_b = obtener_movimiento_ia(tablero, 'B', 0, 0, "test-id")
    assert movimiento_b in ["UP", "DOWN", "LEFT", "RIGHT"]
    
    movimiento_tortuga = obtener_movimiento_ia(tablero, 'A', 600, 0, "test-id")
    assert movimiento_tortuga in ["UP", "DOWN", "LEFT", "RIGHT"]

def test_obtener_movimiento_encerrado():
    tablero_encerrado = (
        "|A|....\n"
        "|-|....\n"
        ".......\n"
        ".......\n"
        ".......\n"
        ".......\n"
        ".......\n"
    )
    movimiento_encerrado = obtener_movimiento_ia(tablero_encerrado, 'A', 0, 0)
    assert movimiento_encerrado in ["UP", "DOWN", "LEFT", "RIGHT"]
