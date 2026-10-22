import sys
from PyQt5.QtWidgets import QApplication

from main_window import WaveVisualization


def main():
    app = QApplication(sys.argv)
    window = WaveVisualization()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()