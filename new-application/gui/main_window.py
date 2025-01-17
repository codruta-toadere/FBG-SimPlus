from pathlib import Path
from functools import partial
from itertools import pairwise
import locale
from numpy import linspace
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt, Slot, QCoreApplication
from PySide6.QtGui import QTextCursor, QDoubleValidator, QCloseEvent

from osa.simulator import StrainTypes, StressTypes, SiUnits
from gui.worker import WorkerThread
from gui.plot_window import SpectrumView


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        view = ParametersView(self)
        self.setCentralWidget(view)


class ParametersView(QWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent=parent)

        self.worker = None
        self.simulation_data = None

        self.float_validator = QDoubleValidator(self)
        self.setup_ui()

    def setup_ui(self):
        self.layout = QHBoxLayout(self)

        main_layout = self.make_main_layout()
        self.layout.addLayout(main_layout, 78)

        side_layout = self.make_side_layout()
        self.layout.addLayout(side_layout, 22)

    def make_side_layout(self):
        layout = QVBoxLayout()

        section_5 = self.make_spectrum_section(5)
        layout.addLayout(section_5)

        section_6 = self.make_journal_section(6)
        layout.addLayout(section_6)

        return layout

    def make_main_layout(self):
        grid = QGridLayout()

        section_1 = self.make_loader_section(1)
        grid.addLayout(section_1, 1, 1)

        section_2 = self.make_deform_types_section(3)
        grid.addLayout(section_2, 1, 2)

        section_3 = self.make_parameters_section(2)
        grid.addLayout(section_3, 2, 1)

        section_4 = self.make_virtual_configuration_section(4)
        grid.addLayout(section_4, 2, 2)

        return grid

    def make_loader_section(self, section_id: int):
        title = QLabel(
            "<b>({}) {}</b>".format(section_id, _("Load strain / stress data from file"))
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        load_button = QPushButton(_("Choose file"))
        load_button.clicked.connect(self.load_file)

        self.filepath = QLineEdit(self)
        self.filepath.setReadOnly(True)

        row = QHBoxLayout()
        row.addWidget(self.filepath)
        row.addWidget(load_button)

        si_units_group = QGroupBox(_("If distances are not expressed in millimeters [mm]"))
        self.has_si_units = QCheckBox(_("Apply conversion from m to mm"), si_units_group)
        group_layout = QVBoxLayout()
        group_layout.addWidget(self.has_si_units)
        si_units_group.setLayout(group_layout)

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addLayout(row)
        layout.addWidget(si_units_group)
        layout.addStretch()

        return layout

    def make_deform_types_section(self, section_id: int):
        def set_strain_type(value: StrainTypes):
            self.strain_type = value

        def set_stress_type(value: StressTypes):
            self.stress_type = value

        self.strain_type = StrainTypes.NONE
        self.stress_type = StressTypes.NONE

        title = QLabel("<b>({}) {}</b>".format(section_id, _("Choose a simulation type")))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        strain_type_group = QGroupBox(_("Longitudinal strain"))
        strain_group_layout = QVBoxLayout()

        no_strain = QRadioButton(_("None"), strain_type_group)
        no_strain.setChecked(True)
        uniform_strain = QRadioButton(_("Uniform"), strain_type_group)
        non_uniform_strain = QRadioButton(_("Non-uniform"), strain_type_group)

        no_strain.clicked.connect(lambda: set_strain_type(StrainTypes.NONE))
        uniform_strain.clicked.connect(lambda: set_strain_type(StrainTypes.UNIFORM))
        non_uniform_strain.clicked.connect(lambda: set_strain_type(StrainTypes.NON_UNIFORM))

        strain_group_layout.addWidget(no_strain)
        strain_group_layout.addWidget(uniform_strain)
        strain_group_layout.addWidget(non_uniform_strain)
        strain_type_group.setLayout(strain_group_layout)

        stress_type_group = QGroupBox(_("Include stress"))
        stress_group_layout = QVBoxLayout()

        no_stress = QRadioButton(_("None"), stress_type_group)
        no_stress.setChecked(True)
        included_stress = QRadioButton(_("Transverse stress"), stress_type_group)

        no_stress.clicked.connect(lambda: set_stress_type(StressTypes.NONE))
        included_stress.clicked.connect(lambda: set_stress_type(StressTypes.INCLUDED))

        stress_group_layout.addWidget(no_stress)
        stress_group_layout.addWidget(included_stress)
        stress_type_group.setLayout(stress_group_layout)

        emulation_group = QGroupBox(_("Emulation options"))

        row1, self.emulate_temperature = self.make_float_parameter(
            _("Emulate model temperature"), "[K]", "293.15"
        )
        self.has_emulate_temperature = QCheckBox(emulation_group)
        self.emulate_temperature.setEnabled(False)
        self.has_emulate_temperature.toggled.connect(self.emulate_temperature.setEnabled)
        row1.insertWidget(0, self.has_emulate_temperature)

        row2, self.host_expansion_coefficient = self.make_float_parameter(
            _("Host thermal expansion coefficient"), "[K<sup>-1</sup>]", "5e-5"
        )
        self.has_host_expansion = QCheckBox(emulation_group)
        self.host_expansion_coefficient.setEnabled(False)
        self.has_host_expansion.toggled.connect(self.host_expansion_coefficient.setEnabled)
        row2.insertWidget(0, self.has_host_expansion)

        emulation_group_layout = QVBoxLayout()
        emulation_group_layout.addLayout(row1)
        emulation_group_layout.addLayout(row2)
        emulation_group.setLayout(emulation_group_layout)

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addWidget(strain_type_group)
        layout.addWidget(stress_type_group)
        layout.addWidget(emulation_group)
        layout.addStretch()

        return layout

    def make_parameters_section(self, section_id: int):
        title = QLabel(
            "<b>({}) {}</b>".format(section_id, _("Simulation parameters")),
            alignment=Qt.AlignmentFlag.AlignCenter,
        )

        row1, self.resolution = self.make_float_parameter(
            _("Simulation resolution"), "[nm]", "0.05"
        )
        row2, self.min_bandwidth = self.make_float_parameter(
            _("Minimum bandwidth"), "[nm]", "1500.00"
        )
        row3, self.max_bandwidth = self.make_float_parameter(
            _("Maximum bandwidth"), "[nm]", "1600.00"
        )
        row4, self.ambient_temperature = self.make_float_parameter(
            _("Ambient temperature"), "[K]", "293.15"
        )

        advanded_group = QGroupBox(
            _("Fiber attributes (advanced mode)"), checkable=True, checked=False
        )

        row5, self.initial_refractive_index = self.make_float_parameter(
            _("Initial refractive index"), "[n<sub>eff</sub>]", "1.46"
        )
        row6, self.mean_change_refractive_index = self.make_float_parameter(
            _("Average variation in refractive index"), "[δn<sub>eff</sub>]", "4.5e-4"
        )
        row7, self.fringe_visibility = self.make_float_parameter(
            _("Fringe visibility"), "%", "1.0"
        )
        row8, self.directional_refractive_p11 = self.make_float_parameter(
            _("Pockel's elasto-optic coefficients"), "p<sub>11</sub>", "0.121"
        )
        row9, self.directional_refractive_p12 = self.make_float_parameter(
            _("Pockel's elasto-optic coefficients"), "p<sub>12</sub>", "0.270"
        )
        row10, self.youngs_mod = self.make_float_parameter(_("Young's module"), "[Pa]", "75e9")
        row11, self.poissons_coefficient = self.make_float_parameter(
            _("Poisson's coefficient"), "", "0.17"
        )
        row12, self.fiber_expansion_coefficient = self.make_float_parameter(
            _("Fiber thermal expansion coefficient"), "[K<sup>-1</sup>]", "0.55e-6"
        )
        row13, self.thermo_optic = self.make_float_parameter(
            _("Thermo-optic coefficient"), "[K<sup>-1</sup>]", "8.3e-6"
        )

        advanced_group_layout = QVBoxLayout()
        advanced_group_layout.addLayout(row5)
        advanced_group_layout.addLayout(row6)
        advanced_group_layout.addLayout(row7)
        advanced_group_layout.addLayout(row8)
        advanced_group_layout.addLayout(row9)
        advanced_group_layout.addLayout(row10)
        advanced_group_layout.addLayout(row11)
        advanced_group_layout.addLayout(row12)
        advanced_group_layout.addLayout(row13)
        advanded_group.setLayout(advanced_group_layout)

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addLayout(row1)
        layout.addLayout(row2)
        layout.addLayout(row3)
        layout.addLayout(row4)
        layout.addWidget(advanded_group)
        layout.addStretch()

        return layout

    def make_float_parameter(self, display_text: str, unit_text, value_text):
        row = QHBoxLayout()
        label = QLabel(display_text)
        unit_label = QLabel(unit_text)
        value = QLineEdit(
            locale.str(float(value_text)),
            alignment=Qt.AlignmentFlag.AlignRight,
            validator=self.float_validator,
        )
        row.addWidget(label, stretch=3)
        row.addWidget(unit_label)
        row.addWidget(value)
        return row, value

    def make_int_parameter(self, display_text: str, unit_text, value_text):
        row = QHBoxLayout()
        label = QLabel(display_text)
        unit_label = QLabel(unit_text)
        value = QSpinBox(
            value=int(value_text),
            alignment=Qt.AlignmentFlag.AlignRight,
            minimum=1,
        )
        row.addWidget(label, stretch=3)
        row.addWidget(unit_label)
        row.addWidget(value)
        return row, value

    def make_virtual_configuration_section(self, section_id: int):
        title = QLabel(
            "<b>({}) {}</b>".format(
                section_id, _("Virtual Fiber Bragg Grating array configuration")
            ),
            alignment=Qt.AlignmentFlag.AlignCenter,
        )

        row1, self.fbg_count = self.make_int_parameter(_("Number of FBG sensors"), "", "1")
        row2, self.fbg_length = self.make_float_parameter(_("Sensor length"), "mm", "10.0")
        row3, self.tolerance = self.make_float_parameter(_("Tolerance"), "mm", "0.01")

        positions_group, self.fbg_positions = self.make_float_list_parameter(
            _("Positions of FBG sensors (distance from the start)"),
            "[mm]",
            _("position"),
        )
        wavelengths_group, self.original_wavelengths = self.make_float_list_parameter(
            _("Original wavelengths"), "[nm]", _("wavelength"), with_auto=True
        )

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addLayout(row1)
        layout.addLayout(row2)
        layout.addLayout(row3)
        layout.addWidget(positions_group)
        layout.addWidget(wavelengths_group)
        layout.addStretch()

        return layout

    def make_float_list_parameter(
        self, display_text: str, unit_text: str, keyword: str, with_auto: bool = False
    ):
        group = QGroupBox(f"{display_text} {unit_text}")

        values = QTextEdit(group, readOnly=True)

        add_button = QPushButton(_("Add"), group)
        add_button.clicked.connect(partial(self.add_float_list, values, keyword))
        clear_button = QPushButton(_("Remove"), group)
        clear_button.clicked.connect(values.clear)

        actions_layout = QVBoxLayout()
        actions_layout.addWidget(add_button)
        actions_layout.addWidget(clear_button)

        if with_auto:
            auto_button = QPushButton(_("Auto"), group)
            min_bandwidth = (locale.atof(self.min_bandwidth.text()),)
            max_bandwidth = (locale.atof(self.max_bandwidth.text()),)
            auto_button.clicked.connect(
                partial(self.fill_float_list, values, (min_bandwidth, max_bandwidth))
            )
            actions_layout.insertWidget(0, auto_button)

        layout = QHBoxLayout()
        layout.addWidget(values)
        layout.addLayout(actions_layout)
        group.setLayout(layout)

        return group, values

    def add_float_list(self, target: QTextEdit, keyword: str):
        values = list()

        for i in range(self.fbg_count.value()):
            value, ok = QInputDialog.getDouble(
                self,
                "",
                "{} #{} {}".format(_("Please enter a value for FBG"), i + 1, keyword),
                flags=Qt.WindowType.Popup,
            )
            if ok:
                values.append(value)
            else:
                return  # User has cancelled

            QCoreApplication.processEvents()

        values.sort()
        target.setText("\n".join(map(locale.str, values)))

    def fill_float_list(self, target: QTextEdit, range: tuple):
        left, right = range
        values = linspace(left, right, self.fbg_count.value() + 1, endpoint=False)
        target.setText("\n".join(map(locale.str, values[1:])))

    def make_spectrum_section(self, section_id: int):
        title = QLabel(
            "<b>({}) {}</b>".format(section_id, _("Spectrum simulation")),
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.has_reflected_signal = QCheckBox(
            _("Include the undeformed FBG reflected signal"), checked=True
        )
        simulate_button = QPushButton(_("Start simulation"))
        simulate_button.clicked.connect(self.run_simulation)
        self.progress = QProgressBar(value=0)
        show_plot_button = QPushButton(_("Open simulation results"))
        show_plot_button.clicked.connect(self.showPlot)

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addWidget(self.has_reflected_signal)
        layout.addWidget(simulate_button)
        layout.addWidget(self.progress)
        layout.addWidget(show_plot_button)

        return layout

    def make_journal_section(self, section_id: int):
        title = QLabel(
            "<b>({}) {}</b>".format(section_id, _("Message log")),
            alignment=Qt.AlignmentFlag.AlignCenter,
        )

        self.console = QTextEdit(self)
        self.console.setReadOnly(True)

        clear_button = QPushButton(_("Clear log"), self)
        clear_button.clicked.connect(self.console.clear)

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addWidget(self.console)
        layout.addWidget(clear_button)

        return layout

    def println(self, text: str):
        if isinstance(text, str):
            show_text = text
        else:
            show_text = repr(text)
        self.console.append(show_text)
        self.console.moveCursor(QTextCursor.MoveOperation.End)
        print(show_text)

    def load_file(self):
        fullpath, filter = QFileDialog.getOpenFileName(
            self, _("Load data from"), "./sample", "text (*.txt)"
        )
        self.filepath.setText(fullpath)

    def print_error(self, message: str):
        self.println("{}: {}".format(_("ERROR"), message))

    def validate_params(self):
        """Collect all simulation parameters from self and validate them."""

        params = dict(
            units=SiUnits(int(self.has_si_units.isChecked())),
            strain_type=self.strain_type,
            stress_type=self.stress_type,
            emulate_temperature=locale.atof(self.emulate_temperature.text())
            if self.has_emulate_temperature.isChecked()
            else None,
            host_expansion_coefficient=locale.atof(
                self.host_expansion_coefficient.text()
                if self.has_host_expansion.isChecked()
                else self.fiber_expansion_coefficient.text()
            ),
            resolution=locale.atof(self.resolution.text()),
            min_bandwidth=locale.atof(self.min_bandwidth.text()),
            max_bandwidth=locale.atof(self.max_bandwidth.text()),
            ambient_temperature=locale.atof(self.ambient_temperature.text()),
            initial_refractive_index=locale.atof(self.initial_refractive_index.text()),
            mean_change_refractive_index=locale.atof(self.mean_change_refractive_index.text()),
            fringe_visibility=locale.atof(self.fringe_visibility.text()),
            directional_refractive_p11=locale.atof(self.directional_refractive_p11.text()),
            directional_refractive_p12=locale.atof(self.directional_refractive_p12.text()),
            youngs_mod=locale.atof(self.youngs_mod.text()),
            poissons_coefficient=locale.atof(self.poissons_coefficient.text()),
            fiber_expansion_coefficient=locale.atof(self.fiber_expansion_coefficient.text()),
            thermo_optic=locale.atof(self.thermo_optic.text()),
            fbg_count=int(self.fbg_count.text()),
            fbg_length=locale.atof(self.fbg_length.text()),
            tolerance=locale.atof(self.tolerance.text()),
            has_reflected_signal=self.has_reflected_signal.isChecked(),
        )

        datafile = self.filepath.text()
        if Path(datafile).is_file():
            params["filepath"] = datafile
        else:
            raise ValueError("'{}' {}".format(datafile, _("is not a valid data file.")))

        if positions := self.fbg_positions.toPlainText():
            fbg_positions = list(map(float, positions.split("\n")))
        else:
            fbg_positions = []

        steps = [right - left for left, right in pairwise(fbg_positions)]
        if len(fbg_positions) != params["fbg_count"]:
            raise ValueError(
                "Sensors count ({}) and positions count ({}) should be equal.".format(
                    params["fbg_count"], len(fbg_positions)
                )
            )
        elif min(steps, default=params["fbg_length"]) < params["fbg_length"]:
            raise ValueError(_("Two consecutive FBG positions cannot be shorter than FBG length."))
        else:
            params["fbg_positions"] = fbg_positions

        if wavelengths := self.original_wavelengths.toPlainText():
            original_wavelengths = list(map(float, wavelengths.split("\n")))
        else:
            original_wavelengths = []

        if min(original_wavelengths, default=params["min_bandwidth"]) < params["min_bandwidth"]:
            raise ValueError(_("At least one wavelength is below the minimum bandwidth setting."))
        elif max(original_wavelengths, default=params["max_bandwidth"]) > params["max_bandwidth"]:
            raise ValueError(_("At least one wavelength is above the maximum bandwidth setting."))
        elif len(original_wavelengths) != params["fbg_count"]:
            raise ValueError(
                _("Sensors count ({}) and original wavelengths count ({}) must be equal.").format(
                    params["fbg_count"], len(original_wavelengths)
                )
            )
        else:
            params["original_wavelengths"] = original_wavelengths

        return params

    @Slot()
    def run_simulation(self):
        if self.worker is not None:
            self.print_error(_("A simulator session is already running."))
            return

        self.simulation_data = None
        self.progress.setValue(0)
        try:
            params = self.validate_params()
        except ValueError as err:
            self.print_error(str(err))
            return

        self.progress.setValue(5)
        self.worker = WorkerThread(params)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.finished.connect(self.worker_finished)
        self.worker.start()
        self.progress.setValue(8)

    def worker_finished(self):
        if self.worker.error_message:
            message = _("Simulation has failed, reason: {}").format(self.worker.error_message)
            self.print_error(message)
        else:
            self.simulation_data = self.worker.data
            self.simulation_data["params"] = self.worker.params
            self.println(_("Simulation completed successfully."))
        self.worker = None

    def showPlot(self):
        if self.simulation_data is None:
            self.print_error(_("There is no data to show, please run the simulation first."))
            return

        plot = SpectrumView(self, data=self.simulation_data)
        plot.exec()
