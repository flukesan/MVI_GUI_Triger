"""
Test script for ROI coordinate fix
Tests ROI drawing with different image sizes
"""

import sys
import os
from pathlib import Path

try:
    from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont
except ImportError:
    from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont

from component_definition_widget import ComponentDefinitionWidget

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🧪 ROI Fix Test - ทดสอบการวาด ROI")
        self.setGeometry(100, 100, 1400, 900)

        # Main widget
        main_widget = QWidget()
        layout = QVBoxLayout()

        # Header
        header = QLabel("🧪 ROI Coordinate Fix Test")
        header.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: #2c3e50; padding: 10px; background-color: #ecf0f1;")
        layout.addWidget(header)

        # Instructions
        instructions = QLabel(
            "📝 วิธีทดสอบ:\n"
            "1. คลิก 'New' เพื่อสร้าง Product ใหม่\n"
            "2. กรอกชื่อ Product\n"
            "3. คลิก 'Browse...' เพื่อโหลดภาพ (ทดสอบทั้งภาพ 1 MB และ 3 MB)\n"
            "4. กรอกชื่อ Component\n"
            "5. วาด ROI บนภาพโดยคลิกและลาก\n"
            "6. ตรวจสอบว่า ROI ตรงกับจุดที่คลิกหรือไม่\n\n"
            "✅ ควรวาดได้ตรงจุดทั้งภาพเล็กและภาพใหญ่\n"
            "✅ ระบบจะปรับ offset อัตโนมัติเมื่อภาพ scale"
        )
        instructions.setStyleSheet(
            "background-color: #e8f4f8; padding: 15px; "
            "border-radius: 5px; border: 2px solid #3498db;"
        )
        layout.addWidget(instructions)

        # Component Definition Widget
        self.comp_def_widget = ComponentDefinitionWidget()
        layout.addWidget(self.comp_def_widget)

        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)

        print("\n" + "="*60)
        print("🧪 ROI FIX TEST")
        print("="*60)
        print("✅ Fix applied:")
        print("   - Added image_offset calculation")
        print("   - Added _widget_pos_to_image_pos() method")
        print("   - Updated mouse events to use coordinate transformation")
        print("\n📝 Test procedure:")
        print("   1. Load small image (1 MB) → draw ROI → should be accurate")
        print("   2. Load large image (3 MB) → draw ROI → should be accurate")
        print("="*60 + "\n")

def main():
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
