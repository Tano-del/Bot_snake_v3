
from collections import deque
import random
import sys
import copy

import run_v3
from run_v3 import obtener_movimiento_ia

# parametros simulacion
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
    empties = []
    for y in range(BOARD_H):
        for x in range(BOARD_W):
            if board[y][x] == '.':
                empties.append((x, y))
    if not empties:
        return None
    pos = random.choice(empties)
    board[pos[1]][pos[0]] = '*'
    return pos


def render_board(board, snakes):
    b = copy.deepcopy(board)
    for s in snakes:
        if s.alive:
            x, y = s.head
            b[y][x] = s.side
            for seg in s.body:
                bx, by = seg
                b[by][bx] = s.side.lower()
    return b


def simulate_match(config_a=None, config_b=None, seed=None):
    if seed is not None:
        random.seed(seed)

    board = make_empty_board()


    a_head = (3, BOARD_H // 2)
    b_head = (BOARD_W - 4, BOARD_H // 2)
    a_body = [(2, BOARD_H // 2), (1, BOARD_H // 2)]
    b_body = [(BOARD_W - 3, BOARD_H // 2), (BOARD_W - 2, BOARD_H // 2)]

    snake_a = Snake(a_head, a_body, 'A')
    snake_b = Snake(b_head, b_body, 'B')

    snakes = [snake_a, snake_b]

   
    for _ in range(3):
        place_apple(board, snakes)

    turns = 0
    while turns < MAX_TURNS and (snake_a.alive and snake_b.alive):
        turns += 1

        bstate = render_board(board, snakes)
        board_str = board_to_string(bstate)

        
        score_1 = snake_a.score
        score_2 = snake_b.score


        orig_config = run_v3.CONFIG
        try:
            if config_a is not None:
                run_v3.CONFIG = config_a
            move_a = obtener_movimiento_ia(board_str, 'A', score_1, score_2)

            if config_b is not None:
                run_v3.CONFIG = config_b
            move_b = obtener_movimiento_ia(board_str, 'B', score_2, score_1)
        finally:
            run_v3.CONFIG = orig_config

        D = {'UP': (0, -1), 'DOWN': (0, 1), 'LEFT': (-1, 0), 'RIGHT': (1, 0)}
        da = D.get(move_a, (0, -1))
        db = D.get(move_b, (0, -1))

        na = (snake_a.head[0] + da[0], snake_a.head[1] + da[1])
        nb = (snake_b.head[0] + db[0], snake_b.head[1] + db[1])

        occupied = set()
        for s in snakes:
            occupied |= s.coords_set()

        def is_crash(pos, snake_self):
            x, y = pos
            if x < 0 or x >= BOARD_W or y < 0 or y >= BOARD_H:
                return True

            if pos in occupied and pos != snake_self.body[-1]:
                return True
            return False

        crash_a = is_crash(na, snake_a)
        crash_b = is_crash(nb, snake_b)

        if na == nb and na != None:
            crash_a = crash_b = True

        
        if crash_a:
            snake_a.alive = False
            snake_a.score -= 500
            if snake_b.alive:
                snake_b.score += 1000
        if crash_b:
            snake_b.alive = False
            snake_b.score -= 500
            if snake_a.alive:
                snake_a.score += 1000

       
        for s, npos in [(snake_a, na), (snake_b, nb)]:
            if not s.alive:
                continue
            s.body.appendleft(s.head)
            s.head = npos
            x, y = npos
            if board[y][x] == '*':
                s.score += run_v3.CONFIG['APPLE_VALUE']
                board[y][x] = '.'
                if random.random() < 0.7:
                    place_apple(board, snakes)
            else:
                if s.body:
                    s.body.pop()
            s.score += run_v3.CONFIG['TURN_POINT']

    winner = None
    if snake_a.alive and not snake_b.alive:
        winner = 'A'
    elif snake_b.alive and not snake_a.alive:
        winner = 'B'
    elif snake_a.alive and snake_b.alive:
        winner = 'A' if snake_a.score >= snake_b.score else 'B'

    return {
        'winner': winner,
        'score_a': snake_a.score,
        'score_b': snake_b.score,
        'turns': turns,
    }


def run_batch(n_matches=DEFAULT_MATCHES):
    stats = {'A_wins': 0, 'B_wins': 0, 'sum_score_a': 0, 'sum_score_b': 0}
    for i in range(n_matches):
        r = simulate_match()
        if r['winner'] == 'A':
            stats['A_wins'] += 1
        else:
            stats['B_wins'] += 1
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


