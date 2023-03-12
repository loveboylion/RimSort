import logging

from PySide2.QtCore import QProcess
from PySide2.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QWidget,
    QVBoxLayout,
)

logger = logging.getLogger(__name__)


class RunnerPanel(QWidget):
    """
    A generic, read-only panel that can be used to display output from something.
    It also has a built-in QProcess functionality.
    """

    def __init__(self):
        super().__init__()
        self.text = QPlainTextEdit(readOnly=True)
        self.text.verticalScrollBar().setValue(self.text.verticalScrollBar().maximum())

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.text)
        self.setLayout(self.layout)
        self.resize(800, 600)

        self.message("ヽ༼ ຈل͜ຈ༼ ▀̿̿Ĺ̯̿̿▀̿ ̿༽Ɵ͆ل͜Ɵ͆ ༽ﾉ")

    def execute(self, command: str, args: list):
        logger.info(f"Executing command: {command} " + f"with args {args}")
        self.message(f"Executing command: {command} " + f"with args {args}")
        self.process = QProcess(self)
        self.process.setProgram(command)
        self.process.setArguments(args)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.readyReadStandardOutput)
        self.process.finished.connect(self.finished)
        self.process.start()

    def message(self, line: str):
        self.text.appendPlainText(line)

    def readyReadStandardOutput(self):
        text = self.process.readAllStandardOutput().data().decode()
        self.text.appendPlainText(text)

    def finished(self):
        logger.info("Subprocess completed")
        #self.destroy()