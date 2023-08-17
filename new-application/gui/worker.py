from PySide6.QtCore import QThread, Signal
from osa.simulator import OsaSimulator, StrainTypes, StressTypes


class WorkerThread(QThread):
    progress = Signal(int)

    def __init__(self, params: dict) -> None:
        super().__init__()

        self.units = params.pop("units")
        self.include_underformed_signal = params.pop("has_reflected_signal")
        self.strain_type = params.pop("strain_type")
        self.stress_type = params.pop("stress_type")
        self.datafile = params.pop("filepath")
        self.params = params
        self.error_message = ""

    def run(self):
        self.progress.emit(13)
        try:
            simu = OsaSimulator(**self.params)
            simu.from_file(filepath=self.datafile, units=self.units)
            self.progress.emit(21)

            if self.include_underformed_signal:
                underformed_data = simu.undeformed_fbg()
                print("undeformed reflected signal", underformed_data["reflec"][:5])
                self.progress.emit(34)

            self.progress.emit(55)
            deformed_data = simu.deformed_fbg(
                strain_type=StrainTypes.NON_UNIFORM,
                stress_type=StressTypes.INCLUDED,
            )
            print("deformed reflected signal", deformed_data["reflec"][:5])
            self.progress.emit(89)

            summary_data = simu.compute_fbg_shifts_and_widths(
                strain_type=StrainTypes.NON_UNIFORM,
                stress_type=StressTypes.INCLUDED,
            )
            print(f"{summary_data=}")
            self.progress.emit(100)

        except Exception as err:
            self.error_message = str(err)