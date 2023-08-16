#!python3
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from gui.main_window import MainWindow
from version import VERSION


def main(argv):
    app = QApplication(argv)

    window = MainWindow()
    window.setWindowTitle(f"Simulator FBG {VERSION} - Codruta Toadere (2023)")
    window.setWindowIcon(QIcon("resources/app-icon-96.ico"))
    window.resize(1024, 768)
    window.show()

    # maybe call some post init stuff
    ret_code = app.exec()
    # maybe call some closing handlers

    return ret_code


if __name__ == "__main__":
    exit(main(sys.argv))
