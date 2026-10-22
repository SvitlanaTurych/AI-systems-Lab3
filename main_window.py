import csv
import os
import time
from datetime import datetime

from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QRectF
from PyQt5.QtGui import QPainter, QColor, QFont, QPen
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QLabel, QComboBox, QSpinBox, QSlider, QMessageBox, QScrollArea, QFrame,
    QDialog, QPlainTextEdit
)

from maze_model import Maze, WALL
from wave_search import WaveSearch, OPERATOR_TITLES, run_full

COLOR_WALL = QColor("#3A3A3A")
COLOR_FREE = QColor("#FFFFFF")
COLOR_WAVE = QColor("#87CEFA")    # позначена (розкрита) клітинка
COLOR_FRONT = QColor("#FFD700")   # поточний фронт хвилі
COLOR_PATH = QColor("#FFA500")    # знайдений шлях
COLOR_START = QColor("#2E8B57")
COLOR_GOAL = QColor("#DC143C")

RESULTS_CSV = "wave_results.csv"

class MazeWidget(QWidget):
    cellClicked = pyqtSignal(int, int)

    def __init__(self, maze):
        super().__init__()
        self.maze = maze
        self.search = None
        self.setMinimumSize(520, 520)

    def _geometry(self):
        m = 10
        cell = min((self.width() - 2 * m) / self.maze.cols,
                   (self.height() - 2 * m) / self.maze.rows)
        w, h = cell * self.maze.cols, cell * self.maze.rows
        return cell, (self.width() - w) / 2, (self.height() - h) / 2

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#F5F5F5"))
        cell, ox, oy = self._geometry()

        font = QFont("Arial")
        font.setPixelSize(max(8, int(cell * 0.38)))
        p.setFont(font)

        s = self.search
        wave = s.wave if s else {}
        front = set(s.front) if (s and not s.finished) else set()
        path = set(s.path) if s else set()

        for r in range(self.maze.rows):
            for c in range(self.maze.cols):
                rect = QRectF(ox + c * cell, oy + r * cell, cell, cell)
                pos = (r, c)
                if self.maze.grid[r][c] == WALL:
                    color = COLOR_WALL
                elif pos == self.maze.start:
                    color = COLOR_START
                elif pos == self.maze.goal:
                    color = COLOR_GOAL
                elif pos in path:
                    color = COLOR_PATH
                elif pos in front:
                    color = COLOR_FRONT
                elif pos in wave:
                    color = COLOR_WAVE
                else:
                    color = COLOR_FREE
                p.fillRect(rect, color)
                p.setPen(QPen(QColor("#9E9E9E"), 1))
                p.drawRect(rect)

                text = None
                if pos == self.maze.start:
                    text = "S"
                elif pos == self.maze.goal:
                    text = "G" if pos not in wave else str(wave[pos])
                elif pos in wave:
                    text = str(wave[pos])
                if text is not None and self.maze.grid[r][c] != WALL:
                    p.setPen(QColor("#FFFFFF") if pos in (self.maze.start, self.maze.goal)
                             else QColor("#000000"))
                    p.drawText(rect, Qt.AlignCenter, text)

    def mousePressEvent(self, event):
        cell, ox, oy = self._geometry()
        c = int((event.x() - ox) // cell)
        r = int((event.y() - oy) // cell)
        if self.maze.in_bounds(r, c):
            self.cellClicked.emit(r, c)


# ----------------------------------------------------------------------
#  Окреме вікно результатів
# ----------------------------------------------------------------------
class ResultDialog(QDialog):
    def __init__(self, parent, title, text):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(560, 360)
        lay = QVBoxLayout(self)
        box = QPlainTextEdit()
        box.setReadOnly(True)
        box.setPlainText(text)
        box.setFont(QFont("Consolas", 10))
        lay.addWidget(box)
        btn = QPushButton("OK")
        btn.clicked.connect(self.accept)
        lay.addWidget(btn)


# ----------------------------------------------------------------------
#  Головне вікно
# ----------------------------------------------------------------------
class WaveVisualization(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Wave search (хвильовий алгоритм у лабіринті)")
        self.resize(1250, 800)

        self.maze = Maze(15, 15)
        self.maze.generate(25, 1)
        self.search = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.search_step)

        self._build_ui()
        self._sync_spins()
        self._reset_info()

    # ------------------------------------------------------------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main = QHBoxLayout(central)

        panel = QWidget()
        pl = QVBoxLayout(panel)
        pl.setAlignment(Qt.AlignTop)

        def spin(lo, hi, val):
            s = QSpinBox()
            s.setRange(lo, hi)
            s.setValue(val)
            return s

        pl.addWidget(QLabel("Maze size: rows x columns"))
        self.rows_spin = spin(5, 30, 15)
        self.cols_spin = spin(5, 30, 15)
        pl.addWidget(self.rows_spin)
        pl.addWidget(self.cols_spin)
        b = QPushButton("Apply size")
        b.clicked.connect(self.apply_size)
        pl.addWidget(b)

        pl.addWidget(self._hline())
        pl.addWidget(QLabel("Wall density (%):"))
        self.density_spin = spin(0, 70, 25)
        pl.addWidget(self.density_spin)
        pl.addWidget(QLabel("Seed:"))
        self.seed_spin = spin(0, 9999, 1)
        pl.addWidget(self.seed_spin)
        b = QPushButton("Generate maze")
        b.clicked.connect(self.generate_maze)
        pl.addWidget(b)
        b = QPushButton("Clear walls")
        b.clicked.connect(self.clear_maze)
        pl.addWidget(b)

        pl.addWidget(self._hline())
        pl.addWidget(QLabel("Mouse click on maze does:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Toggle wall", "Set start", "Set goal"])
        pl.addWidget(self.mode_combo)

        pl.addWidget(QLabel("Start (row, col):"))
        self.srow, self.scol = spin(0, 29, 0), spin(0, 29, 0)
        pl.addWidget(self.srow)
        pl.addWidget(self.scol)
        pl.addWidget(QLabel("Goal (row, col):"))
        self.grow, self.gcol = spin(0, 29, 14), spin(0, 29, 14)
        pl.addWidget(self.grow)
        pl.addWidget(self.gcol)
        for s in (self.srow, self.scol, self.grow, self.gcol):
            s.valueChanged.connect(self._points_from_spins)

        pl.addWidget(self._hline())
        pl.addWidget(QLabel("Transition operator:"))
        self.op_combo = QComboBox()
        for key, title in OPERATOR_TITLES.items():
            self.op_combo.addItem(title, key)
        pl.addWidget(self.op_combo)

        self.start_btn = QPushButton("Start search")
        self.start_btn.clicked.connect(self.start_search)
        pl.addWidget(self.start_btn)
        b = QPushButton("Pause/Resume")
        b.clicked.connect(self.pause_resume)
        pl.addWidget(b)
        b = QPushButton("Reset colors")
        b.clicked.connect(self.reset_colors)
        pl.addWidget(b)
        b = QPushButton("Compare operators")
        b.clicked.connect(self.compare_operators)
        pl.addWidget(b)

        pl.addWidget(self._hline())
        self.wave_label = QLabel("Wave: 0")
        self.expanded_label = QLabel("Expanded cells: 0")
        pl.addWidget(self.wave_label)
        pl.addWidget(self.expanded_label)
        pl.addWidget(QLabel("Speed:"))
        self.speed = QSlider(Qt.Horizontal)
        self.speed.setRange(30, 1500)
        self.speed.setValue(300)
        self.speed.setInvertedAppearance(True)
        pl.addWidget(self.speed)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        pl.addWidget(self.status)

        scroll = QScrollArea()
        scroll.setWidget(panel)
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(300)
        main.addWidget(scroll)

        self.view = MazeWidget(self.maze)
        self.view.cellClicked.connect(self.on_cell_clicked)
        main.addWidget(self.view, 1)

    @staticmethod
    def _hline():
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        return line

    # ------------------------------------------------------------------
    def _sync_spins(self):
        """Підганяє межі та значення полів старту/цілі під лабіринт."""
        widgets = (self.srow, self.scol, self.grow, self.gcol)
        for w in widgets:
            w.blockSignals(True)
        self.srow.setRange(0, self.maze.rows - 1)
        self.grow.setRange(0, self.maze.rows - 1)
        self.scol.setRange(0, self.maze.cols - 1)
        self.gcol.setRange(0, self.maze.cols - 1)
        self.srow.setValue(self.maze.start[0])
        self.scol.setValue(self.maze.start[1])
        self.grow.setValue(self.maze.goal[0])
        self.gcol.setValue(self.maze.goal[1])
        for w in widgets:
            w.blockSignals(False)

    def _points_from_spins(self):
        ok_s = self.maze.set_start(self.srow.value(), self.scol.value())
        ok_g = self.maze.set_goal(self.grow.value(), self.gcol.value())
        if not (ok_s and ok_g):
            self.status.setText("Start and goal must be different cells")
        self._sync_spins()
        self._reset_search()
        self.view.update()

    def _reset_info(self):
        self.wave_label.setText("Wave: 0")
        self.expanded_label.setText("Expanded cells: 0")

    def _reset_search(self):
        self.timer.stop()
        self.search = None
        self.view.search = None
        self._reset_info()
        self.view.update()

    def _info(self):
        walls = self.maze.wall_count()
        total = self.maze.rows * self.maze.cols
        return f"{self.maze.rows}x{self.maze.cols}, walls={walls} ({100 * walls / total:.0f}%)"

    # ------------------------------------------------------------------
    #  Редагування лабіринту
    # ------------------------------------------------------------------
    def apply_size(self):
        self.maze.resize(self.rows_spin.value(), self.cols_spin.value())
        self._sync_spins()
        self._reset_search()
        self.status.setText(f"Size applied: {self._info()}")

    def generate_maze(self):
        self.maze.resize(self.rows_spin.value(), self.cols_spin.value())
        self.maze.reset_points()          # старт (0,0), ціль (rows-1, cols-1)
        self.maze.generate(self.density_spin.value(), self.seed_spin.value())
        self._sync_spins()
        self._reset_search()
        self.status.setText(f"Maze generated (seed={self.seed_spin.value()}): {self._info()}")

    def clear_maze(self):
        self.maze.clear()
        self._reset_search()
        self.status.setText("All walls removed")

    def on_cell_clicked(self, r, c):
        mode = self.mode_combo.currentText()
        if mode == "Toggle wall":
            self.maze.toggle_wall(r, c)
        elif mode == "Set start":
            self.maze.set_start(r, c)
        else:
            self.maze.set_goal(r, c)
        self._sync_spins()
        self._reset_search()
        self.status.setText(self._info())

    # ------------------------------------------------------------------
    #  Пошук
    # ------------------------------------------------------------------
    def start_search(self):
        self._reset_search()
        self.search = WaveSearch(self.maze, self.op_combo.currentData())
        self.view.search = self.search
        self.status.setText(f"Search started: {OPERATOR_TITLES[self.search.operator]}")
        if self.search.finished:
            self.finish_search()
        else:
            self.timer.start(self.speed.value())
        self.view.update()

    def pause_resume(self):
        if self.search is None or self.search.finished:
            return
        if self.timer.isActive():
            self.timer.stop()
            self.status.setText("Search paused")
        else:
            self.timer.start(self.speed.value())
            self.status.setText("Search resumed")

    def reset_colors(self):
        self._reset_search()
        self.status.setText("Colors reset")

    def search_step(self):
        if self.search is None:
            self.timer.stop()
            return
        result = self.search.step()
        self.wave_label.setText(f"Wave: {self.search.wave_number}")
        self.expanded_label.setText(f"Expanded cells: {self.search.expanded_count}")
        self.view.update()
        if result in ("found", "not_found"):
            self.timer.stop()
            self.finish_search()

    def finish_search(self):
        s = self.search
        self.wave_label.setText(f"Wave: {s.wave_number}")
        self.expanded_label.setText(f"Expanded cells: {s.expanded_count}")
        self.view.update()
        self._save_csv(s)

        lines = [f"Оператор переходу: {OPERATOR_TITLES[s.operator]}",
                 f"Лабіринт: {self._info()}",
                 f"Старт (рядок, стовпець): {s.start}   Ціль: {s.goal}", ""]
        if s.found:
            lines += [
                "Шлях знайдено!",
                f"Довжина шляху (кроків): {s.path_length}",
                f"Кількість хвиль: {s.wave_number}",
                f"Кількість розкритих вершин (циклів розкриття): {s.expanded_count}",
                f"Час пошуку (мс): {s.elapsed * 1000:.3f}",
                f"Координати вершин шляху (рядок, стовпець):",
                " -> ".join(f"({r},{c})" for r, c in s.path),
            ]
            self.status.setText("Path found, results saved to file")
        else:
            lines += [
                "Шлях не знайдено!",
                f"Кількість хвиль: {s.wave_number}",
                f"Кількість розкритих вершин (циклів розкриття): {s.expanded_count}",
                f"Час пошуку (мс): {s.elapsed * 1000:.3f}",
            ]
            self.status.setText("No path, results saved to file")
        ResultDialog(self, "Результати пошуку", "\n".join(lines)).exec_()

    def _save_csv(self, s):
        new_file = not os.path.exists(RESULTS_CSV)
        with open(RESULTS_CSV, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new_file:
                w.writerow(["timestamp", "operator", "rows", "cols", "walls", "start", "goal",
                            "found", "path_len", "waves", "expanded", "time_ms"])
            w.writerow([datetime.now().isoformat(timespec="seconds"), s.operator,
                        self.maze.rows, self.maze.cols, self.maze.wall_count(),
                        s.start, s.goal, s.found, s.path_length, s.wave_number,
                        s.expanded_count, f"{s.elapsed * 1000:.3f}"])

    def compare_operators(self):
        """Виконує пошук усіма трьома операторами на поточному лабіринті
        й виводить порівняльну таблицю (анімований стан не змінюється)."""
        header = f"{'Оператор':<26}{'знайдено':<10}{'шлях':<6}{'хвилі':<7}{'розкрито':<10}{'час, мс':<9}"
        lines = [f"Лабіринт: {self._info()}",
                 f"Старт {self.maze.start}, ціль {self.maze.goal}", "", header]
        for key, title in OPERATOR_TITLES.items():
            r = run_full(self.maze, key)
            lines.append(
                f"{title:<26}{('так' if r['found'] else 'ні'):<10}"
                f"{str(r['path_len'] if r['found'] else '-'):<6}{r['waves']:<7}"
                f"{r['expanded']:<10}{r['time_ms']:<9.3f}")
        ResultDialog(self, "Порівняння операторів переходу", "\n".join(lines)).exec_()
        self.status.setText("Operators compared (search state unchanged)")