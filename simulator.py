from collections import deque
import random
import sys
import copy

import run_v3
from run_v3 import obtener_movimiento_ia

BOARD_W = 15
BOARD_H = 15
MAX_TURNS = 200
DEFAULT_MATCHES = 100

def make_empty_board():
    return [['.' for _ in range(BOARD_W)] for _ in range(BOARD_H)]

def board_to_string(board):
    return '\n'.join(''.join(row) for row in board)

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

def place_apple(board, snakes):
    empties = [(x, y) for y in range(BOARD_H) for x in range(BOARD_W) if board[y][x] == '.']
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

def is_crash(pos, snake_self, occupied, board_w, board_h):
    if not pos: return True
    if not (0 <= pos[0] < board_w and 0 <= pos[1] < board_h): return True
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

def update_snake(s, npos, board, snakes):
    if not s.alive: return
    s.body.appendleft(s.head)
    s.head = npos
    if board[npos[1]][npos[0]] == '*':
        s.score += run_v3.CONFIG['APPLE_VALUE']
        board[npos[1]][npos[0]] = '.'
        if random.random() < 0.7: place_apple(board, snakes)
    elif s.body:
        s.body.pop()
    s.score += run_v3.CONFIG['TURN_POINT']

def apply_crash_penalty(dead_snake, other_snake):
    dead_snake.alive = False
    dead_snake.score -= 500
    if other_snake.alive:
        other_snake.score += 1000

def process_turn(snake_a, snake_b, move_a, move_b, board, snakes):
    D = {'UP': (0, -1), 'DOWN': (0, 1), 'LEFT': (-1, 0), 'RIGHT': (1, 0)}
    na = (snake_a.head[0] + D.get(move_a, (0, -1))[0], snake_a.head[1] + D.get(move_a, (0, -1))[1])
    nb = (snake_b.head[0] + D.get(move_b, (0, -1))[0], snake_b.head[1] + D.get(move_b, (0, -1))[1])

    occupied = snake_a.coords_set() | snake_b.coords_set()
    crash_a = is_crash(na, snake_a, occupied, BOARD_W, BOARD_H)
    crash_b = is_crash(nb, snake_b, occupied, BOARD_W, BOARD_H)

    if na == nb and na is not None:
        crash_a = crash_b = True

    if crash_a: apply_crash_penalty(snake_a, snake_b)
    if crash_b: apply_crash_penalty(snake_b, snake_a)

    update_snake(snake_a, na, board, snakes)
    update_snake(snake_b, nb, board, snakes)

def determine_winner(snake_a, snake_b):
    if snake_a.alive != snake_b.alive:
        return 'A' if snake_a.alive else 'B'
    return 'A' if snake_a.score >= snake_b.score else 'B'

def setup_simulation(seed):
    if seed is not None: random.seed(seed)
    board = make_empty_board()
    s_a = Snake((3, BOARD_H // 2), [(2, BOARD_H // 2), (1, BOARD_H // 2)], 'A')
    s_b = Snake((BOARD_W - 4, BOARD_H // 2), [(BOARD_W - 3, BOARD_H // 2), (BOARD_W - 2, BOARD_H // 2)], 'B')
    for _ in range(3): place_apple(board, [s_a, s_b])
    return board, s_a, s_b

def simulation_running(turns, snake_a, snake_b):
    if turns >= MAX_TURNS: return False
    if not snake_a.alive: return False
    return snake_b.alive

def simulate_match(config_a=None, config_b=None, seed=None):
    board, snake_a, snake_b = setup_simulation(seed)
    turns = 0
    
    while simulation_running(turns, snake_a, snake_b):
        turns += 1
        board_str = board_to_string(render_board(board, [snake_a, snake_b]))
        move_a, move_b = get_moves(board_str, snake_a, snake_b, config_a, config_b)
        process_turn(snake_a, snake_b, move_a, move_b, board, [snake_a, snake_b])

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
            print(f"Completed {i+1}/{n_matches} matches")
            
    print('--- Batch results ---')
    print(f"A wins: {stats['A_wins']}  |  B wins: {stats['B_wins']}")
    print(f"Avg score A: {stats['sum_score_a']/n_matches:.2f}  |  Avg score B: {stats['sum_score_b']/n_matches:.2f}")

if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_MATCHES
    print('Running simulator with CONFIG:', run_v3.CONFIG)
    run_batch(n)
