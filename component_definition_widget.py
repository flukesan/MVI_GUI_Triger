"""
Component Definition Widget
GUI สำหรับจัดการ Component Definitions

Features:
- Product management (create, edit, delete)
- Component definition setup
- ROI selection on image
- Visual preview
- Configuration import/export
"""

import os
import cv2
import numpy as np
from pathlib import Path

try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
        QLineEdit, QComboBox, QGroupBox, QGridLayout, QTableWidget,
        QTableWidgetItem, QMessageBox, QFileDialog, QSpinBox,
        QDoubleSpinBox, QCheckBox, QTextEdit, QSplitter, QFrame
    )
    from PyQt6.QtCore import Qt, QPoint, QRect
    from PyQt6.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QFont
except ImportError:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
        QLineEdit, QComboBox, QGroupBox, QGridLayout, QTableWidget,
        QTableWidgetItem, QMessageBox, QFileDialog, QSpinBox,
        QDoubleSpinBox, QCheckBox, QTextEdit, QSplitter, QFrame
    )
    from PySide6.QtCore import Qt, QPoint, QRect
    from PySide6.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QFont

from component_definition import ComponentDefinitionManager


class ImageROISelector(QLabel):
    """Widget สำหรับเลือก ROI บนภาพ"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(600, 400)
        self.setStyleSheet("border: 2px solid #cccccc; background-color: #f5f5f5;")

        self.original_pixmap = None
        self.drawing = False
        self.start_point = None
        self.current_rect = None
        self.rois = []  # List of {"name": str, "rect": QRect, "color": QColor}
        self.selected_roi_index = None

    def load_image(self, image_path):
        """โหลดภาพ"""
        self.original_pixmap = QPixmap(image_path)
        self.update_display()

    def update_display(self):
        """อัพเดทการแสดงผล"""
        if self.original_pixmap:
            # Scale to fit widget
            scaled = self.original_pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            # Draw ROIs
            painter = QPainter(scaled)

            # Draw existing ROIs
            for i, roi in enumerate(self.rois):
                color = roi["color"]
                if i == self.selected_roi_index:
                    pen = QPen(color, 3)
                else:
                    pen = QPen(color, 2)
                painter.setPen(pen)
                painter.drawRect(roi["rect"])

                # Draw label
                painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
                painter.drawText(
                    roi["rect"].topLeft() + QPoint(5, -5),
                    roi["name"]
                )

            # Draw current drawing rect
            if self.drawing and self.current_rect:
                pen = QPen(QColor(255, 0, 0), 2, Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.drawRect(self.current_rect)

            painter.end()
            self.setPixmap(scaled)
        else:
            self.setText("📷 โหลดภาพ Golden Template\n(คลิก 'Browse...' ด้านล่าง)")

    def mousePressEvent(self, event):
        """เริ่มวาด ROI"""
        if self.original_pixmap and event.button() == Qt.MouseButton.LeftButton:
            self.drawing = True
            self.start_point = event.pos()
            self.current_rect = QRect(self.start_point, self.start_point)

    def mouseMoveEvent(self, event):
        """วาด ROI ขณะเลื่อนเมาส์"""
        if self.drawing:
            self.current_rect = QRect(self.start_point, event.pos()).normalized()
            self.update_display()

    def mouseReleaseEvent(self, event):
        """จบการวาด ROI"""
        if self.drawing and event.button() == Qt.MouseButton.LeftButton:
            self.drawing = False
            # ROI will be added via add_roi() method called from parent

    def add_roi(self, name, rect, color):
        """เพิ่ม ROI"""
        self.rois.append({"name": name, "rect": rect, "color": color})
        self.current_rect = None
        self.update_display()

    def get_current_rect(self):
        """ดึง rect ปัจจุบัน"""
        return self.current_rect

    def clear_current_rect(self):
        """ล้าง rect ปัจจุบัน"""
        self.current_rect = None
        self.update_display()

    def remove_roi(self, index):
        """ลบ ROI"""
        if 0 <= index < len(self.rois):
            del self.rois[index]
            if self.selected_roi_index == index:
                self.selected_roi_index = None
            self.update_display()

    def select_roi(self, index):
        """เลือก ROI"""
        self.selected_roi_index = index
        self.update_display()

    def clear_all_rois(self):
        """ล้าง ROI ทั้งหมด"""
        self.rois = []
        self.selected_roi_index = None
        self.update_display()


class ComponentDefinitionWidget(QWidget):
    """Widget หลักสำหรับ Component Definition"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.comp_manager = ComponentDefinitionManager()
        self.current_product_id = None
        self.golden_template_path = None

        self.init_ui()
        self.load_products()

    def init_ui(self):
        """สร้าง UI"""
        main_layout = QVBoxLayout()

        # Header
        header = QLabel("📋 Component Definition Manager")
        header.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        header.setStyleSheet("color: #2c3e50; padding: 10px;")
        main_layout.addWidget(header)

        # Splitter for left/right panels
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel - Image & ROI selector
        left_panel = self.create_image_panel()
        splitter.addWidget(left_panel)

        # Right panel - Product & Component management
        right_panel = self.create_management_panel()
        splitter.addWidget(right_panel)

        splitter.setSizes([600, 400])
        main_layout.addWidget(splitter)

        self.setLayout(main_layout)

    def create_image_panel(self):
        """สร้าง panel ด้านซ้าย (ภาพและ ROI)"""
        panel = QWidget()
        layout = QVBoxLayout()

        # Golden Template section
        template_group = QGroupBox("Golden Template")
        template_layout = QVBoxLayout()

        # Image display
        self.image_selector = ImageROISelector()
        template_layout.addWidget(self.image_selector)

        # Browse button
        browse_layout = QHBoxLayout()
        self.template_path_label = QLabel("ยังไม่ได้เลือกภาพ")
        browse_btn = QPushButton("📁 Browse...")
        browse_btn.clicked.connect(self.browse_golden_template)
        browse_layout.addWidget(self.template_path_label)
        browse_layout.addWidget(browse_btn)
        template_layout.addLayout(browse_layout)

        template_group.setLayout(template_layout)
        layout.addWidget(template_group)

        # ROI drawing instructions
        instructions = QLabel(
            "💡 วิธีใช้:\n"
            "1. โหลด Golden Template\n"
            "2. กรอกชื่อ component\n"
            "3. คลิกและลาก เพื่อวาด ROI บนภาพ\n"
            "4. คลิก 'Add Component'"
        )
        instructions.setStyleSheet("background-color: #e8f4f8; padding: 10px; border-radius: 5px;")
        layout.addWidget(instructions)

        panel.setLayout(layout)
        return panel

    def create_management_panel(self):
        """สร้าง panel ด้านขวา (จัดการ Product & Components)"""
        panel = QWidget()
        layout = QVBoxLayout()

        # Product section
        product_group = QGroupBox("Product")
        product_layout = QGridLayout()

        # Product selector
        product_layout.addWidget(QLabel("Product:"), 0, 0)
        self.product_combo = QComboBox()
        self.product_combo.currentIndexChanged.connect(self.on_product_changed)
        product_layout.addWidget(self.product_combo, 0, 1)

        # New product button
        new_product_btn = QPushButton("➕ New")
        new_product_btn.clicked.connect(self.create_new_product)
        product_layout.addWidget(new_product_btn, 0, 2)

        # Product name
        product_layout.addWidget(QLabel("Name:"), 1, 0)
        self.product_name_input = QLineEdit()
        product_layout.addWidget(self.product_name_input, 1, 1, 1, 2)

        # Pass threshold
        product_layout.addWidget(QLabel("Pass Threshold:"), 2, 0)
        self.pass_threshold_input = QDoubleSpinBox()
        self.pass_threshold_input.setRange(0.0, 1.0)
        self.pass_threshold_input.setSingleStep(0.1)
        self.pass_threshold_input.setValue(1.0)
        self.pass_threshold_input.setSuffix(" (100% = ต้องครบ)")
        product_layout.addWidget(self.pass_threshold_input, 2, 1, 1, 2)

        product_group.setLayout(product_layout)
        layout.addWidget(product_group)

        # Component section
        component_group = QGroupBox("Component Definition")
        component_layout = QVBoxLayout()

        # Component input form
        form_layout = QGridLayout()

        # Component name
        form_layout.addWidget(QLabel("Name:"), 0, 0)
        self.comp_name_input = QLineEdit()
        self.comp_name_input.setPlaceholderText("เช่น pig, monk, peacock")
        form_layout.addWidget(self.comp_name_input, 0, 1)

        # Position label
        form_layout.addWidget(QLabel("Position:"), 1, 0)
        self.comp_position_input = QLineEdit()
        self.comp_position_input.setPlaceholderText("เช่น left, center, right")
        form_layout.addWidget(self.comp_position_input, 1, 1)

        # Type
        form_layout.addWidget(QLabel("Type:"), 2, 0)
        self.comp_type_combo = QComboBox()
        self.comp_type_combo.addItems(["object", "circle", "rectangle", "custom"])
        form_layout.addWidget(self.comp_type_combo, 2, 1)

        # Tolerance
        form_layout.addWidget(QLabel("Tolerance:"), 3, 0)
        self.tolerance_input = QSpinBox()
        self.tolerance_input.setRange(10, 200)
        self.tolerance_input.setValue(50)
        self.tolerance_input.setSuffix(" pixels")
        form_layout.addWidget(self.tolerance_input, 3, 1)

        # Min confidence
        form_layout.addWidget(QLabel("Min Confidence:"), 4, 0)
        self.confidence_input = QDoubleSpinBox()
        self.confidence_input.setRange(0.0, 1.0)
        self.confidence_input.setSingleStep(0.05)
        self.confidence_input.setValue(0.8)
        form_layout.addWidget(self.confidence_input, 4, 1)

        # Critical
        self.critical_checkbox = QCheckBox("Critical (ต้องมีเสมอ)")
        self.critical_checkbox.setChecked(True)
        form_layout.addWidget(self.critical_checkbox, 5, 0, 1, 2)

        component_layout.addLayout(form_layout)

        # Add component button
        add_comp_btn = QPushButton("➕ Add Component")
        add_comp_btn.clicked.connect(self.add_component)
        add_comp_btn.setStyleSheet("background-color: #27ae60; color: white; padding: 8px; font-weight: bold;")
        component_layout.addWidget(add_comp_btn)

        component_group.setLayout(component_layout)
        layout.addWidget(component_group)

        # Components table
        table_group = QGroupBox("Components List")
        table_layout = QVBoxLayout()

        self.components_table = QTableWidget()
        self.components_table.setColumnCount(6)
        self.components_table.setHorizontalHeaderLabels([
            "Name", "Position", "Type", "Tolerance", "Confidence", "Critical"
        ])
        self.components_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table_layout.addWidget(self.components_table)

        # Table buttons
        table_btn_layout = QHBoxLayout()
        remove_btn = QPushButton("🗑️ Remove")
        remove_btn.clicked.connect(self.remove_component)
        table_btn_layout.addWidget(remove_btn)

        clear_btn = QPushButton("🧹 Clear All")
        clear_btn.clicked.connect(self.clear_all_components)
        table_btn_layout.addWidget(clear_btn)

        table_layout.addLayout(table_btn_layout)
        table_group.setLayout(table_layout)
        layout.addWidget(table_group)

        # Action buttons
        action_layout = QHBoxLayout()

        save_btn = QPushButton("💾 Save Product")
        save_btn.clicked.connect(self.save_product)
        save_btn.setStyleSheet("background-color: #3498db; color: white; padding: 10px; font-weight: bold;")
        action_layout.addWidget(save_btn)

        export_btn = QPushButton("📤 Export Config")
        export_btn.clicked.connect(self.export_config)
        action_layout.addWidget(export_btn)

        import_btn = QPushButton("📥 Import Config")
        import_btn.clicked.connect(self.import_config)
        action_layout.addWidget(import_btn)

        layout.addLayout(action_layout)

        panel.setLayout(layout)
        return panel

    def browse_golden_template(self):
        """เลือกไฟล์ Golden Template"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Golden Template Image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp)"
        )

        if file_path:
            self.golden_template_path = file_path
            self.template_path_label.setText(os.path.basename(file_path))
            self.image_selector.load_image(file_path)

    def load_products(self):
        """โหลดรายการ Products"""
        self.product_combo.clear()
        self.product_combo.addItem("-- Select Product --", None)

        products = self.comp_manager.list_products()
        for product in products:
            self.product_combo.addItem(
                f"{product['name']} ({product['component_count']} components)",
                product['id']
            )

    def on_product_changed(self, index):
        """เมื่อเปลี่ยน Product"""
        product_id = self.product_combo.currentData()

        if product_id:
            self.current_product_id = product_id
            self.load_product_data(product_id)
        else:
            self.current_product_id = None
            self.clear_form()

    def load_product_data(self, product_id):
        """โหลดข้อมูล Product"""
        product = self.comp_manager.get_product(product_id)
        if product:
            self.product_name_input.setText(product['name'])
            self.pass_threshold_input.setValue(product['pass_threshold'])

            # Load golden template if exists
            if product['golden_template_path'] and os.path.exists(product['golden_template_path']):
                self.golden_template_path = product['golden_template_path']
                self.template_path_label.setText(os.path.basename(self.golden_template_path))
                self.image_selector.load_image(self.golden_template_path)

            # Load components
            self.load_components(product_id)

    def load_components(self, product_id):
        """โหลด Components"""
        components = self.comp_manager.get_product_components(product_id)

        self.components_table.setRowCount(len(components))
        self.image_selector.clear_all_rois()

        colors = [
            QColor(0, 255, 0),    # Green
            QColor(0, 0, 255),    # Blue
            QColor(255, 165, 0),  # Orange
            QColor(255, 0, 255),  # Magenta
            QColor(0, 255, 255),  # Cyan
        ]

        for i, comp in enumerate(components):
            self.components_table.setItem(i, 0, QTableWidgetItem(comp['name']))
            self.components_table.setItem(i, 1, QTableWidgetItem(comp.get('position', '')))
            self.components_table.setItem(i, 2, QTableWidgetItem(comp['type']))
            self.components_table.setItem(i, 3, QTableWidgetItem(str(comp.get('tolerance', 50))))
            self.components_table.setItem(i, 4, QTableWidgetItem(f"{comp['min_confidence']:.2f}"))
            self.components_table.setItem(i, 5, QTableWidgetItem("✓" if comp['critical'] else ""))

            # Add ROI to image
            roi = comp['roi']
            rect = QRect(roi['x'], roi['y'], roi['width'], roi['height'])
            color = colors[i % len(colors)]
            self.image_selector.add_roi(comp['name'], rect, color)

    def create_new_product(self):
        """สร้าง Product ใหม่"""
        self.current_product_id = None
        self.clear_form()
        self.product_name_input.setFocus()

    def clear_form(self):
        """ล้างฟอร์ม"""
        self.product_name_input.clear()
        self.pass_threshold_input.setValue(1.0)
        self.comp_name_input.clear()
        self.comp_position_input.clear()
        self.tolerance_input.setValue(50)
        self.confidence_input.setValue(0.8)
        self.critical_checkbox.setChecked(True)
        self.components_table.setRowCount(0)
        self.image_selector.clear_all_rois()
        self.golden_template_path = None
        self.template_path_label.setText("ยังไม่ได้เลือกภาพ")

    def add_component(self):
        """เพิ่ม Component"""
        name = self.comp_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Warning", "กรุณากรอกชื่อ component")
            return

        # Get ROI from image selector
        rect = self.image_selector.get_current_rect()
        if not rect or rect.width() < 10 or rect.height() < 10:
            QMessageBox.warning(
                self,
                "Warning",
                "กรุณาวาด ROI บนภาพ\n(คลิกและลากเพื่อสร้าง ROI)"
            )
            return

        # Add to table
        row = self.components_table.rowCount()
        self.components_table.insertRow(row)

        position = self.comp_position_input.text().strip()
        comp_type = self.comp_type_combo.currentText()
        tolerance = self.tolerance_input.value()
        confidence = self.confidence_input.value()
        critical = self.critical_checkbox.isChecked()

        self.components_table.setItem(row, 0, QTableWidgetItem(name))
        self.components_table.setItem(row, 1, QTableWidgetItem(position))
        self.components_table.setItem(row, 2, QTableWidgetItem(comp_type))
        self.components_table.setItem(row, 3, QTableWidgetItem(str(tolerance)))
        self.components_table.setItem(row, 4, QTableWidgetItem(f"{confidence:.2f}"))
        self.components_table.setItem(row, 5, QTableWidgetItem("✓" if critical else ""))

        # Add ROI to image
        colors = [
            QColor(0, 255, 0), QColor(0, 0, 255), QColor(255, 165, 0),
            QColor(255, 0, 255), QColor(0, 255, 255)
        ]
        color = colors[row % len(colors)]
        self.image_selector.add_roi(name, rect, color)

        # Clear inputs
        self.comp_name_input.clear()
        self.comp_position_input.clear()
        self.image_selector.clear_current_rect()

        QMessageBox.information(self, "Success", f"เพิ่ม component '{name}' แล้ว")

    def remove_component(self):
        """ลบ Component ที่เลือก"""
        current_row = self.components_table.currentRow()
        if current_row >= 0:
            name = self.components_table.item(current_row, 0).text()
            reply = QMessageBox.question(
                self,
                "Confirm",
                f"ต้องการลบ component '{name}' หรือไม่?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.components_table.removeRow(current_row)
                self.image_selector.remove_roi(current_row)
                QMessageBox.information(self, "Success", "ลบ component แล้ว")
        else:
            QMessageBox.warning(self, "Warning", "กรุณาเลือก component ที่ต้องการลบ")

    def clear_all_components(self):
        """ล้าง Components ทั้งหมด"""
        if self.components_table.rowCount() > 0:
            reply = QMessageBox.question(
                self,
                "Confirm",
                "ต้องการลบ components ทั้งหมดหรือไม่?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.components_table.setRowCount(0)
                self.image_selector.clear_all_rois()
                QMessageBox.information(self, "Success", "ล้าง components แล้ว")

    def save_product(self):
        """บันทึก Product และ Components"""
        product_name = self.product_name_input.text().strip()
        if not product_name:
            QMessageBox.warning(self, "Warning", "กรุณากรอกชื่อ product")
            return

        if self.components_table.rowCount() == 0:
            QMessageBox.warning(self, "Warning", "กรุณาเพิ่ม components อย่างน้อย 1 ชิ้น")
            return

        try:
            # Create or update product
            if self.current_product_id:
                # Update existing
                self.comp_manager.update_product(
                    self.current_product_id,
                    name=product_name,
                    golden_template_path=self.golden_template_path or "",
                    pass_threshold=self.pass_threshold_input.value()
                )
                product_id = self.current_product_id

                # Delete old components (will recreate)
                # TODO: Implement update instead of delete+create

            else:
                # Create new
                product_id = self.comp_manager.create_product(
                    name=product_name,
                    golden_template_path=self.golden_template_path or "",
                    pass_threshold=self.pass_threshold_input.value()
                )

            # Add components
            for row in range(self.components_table.rowCount()):
                name = self.components_table.item(row, 0).text()
                position = self.components_table.item(row, 1).text()
                comp_type = self.components_table.item(row, 2).text()
                tolerance = int(self.components_table.item(row, 3).text())
                confidence = float(self.components_table.item(row, 4).text())
                critical = self.components_table.item(row, 5).text() == "✓"

                # Get ROI from image
                roi_data = self.image_selector.rois[row]
                rect = roi_data["rect"]

                self.comp_manager.add_component_definition(
                    product_id=product_id,
                    component_name=name,
                    component_type=comp_type,
                    roi={
                        "x": rect.x(),
                        "y": rect.y(),
                        "width": rect.width(),
                        "height": rect.height()
                    },
                    position_label=position,
                    tolerance=tolerance,
                    min_confidence=confidence,
                    is_critical=critical
                )

            QMessageBox.information(
                self,
                "Success",
                f"บันทึก product '{product_name}' แล้ว\n"
                f"Components: {self.components_table.rowCount()} ชิ้น"
            )

            # Reload products list
            self.load_products()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"เกิดข้อผิดพลาด:\n{str(e)}")

    def export_config(self):
        """Export configuration"""
        if not self.current_product_id:
            QMessageBox.warning(self, "Warning", "กรุณาเลือก product ก่อน")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Configuration",
            f"product_{self.current_product_id}_config.json",
            "JSON Files (*.json)"
        )

        if file_path:
            try:
                self.comp_manager.export_product_config(self.current_product_id, file_path)
                QMessageBox.information(
                    self,
                    "Success",
                    f"Export config เรียบร้อยแล้ว:\n{file_path}"
                )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"เกิดข้อผิดพลาด:\n{str(e)}")

    def import_config(self):
        """Import configuration"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Configuration",
            "",
            "JSON Files (*.json)"
        )

        if file_path:
            try:
                product_id = self.comp_manager.import_product_config(file_path)
                QMessageBox.information(
                    self,
                    "Success",
                    f"Import config เรียบร้อยแล้ว\nProduct ID: {product_id}"
                )

                # Reload products
                self.load_products()

                # Select imported product
                for i in range(self.product_combo.count()):
                    if self.product_combo.itemData(i) == product_id:
                        self.product_combo.setCurrentIndex(i)
                        break

            except Exception as e:
                QMessageBox.critical(self, "Error", f"เกิดข้อผิดพลาด:\n{str(e)}")


# Example usage
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = ComponentDefinitionWidget()
    widget.setWindowTitle("Component Definition Manager")
    widget.resize(1200, 800)
    widget.show()
    sys.exit(app.exec())
