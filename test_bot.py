def heuristica_manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

def test_distancia_manhattan():
    punto_a = (0, 0)
    punto_b = (3, 4)
    assert heuristica_manhattan(punto_a, punto_b) == 7

def test_distancia_mismo_punto():
    punto = (5, 5)
    assert heuristica_manhattan(punto, punto) == 0
