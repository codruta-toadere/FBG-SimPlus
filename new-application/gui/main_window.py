from pathlib import Path
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QTextCursor, QDoubleValidator, QCloseEvent

import translation
from osa.simulator import StrainTypes, StressTypes, SiUnits
from gui.worker import WorkerThread


class MainWindow(QWidget):
    translation.install("ro")

    def __init__(self):
        super().__init__()

        self.worker = None
        self.float_validator = QDoubleValidator(self)
        self.setup_ui()

    def setup_ui(self):
        self.layout = QHBoxLayout(self)

        main_layout = self.make_main_layout()
        self.layout.addLayout(main_layout, 78)

        side_layout = self.make_side_layout()
        self.layout.addLayout(side_layout, 22)

        self.println(_("Aplicatia a fost initializata cu succes."))

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

        section_2 = self.make_deform_types_section(2)
        grid.addLayout(section_2, 1, 2)

        section_3 = self.make_parameters_section(3)
        grid.addLayout(section_3, 2, 1)

        section_4 = self.make_virtual_configuration_section(4)
        grid.addLayout(section_4, 2, 2)

        return grid

    def make_loader_section(self, section_id: int):
        title = QLabel(
            "<b>({}) {}</b>".format(section_id, _("Incarca datele de tensiune si deformare"))
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        load_button = QPushButton(_("Alege fisier"))
        load_button.clicked.connect(self.load_file)

        self.filepath = QLineEdit(self)
        self.filepath.setReadOnly(True)

        row = QHBoxLayout()
        row.addWidget(self.filepath)
        row.addWidget(load_button)

        si_units_group = QGroupBox(_("Daca distantele nu sunt exprimate in milimetri [mm]"))
        self.has_si_units = QCheckBox(_("Aplica conversia din m in mm"), si_units_group)
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

        title = QLabel("<b>({}) {}</b>".format(section_id, _("Alege tipul simularii")))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        strain_type_group = QGroupBox(_("Alege tipul de deformare"))
        strain_group_layout = QVBoxLayout()

        no_strain = QRadioButton(_("Fara deformare"), strain_type_group)
        no_strain.setChecked(True)
        uniform_strain = QRadioButton(_("Deformare longitudinala uniforma"), strain_type_group)
        non_uniform_strain = QRadioButton(
            _("Deformare longitudinala neuniforma"), strain_type_group
        )

        no_strain.clicked.connect(lambda: set_strain_type(StrainTypes.NONE))
        uniform_strain.clicked.connect(lambda: set_strain_type(StrainTypes.UNIFORM))
        non_uniform_strain.clicked.connect(lambda: set_strain_type(StrainTypes.NON_UNIFORM))

        strain_group_layout.addWidget(no_strain)
        strain_group_layout.addWidget(uniform_strain)
        strain_group_layout.addWidget(non_uniform_strain)
        strain_type_group.setLayout(strain_group_layout)

        stress_type_group = QGroupBox(_("Alege tipul de tensiune"))
        stress_group_layout = QVBoxLayout()

        no_stress = QRadioButton(_("Fara tensiune"), stress_type_group)
        no_stress.setChecked(True)
        included_stress = QRadioButton(_("Cu tensiune transversala"), stress_type_group)

        no_stress.clicked.connect(lambda: set_stress_type(StressTypes.NONE))
        included_stress.clicked.connect(lambda: set_stress_type(StressTypes.INCLUDED))

        stress_group_layout.addWidget(no_stress)
        stress_group_layout.addWidget(included_stress)
        stress_type_group.setLayout(stress_group_layout)

        emulation_group = QGroupBox(_("Optiuni emulare"))

        row1, self.emulate_temperature = self.make_float_parameter(
            _("Emuleaza temperatura model"), "[K]", "293.15"
        )
        self.has_emulate_temperature = QCheckBox(emulation_group)
        self.emulate_temperature.setEnabled(False)
        self.has_emulate_temperature.toggled.connect(self.emulate_temperature.setEnabled)
        row1.insertWidget(0, self.has_emulate_temperature)

        row2, self.host_expansion_coefficient = self.make_float_parameter(
            _("Coeficientul de dilatatie termica (host)"), "[K<sup>-1</sup>]", "5e-5"
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
            "<b>({}) {}</b>".format(section_id, _("Parametri simulare")),
            alignment=Qt.AlignmentFlag.AlignCenter,
        )

        row1, self.resolution = self.make_float_parameter(_("Rezolutia simularii"), "[nm]", "0.05")
        row2, self.min_bandwidth = self.make_float_parameter(
            _("Latime de banda minima"), "[nm]", "1500.00"
        )
        row3, self.max_bandwidth = self.make_float_parameter(
            _("Latime de banda maxima"), "[nm]", "1600.00"
        )
        row4, self.ambient_temperature = self.make_float_parameter(
            _("Temperatura ambientala"), "[K]", "293.15"
        )

        advanded_group = QGroupBox(
            _("Atributele fibrei (mod avansat)"), checkable=True, checked=False
        )

        row5, self.initial_refractive_index = self.make_float_parameter(
            _("Indicele de refractie initiala"), "[n<sub>eff</sub>]", "1.46"
        )
        row6, self.mean_change_refractive_index = self.make_float_parameter(
            _("Variatia medie in indicele de refractie"), "[δn<sub>eff</sub>]", "4.5e-4"
        )
        row7, self.fringe_visibility = self.make_float_parameter(
            _("Vizibilitatea franjelor"), "%", "1.0"
        )
        row8, self.directional_refractive_p11 = self.make_float_parameter(
            _("Constanta fotoelastica normala (Pockel)"), "p<sub>11</sub>", "0.121"
        )
        row9, self.directional_refractive_p12 = self.make_float_parameter(
            _("Constanta fotoelastica de taiere (Pockel)"), "p<sub>12</sub>", "0.270"
        )
        row10, self.youngs_mod = self.make_float_parameter(
            _("Modulul de elasticitate (Young)"), "[Pa]", "75e9"
        )
        row11, self.poissons_coefficient = self.make_float_parameter(
            _("Coeficientul Poisson"), "", "0.17"
        )
        row12, self.fiber_expansion_coefficient = self.make_float_parameter(
            _("Coeficientul de dilatatie termica"), "[K<sup>-1</sup>]", "0.55e-6"
        )
        row13, self.thermo_optic = self.make_float_parameter(
            _("Coeficientul termo-optic"), "[K<sup>-1</sup>]", "8.3e-6"
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
            value_text,
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
            "<b>({}) {}</b>".format(section_id, _("Configuratia matricei virtuale FBG")),
            alignment=Qt.AlignmentFlag.AlignCenter,
        )

        row1, self.fbg_count = self.make_int_parameter(_("Numarul de senzori"), "", "1")
        row2, self.fbg_length = self.make_float_parameter(_("Lungimea"), "mm", "10.0")
        row3, self.tolerance = self.make_float_parameter(_("Toleranta"), "mm", "0.01")

        positions_group, self.fbg_positions = self.make_float_list_parameter(
            _("Pozitiile senzorilor FBG fata de start"), "[mm]"
        )
        wavelengths_group, self.original_wavelengths = self.make_float_list_parameter(
            _("Lungimile de unda originale"), "[nm]"
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

    def make_float_list_parameter(self, display_text: str, unit_text):
        group = QGroupBox(f"{display_text}")

        values = QTextEdit(group)
        unit_label = QLabel(
            f"<small>{unit_text}</small>", group, alignment=Qt.AlignmentFlag.AlignCenter
        )
        add_button = QPushButton("✚", group)
        clear_button = QPushButton("✗", group)
        clear_button.clicked.connect(values.clear)

        actions_layout = QVBoxLayout()
        actions_layout.addWidget(unit_label)
        actions_layout.addWidget(add_button)
        actions_layout.addWidget(clear_button)

        layout = QHBoxLayout()
        layout.addWidget(values)
        layout.addLayout(actions_layout)
        group.setLayout(layout)

        return group, values

    def make_spectrum_section(self, section_id: int):
        title = QLabel(
            "<b>({}) {}</b>".format(section_id, _("Simulare de spectru")),
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.has_reflected_signal = QCheckBox(_("Include semnalul reflectat nedeformat"))
        simulate_button = QPushButton(_("Porneste simularea"))
        simulate_button.clicked.connect(self.run_simulation)
        self.progress = QProgressBar(value=0)
        show_plot_button = QPushButton(_("Deschide grafic simulare"))

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addWidget(self.has_reflected_signal)
        layout.addWidget(simulate_button)
        layout.addWidget(self.progress)
        layout.addWidget(show_plot_button)

        return layout

    def make_journal_section(self, section_id: int):
        title = QLabel(
            "<b>({}) {}</b>".format(section_id, _("Jurnal mesaje")),
            alignment=Qt.AlignmentFlag.AlignCenter,
        )

        self.console = QTextEdit(self)
        self.console.setReadOnly(True)

        clear_button = QPushButton(_("Sterge jurnal"), self)
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
            self, _("Incarca datele din"), "./sample", "text (*.txt)"
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
            emulate_temperature=float(self.emulate_temperature.text())
            if self.has_emulate_temperature.isChecked()
            else None,
            host_expansion_coefficient=float(
                self.host_expansion_coefficient.text()
                if self.has_host_expansion.isChecked()
                else self.fiber_expansion_coefficient.text()
            ),
            resolution=float(self.resolution.text()),
            min_bandwidth=float(self.min_bandwidth.text()),
            max_bandwidth=float(self.max_bandwidth.text()),
            ambient_temperature=float(self.ambient_temperature.text()),
            initial_refractive_index=float(self.initial_refractive_index.text()),
            mean_change_refractive_index=float(self.mean_change_refractive_index.text()),
            fringe_visibility=float(self.fringe_visibility.text()),
            directional_refractive_p11=float(self.directional_refractive_p11.text()),
            directional_refractive_p12=float(self.directional_refractive_p12.text()),
            youngs_mod=float(self.youngs_mod.text()),
            poissons_coefficient=float(self.poissons_coefficient.text()),
            fiber_expansion_coefficient=float(self.fiber_expansion_coefficient.text()),
            thermo_optic=float(self.thermo_optic.text()),
            fbg_count=int(self.fbg_count.text()),
            fbg_length=float(self.fbg_length.text()),
            tolerance=float(self.tolerance.text()),
            has_reflected_signal=self.has_reflected_signal.isChecked(),
        )

        datafile = self.filepath.text()
        if Path(datafile).is_file():
            params["filepath"] = datafile
        else:
            raise ValueError("'{}' {}".format(datafile, _("is not a valid data file.")))

        if positions := self.fbg_positions.toPlainText():
            fbg_positions = positions.split("\n")
        else:
            fbg_positions = [22, 50, 70]

        if len(fbg_positions) == params["fbg_count"]:
            params["fbg_positions"] = list(map(float, fbg_positions))
        else:
            raise ValueError(
                "Sensors count ({}) and positions count ({}) should be equal.".format(
                    params["fbg_count"], len(fbg_positions)
                )
            )

        if wave_legths := self.original_wavelengths.toPlainText():
            original_wavelengths = wave_legths.split("\n")
        else:
            original_wavelengths = [1500.0, 1525.0, 1550.0]

        if len(original_wavelengths) == params["fbg_count"]:
            params["original_wavelengths"] = list(map(float, original_wavelengths))
        else:
            raise ValueError(
                "Sensors count ({}) and original wavelengths count ({}) should be equal.".format(
                    params["fbg_count"], len(original_wavelengths)
                )
            )

        return params

    @Slot()
    def run_simulation(self):
        if self.worker is not None:
            self.print_error(_("A simulator session is already in progress."))
            return

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
            self.println(_("Simulation completed successfully."))
        self.worker = None

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.worker and self.worker.is_alive():
            raise RuntimeError("Simulation thread is still in progress.")
        return super().closeEvent(event)
