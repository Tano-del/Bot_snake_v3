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

def obtener_movimiento_ia(board_string, mi_lado, mi_puntaje=0, rival_puntaje=0, game_id=None):
    filas = board_string.strip('\n').split('\n')
    
    cuerpo_propio = []
    cuerpos_enemigos = set()
    cabezas_enemigas = []
    comida = []
    paredes = set()
    cabeza = None

    mi_cabeza_char = mi_lado
    mi_cuerpo_char = mi_lado.lower()
    
    for y, fila in enumerate(filas):
        for x, char in enumerate(fila):
            if char == mi_cabeza_char: cabeza = (x, y)
            elif char == mi_cuerpo_char: cuerpo_propio.append((x, y))
            elif char in ['A', 'B'] and char != mi_cabeza_char:
                cabezas_enemigas.append((x, y))
                cuerpos_enemigos.add((x, y))
            elif char in ['a', 'b'] and char != mi_cuerpo_char:
                cuerpos_enemigos.add((x, y))
            elif char == '*': comida.append((x, y))
            elif char in ['|', '-']: paredes.add((x, y))

    if not cabeza: return "UP"

    ancho = len(filas[0]) if filas else 0
    alto = len(filas)
    centro_x, centro_y = ancho // 2, alto // 2 
    
    obstaculos_totales = set(cuerpo_propio) | cuerpos_enemigos | paredes

    zonas_peligro = set()
    for cx, cy in cabezas_enemigas:
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < ancho and 0 <= ny < alto:
                zonas_peligro.add((nx, ny))

    largo_serpiente = len(cuerpo_propio) + 1 
    espacio_seguro_minimo = largo_serpiente + 2 
    movimientos = [(0, -1, "UP"), (0, 1, "DOWN"), (-1, 0, "LEFT"), (1, 0, "RIGHT")]
    
    distancia_enemigo_manzana = {}
    for manzana in comida:
        min_dist = 9999
        for cab_en in cabezas_enemigas:
            dist = astar_distancia(cab_en, manzana, obstaculos_totales, ancho, alto)
            if dist < min_dist: min_dist = dist
        distancia_enemigo_manzana[manzana] = min_dist

    cola = encontrar_cola(cuerpo_propio, cabeza)

    espacio_enemigo_before = {}
    for cab_en in cabezas_enemigas:
        espacio_enemigo_before[cab_en] = calcular_espacio_libre(cab_en, obstaculos_totales, zonas_peligro, ancho, alto, 1000)

    def distancia_a_cabeza_enemiga(pos):
        if not cabezas_enemigas:
            return 9999
        return min(abs(pos[0] - cx) + abs(pos[1] - cy) for cx, cy in cabezas_enemigas)

    mejor_accion = "UP"
    max_puntaje = -999999
    
    for dx, dy, accion in movimientos:
        nx, ny = cabeza[0] + dx, cabeza[1] + dy
        siguiente_pos = (nx, ny)
        
        if not (0 <= nx < ancho and 0 <= ny < alto):
            continue
        if siguiente_pos in obstaculos_totales:
            continue
        
        puntaje_movimiento = 0
        
        if siguiente_pos in zonas_peligro:
            puntaje_movimiento -= 1400
            
        espacio = calcular_espacio_libre(siguiente_pos, obstaculos_totales, zonas_peligro, ancho, alto, 100)
        
        if espacio < espacio_seguro_minimo:
            puntaje_movimiento -= 3200
        else:
            puntaje_movimiento += espacio * 8

        if cola and not hay_camino_a_objetivo(siguiente_pos, cola, obstaculos_totales, ancho, alto):
            puntaje_movimiento -= 4200

        obstaculos_sim = set(obstaculos_totales)
        obstaculos_sim.add(siguiente_pos)

        

        es_borde = (nx == 0 or nx == ancho - 1 or ny == 0 or ny == alto - 1)
        
        casilleros_libres_alrededor = 0
        for vx, vy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            vecino_nx, vecino_ny = nx + vx, ny + vy
            if 0 <= vecino_nx < ancho and 0 <= vecino_ny < alto:
                if (vecino_nx, vecino_ny) not in obstaculos_sim:
                    casilleros_libres_alrededor += 1
                    
        es_pasillo = casilleros_libres_alrededor <= 2

        if (es_borde or es_pasillo) and cabezas_enemigas:
            dist_enemigo = distancia_a_cabeza_enemiga(siguiente_pos)
            if dist_enemigo <= 4:
                puntaje_movimiento -= 50000  
                
        self_area = calcular_espacio_libre(siguiente_pos, obstaculos_sim, zonas_peligro, ancho, alto, 1000)
        if self_area < espacio_seguro_minimo:
            puntaje_movimiento -= 1800
        else:
            puntaje_movimiento += self_area * 5

        espacio_reducido_total = 0
        enemigo_posible_asesinato = False
        est_len_enemigo = max(3, len(cuerpos_enemigos) // max(1, len(cabezas_enemigas)))
        for cab_en, antes in espacio_enemigo_before.items():
            despues = calcular_espacio_libre(cab_en, obstaculos_sim, zonas_peligro, ancho, alto, 1000)
            espacio_reducido_total += max(0, antes - despues)
            if despues < est_len_enemigo + 2:
                enemigo_posible_asesinato = True

        if espacio_reducido_total > 0:
            puntaje_movimiento += espacio_reducido_total * CONFIG['SPACE_KILL_FACTOR']
        if enemigo_posible_asesinato:
            puntaje_movimiento += CONFIG['KILL_VALUE'] * CONFIG['KILL_MULT'] + 300

        if siguiente_pos in comida:
            puntaje_movimiento += CONFIG['APPLE_VALUE'] * CONFIG['APPLE_MULT']

        lider_diario = mi_puntaje - rival_puntaje
        modo_tortuga = lider_diario >= CONFIG['TURTLE_THRESHOLD']
        if modo_tortuga:
            puntaje_movimiento -= 700 * (1 if siguiente_pos in zonas_peligro else 0)
            if siguiente_pos in comida:
                puntaje_movimiento -= CONFIG['APPLE_VALUE'] * 2
            puntaje_movimiento += self_area * 3

        dist_enemigo_cabeza = distancia_a_cabeza_enemiga(siguiente_pos)
        if dist_enemigo_cabeza == 0:
            puntaje_movimiento -= 6000
        elif dist_enemigo_cabeza == 1 and not enemigo_posible_asesinato:
            puntaje_movimiento -= 1200
        else:
            puntaje_movimiento += dist_enemigo_cabeza * 5
            
        dist_manzana_cercana = 9999
        objetivo = None
        
        for manzana in comida:
            dist = astar_distancia(siguiente_pos, manzana, obstaculos_totales, ancho, alto)
            if dist < dist_manzana_cercana:
                dist_manzana_cercana = dist
                objetivo = manzana
                
        if objetivo:
            dist_enemigo = distancia_enemigo_manzana.get(objetivo, 9999)
            if dist_manzana_cercana < dist_enemigo:
                puntaje_movimiento += max(0, 4000 - dist_manzana_cercana * 60)
            elif dist_manzana_cercana == dist_enemigo:
                puntaje_movimiento += max(0, 2000 - dist_manzana_cercana * 30)
            else:
                puntaje_movimiento -= 1000 
                dist_al_centro = abs(siguiente_pos[0] - centro_x) + abs(siguiente_pos[1] - centro_y)
                puntaje_movimiento += max(0, 200 - dist_al_centro * 8)
            puntaje_movimiento += max(0, 1500 - dist_manzana_cercana * 40)
        else:
            dist_al_centro = abs(siguiente_pos[0] - centro_x) + abs(siguiente_pos[1] - centro_y)
            puntaje_movimiento += espacio * 3
            puntaje_movimiento -= dist_al_centro * 3

        if puntaje_movimiento > max_puntaje:
            max_puntaje = puntaje_movimiento
            mejor_accion = accion

    return mejor_accion


async def send(websocket, action, data):
    message = json.dumps({"action": action, "data": data})
    print(f"> Enviando: {message}")
    await websocket.send(message)

async def process_event(websocket, message_str):
    print(f"< Recibido: {message_str[:150]}...")
    try:
        message = json.loads(message_str)
        event = message.get("event")
        data = message.get("data", {})

        if event == "challenge":
            challenge_id = data.get("challenge_id")
            await send(websocket, "accept_challenge", {"challenge_id": challenge_id})

        elif event == "your_turn":
            game_id = data.get("game_id")
            turn_token = data.get("turn_token")
            board_string = data.get("board")
            side = data.get("side") 
            
            jugador_1 = data.get("player_1", "Jugador 1")
            puntaje_1 = data.get("score_1", 0)
            jugador_2 = data.get("player_2", "Jugador 2")
            puntaje_2 = data.get("score_2", 0)

            marcador_texto = f"{jugador_1}: {puntaje_1} pts  |  {jugador_2}: {puntaje_2} pts"

            with games_lock:
                if game_id in active_games and active_games[game_id].get("game_over"):
                    return 

                active_games[game_id] = {
                    "tablero": board_string,
                    "marcador": marcador_texto,
                    "side": side,
                    "game_over": False
                }
            
            if side == 'A':
                mi_puntaje = puntaje_1
                rival_puntaje = puntaje_2
            else:
                mi_puntaje = puntaje_2
                rival_puntaje = puntaje_1

            movimiento = obtener_movimiento_ia(board_string, side, mi_puntaje, rival_puntaje, game_id)
            
            await send(websocket, "move", {
                "game_id": game_id,
                "turn_token": turn_token,
                "direction": movimiento 
            })

        elif event == "game_over":
            game_id = data.get("game_id")
            print(f"\n--- [!] Partida {game_id} terminada ---\n")
            
            with games_lock:
                if game_id in active_games:
                    active_games[game_id]["game_over"] = True
                    active_games[game_id]["marcador"] = f"GAME OVER | {active_games[game_id]['marcador']}"
            
        elif event in ["list_users", "update_user_list"]:
            pass 
            
    except json.JSONDecodeError:
        print("[X] Error: El servidor no envió un JSON válido.")
    except Exception as e:
        print(f"[X] Error procesando el evento: {e}")

async def play(websocket):
    async for message in websocket:
        await process_event(websocket, message)

async def start(auth_token):
    uri = f"wss://codechallenge-server.up.railway.app:443/ws?token={auth_token}"
    
    while True:
        try:
            print(f"\n[*] Conectando al servidor con V3 parcheada (Anti-Pinning)...")
            async with websockets.connect(uri) as websocket:
                print("[*] ¡Conexión establecida exitosamente!")
                await play(websocket)
        except websockets.ConnectionClosed:
            print("[!] Conexión cerrada. Reintentando en 3 segundos...")
            await asyncio.sleep(3)
        except Exception as e:
            print(f"[X] Error de conexión: {e}. Reintentando en 3 segundos...")
            await asyncio.sleep(3)

if __name__ == "__main__":
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
        target=run_asyncio_client,
        daemon=True,
        name="WebSocketClient"
    )
    hilo_websocket.start()
    
    try:
        iniciar_interfaz_multitab(get_all_games)
    except KeyboardInterrupt:
        print("\n[*] Interfaz detenida manualmente.")
    finally:
        print("\n[*] Saliendo...")


