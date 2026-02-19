import json
import os
import sys
import traceback
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

from PySide6.QtCore import QObject, Qt, QThread, QTimer, QSettings, Signal, Slot
from PySide6.QtGui import QColor, QCursor, QFont, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QProgressBar,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QToolTip,
    QVBoxLayout,
    QWidget,
    QLabel,
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cad_boundary_to_cc.cad import list_dxf_layers
from cad_boundary_to_cc.pipeline import run


@dataclass
class UiState:
    dxf_path: str
    cloud_path: str
    layer: str
    z_mode: str
    step_m: float
    density: str
    z_offset: float
    z_radius_m: float
    z_k: int
    z_quantile: float
    las_max_points: int
    rgb: Tuple[int, int, int]
    rgb_enabled: bool
    write_poly_id: bool
    write_sf: bool
    sf_mode: str
    sf_value: float
    layers_selected: list[str]
    layer_colors: dict[str, Tuple[int, int, int]]
    all_layers_one_color: bool
    out_las_path: str


class LayerPickerDialog(QDialog):
    def __init__(
        self,
        *,
        dxf_path: str,
        palette_colors: list[Tuple[int, int, int]],
        selected_layers: list[str],
        layer_colors: dict[str, Tuple[int, int, int]],
        all_layers_one_color: bool,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Слои DXF")
        self._palette_colors = list(palette_colors)
        self._selected_layers = list(selected_layers)
        self._layer_colors = dict(layer_colors)
        self._all_layers_one_color = bool(all_layers_one_color)
        self._layers = list_dxf_layers(dxf_path)

        root = QVBoxLayout()

        self._all_one_cb = QCheckBox("Все слои одним цветом")
        self._all_one_cb.setChecked(self._all_layers_one_color)
        root.addWidget(self._all_one_cb)

        area = QScrollArea()
        area.setWidgetResizable(True)
        cont = QWidget()
        cont_l = QVBoxLayout()
        cont_l.setContentsMargins(0, 0, 0, 0)
        cont_l.setSpacing(6)

        self._row_widgets: dict[str, Tuple[QCheckBox, QPushButton]] = {}

        for i, layer in enumerate(self._layers):
            row = QWidget()
            row_l = QHBoxLayout()
            row_l.setContentsMargins(0, 0, 0, 0)
            row_l.setSpacing(10)
            cb = QCheckBox(layer)
            cb.setChecked(layer in self._selected_layers)
            cb.stateChanged.connect(lambda _, ln=layer: self._on_layer_checked(ln))
            sw = QPushButton("")
            sw.setObjectName("PaletteSwatch")
            sw.setFixedSize(28, 28)
            sw.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            sw.clicked.connect(lambda _, ln=layer: self._pick_layer_color(ln))

            if layer not in self._layer_colors:
                self._layer_colors[layer] = self._palette_colors[i % max(1, len(self._palette_colors))]
            self._apply_swatch_style(sw, self._layer_colors[layer])

            row_l.addWidget(cb, 1)
            row_l.addWidget(sw, 0)
            row.setLayout(row_l)
            cont_l.addWidget(row)
            self._row_widgets[layer] = (cb, sw)

        cont_l.addStretch(1)
        cont.setLayout(cont_l)
        area.setWidget(cont)
        root.addWidget(area, 1)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

        self.setLayout(root)

    def _apply_swatch_style(self, btn: QPushButton, rgb: Tuple[int, int, int]) -> None:
        r, g, b = rgb
        btn.setStyleSheet(
            f"background: rgb({r},{g},{b}); border: 2px solid #1E1F22; border-radius: 4px;"
        )

    def _on_layer_checked(self, layer: str) -> None:
        cb, _ = self._row_widgets[layer]
        if cb.isChecked():
            if layer not in self._selected_layers:
                self._selected_layers.append(layer)
        else:
            self._selected_layers = [x for x in self._selected_layers if x != layer]

    def _pick_layer_color(self, layer: str) -> None:
        rgb = self._layer_colors.get(layer)
        if rgb is None:
            rgb = self._palette_colors[0] if self._palette_colors else (255, 0, 0)
        r, g, b = rgb
        c = QColorDialog.getColor(
            QColor(r, g, b),
            self,
            "Выбор цвета слоя",
            QColorDialog.ColorDialogOption.DontUseNativeDialog,
        )
        if not c.isValid():
            return
        new_rgb = (int(c.red()), int(c.green()), int(c.blue()))
        self._layer_colors[layer] = new_rgb
        _, sw = self._row_widgets[layer]
        self._apply_swatch_style(sw, new_rgb)

    def selected_layers(self) -> list[str]:
        if not self._selected_layers:
            return []
        return list(self._selected_layers)

    def layer_colors(self) -> dict[str, Tuple[int, int, int]]:
        return dict(self._layer_colors)

    def all_layers_one_color(self) -> bool:
        return bool(self._all_one_cb.isChecked())


def apply_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()

    base = QColor(49, 51, 56)
    alt_base = QColor(43, 45, 49)
    text = QColor(219, 222, 225)
    disabled = QColor(148, 155, 164)
    button = QColor(43, 45, 49)
    highlight = QColor(88, 101, 242)

    palette.setColor(QPalette.Window, base)
    palette.setColor(QPalette.WindowText, text)
    palette.setColor(QPalette.Base, alt_base)
    palette.setColor(QPalette.AlternateBase, base)
    palette.setColor(QPalette.ToolTipBase, text)
    palette.setColor(QPalette.ToolTipText, text)
    palette.setColor(QPalette.Text, text)
    palette.setColor(QPalette.Disabled, QPalette.Text, disabled)
    palette.setColor(QPalette.Button, button)
    palette.setColor(QPalette.ButtonText, text)
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, disabled)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Highlight, highlight)
    palette.setColor(QPalette.HighlightedText, Qt.white)

    app.setPalette(palette)

    f = QFont("Segoe UI", 10)
    app.setFont(f)


def apply_discord_qss(app: QApplication) -> None:
    app.setStyleSheet(
        """
        QWidget { color: #DBDEE1; }
        QToolTip {
            background: #111214;
            color: #DBDEE1;
            border: 1px solid #1E1F22;
            border-radius: 8px;
            padding: 6px 8px;
        }
        QListWidget { background: #2B2D31; border: none; padding: 8px; }
        QListWidget::item { padding: 10px 12px; margin: 2px 0px; border-radius: 8px; }
        QListWidget::item:selected { background: #3B3D44; }

        QGroupBox {
            border: 1px solid #1E1F22;
            border-radius: 10px;
            margin-top: 10px;
            background: #313338;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 6px;
            color: #DBDEE1;
        }

        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
            background: #1E1F22;
            border: 1px solid #1E1F22;
            border-radius: 8px;
            padding: 6px 10px;
            selection-background-color: #5865F2;
            min-height: 30px;
        }
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
            border: 1px solid #5865F2;
        }

        QTextEdit {
            background: #1E1F22;
            border: 1px solid #1E1F22;
            border-radius: 10px;
            padding: 10px;
        }

        QPushButton {
            background: #2B2D31;
            border: 1px solid #1E1F22;
            border-radius: 10px;
            padding: 8px 14px;
            min-height: 34px;
        }
        QPushButton:hover { background: #34363C; }
        QPushButton:disabled { color: #949BA4; background: #232428; }

        QPushButton#PaletteSwatch {
            padding: 0px;
            min-height: 0px;
            min-width: 0px;
            border-radius: 4px;
        }

        QPushButton#PickColorButton {
            padding: 2px 8px;
            min-height: 0px;
            border-radius: 10px;
        }

        QPushButton#PrimaryButton {
            background: #5865F2;
            border: none;
            font-weight: 600;
        }
        QPushButton#PrimaryButton:hover { background: #4752C4; }
        """
    )


class Worker(QObject):
    log = Signal(str)
    progress = Signal(int, str)
    done = Signal(str)
    error = Signal(str)

    def __init__(self, state: "UiState") -> None:
        super().__init__()
        self._state = state

    @Slot()
    def run_job(self) -> None:
        try:
            st = self._state
            self.log.emit("---")
            self.log.emit(f"DXF: {st.dxf_path}")
            self.log.emit(f"Облако: {st.cloud_path}")
            self.log.emit(f"LAS+CAD: {st.out_las_path}")
            self.log.emit(f"Режим высоты: {st.z_mode}")
            self.log.emit(f"Шаг (м): {st.step_m}  ({st.density})")
            self.log.emit(f"Смещение Z (м): {st.z_offset}")
            self.log.emit(f"RGB: {st.rgb}")
            if getattr(st, "layers_selected", None) is not None:
                self.log.emit(f"Слои: {len(st.layers_selected)}  all_one_color={st.all_layers_one_color}")

            las_max_points: Optional[int] = None if st.las_max_points == 0 else st.las_max_points

            run(
                dxf_path=st.dxf_path,
                cloud_path=st.cloud_path,
                out_xyz=None,
                step_m=st.step_m,
                layer=st.layer if st.layer else None,
                assume_same_crs=True,
                cad_crs_str=None,
                cloud_crs_str=None,
                z_mode=st.z_mode,
                z_offset=st.z_offset,
                z_radius_m=st.z_radius_m,
                z_k=st.z_k,
                z_quantile=st.z_quantile,
                las_max_points=las_max_points,
                write_poly_id=False,
                out_rgb=True,
                rgb=st.rgb,
                layers_selected=st.layers_selected,
                layer_colors=st.layer_colors,
                all_layers_one_color=st.all_layers_one_color,
                write_combined_las=True,
                out_las=st.out_las_path,
                progress=lambda p, t: self.progress.emit(int(p), str(t)),
            )

            self.done.emit(st.out_las_path)
        except Exception as e:
            self.error.emit(f"ERROR: {e}\n{traceback.format_exc()}")


class MainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CAD на облако точек (для CloudCompare)")
        self.resize(980, 640)

        self._settings = QSettings("cad_boundary_to_cc", "cad_boundary_gui")

        self.dxf_edit = QLineEdit()
        self.cloud_edit = QLineEdit()
        self.out_las_edit = QLineEdit("")
        self.layer_edit = QLineEdit()
        self.layer_pick_btn = QPushButton("Выбрать слои…")
        fm = self.layer_pick_btn.fontMetrics()
        w = fm.horizontalAdvance(self.layer_pick_btn.text()) + 26
        self.layer_pick_btn.setFixedWidth(max(140, min(220, w)))
        self.layer_summary_lbl = QLabel("")
        self.layer_summary_lbl.setStyleSheet("color: #949BA4;")

        self.dxf_edit.setToolTip("Путь к DXF с линиями/полилиниями границ")
        self.cloud_edit.setToolTip("Путь к облаку точек LAS/LAZ")
        self.out_las_edit.setToolTip("Куда сохранить итоговое облако LAS с добавленными CAD-точками")
        self.layer_pick_btn.setToolTip("Выбрать один или несколько слоёв из DXF")

        self.z_mode_combo = QComboBox()
        self.z_mode_combo.addItem("По рельефу", "surface_p10")
        self.z_mode_combo.addItem("Над рельефом", "surface_offset")
        self.z_mode_combo.setToolTip("Как назначать высоту Z для точек границы")

        self.density_combo = QComboBox()
        self.density_combo.addItems(["По умолчанию", "Пользовательский"])
        self.density_combo.setCurrentText("По умолчанию")
        self.density_combo.setToolTip(
            "Плотность точек вдоль линии. 'По умолчанию' = шаг 0.1 м. В 'Пользовательский' шаг задаётся вручную"
        )

        self.step_spin = QDoubleSpinBox()
        self.step_spin.setRange(0.01, 1000.0)
        self.step_spin.setDecimals(3)
        self.step_spin.setSingleStep(0.1)
        self.step_spin.setValue(0.1)
        self.step_spin.setToolTip(
            "Шаг дискретизации вдоль линий/контуров (м).\n"
            "Меньше шаг = больше точек = линия выглядит сплошнее, но файл больше и расчет дольше.\n"
            "Больше шаг = быстрее и легче, но линия может быть 'редкой'."
        )

        self.z_offset_spin = QDoubleSpinBox()
        self.z_offset_spin.setRange(-1000.0, 1000.0)
        self.z_offset_spin.setDecimals(3)
        self.z_offset_spin.setSingleStep(0.05)
        self.z_offset_spin.setValue(0.2)
        self.z_offset_spin.setToolTip(
            "Добавка к высоте Z (м).\n"
            "Увеличение поднимает линию выше (лучше видно, но хуже совпадение с рельефом).\n"
            "Уменьшение опускает линию ближе к поверхности."
        )

        self.z_radius_spin = QDoubleSpinBox()
        self.z_radius_spin.setRange(0.1, 1000.0)
        self.z_radius_spin.setDecimals(3)
        self.z_radius_spin.setSingleStep(0.1)
        self.z_radius_spin.setValue(2.0)
        self.z_radius_spin.setToolTip(
            "Для режима 'По рельефу': радиус поиска соседей (м).\n"
            "Больше радиус = стабильнее, но сильнее сглаживание и медленнее.\n"
            "Меньше радиус = точнее локально, но может не найти соседей (провалы)."
        )

        self.z_k_spin = QSpinBox()
        self.z_k_spin.setRange(1, 5000)
        self.z_k_spin.setValue(64)
        self.z_k_spin.setToolTip(
            "Для режима 'По рельефу': максимум соседей (k).\n"
            "Больше k = стабильнее оценка, но медленнее.\n"
            "Меньше k = быстрее, но чувствительнее к шуму."
        )

        self.z_quantile_spin = QDoubleSpinBox()
        self.z_quantile_spin.setRange(0.0, 1.0)
        self.z_quantile_spin.setDecimals(3)
        self.z_quantile_spin.setSingleStep(0.01)
        self.z_quantile_spin.setValue(0.10)
        self.z_quantile_spin.setToolTip(
            "Для режима 'По рельефу': квантиль по Z соседей.\n"
            "0.10 ближе к земле (отсекает кусты/шум сверху).\n"
            "Увеличение (0.3..0.5) поднимет линию выше по соседям."
        )

        self.las_max_points_spin = QSpinBox()
        self.las_max_points_spin.setRange(0, 100_000_000)
        self.las_max_points_spin.setValue(2_000_000)
        self.las_max_points_spin.setToolTip(
            "Ограничение точек облака, загружаемых для surface (ускорение).\n"
            "0 = без ограничения (может быть очень медленно)"
        )

        self.rgb_edit = QLineEdit("255,0,0")
        self.rgb_edit.setToolTip("Цвет для XYZRGB в формате R,G,B (0..255), например 255,0,0")
        self.rgb_edit.setFixedWidth(120)

        self.rgb_preview = QLabel("")
        self.rgb_preview.setFixedSize(55, 55)
        self.rgb_preview.setToolTip("Текущий цвет")

        self.pick_color_btn = QPushButton("Палитра")
        self.pick_color_btn.setFixedHeight(34)
        self.pick_color_btn.setMaximumHeight(34)
        fm = self.pick_color_btn.fontMetrics()
        w = fm.horizontalAdvance(self.pick_color_btn.text()) + 26
        self.pick_color_btn.setFixedWidth(max(120, min(180, w)))
        self.pick_color_btn.setObjectName("PickColorButton")
        self.pick_color_btn.setToolTip("Выбрать свой цвет")

        self._color_dialog_open = False

        self._palette_colors = [
            (255, 0, 0),
            (255, 255, 0),
            (0, 255, 0),
            (0, 255, 255),
            (0, 0, 255),
            (255, 0, 255),
            (255, 255, 255),
            (0, 0, 0),
        ]
        self._palette_buttons: list[QPushButton] = []
        self._selected_palette_idx: int = 0

        self._layers_selected: list[str] = []
        self._layer_colors: dict[str, Tuple[int, int, int]] = {}
        self._all_layers_one_color: bool = False
        self._last_dxf_for_layers: str = ""
        self._last_inputs_for_out: Tuple[str, str] = ("", "")

        self.run_btn = QPushButton("Сгенерировать и выгрузить LAS+CAD")
        self.run_btn.setObjectName("PrimaryButton")
        self.run_btn.clicked.connect(self.on_run)
        self.run_btn.setToolTip("Сгенерировать CAD-точки и сохранить новое облако LAS с добавленными CAD-точками")

        self.defaults_btn = QPushButton("Настройки по умолчанию")
        fm = self.defaults_btn.fontMetrics()
        w = fm.horizontalAdvance(self.defaults_btn.text()) + 70
        self.defaults_btn.setFixedWidth(max(260, min(520, w)))
        self.defaults_btn.clicked.connect(self.on_defaults)

        self.export_btn = QPushButton("Выгрузить LAS+CAD")
        self.export_btn.setEnabled(False)
        self.export_btn.setVisible(False)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setFixedHeight(16)
        self.progress_bar.setStyleSheet(
            "QProgressBar { border: 1px solid #1E1F22; border-radius: 8px; background: #232428; }"
            "QProgressBar::chunk { background-color: #2ECC71; border-radius: 8px; }"
        )
        self.defaults_btn.setToolTip("Сбросить настройки на базовые")

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #949BA4;")
        self.status_lbl.setToolTip("Статус последней генерации")

        self.log = QTextEdit()
        self.log.setReadOnly(True)

        self._wire_density_logic()
        self._wire_color_logic()
        self._wire_layer_logic()
        self._wire_out_las_logic()

        self.stack = QStackedWidget()
        self.page_files = self._build_files_group()
        self.page_params = self._build_params_group()
        self.page_log = self._build_log_group()
        self.stack.addWidget(self.page_files)
        self.stack.addWidget(self.page_params)
        self.stack.addWidget(self.page_log)

        self.nav = QListWidget()
        self.nav.setFixedWidth(220)
        for t in ["Файлы", "Параметры", "Лог", "Выход"]:
            self.nav.addItem(QListWidgetItem(t))
        self.nav.setCurrentRow(0)
        self.nav.currentRowChanged.connect(self._on_nav_changed)

        right = QVBoxLayout()
        right.addWidget(self._build_header())
        right.addWidget(self.stack, 1)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.defaults_btn)
        btn_row.addWidget(self.status_lbl)
        btn_row.addStretch(1)
        btn_row.addWidget(self.run_btn)
        right.addLayout(btn_row)

        wrap = QHBoxLayout()
        wrap.addWidget(self.nav)
        right_w = QWidget()
        right_w.setLayout(right)
        wrap.addWidget(right_w, 1)
        self.setLayout(wrap)

        self._thread: Optional[QThread] = None
        self._worker: Optional[QObject] = None

        self._last_export_key: Optional[str] = None
        self._last_cloud_path: Optional[str] = None
        self._last_cad_xyz: Optional[np.ndarray] = None
        self._last_cad_rgb_u8: Optional[np.ndarray] = None
        self._last_out_las: Optional[str] = None

        self._apply_saved_settings()

    def _build_files_group(self) -> QGroupBox:
        g = QGroupBox("Файлы")
        lay = QGridLayout()

        dxf_btn = QPushButton("Выбрать")
        dxf_btn.clicked.connect(self.on_pick_dxf)
        dxf_btn.setToolTip("Выбрать DXF файл")

        cloud_btn = QPushButton("Выбрать")
        cloud_btn.clicked.connect(self.on_pick_cloud)
        cloud_btn.setToolTip("Выбрать LAS/LAZ файл")

        out_las_btn = QPushButton("Выбрать")
        out_las_btn.clicked.connect(self.on_pick_out_las)
        out_las_btn.setToolTip("Выбрать куда сохранить LAS с CAD-точками")

        lay.addWidget(QLabel("DXF"), 0, 0)
        lay.addWidget(self.dxf_edit, 0, 1)
        lay.addWidget(dxf_btn, 0, 2)

        lay.addWidget(QLabel("Облако (LAS/LAZ)"), 1, 0)
        lay.addWidget(self.cloud_edit, 1, 1)
        lay.addWidget(cloud_btn, 1, 2)

        lay.addWidget(QLabel("Выходной LAS+CAD"), 2, 0)
        lay.addWidget(self.out_las_edit, 2, 1)
        lay.addWidget(out_las_btn, 2, 2)

        g.setLayout(lay)
        return g

    def _wire_layer_logic(self) -> None:
        self.layer_pick_btn.clicked.connect(self.on_pick_layers)
        self.dxf_edit.textChanged.connect(lambda _: self._reset_layers_on_dxf_change())

    def _reset_layers_on_dxf_change(self) -> None:
        dxf = self.dxf_edit.text().strip()
        if not dxf or dxf == getattr(self, "_last_dxf_for_layers", ""):
            return
        self._last_dxf_for_layers = dxf
        self._layers_selected = []
        self._layer_colors = {}
        self._all_layers_one_color = False
        self._update_layer_summary()
        self._save_settings()

    def _update_layer_summary(self) -> None:
        n = len(getattr(self, "_layers_selected", []))
        if n <= 0:
            self.layer_summary_lbl.setText("Слои: все")
        else:
            shown = ", ".join(self._layers_selected[:4])
            tail = "" if n <= 4 else f" +{n-4}"
            self.layer_summary_lbl.setText(f"Слои: {shown}{tail}")

    def on_pick_layers(self) -> None:
        dxf = self.dxf_edit.text().strip()
        if not dxf or not os.path.exists(dxf):
            self._set_status("Сначала выбери DXF", ok=False)
            return
        dlg = LayerPickerDialog(
            dxf_path=dxf,
            palette_colors=self._palette_colors,
            selected_layers=list(self._layers_selected),
            layer_colors=dict(self._layer_colors),
            all_layers_one_color=bool(self._all_layers_one_color),
            parent=self,
        )
        if dlg.exec() != QDialog.Accepted:
            return
        self._layers_selected = dlg.selected_layers()
        self._layer_colors = dlg.layer_colors()
        self._all_layers_one_color = dlg.all_layers_one_color()
        self._update_layer_summary()
        self._save_settings()

    def _set_status(self, text: str, *, ok: bool) -> None:
        if ok:
            self.status_lbl.setStyleSheet("color: #3BA55D; font-weight: 600;")
        else:
            self.status_lbl.setStyleSheet("color: #ED4245; font-weight: 600;")
        self.status_lbl.setText(text)

    def _build_log_group(self) -> QGroupBox:
        g = QGroupBox("Лог")
        lay = QVBoxLayout()
        lay.addWidget(self.progress_bar)
        lay.addWidget(self.log)
        g.setLayout(lay)
        return g

    def _build_header(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout()
        lay.setContentsMargins(0, 0, 0, 0)
        title = QLabel("CAD на облако точек")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        subtitle = QLabel("Наложение в CloudCompare")
        subtitle.setStyleSheet("color: #949BA4;")
        box = QVBoxLayout()
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(title)
        box.addWidget(subtitle)
        lay.addLayout(box)
        lay.addStretch(1)
        w.setLayout(lay)
        return w

    def _build_params_group(self) -> QGroupBox:
        g = QGroupBox("Параметры")
        lay = QGridLayout()

        form_left = QFormLayout()
        form_left.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form_left.addRow("Режим высоты", self.z_mode_combo)
        form_left.addRow("Смещение Z (м)", self.z_offset_spin)
        form_left.addRow("Плотность точек на линии", self.density_combo)
        form_left.addRow("Шаг между точками (м)", self.step_spin)

        out_box = QGroupBox("Цвет линий CAD")
        out_lay = QVBoxLayout()

        row = QWidget()
        row_l = QHBoxLayout()
        row_l.setContentsMargins(0, 0, 0, 0)
        row_l.setSpacing(14)

        left = QWidget()
        left_l = QVBoxLayout()
        left_l.setContentsMargins(0, 0, 0, 0)
        left_l.setSpacing(6)

        swatches = QWidget()
        sw_l = QHBoxLayout()
        sw_l.setContentsMargins(0, 0, 0, 0)
        sw_l.setSpacing(1)
        for i, (r, gg, bb) in enumerate(self._palette_colors):
            btn = QPushButton("")
            btn.setObjectName("PaletteSwatch")
            btn.setFixedSize(42, 42)
            btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            btn.setProperty("palette_idx", i)
            btn.setStyleSheet(
                f"background: rgb({r},{gg},{bb}); border: 2px solid #1E1F22; border-radius: 4px;"
            )
            btn.clicked.connect(lambda _, j=i: self._on_palette_clicked(j))
            self._palette_buttons.append(btn)
            sw_l.addWidget(btn)
        swatches.setLayout(sw_l)

        left_l.addWidget(swatches)
        left_l.addWidget(self.pick_color_btn, alignment=Qt.AlignLeft)

        layer_sel = QWidget()
        layer_sel_l = QHBoxLayout()
        layer_sel_l.setContentsMargins(0, 0, 0, 0)
        layer_sel_l.setSpacing(8)
        layer_sel_l.addWidget(self.layer_pick_btn, 0)
        layer_sel_l.addWidget(self.layer_summary_lbl, 1)
        layer_sel.setLayout(layer_sel_l)
        left_l.addWidget(layer_sel)
        left.setLayout(left_l)

        self.rgb_preview.setFixedSize(55, 55)
        row_l.addWidget(left, 1)
        prev_box = QWidget()
        prev_l = QVBoxLayout()
        prev_l.setContentsMargins(0, 0, 0, 0)
        prev_l.setSpacing(12)
        lbl = QLabel("Выбранный цвет")
        lbl.setContentsMargins(0, 5, 0, 0)
        prev_l.addWidget(lbl, alignment=Qt.AlignTop)
        prev_l.addSpacing(13)
        prev_l.addWidget(self.rgb_preview, alignment=Qt.AlignTop)
        prev_l.addStretch(1)
        prev_box.setLayout(prev_l)
        row_l.addWidget(prev_box, 0, alignment=Qt.AlignTop)
        row.setLayout(row_l)

        out_lay.addWidget(row)
        out_box.setLayout(out_lay)

        left_box = QWidget()
        left_box.setLayout(form_left)
        lay.addWidget(left_box, 0, 0, 1, 2)
        lay.addWidget(out_box, 1, 0, 1, 2)

        g.setLayout(lay)
        return g

    def _wire_density_logic(self) -> None:
        self.density_combo.currentTextChanged.connect(self.on_density_changed)
        self.on_density_changed(self.density_combo.currentText())

        self.z_mode_combo.currentIndexChanged.connect(lambda _: self._sync_z_mode_help())
        self._sync_z_mode_help()

        self._install_z_mode_item_tooltips()

    def _install_z_mode_item_tooltips(self) -> None:
        view = self.z_mode_combo.view()
        view.entered.connect(self._on_z_mode_item_hovered)
        view.viewport().leaveEvent = self._on_z_mode_viewport_leave  # type: ignore[method-assign]
        view.viewport().mouseMoveEvent = self._on_z_mode_viewport_mouse_move  # type: ignore[method-assign]
        self.z_mode_combo.hidePopup = self._on_z_mode_hide_popup  # type: ignore[method-assign]
        self._last_z_mode_tip: str = ""
        self._z_mode_tip_text: str = ""
        self._z_mode_tip_index = None
        self._z_mode_original_hide_popup = QComboBox.hidePopup

        if not hasattr(self, "_z_mode_tip_widget"):
            self._z_mode_tip_widget = QLabel("", None)
            self._z_mode_tip_widget.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint)
            self._z_mode_tip_widget.setTextFormat(Qt.PlainText)
            self._z_mode_tip_widget.setWordWrap(True)
            self._z_mode_tip_widget.setStyleSheet(
                "QLabel { background: #111214; color: #E6E6E6; border: 1px solid #2B2D31; border-radius: 6px; padding: 8px; }"
            )
            self._z_mode_tip_widget.hide()

    @Slot(object)
    def _on_z_mode_item_hovered(self, index) -> None:
        data = self.z_mode_combo.itemData(index.row())
        tip = self._z_mode_tooltip(str(data))
        if not tip:
            return
        self._last_z_mode_tip = tip
        self._z_mode_tip_text = tip
        view = self.z_mode_combo.view()
        rect = view.visualRect(index)
        pos = view.viewport().mapToGlobal(rect.bottomLeft())
        self._z_mode_tip_index = index
        if hasattr(self, "_z_mode_tip_widget"):
            self._z_mode_tip_widget.setText(tip)
            self._z_mode_tip_widget.adjustSize()
            self._z_mode_tip_widget.move(pos.x(), pos.y() + 2)
            self._z_mode_tip_widget.show()
            self._z_mode_tip_widget.raise_()

    def _hide_z_mode_tip(self) -> None:
        if hasattr(self, "_z_mode_tip_widget"):
            self._z_mode_tip_widget.hide()
        self._z_mode_tip_text = ""
        self._z_mode_tip_index = None

    def _on_z_mode_viewport_mouse_move(self, event) -> None:
        view = self.z_mode_combo.view()
        idx = view.indexAt(event.pos())
        if not idx.isValid():
            if getattr(self, "_z_mode_tip_index", None) is not None:
                self._hide_z_mode_tip()
            return super(type(view.viewport()), view.viewport()).mouseMoveEvent(event)

        current = getattr(self, "_z_mode_tip_index", None)
        if current is None or not current.isValid() or current.row() != idx.row():
            self._on_z_mode_item_hovered(idx)

        if getattr(self, "_z_mode_tip_index", None) is not None and hasattr(self, "_z_mode_tip_timer"):
            if not self._z_mode_tip_timer.isActive():
                self._z_mode_tip_timer.start()

        return super(type(view.viewport()), view.viewport()).mouseMoveEvent(event)

    def _on_z_mode_viewport_leave(self, event) -> None:
        self._hide_z_mode_tip()
        return super(type(self.z_mode_combo.view().viewport()), self.z_mode_combo.view().viewport()).leaveEvent(event)

    def _on_z_mode_hide_popup(self) -> None:
        self._hide_z_mode_tip()
        self._z_mode_original_hide_popup(self.z_mode_combo)

    def _sync_z_mode_help(self) -> None:
        key = str(self.z_mode_combo.currentData())
        self.z_mode_combo.setToolTip(self._tip_for_z_mode(key) or "Как назначать высоту Z")
        is_relief = str(key).lower().startswith("surface_p10")
        is_relief_offset = str(key).lower().startswith("surface_offset")
        self.z_offset_spin.setEnabled(bool(is_relief_offset))

    def _z_mode_tooltip(self, z_mode_key: str) -> str:
        return self._tip_for_z_mode(z_mode_key)

    def _tip_for_z_mode(self, z_mode_key: str) -> str:
        k = str(z_mode_key).lower()
        if k == "surface_p10":
            return "Линии CAD наносятся исходя из рельефа в облаке точек"
        if k == "surface_offset":
            return "Как 'По рельефу', но затем добавляем смещение Z (например +0.2 м), чтобы линия была видна над поверхностью."
        if k == "p95":
            return "Одна высота для всех точек, по высокому процентилю облака (линия будет выше, но не по рельефу)."
        if k == "median":
            return "Одна высота для всех точек, по среднему уровню облака."
        return ""

    def _wire_color_logic(self) -> None:
        def sync_selected_from_rgb() -> None:
            try:
                r, g, b = self._parse_rgb()
            except Exception:
                return

            best = 0
            best_d = 1e18
            for i, (pr, pg, pb) in enumerate(self._palette_colors):
                d = (pr - r) * (pr - r) + (pg - g) * (pg - g) + (pb - b) * (pb - b)
                if d < best_d:
                    best_d = d
                    best = i
            self._set_selected_palette_idx(best)

        def pick_custom_color() -> None:
            if getattr(self, "_color_dialog_open", False):
                return
            self._color_dialog_open = True
            try:
                r, g, b = self._parse_rgb()
                c = QColorDialog.getColor(
                    QColor(r, g, b),
                    self,
                    "Выбор цвета",
                    QColorDialog.ColorDialogOption.DontUseNativeDialog,
                )
                if not c.isValid():
                    return
                self.rgb_edit.setText(f"{c.red()},{c.green()},{c.blue()}")
            finally:
                self._color_dialog_open = False

        self.rgb_edit.textChanged.connect(lambda _: (self._update_preview(), sync_selected_from_rgb(), self._save_settings()))
        self.pick_color_btn.clicked.connect(pick_custom_color)
        self._update_preview()
        sync_selected_from_rgb()
        if not hasattr(self, "_selected_palette_idx"):
            self._selected_palette_idx = 0
        self._set_selected_palette_idx(self._selected_palette_idx)

    def _update_preview(self) -> None:
        try:
            r, g, b = self._parse_rgb()
            self.rgb_preview.setStyleSheet(
                f"background: rgb({int(r)},{int(g)},{int(b)}); border: 1px solid #1E1F22; border-radius: 6px;"
            )
        except Exception:
            self.rgb_preview.setStyleSheet(
                "background: #232428; border: 1px solid #1E1F22; border-radius: 6px;"
            )

    def _set_selected_palette_idx(self, idx: int) -> None:
        self._selected_palette_idx = int(idx)
        for i, btn in enumerate(self._palette_buttons):
            r, g, b = self._palette_colors[i]
            if i == self._selected_palette_idx:
                btn.setStyleSheet(
                    f"background: rgb({r},{g},{b}); border: 4px solid #00A8FF; border-radius: 4px;"
                )
            else:
                btn.setStyleSheet(
                    f"background: rgb({r},{g},{b}); border: 2px solid #1E1F22; border-radius: 4px;"
                )

    def _on_palette_clicked(self, idx: int) -> None:
        self._set_selected_palette_idx(idx)
        r, g, b = self._palette_colors[idx]
        self.rgb_edit.setText(f"{r},{g},{b}")

    def on_density_changed(self, t: str) -> None:
        preset = t.strip()
        if preset == "Пользовательский":
            self.step_spin.setEnabled(True)
        else:
            self.step_spin.setValue(0.1)
            self.step_spin.setEnabled(False)

        self._save_settings()

    def on_defaults(self) -> None:
        self._apply_defaults()
        self._save_settings()

    def _apply_defaults(self) -> None:
        self.layer_edit.setText("")
        self.z_mode_combo.setCurrentIndex(0)
        self.density_combo.setCurrentText("По умолчанию")
        self.step_spin.setValue(0.1)
        self.z_offset_spin.setValue(0.2)
        self.z_radius_spin.setValue(2.0)
        self.z_k_spin.setValue(64)
        self.z_quantile_spin.setValue(0.10)
        self.las_max_points_spin.setValue(2_000_000)
        self.rgb_edit.setText("255,0,0")
        self._set_selected_palette_idx(0)
        self._invalidate_last_result()

        self._maybe_update_default_out_las()

    def _apply_saved_settings(self) -> None:
        if self._settings.value("_initialized", "0") != "1":
            self._apply_defaults()
            self._settings.setValue("_initialized", "1")
            return

        self.dxf_edit.setText(str(self._settings.value("dxf", "")))
        self.cloud_edit.setText(str(self._settings.value("cloud", "")))
        self.out_las_edit.setText(str(self._settings.value("out_las", "")))
        self.layer_edit.setText(str(self._settings.value("layer", "")))

        self._last_dxf_for_layers = self.dxf_edit.text().strip()
        try:
            self._layers_selected = json.loads(str(self._settings.value("layers_selected", "[]")))
        except Exception:
            self._layers_selected = []
        try:
            raw = json.loads(str(self._settings.value("layer_colors", "{}")))
            if isinstance(raw, dict):
                tmp: dict[str, Tuple[int, int, int]] = {}
                for k, v in raw.items():
                    parts = [int(x.strip()) for x in str(v).split(",")]
                    if len(parts) == 3:
                        tmp[str(k)] = (parts[0], parts[1], parts[2])
                self._layer_colors = tmp
            else:
                self._layer_colors = {}
        except Exception:
            self._layer_colors = {}
        self._all_layers_one_color = str(self._settings.value("all_layers_one_color", "0")) == "1"
        self._update_layer_summary()

        z_key = str(self._settings.value("z_mode", "surface_p10"))
        idx = max(0, self.z_mode_combo.findData(z_key))
        self.z_mode_combo.setCurrentIndex(idx)

        dens = str(self._settings.value("density", "По умолчанию"))
        if dens in ["По умолчанию", "Пользовательский"]:
            self.density_combo.setCurrentText(dens)

        self.step_spin.setValue(float(self._settings.value("step_m", 0.1)))
        self.z_offset_spin.setValue(float(self._settings.value("z_offset", 0.2)))
        self.z_radius_spin.setValue(float(self._settings.value("z_radius", 2.0)))
        self.z_k_spin.setValue(int(self._settings.value("z_k", 64)))
        self.z_quantile_spin.setValue(float(self._settings.value("z_quantile", 0.10)))
        self.las_max_points_spin.setValue(int(self._settings.value("las_max_points", 2_000_000)))
        self.rgb_edit.setText(str(self._settings.value("rgb", "255,0,0")))
        self._invalidate_last_result()

        self._settings.setValue("dxf", self.dxf_edit.text())
        self._settings.setValue("cloud", self.cloud_edit.text())
        self._settings.setValue("out_las", self.out_las_edit.text())
        self._settings.setValue("layer", self.layer_edit.text())
        self._settings.setValue("z_mode", str(self.z_mode_combo.currentData()))
        self._settings.setValue("density", self.density_combo.currentText())
        self._settings.setValue("step_m", float(self.step_spin.value()))
        self._settings.setValue("z_offset", float(self.z_offset_spin.value()))
        self._settings.setValue("z_radius", float(self.z_radius_spin.value()))
        self._settings.setValue("z_k", int(self.z_k_spin.value()))
        self._settings.setValue("z_quantile", float(self.z_quantile_spin.value()))
        self._settings.setValue("las_max_points", int(self.las_max_points_spin.value()))
        self._settings.setValue("rgb", self.rgb_edit.text().strip())
        self._settings.setValue("layers_selected", json.dumps(self._layers_selected, ensure_ascii=False))
        self._settings.setValue(
            "layer_colors",
            json.dumps({k: f"{v[0]},{v[1]},{v[2]}" for k, v in self._layer_colors.items()}, ensure_ascii=False),
        )
        self._settings.setValue("all_layers_one_color", "1" if self._all_layers_one_color else "0")
        self._settings.sync()

    def _save_settings(self) -> None:
        if not hasattr(self, "_settings"):
            return

        self._settings.setValue("dxf", self.dxf_edit.text())
        self._settings.setValue("cloud", self.cloud_edit.text())
        self._settings.setValue("out_las", self.out_las_edit.text())
        self._settings.setValue("layer", self.layer_edit.text())
        self._settings.setValue("z_mode", str(self.z_mode_combo.currentData()))
        self._settings.setValue("density", self.density_combo.currentText())
        self._settings.setValue("step_m", float(self.step_spin.value()))
        self._settings.setValue("z_offset", float(self.z_offset_spin.value()))
        self._settings.setValue("z_radius", float(self.z_radius_spin.value()))
        self._settings.setValue("z_k", int(self.z_k_spin.value()))
        self._settings.setValue("z_quantile", float(self.z_quantile_spin.value()))
        self._settings.setValue("las_max_points", int(self.las_max_points_spin.value()))
        self._settings.setValue("rgb", self.rgb_edit.text())
        self._settings.setValue("layers_selected", json.dumps(self._layers_selected, ensure_ascii=False))
        self._settings.setValue(
            "layer_colors",
            json.dumps({k: f"{v[0]},{v[1]},{v[2]}" for k, v in self._layer_colors.items()}, ensure_ascii=False),
        )
        self._settings.setValue("all_layers_one_color", "1" if self._all_layers_one_color else "0")
        self._settings.sync()

    def _on_nav_changed(self, idx: int) -> None:
        if idx == 3:
            self.close()
            return
        self.stack.setCurrentIndex(idx)

    def on_pick_dxf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Выбор DXF", "", "DXF (*.dxf)")
        if path:
            self.dxf_edit.setText(path)
            self._reset_layers_on_dxf_change()

    def on_pick_cloud(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Выбор LAS/LAZ", "", "LAS/LAZ (*.las *.laz)")
        if path:
            self.cloud_edit.setText(path)

    def on_pick_out_las(self) -> None:
        cur = self.out_las_edit.text().strip() or self._default_out_las_path(dxf_path=self.dxf_edit.text().strip(), cloud_path=self.cloud_edit.text().strip())
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить LAS", cur, "LAS (*.las)")
        if path:
            self.out_las_edit.setText(path)
            self._save_settings()

    def _parse_rgb(self) -> Tuple[int, int, int]:
        s = self.rgb_edit.text().strip()
        parts = [int(x.strip()) for x in s.split(",")]
        if len(parts) != 3:
            raise ValueError("RGB должно быть в формате R,G,B")
        r, g, b = parts
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))
        return r, g, b

    def _read_state(self) -> UiState:
        dxf_path = self.dxf_edit.text().strip()
        cloud_path = self.cloud_edit.text().strip()
        layer = self.layer_edit.text().strip()
        out_las_path = self.out_las_edit.text().strip()

        if not dxf_path:
            raise ValueError("Не выбран DXF")
        if not cloud_path:
            raise ValueError("Не выбрано облако LAS/LAZ")
        if not out_las_path:
            raise ValueError("Не задан путь для сохранения LAS")

        if not os.path.exists(dxf_path):
            raise ValueError("DXF файл не найден")
        if not os.path.exists(cloud_path):
            raise ValueError("LAS/LAZ файл не найден")

        z_mode = str(self.z_mode_combo.currentData())

        density = self.density_combo.currentText().strip()
        if density == "По умолчанию":
            step_m = 0.1
        else:
            step_m = float(self.step_spin.value())

        z_offset = float(self.z_offset_spin.value())
        if str(z_mode).lower().startswith("surface_p10"):
            z_offset = 0.0
        z_radius_m = float(self.z_radius_spin.value())
        z_k = int(self.z_k_spin.value())
        z_quantile = float(self.z_quantile_spin.value())

        las_max_points = int(self.las_max_points_spin.value())

        rgb = self._parse_rgb()

        out_las_path = str(out_las_path)

        return UiState(
            dxf_path=dxf_path,
            cloud_path=cloud_path,
            layer=layer,
            z_mode=z_mode,
            step_m=step_m,
            density=density,
            z_offset=z_offset,
            z_radius_m=z_radius_m,
            z_k=z_k,
            z_quantile=z_quantile,
            las_max_points=las_max_points,
            rgb_enabled=True,
            rgb=rgb,
            write_poly_id=False,
            write_sf=False,
            sf_mode="const",
            sf_value=1.0,
            layers_selected=list(self._layers_selected),
            layer_colors=dict(self._layer_colors),
            all_layers_one_color=bool(self._all_layers_one_color),
            out_las_path=str(out_las_path),
        )

    def _default_out_las_path(self, *, dxf_path: str, cloud_path: str) -> str:
        base = os.path.splitext(os.path.basename(cloud_path))[0] if cloud_path else "out"
        folder = os.path.dirname(os.path.abspath(cloud_path)) if cloud_path else os.getcwd()

        z_key = str(self.z_mode_combo.currentData() or "").lower()
        if z_key.startswith("surface_p10"):
            suffix = "_relief"
        elif z_key.startswith("surface_offset"):
            z_val = float(self.z_offset_spin.value())
            suffix = f"_Z_{z_val:g}"
        else:
            suffix = ""

        return os.path.join(folder, f"{base}{suffix}_with_cad.las")

    def _is_auto_out_las_path(self, out_path: str) -> bool:
        p = (out_path or "").strip()
        if not p:
            return True
        stem, ext = os.path.splitext(os.path.basename(p))
        if (ext or ".las").lower() != ".las":
            return False
        if stem.endswith("_with_cad"):
            return True
        if stem.endswith("_relief_with_cad"):
            return True
        if "_Z_" in stem and stem.endswith("_with_cad"):
            return True
        return False

    def _maybe_update_default_out_las(self) -> None:
        new_path = self._default_out_las_path(dxf_path=self.dxf_edit.text().strip(), cloud_path=self.cloud_edit.text().strip())
        cur = self.out_las_edit.text().strip()
        if not cur or self._is_auto_out_las_path(cur):
            self.out_las_edit.setText(new_path)

    def _wire_out_las_logic(self) -> None:
        self.dxf_edit.textChanged.connect(lambda _: (self._maybe_update_default_out_las(), self._save_settings()))
        self.cloud_edit.textChanged.connect(lambda _: (self._maybe_update_default_out_las(), self._save_settings()))
        self.z_mode_combo.currentIndexChanged.connect(lambda _: (self._maybe_update_default_out_las(), self._save_settings()))
        self.z_offset_spin.valueChanged.connect(lambda _: (self._maybe_update_default_out_las(), self._save_settings()))
        self.out_las_edit.textChanged.connect(lambda _: self._save_settings())

    def _ensure_unique_out_las_path(self, path: str) -> str:
        base, ext = os.path.splitext(path)
        if not ext:
            ext = ".las"
        p = f"{base}{ext}"
        if not os.path.exists(p):
            return p
        i = 2
        while True:
            cand = f"{base}_{i}{ext}"
            if not os.path.exists(cand):
                return cand
            i += 1

    def _invalidate_last_result(self) -> None:
        self._last_export_key = None
        self._last_cloud_path = None
        self._last_cad_xyz = None
        self._last_cad_rgb_u8 = None
        self._last_out_las = None
        self.export_btn.setEnabled(False)

    def _append_log(self, s: str) -> None:
        self.log.append(s)
        try:
            self.log.ensureCursorVisible()
        except Exception:
            pass
        

    def on_run(self) -> None:
        if self._thread is not None:
            return

        self.run_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("0%")
        self._set_status("", ok=True)
        try:
            state = self._read_state()
            state.out_las_path = self._ensure_unique_out_las_path(state.out_las_path)
        except Exception as e:
            msg = f"Ошибка параметров: {e}"
            self._append_log(f"ERROR: {msg}\n{traceback.format_exc()}")
            self._set_status(msg, ok=False)
            self.run_btn.setEnabled(True)
            return
        self.nav.setCurrentRow(2)
        self._thread = QThread()
        self._worker = Worker(state)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run_job)
        self._worker.log.connect(self._append_log)
        self._worker.progress.connect(self._on_progress)
        self._worker.done.connect(lambda out_path: self._on_done_generate(out_path, state))
        self._worker.error.connect(self._on_error)
        self._thread.start()

    @Slot(str)
    def _on_done_generate(self, out_path: str, state: UiState) -> None:
        self._on_done(out_path)

    @Slot(int, str)
    def _on_progress(self, p: int, text: str) -> None:
        v = max(0, min(100, int(p)))
        self.progress_bar.setValue(v)
        t = (text or "").strip()
        self.progress_bar.setFormat(f"{v}%" if not t else f"{v}%  {t}")

    @Slot(str)
    def _on_done(self, out_path: str) -> None:
        self._append_log(f"Готово: {out_path}")
        self._set_status("Успешно", ok=True)
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("100%  Готово")
        self._cleanup_thread()

    @Slot(str)
    def _on_error(self, msg: str) -> None:
        self._append_log(msg)
        text = (msg or "").strip()
        first_line = text.splitlines()[0] if text else "Ошибка"
        if first_line.startswith("ERROR:"):
            first_line = first_line[len("ERROR:") :].strip() or "Ошибка"
        self._set_status(first_line, ok=False)
        self.progress_bar.setFormat("Ошибка")
        self._cleanup_thread()

    def _cleanup_thread(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(2000)
        self._thread = None
        self._worker = None
        self.run_btn.setEnabled(True)
        self.export_btn.setEnabled(False)


def main() -> None:
    app = QApplication(sys.argv)
    apply_dark_theme(app)
    apply_discord_qss(app)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
