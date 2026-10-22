import random

WALL = -1
FREE = 0


class Maze:
    def __init__(self, rows=15, cols=15):
        self.rows = rows
        self.cols = cols
        self.grid = [[FREE] * cols for _ in range(rows)]
        self.start = (0, 0)
        self.goal = (rows - 1, cols - 1)

    # ------------------------------------------------------------------
    def in_bounds(self, r, c):
        return 0 <= r < self.rows and 0 <= c < self.cols

    def is_free(self, r, c):
        return self.in_bounds(r, c) and self.grid[r][c] == FREE

    def wall_count(self):
        return sum(1 for row in self.grid for v in row if v == WALL)

    # ------------------------------------------------------------------
    def toggle_wall(self, r, c):
        """Змінює прохідність клітинки. Старт і ціль завжди прохідні."""
        if not self.in_bounds(r, c) or (r, c) in (self.start, self.goal):
            return False
        self.grid[r][c] = FREE if self.grid[r][c] == WALL else WALL
        return True

    def set_start(self, r, c):
        if not self.in_bounds(r, c) or (r, c) == self.goal:
            return False
        self.start = (r, c)
        self.grid[r][c] = FREE
        return True

    def set_goal(self, r, c):
        if not self.in_bounds(r, c) or (r, c) == self.start:
            return False
        self.goal = (r, c)
        self.grid[r][c] = FREE
        return True

    # ------------------------------------------------------------------
    def clear(self):
        self.grid = [[FREE] * self.cols for _ in range(self.rows)]

    def reset_points(self):
        """Старт у лівому верхньому куті, ціль у правому нижньому."""
        self.start = (0, 0)
        self.goal = (self.rows - 1, self.cols - 1)

    def generate(self, density_percent, seed):
        """Детермінована генерація: кожна клітинка стає стіною з імовірністю
        density_percent %, після чого старт і ціль примусово робляться
        прохідними. Випадкове число витрачається для кожної клітинки, тому
        лабіринт залежить лише від (rows, cols, density, seed), а не від
        положення старту й цілі."""
        rnd = random.Random(seed)
        for r in range(self.rows):
            for c in range(self.cols):
                self.grid[r][c] = WALL if rnd.random() < density_percent / 100.0 else FREE
        self.grid[self.start[0]][self.start[1]] = FREE
        self.grid[self.goal[0]][self.goal[1]] = FREE

    def resize(self, rows, cols):
        """Змінює розмір матриці зі збереженням наявної частини лабіринту;
        нові клітинки прохідні. Старт і ціль, що вийшли за межі,
        переносяться до кутів."""
        new_grid = [[FREE] * cols for _ in range(rows)]
        for r in range(min(rows, self.rows)):
            for c in range(min(cols, self.cols)):
                new_grid[r][c] = self.grid[r][c]
        self.rows, self.cols, self.grid = rows, cols, new_grid
        if not self.in_bounds(*self.start):
            self.start = (0, 0)
        if not self.in_bounds(*self.goal) or self.goal == self.start:
            self.goal = (rows - 1, cols - 1)
        self.grid[self.start[0]][self.start[1]] = FREE
        self.grid[self.goal[0]][self.goal[1]] = FREE