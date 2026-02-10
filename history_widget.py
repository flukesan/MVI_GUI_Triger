"""
History Widget for Dual Mode Inspection System
Displays inspection history with Product, Mode, Missing Parts columns
"""
import os
import json
from datetime import datetime, timedelta

try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
        QTableWidgetItem, QLabel, QComboBox, QDateEdit, QHeaderView,
        QDialog, QMessageBox, QFileDialog, QGroupBox
    )
    from PyQt6.QtCore import Qt, QDate
    from PyQt6.QtGui import QFont, QPixmap
except ImportError:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
        QTableWidgetItem, QLabel, QComboBox, QDateEdit, QHeaderView,
        QDialog, QMessageBox, QFileDialog, QGroupBox
    )
    from PySide6.QtCore import Qt, QDate
    from PySide6.QtGui import QFont, QPixmap

from history_manager import HistoryManager


class HistoryWidget(QWidget):
    """Widget for displaying and managing inspection history"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.history_manager = HistoryManager()
        self.current_page = 0
        self.page_size = 50
        self.init_ui()
        self.load_history()

    def init_ui(self):
        """Initialize UI components"""
        layout = QVBoxLayout(self)

        # === Statistics Panel ===
        stats_group = QGroupBox("Statistics")
        stats_layout = QHBoxLayout()

        self.stats_total_label = QLabel("Total: 0")
        self.stats_total_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))

        self.stats_pass_label = QLabel("PASS: 0")
        self.stats_pass_label.setStyleSheet("color: #28a745; font-weight: bold;")

        self.stats_fail_label = QLabel("FAIL: 0")
        self.stats_fail_label.setStyleSheet("color: #dc3545; font-weight: bold;")

        self.stats_today_label = QLabel("Today: 0")
        self.stats_today_label.setStyleSheet("color: #007bff; font-weight: bold;")

        stats_layout.addWidget(self.stats_total_label)
        stats_layout.addWidget(self.stats_pass_label)
        stats_layout.addWidget(self.stats_fail_label)
        stats_layout.addWidget(self.stats_today_label)
        stats_layout.addStretch()

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        # === Filters ===
        filter_group = QGroupBox("Filters")
        filter_layout = QHBoxLayout()

        # Date range
        filter_layout.addWidget(QLabel("From:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addDays(-30))
        filter_layout.addWidget(self.date_from)

        filter_layout.addWidget(QLabel("To:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        filter_layout.addWidget(self.date_to)

        # Product filter
        filter_layout.addWidget(QLabel("Product:"))
        self.product_combo = QComboBox()
        self.product_combo.addItem("All")
        filter_layout.addWidget(self.product_combo)

        # Result filter
        filter_layout.addWidget(QLabel("Result:"))
        self.result_combo = QComboBox()
        self.result_combo.addItems(["All", "pass", "fail"])
        filter_layout.addWidget(self.result_combo)

        # Mode filter
        filter_layout.addWidget(QLabel("Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["All", "capture", "realtime"])
        filter_layout.addWidget(self.mode_combo)

        # Search button
        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self.apply_filters)
        filter_layout.addWidget(self.search_btn)

        # Reset button
        self.reset_btn = QPushButton("Reset")
        self.reset_btn.clicked.connect(self.reset_filters)
        filter_layout.addWidget(self.reset_btn)

        filter_layout.addStretch()
        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        # === History Table ===
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Date", "Time", "Camera", "Product", "Result",
            "Found", "Missing", "Mode", "Actions"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 90)
        self.table.setColumnWidth(1, 70)
        self.table.setColumnWidth(5, 70)
        self.table.setColumnWidth(7, 70)
        self.table.setColumnWidth(8, 80)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        # === Pagination ===
        pagination_layout = QHBoxLayout()

        self.prev_btn = QPushButton("Prev")
        self.prev_btn.clicked.connect(self.prev_page)
        pagination_layout.addWidget(self.prev_btn)

        self.page_label = QLabel("Page 1")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pagination_layout.addWidget(self.page_label)

        self.next_btn = QPushButton("Next")
        self.next_btn.clicked.connect(self.next_page)
        pagination_layout.addWidget(self.next_btn)

        pagination_layout.addStretch()

        self.export_btn = QPushButton("Export CSV")
        self.export_btn.clicked.connect(self.export_csv)
        pagination_layout.addWidget(self.export_btn)

        self.cleanup_btn = QPushButton("Clean Old (>30 days)")
        self.cleanup_btn.clicked.connect(self.cleanup_old)
        pagination_layout.addWidget(self.cleanup_btn)

        layout.addLayout(pagination_layout)

    def load_history(self):
        """Load history from database"""
        product_name = None if self.product_combo.currentText() == "All" else self.product_combo.currentText()
        result = None if self.result_combo.currentText() == "All" else self.result_combo.currentText()
        mode = None if self.mode_combo.currentText() == "All" else self.mode_combo.currentText()
        date_from = self.date_from.date().toString("yyyy-MM-dd")
        date_to = self.date_to.date().toString("yyyy-MM-dd")

        records = self.history_manager.get_inspections(
            limit=self.page_size,
            offset=self.current_page * self.page_size,
            product_name=product_name,
            result=result,
            mode=mode,
            date_from=date_from,
            date_to=date_to
        )

        total_count = self.history_manager.get_total_count(
            product_name=product_name,
            result=result,
            mode=mode,
            date_from=date_from,
            date_to=date_to
        )

        self.table.setRowCount(len(records))
        for row, record in enumerate(records):
            timestamp = record.get("timestamp", "")
            if " " in timestamp:
                date_str, time_str = timestamp.split(" ", 1)
            else:
                date_str, time_str = "", timestamp

            # Date
            self.table.setItem(row, 0, QTableWidgetItem(date_str))

            # Time
            self.table.setItem(row, 1, QTableWidgetItem(time_str))

            # Camera
            self.table.setItem(row, 2, QTableWidgetItem(record.get("camera_id", "-") or "-"))

            # Product
            self.table.setItem(row, 3, QTableWidgetItem(record.get("product_name", "-") or "-"))

            # Result
            result_val = record.get("result", "")
            result_item = QTableWidgetItem(result_val.upper())
            if result_val == "pass":
                result_item.setForeground(Qt.GlobalColor.darkGreen)
            elif result_val == "fail":
                result_item.setForeground(Qt.GlobalColor.red)
            self.table.setItem(row, 4, result_item)

            # Found count
            found = record.get("found_count", 0)
            total = record.get("total_expected", 0)
            found_text = f"{found}/{total}" if total > 0 else str(found)
            self.table.setItem(row, 5, QTableWidgetItem(found_text))

            # Missing parts
            missing = record.get("missing_parts", "[]")
            if isinstance(missing, str):
                try:
                    missing_list = json.loads(missing)
                except (json.JSONDecodeError, TypeError):
                    missing_list = []
            else:
                missing_list = missing if missing else []
            missing_text = ", ".join(missing_list) if missing_list else "-"
            if len(missing_text) > 30:
                missing_text = missing_text[:27] + "..."
            self.table.setItem(row, 6, QTableWidgetItem(missing_text))

            # Mode
            self.table.setItem(row, 7, QTableWidgetItem(record.get("mode", "-") or "-"))

            # Actions
            view_btn = QPushButton("View")
            view_btn.clicked.connect(lambda checked, r=record: self.view_detail(r))
            self.table.setCellWidget(row, 8, view_btn)

        # Update pagination
        total_pages = max(1, (total_count + self.page_size - 1) // self.page_size)
        self.page_label.setText(f"Page {self.current_page + 1} of {total_pages}")
        self.prev_btn.setEnabled(self.current_page > 0)
        self.next_btn.setEnabled((self.current_page + 1) * self.page_size < total_count)

        self.update_statistics()
        self.update_product_combo()

    def update_statistics(self):
        """Update statistics labels"""
        stats = self.history_manager.get_statistics()
        self.stats_total_label.setText(f"Total: {stats['total']}")
        self.stats_pass_label.setText(f"PASS: {stats['pass']}")
        self.stats_fail_label.setText(f"FAIL: {stats['fail']}")
        self.stats_today_label.setText(f"Today: {stats['today']}")

    def update_product_combo(self):
        """Update product combo with available products"""
        stats = self.history_manager.get_statistics()
        current = self.product_combo.currentText()

        self.product_combo.clear()
        self.product_combo.addItem("All")

        for product in stats.get("products", {}).keys():
            if product:
                self.product_combo.addItem(product)

        index = self.product_combo.findText(current)
        if index >= 0:
            self.product_combo.setCurrentIndex(index)

    def apply_filters(self):
        self.current_page = 0
        self.load_history()

    def reset_filters(self):
        self.date_from.setDate(QDate.currentDate().addDays(-30))
        self.date_to.setDate(QDate.currentDate())
        self.product_combo.setCurrentIndex(0)
        self.result_combo.setCurrentIndex(0)
        self.mode_combo.setCurrentIndex(0)
        self.current_page = 0
        self.load_history()

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.load_history()

    def next_page(self):
        self.current_page += 1
        self.load_history()

    def view_detail(self, record):
        dialog = HistoryDetailDialog(record, self)
        dialog.exec()

    def export_csv(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export to CSV",
            f"inspection_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV Files (*.csv)"
        )
        if not filepath:
            return

        product_name = None if self.product_combo.currentText() == "All" else self.product_combo.currentText()
        result = None if self.result_combo.currentText() == "All" else self.result_combo.currentText()
        mode = None if self.mode_combo.currentText() == "All" else self.mode_combo.currentText()
        date_from = self.date_from.date().toString("yyyy-MM-dd")
        date_to = self.date_to.date().toString("yyyy-MM-dd")

        count = self.history_manager.export_to_csv(
            filepath,
            product_name=product_name,
            result=result,
            mode=mode,
            date_from=date_from,
            date_to=date_to
        )
        QMessageBox.information(self, "Export Complete", f"Exported {count} records to:\n{filepath}")

    def cleanup_old(self):
        reply = QMessageBox.question(
            self, "Confirm Cleanup",
            "Delete all records older than 30 days?\nThis will also delete associated images.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            count = self.history_manager.cleanup_old_records(days=30)
            QMessageBox.information(self, "Cleanup Complete", f"Deleted {count} old records")
            self.load_history()


class HistoryDetailDialog(QDialog):
    """Dialog for showing detailed inspection information"""

    def __init__(self, record, parent=None):
        super().__init__(parent)
        self.record = record
        self.setWindowTitle(f"Inspection Detail - ID: {record.get('id', '?')}")
        self.setMinimumSize(900, 600)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        content_layout = QHBoxLayout()

        # === Image ===
        image_layout = QVBoxLayout()
        image_label = QLabel()
        image_path = self.record.get("image_path", "")
        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            scaled = pixmap.scaled(
                500, 400,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            image_label.setPixmap(scaled)
        else:
            image_label.setText("Image not available")
            image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            image_label.setStyleSheet("QLabel { background-color: #e9ecef; padding: 40px; }")

        image_layout.addWidget(image_label)
        content_layout.addLayout(image_layout, 1)

        # === Metadata ===
        metadata_layout = QVBoxLayout()

        result_val = self.record.get("result", "unknown").upper()
        if self.record.get("result") == "pass":
            result_html = f'<span style="color: #28a745; font-weight: bold;">PASS</span>'
        elif self.record.get("result") == "fail":
            result_html = f'<span style="color: #dc3545; font-weight: bold;">FAIL</span>'
        else:
            result_html = result_val

        # Missing parts
        missing = self.record.get("missing_parts", "[]")
        if isinstance(missing, str):
            try:
                missing_list = json.loads(missing)
            except (json.JSONDecodeError, TypeError):
                missing_list = []
        else:
            missing_list = missing if missing else []
        missing_text = ", ".join(missing_list) if missing_list else "None"

        found = self.record.get("found_count", 0)
        total = self.record.get("total_expected", 0)
        inf_time = self.record.get("inference_time_ms", 0)

        info_text = f"""
<b>Time:</b> {self.record.get('timestamp', '-')}<br>
<b>Camera:</b> {self.record.get('camera_id', '-') or '-'}<br>
<b>Product:</b> {self.record.get('product_name', '-') or '-'}<br>
<b>Mode:</b> {self.record.get('mode', '-') or '-'}<br>
<b>Result:</b> {result_html}<br>
<br>
<b>Found:</b> {found}/{total}<br>
<b>Missing:</b> {missing_text}<br>
<b>Inference:</b> {inf_time:.1f} ms<br>
        """

        info_label = QLabel(info_text)
        info_label.setWordWrap(True)
        info_label.setTextFormat(Qt.TextFormat.RichText)
        info_label.setStyleSheet("""
            QLabel {
                background-color: #f8f9fa;
                padding: 15px;
                border: 1px solid #dee2e6;
                border-radius: 5px;
            }
        """)

        metadata_layout.addWidget(info_label)
        metadata_layout.addStretch()
        content_layout.addLayout(metadata_layout, 1)

        layout.addLayout(content_layout)

        # === Buttons ===
        button_layout = QHBoxLayout()

        if image_path and os.path.exists(image_path):
            save_img_btn = QPushButton("Save Image")
            save_img_btn.clicked.connect(self.save_image)
            button_layout.addWidget(save_img_btn)

        export_json_btn = QPushButton("Export JSON")
        export_json_btn.clicked.connect(self.export_json)
        button_layout.addWidget(export_json_btn)

        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def save_image(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Image",
            f"inspection_{self.record.get('id', 0)}.jpg",
            "JPEG Images (*.jpg)"
        )
        if filepath and self.record.get("image_path"):
            import shutil
            shutil.copy2(self.record["image_path"], filepath)
            QMessageBox.information(self, "Saved", f"Image saved to:\n{filepath}")

    def export_json(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export JSON",
            f"inspection_{self.record.get('id', 0)}.json",
            "JSON Files (*.json)"
        )
        if filepath:
            json_data = self.record.get("json_data", "{}")
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(json_data)
            QMessageBox.information(self, "Exported", f"JSON exported to:\n{filepath}")
