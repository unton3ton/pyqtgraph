#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
source PYQTGRAPH/bin/activate


sudo apt install libxcb-xinerama0 libxcb-cursor0 libxcb-randr0 libxcb-xtest0 libxcb-shape0 libxcb-xfixes0
pip install pyqt5 pyqtgraph imageio numpy

Инструмент анализа изображений на основе PyQtGraph.
Позволяет загружать фото, выделять области, смотреть гистограмму и профили яркости.

https://www.geeksforgeeks.org/python/image-analysis-tool-using-pyqtgraph/?ysclid=mhbqkksoy3131480206
"""

import os
import sys
import numpy as np

# Указываем Qt, где искать плагины (обход ошибки "xcb" в Ubuntu)
import PyQt5
pyqt_plugins = os.path.join(os.path.dirname(PyQt5.__file__), "Qt5", "plugins")
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = pyqt_plugins

# Импортируем GUI-компоненты
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QGridLayout
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt

# Графика и обработка изображений
import pyqtgraph as pg
import imageio  # Для загрузки изображений (JPG, PNG и др.)

# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
# замените на путь к вашему файлу, например: "/home/user/photo.jpg"
IMAGE_PATH = "/home/van_rossum/Документы/PyQtGraph/insta6x6tg3.jpg"  
# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

class ImageAnalysisWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Анализ изображения")
        self.setGeometry(100, 100, 900, 600)

        # Опционально: иконка окна (если файл skin.png есть)
        # self.setWindowIcon(QIcon("skin.png"))

        # Загружаем и подготавливаем изображение
        self.load_image()
        # Создаём интерфейс
        self.setup_ui()
        # Показываем окно
        self.show()

    def load_image(self):
        """Загружает изображение и конвертирует его в 2D массив яркости (float32)."""
        try:
            raw_img = imageio.imread(IMAGE_PATH)
        except Exception as e:
            print(f"❌ Ошибка загрузки изображения '{IMAGE_PATH}': {e}")
            print("Проверьте путь к файлу и наличие библиотеки imageio.")
            sys.exit(1)

        # Если изображение цветное (3 канала: RGB), конвертируем в оттенки серого
        if raw_img.ndim == 3:
            # Формула яркости по стандарту ITU-R BT.601
            gray = np.dot(raw_img[..., :3], [0.2989, 0.5870, 0.1140])
        else:
            # Уже чёрно-белое
            gray = raw_img.astype(np.float64)

        # Приводим к типу float32 — так лучше работает pyqtgraph
        self.image_data = gray.astype(np.float32)

    def setup_ui(self):
        """Создаёт графический интерфейс."""
        # Главный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Сетка для размещения элементов
        layout = QGridLayout()
        central_widget.setLayout(layout)

        # Метка с заголовком
        title_label = QLabel("Анализ изображения")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setWordWrap(True)
        layout.addWidget(title_label, 0, 0)

        # Окно для графиков (изображение + гистограмма + профиль)
        plot_widget = pg.GraphicsLayoutWidget()
        layout.addWidget(plot_widget, 1, 0, 1, 2)  # занимает 1 строку, 2 столбца

        # === Верхняя часть: изображение ===
        image_plot = plot_widget.addPlot(title="Изображение")
        image_plot.setAspectLocked(True)  # сохраняем пропорции

        # Отображаем изображение
        self.image_item = pg.ImageItem()
        image_plot.addItem(self.image_item)
        self.image_item.setImage(self.image_data)

        # ROI — прямоугольник для выделения области
        self.roi = pg.ROI([10, 10], [50, 50])  # начальный размер и позиция
        self.roi.addScaleHandle([1, 1], [0, 0])  # ручка для масштабирования
        image_plot.addItem(self.roi)
        self.roi.setZValue(10)  # рисуем ROI поверх изображения

        # Гистограмма и управление контрастом
        self.hist = pg.HistogramLUTItem()
        self.hist.setImageItem(self.image_item)
        plot_widget.addItem(self.hist)

        # Линия для управления уровнем изокривой
        self.iso_line = pg.InfiniteLine(angle=0, movable=True, pen='r')
        self.hist.vb.addItem(self.iso_line)
        self.hist.vb.setMouseEnabled(y=False)  # нельзя двигать гистограмму по Y
        self.iso_line.setValue(self.image_data.min() + (self.image_data.max() - self.image_data.min()) * 0.6)

        # Изокривая (линии одинаковой яркости)
        self.iso_curve = pg.IsocurveItem(level=self.iso_line.value(), pen='g')
        self.iso_curve.setParentItem(self.image_item)
        self.iso_curve.setZValue(5)

        # === Нижняя часть: профиль яркости по выделенной области ===
        plot_widget.nextRow()
        self.profile_plot = plot_widget.addPlot(title="Профиль яркости (среднее по строкам ROI)", colspan=2)
        self.profile_plot.setMaximumHeight(150)

        # === Подключаем обработчики событий ===
        self.roi.sigRegionChanged.connect(self.update_profile)
        self.iso_line.sigDragged.connect(self.update_isocurve)

        # Обновляем всё при старте
        self.update_profile()
        self.update_isocurve()

        # Подсказка под курсором: координаты и яркость
        def hover_event(event):
            if event.isExit():
                image_plot.setTitle("Изображение")
                return

            pos = event.pos()
            i, j = int(pos.y()), int(pos.x())

            # Проверяем границы
            if 0 <= i < self.image_data.shape[0] and 0 <= j < self.image_data.shape[1]:
                value = self.image_data[i, j]
                # Переводим координаты в "мировые" (если изображение масштабировано)
                world_pos = self.image_item.mapToParent(pos)
                x, y = world_pos.x(), world_pos.y()
                image_plot.setTitle(f"Позиция: ({x:.1f}, {y:.1f}) | Пиксель: ({j}, {i}) | Яркость: {value:.2f}")
            else:
                image_plot.setTitle("Изображение")

        self.image_item.hoverEvent = hover_event

        # Автоматически подогнать масштаб под изображение
        image_plot.autoRange()

    def update_profile(self):
        """Обновляет график профиля яркости по выделенной области (ROI)."""
        # Получаем данные внутри ROI
        region_data = self.roi.getArrayRegion(self.image_data, self.image_item)
        if region_data is not None and region_data.size > 0:
            # Среднее по строкам → 1D профиль
            profile = np.mean(region_data, axis=0)
            self.profile_plot.plot(profile, clear=True, pen='y')
        else:
            self.profile_plot.clear()

    def update_isocurve(self):
        """Обновляет уровень изокривой при перемещении ползунка."""
        level = self.iso_line.value()
        self.iso_curve.setLevel(level)


# Запуск приложения
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ImageAnalysisWindow()
    sys.exit(app.exec())
