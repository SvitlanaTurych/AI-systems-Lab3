import time

# вверх, вправо, вниз, вліво
ORTHOGONAL = [(-1, 0), (0, 1), (1, 0), (0, -1)]
# по діагоналях: вправо-вверх, вправо-вниз, вліво-вниз, вліво-вверх
DIAGONAL = [(-1, 1), (1, 1), (1, -1), (-1, -1)]

OPERATORS = {
    "4": ORTHOGONAL,
    "diag": DIAGONAL,
    "8": ORTHOGONAL + DIAGONAL,
}

OPERATOR_TITLES = {
    "4": "Up-Down-Left-Right (4)",
    "diag": "Diagonals (4)",
    "8": "Combined (8)",
}


class WaveSearch:
    """Покрокова реалізація хвильового пошуку. Один виклик step()
    розкриває весь поточний фронт хвилі (один «шар»)."""

    def __init__(self, maze, operator="4"):
        self.maze = maze
        self.operator = operator
        self.dirs = OPERATORS[operator]
        self.start = maze.start
        self.goal = maze.goal

        self.wave = {self.start: 0}      # клітинка -> номер хвилі
        self.front = [self.start]        # поточний фронт хвилі
        self.wave_number = 0             # кількість виконаних хвиль
        self.expanded_count = 0          # кількість розкритих клітинок
        self.path = []
        self.found = False
        self.finished = False
        self.elapsed = 0.0               # час роботи алгоритму, с

        if self.start == self.goal:
            self.path = [self.start]
            self.found = True
            self.finished = True

    def step(self):
        """Виконує одну хвилю. Повертає "expanded", "found" або "not_found"."""
        if self.finished:
            return "found" if self.found else "not_found"

        t0 = time.perf_counter()
        new_front = []
        reached = False
        k = self.wave_number + 1

        for (r, c) in self.front:
            self.expanded_count += 1
            for dr, dc in self.dirs:
                nr, nc = r + dr, c + dc
                if self.maze.is_free(nr, nc) and (nr, nc) not in self.wave:
                    self.wave[(nr, nc)] = k
                    new_front.append((nr, nc))
                    if (nr, nc) == self.goal:
                        reached = True
                        break
            if reached:
                break

        self.wave_number = k
        self.front = new_front

        if reached:
            self.path = self._backtrack()
            self.found = True
            self.finished = True
            result = "found"
        elif not new_front:
            self.finished = True
            result = "not_found"
        else:
            result = "expanded"

        self.elapsed += time.perf_counter() - t0
        return result

    def _backtrack(self):
        """Зворотний хід: від цілі до старту по спадних мітках хвилі."""
        cell = self.goal
        path = [cell]
        while cell != self.start:
            w = self.wave[cell]
            for dr, dc in self.dirs:
                nb = (cell[0] + dr, cell[1] + dc)
                if self.wave.get(nb) == w - 1:
                    cell = nb
                    break
            path.append(cell)
        path.reverse()
        return path

    @property
    def path_length(self):
        return len(self.path) - 1 if self.path else None


def run_full(maze, operator):
    """Виконує пошук повністю (без анімації) і повертає підсумок."""
    search = WaveSearch(maze, operator)
    while not search.finished:
        search.step()
    return {
        "operator": operator,
        "found": search.found,
        "path": search.path,
        "path_len": search.path_length,
        "waves": search.wave_number,
        "expanded": search.expanded_count,
        "labeled": len(search.wave),
        "time_ms": search.elapsed * 1000.0,
    }