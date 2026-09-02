import sys
import copy
import random
from collections import deque

import run_v3
from run_v3 import obtener_movimiento_ia

MAX_TURNS = 200
DEFAULT_MATCHES = 100

class Snake:
    def __init__(self, head, body, side_char):
        self.head = head
        self.body = deque(body)  
        self.side = side_char  
        self.alive = True
        self.score = 0

    def coords_set(self):
        s = set(self.body)
        s.add(self.head)
        return s

def make_empty_board(w, h):
    return [['.' for _ in range(w)] for _ in range(h)]

def board_to_string(board):
    return '\n'.join(''.join(row) for row in board)

def place_apple(board, snakes, w, h):
    empties = [(x, y) for y in range(h) for x in range(w) if board[y][x] == '.']
    if not empties: return None
    pos = random.choice(empties)
    board[pos[1]][pos[0]] = '*'
    return pos

def render_board(board, snakes):
    b = copy.deepcopy(board)
    for s in snakes:
        if s.alive:
            b[s.head[1]][s.head[0]] = s.side
            for bx, by in s.body:
                b[by][bx] = s.side.lower()
    return b

def is_crash(pos, snake_self, occupied, w, h):
    if not pos: return True
    if not (0 <= pos[0] < w and 0 <= pos[1] < h): return True
    return pos in occupied and pos != snake_self.body[-1]

def get_moves(board_str, snake_a, snake_b, config_a, config_b):
    orig_config = run_v3.CONFIG
    try:
        if config_a is not None: run_v3.CONFIG = config_a
        move_a = obtener_movimiento_ia(board_str, 'A', snake_a.score, snake_b.score)
        if config_b is not None: run_v3.CONFIG = config_b
        move_b = obtener_movimiento_ia(board_str, 'B', snake_b.score, snake_a.score)
    finally:
        run_v3.CONFIG = orig_config
    return move_a, move_b

def update_snake(s, npos, board, snakes, w, h):
    if not s.alive: return
    s.body.appendleft(s.head)
    s.head = npos
    if board[npos[1]][npos[0]] == '*':
        s.score += run_v3.CONFIG['APPLE_VALUE']
        board[npos[1]][npos[0]] = '.'
        if random.random() < 0.7: place_apple(board, snakes, w, h)
    elif s.body:
        s.body.pop()
    s.score += run_v3.CONFIG['TURN_POINT']

def apply_crash_penalty(dead_snake, other_snake):
    dead_snake.alive = False
    dead_snake.score -= 500
    if other_snake.alive:
        other_snake.score += 1000

def process_turn(snake_a, snake_b, move_a, move_b, board, snakes, w, h):
    D = {'UP': (0, -1), 'DOWN': (0, 1), 'LEFT': (-1, 0), 'RIGHT': (1, 0)}
    na = (snake_a.head[0] + D.get(move_a, (0, -1))[0], snake_a.head[1] + D.get(move_a, (0, -1))[1])
    nb = (snake_b.head[0] + D.get(move_b, (0, -1))[0], snake_b.head[1] + D.get(move_b, (0, -1))[1])

    occupied = snake_a.coords_set() | snake_b.coords_set()
    crash_a = is_crash(na, snake_a, occupied, w, h)
    crash_b = is_crash(nb, snake_b, occupied, w, h)

    if na == nb and na is not None:
        crash_a = crash_b = True

    if crash_a: apply_crash_penalty(snake_a, snake_b)
    if crash_b: apply_crash_penalty(snake_b, snake_a)

    update_snake(snake_a, na, board, snakes, w, h)
    update_snake(snake_b, nb, board, snakes, w, h)

def determine_winner(snake_a, snake_b):
    if snake_a.alive != snake_b.alive:
        return 'A' if snake_a.alive else 'B'
    return 'A' if snake_a.score >= snake_b.score else 'B'

def setup_simulation(seed):
    if seed is not None: random.seed(seed)    
    w = random.randint(12, 18)
    h = random.randint(12, 18)
    board = make_empty_board(w, h)
    
    s_a = Snake((3, h // 2), [(2, h // 2), (1, h // 2)], 'A')
    s_b = Snake((w - 4, h // 2), [(w - 3, h // 2), (w - 2, h // 2)], 'B')
    
    for _ in range(3): place_apple(board, [s_a, s_b], w, h)
    return board, s_a, s_b, w, h

def simulation_running(turns, snake_a, snake_b):
    if turns >= MAX_TURNS: return False
    if not snake_a.alive: return False
    return snake_b.alive

def simulate_match(config_a=None, config_b=None, seed=None):
    board, snake_a, snake_b, w, h = setup_simulation(seed)
    turns = 0
    
    while simulation_running(turns, snake_a, snake_b):
        turns += 1
        board_str = board_to_string(render_board(board, [snake_a, snake_b]))
        move_a, move_b = get_moves(board_str, snake_a, snake_b, config_a, config_b)
        process_turn(snake_a, snake_b, move_a, move_b, board, [snake_a, snake_b], w, h)

    return {
        'winner': determine_winner(snake_a, snake_b),
        'score_a': snake_a.score,
        'score_b': snake_b.score,
        'turns': turns,
    }

def run_batch(n_matches=DEFAULT_MATCHES):
    stats = {'A_wins': 0, 'B_wins': 0, 'sum_score_a': 0, 'sum_score_b': 0}
    for i in range(n_matches):
        r = simulate_match()
        if r['winner'] == 'A': stats['A_wins'] += 1
        else: stats['B_wins'] += 1
        stats['sum_score_a'] += r['score_a']
        stats['sum_score_b'] += r['score_b']
        if (i+1) % 10 == 0:
            print(f"Completadas {i+1}/{n_matches} partidas")
            
    print('\n--- Resultados del Batch ---')
    print(f"Victorias IA A: {stats['A_wins']}  |  Victorias IA B: {stats['B_wins']}")
    print(f"Puntaje prom A: {stats['sum_score_a']/n_matches:.2f}  |  Puntaje prom B: {stats['sum_score_b']/n_matches:.2f}")

if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_MATCHES
    print('Corriendo simulador con CONFIG:', run_v3.CONFIG)
    run_batch(n)
