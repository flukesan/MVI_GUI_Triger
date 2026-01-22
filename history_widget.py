"""
History Widget for displaying inspection history
"""
import os
from datetime import datetime, timedelta

# Try to import PyQt6, fallback to PySide6
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
import json


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
        stats_group = QGroupBox("📊 Statistics")
        stats_layout = QHBoxLayout()

        self.stats_total_label = QLabel("Total: 0")
        self.stats_total_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))

        self.stats_pass_label = QLabel("✓ Pass: 0")
        self.stats_pass_label.setStyleSheet("color: #28a745; font-weight: bold;")

        self.stats_fail_label = QLabel("✗ Fail: 0")
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
        filter_group = QGroupBox("🔍 Filters")
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

        # Device filter
        filter_layout.addWidget(QLabel("Device:"))
        self.device_combo = QComboBox()
        self.device_combo.addItem("All")
        filter_layout.addWidget(self.device_combo)

        # Result filter
        filter_layout.addWidget(QLabel("Result:"))
        self.result_combo = QComboBox()
        self.result_combo.addItems(["All", "pass", "fail"])
        filter_layout.addWidget(self.result_combo)

        # Search button
        self.search_btn = QPushButton("🔍 Search")
        self.search_btn.clicked.connect(self.apply_filters)
        filter_layout.addWidget(self.search_btn)

        # Reset button
        self.reset_btn = QPushButton("🔄 Reset")
        self.reset_btn.clicked.connect(self.reset_filters)
        filter_layout.addWidget(self.reset_btn)

        filter_layout.addStretch()
        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        # === History Table ===
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Time", "Device", "Result", "Station", "Image ID", "Actions", "ID"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(5, 150)  # Actions column
        self.table.setColumnWidth(6, 60)   # ID column
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        # === Pagination ===
        pagination_layout = QHBoxLayout()

        self.prev_btn = QPushButton("◀ Prev")
        self.prev_btn.clicked.connect(self.prev_page)
        pagination_layout.addWidget(self.prev_btn)

        self.page_label = QLabel("Page 1")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pagination_layout.addWidget(self.page_label)

        self.next_btn = QPushButton("Next ▶")
        self.next_btn.clicked.connect(self.next_page)
        pagination_layout.addWidget(self.next_btn)

        pagination_layout.addStretch()

        # Export button
        self.export_btn = QPushButton("📄 Export CSV")
        self.export_btn.clicked.connect(self.export_csv)
        pagination_layout.addWidget(self.export_btn)

        # Cleanup button
        self.cleanup_btn = QPushButton("🗑️ Clean Old (>30 days)")
        self.cleanup_btn.clicked.connect(self.cleanup_old)
        pagination_layout.addWidget(self.cleanup_btn)

        layout.addLayout(pagination_layout)

    def load_history(self):
        """Load history from database"""
        # Get filters
        device_id = None if self.device_combo.currentText() == "All" else self.device_combo.currentText()
        result = None if self.result_combo.currentText() == "All" else self.result_combo.currentText()
        date_from = self.date_from.date().toString("yyyy-MM-dd")
        date_to = self.date_to.date().toString("yyyy-MM-dd")

        # Get records
        records = self.history_manager.get_inspections(
            limit=self.page_size,
            offset=self.current_page * self.page_size,
            device_id=device_id,
            result=result,
            date_from=date_from,
            date_to=date_to
        )

        # Get total count
        total_count = self.history_manager.get_total_count(
            device_id=device_id,
            result=result,
            date_from=date_from,
            date_to=date_to
        )

        # Update table
        self.table.setRowCount(len(records))
        for row, record in enumerate(records):
            # Time
            time_str = record["timestamp"].split()[1] if " " in record["timestamp"] else record["timestamp"]
            self.table.setItem(row, 0, QTableWidgetItem(time_str))

            # Device
            self.table.setItem(row, 1, QTableWidgetItem(record["device_id"] or "-"))

            # Result
            result_item = QTableWidgetItem(f"{record['result'].upper()}")
            if record["result"] == "pass":
                result_item.setForeground(Qt.GlobalColor.darkGreen)
            elif record["result"] == "fail":
                result_item.setForeground(Qt.GlobalColor.red)
            self.table.setItem(row, 2, result_item)

            # Station
            self.table.setItem(row, 3, QTableWidgetItem(record["station"] or "-"))

            # Image ID (truncated)
            image_id = record["image_id"] or "-"
            if len(image_id) > 15:
                image_id = image_id[:12] + "..."
            self.table.setItem(row, 4, QTableWidgetItem(image_id))

            # Actions - View button
            view_btn = QPushButton("👁️ View")
            view_btn.clicked.connect(lambda checked, r=record: self.view_detail(r))
            self.table.setCellWidget(row, 5, view_btn)

            # ID (hidden column for reference)
            self.table.setItem(row, 6, QTableWidgetItem(str(record["id"])))

        # Update pagination
        total_pages = (total_count + self.page_size - 1) // self.page_size
        self.page_label.setText(f"Page {self.current_page + 1} of {total_pages}")
        self.prev_btn.setEnabled(self.current_page > 0)
        self.next_btn.setEnabled((self.current_page + 1) * self.page_size < total_count)

        # Update statistics
        self.update_statistics()

        # Update device combo
        self.update_device_combo()

    def update_statistics(self):
        """Update statistics labels"""
        stats = self.history_manager.get_statistics()
        self.stats_total_label.setText(f"Total: {stats['total']}")
        self.stats_pass_label.setText(f"✓ Pass: {stats['pass']}")
        self.stats_fail_label.setText(f"✗ Fail: {stats['fail']}")
        self.stats_today_label.setText(f"Today: {stats['today']}")

    def update_device_combo(self):
        """Update device combo with available devices"""
        stats = self.history_manager.get_statistics()
        current_device = self.device_combo.currentText()

        self.device_combo.clear()
        self.device_combo.addItem("All")

        for device in stats["devices"].keys():
            if device:
                self.device_combo.addItem(device)

        # Restore selection
        index = self.device_combo.findText(current_device)
        if index >= 0:
            self.device_combo.setCurrentIndex(index)

    def apply_filters(self):
        """Apply filters and reload"""
        self.current_page = 0
        self.load_history()

    def reset_filters(self):
        """Reset all filters"""
        self.date_from.setDate(QDate.currentDate().addDays(-30))
        self.date_to.setDate(QDate.currentDate())
        self.device_combo.setCurrentIndex(0)
        self.result_combo.setCurrentIndex(0)
        self.current_page = 0
        self.load_history()

    def prev_page(self):
        """Go to previous page"""
        if self.current_page > 0:
            self.current_page -= 1
            self.load_history()

    def next_page(self):
        """Go to next page"""
        self.current_page += 1
        self.load_history()

    def view_detail(self, record):
        """View detailed information of a record"""
        dialog = HistoryDetailDialog(record, self)
        dialog.exec()

    def export_csv(self):
        """Export filtered results to CSV"""
        # Ask for file path
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export to CSV",
            f"inspection_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV Files (*.csv)"
        )

        if not filepath:
            return

        # Get filters
        device_id = None if self.device_combo.currentText() == "All" else self.device_combo.currentText()
        result = None if self.result_combo.currentText() == "All" else self.result_combo.currentText()
        date_from = self.date_from.date().toString("yyyy-MM-dd")
        date_to = self.date_to.date().toString("yyyy-MM-dd")

        # Export
        count = self.history_manager.export_to_csv(
            filepath,
            device_id=device_id,
            result=result,
            date_from=date_from,
            date_to=date_to
        )

        QMessageBox.information(self, "Export Complete", f"Exported {count} records to:\n{filepath}")

    def cleanup_old(self):
        """Cleanup old records (>30 days)"""
        reply = QMessageBox.question(
            self,
            "Confirm Cleanup",
            "Delete all records older than 30 days?\n\nThis will also delete associated images.",
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
        self.setWindowTitle(f"Inspection Detail - ID: {record['id']}")
        self.setMinimumSize(900, 600)
        self.init_ui()

    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)

        # Content layout: Image (left) + Metadata (right)
        content_layout = QHBoxLayout()

        # === Image ===
        image_layout = QVBoxLayout()

        image_label = QLabel()
        if self.record["image_path"] and os.path.exists(self.record["image_path"]):
            pixmap = QPixmap(self.record["image_path"])
            scaled_pixmap = pixmap.scaled(500, 400, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            image_label.setPixmap(scaled_pixmap)
        else:
            image_label.setText("Image not available")
            image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            image_label.setStyleSheet("QLabel { background-color: #e9ecef; padding: 40px; }")

        image_layout.addWidget(image_label)
        content_layout.addLayout(image_layout, 1)

        # === Metadata ===
        metadata_layout = QVBoxLayout()

        # Basic info
        info_text = f"""
<b>Time:</b> {self.record['timestamp']}<br>
<b>Device ID:</b> {self.record['device_id'] or '-'}<br>
<b>Image ID:</b> {self.record['image_id'] or '-'}<br>
<b>Station:</b> {self.record['station'] or '-'}<br>
<b>Inspection:</b> {self.record['inspection_name'] or '-'}<br>
        """

        # Result
        result_text = self.record["result"].upper()
        if self.record["result"] == "pass":
            info_text += f'<b>Result:</b> <span style="color: #28a745; font-weight: bold;">✓ {result_text}</span><br>'
        elif self.record["result"] == "fail":
            info_text += f'<b>Result:</b> <span style="color: #dc3545; font-weight: bold;">✗ {result_text}</span><br>'
        else:
            info_text += f"<b>Result:</b> {result_text}<br>"

        # Rule results
        if self.record["rule_results"]:
            try:
                rules = json.loads(self.record["rule_results"])
                info_text += "<br><b>Rule Results:</b><br>"
                for rule in rules:
                    rule_name = rule.get("Rule Name", "Unknown")
                    result_type = rule.get("Result Type", "unknown")
                    color = "#28a745" if result_type.lower() == "pass" else "#dc3545"
                    icon = "✓" if result_type.lower() == "pass" else "✗"
                    info_text += f'  <span style="color: {color};">{icon}</span> {rule_name}<br>'
            except:
                pass

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

        # Save image button
        if self.record["image_path"] and os.path.exists(self.record["image_path"]):
            save_img_btn = QPushButton("💾 Save Image")
            save_img_btn.clicked.connect(self.save_image)
            button_layout.addWidget(save_img_btn)

        # Export JSON button
        export_json_btn = QPushButton("📄 Export JSON")
        export_json_btn.clicked.connect(self.export_json)
        button_layout.addWidget(export_json_btn)

        button_layout.addStretch()

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def save_image(self):
        """Save image to user-selected location"""
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Image",
            f"inspection_{self.record['id']}.jpg",
            "JPEG Images (*.jpg)"
        )

        if filepath and self.record["image_path"]:
            import shutil
            shutil.copy2(self.record["image_path"], filepath)
            QMessageBox.information(self, "Saved", f"Image saved to:\n{filepath}")

    def export_json(self):
        """Export full JSON data"""
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export JSON",
            f"inspection_{self.record['id']}.json",
            "JSON Files (*.json)"
        )

        if filepath:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(self.record["json_data"])
            QMessageBox.information(self, "Exported", f"JSON exported to:\n{filepath}")
