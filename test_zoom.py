"""
Test script for Image Zoom functionality
Tests zoom in/out, scroll, and ROI drawing accuracy with zoom
"""

import sys
import os
from pathlib import Path

try:
    from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QTextEdit
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont
except ImportError:
    from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QTextEdit
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont

from component_definition_widget import ComponentDefinitionWidget

class ZoomTestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🔍 Zoom Functionality Test - ทดสอบการซูมภาพ")
        self.setGeometry(100, 100, 1400, 900)

        # Main widget
        main_widget = QWidget()
        layout = QVBoxLayout()

        # Header
        header = QLabel("🔍 Image Zoom Test")
        header.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: #2c3e50; padding: 10px; background-color: #ecf0f1;")
        layout.addWidget(header)

        # Test instructions
        instructions = QTextEdit()
        instructions.setReadOnly(True)
        instructions.setMaximumHeight(200)
        instructions.setHtml("""
        <h3>📝 วิธีทดสอบการซูม:</h3>
        <ol>
            <li><b>โหลดภาพ:</b> คลิก 'Browse...' เพื่อโหลดภาพทดสอบ
                <ul>
                    <li>ทดสอบภาพเล็ก (1 MB)</li>
                    <li>ทดสอบภาพใหญ่ (3 MB)</li>
                </ul>
            </li>
            <li><b>ทดสอบ Zoom:</b>
                <ul>
                    <li>คลิก ➕ เพื่อซูมเข้า (ขั้นละ 25%)</li>
                    <li>คลิก ➖ เพื่อซูมออก (ขั้นละ 25%)</li>
                    <li>คลิก 🔄 Reset เพื่อรีเซ็ตเป็น 100%</li>
                    <li>ช่วงซูม: 25% - 500%</li>
                </ul>
            </li>
            <li><b>ทดสอบ Scroll:</b>
                <ul>
                    <li>เมื่อซูมเกิน 100% scroll bar จะปรากฏ</li>
                    <li>ลองเลื่อนดูภาพในส่วนต่างๆ</li>
                </ul>
            </li>
            <li><b>ทดสอบการวาด ROI:</b>
                <ul>
                    <li>กรอกชื่อ Component</li>
                    <li>ซูมเข้าที่วัตถุเล็กๆ (เช่น 200%)</li>
                    <li>วาด ROI โดยคลิกและลาก</li>
                    <li>ตรวจสอบว่า ROI ตรงจุดที่คลิกหรือไม่</li>
                    <li>คลิก 'Add Component'</li>
                    <li>ซูมออกและตรวจสอบว่า ROI อยู่ตำแหน่งที่ถูกต้อง</li>
                </ul>
            </li>
        </ol>

        <h3>✅ ผลลัพธ์ที่คาดหวัง:</h3>
        <ul>
            <li>✅ ซูมเข้า/ออกได้ราบรื่น</li>
            <li>✅ Scroll bar ปรากฏเมื่อซูมเกิน 100%</li>
            <li>✅ วาด ROI ได้ตรงจุดทุกระดับ zoom</li>
            <li>✅ ROI คงอยู่ตำแหน่งเดิมเมื่อเปลี่ยน zoom</li>
            <li>✅ ทำงานได้ทั้งภาพเล็กและภาพใหญ่</li>
        </ul>
        """)
        instructions.setStyleSheet(
            "background-color: #e8f4f8; padding: 10px; "
            "border-radius: 5px; border: 2px solid #3498db;"
        )
        layout.addWidget(instructions)

        # Component Definition Widget
        self.comp_def_widget = ComponentDefinitionWidget()
        layout.addWidget(self.comp_def_widget)

        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)

        print("\n" + "="*60)
        print("🔍 ZOOM FUNCTIONALITY TEST")
        print("="*60)
        print("✅ Features implemented:")
        print("   - Zoom In/Out controls (25% steps)")
        print("   - Zoom range: 25% - 500%")
        print("   - Scroll area with automatic scrollbars")
        print("   - Fixed-size image display (no offset calculation)")
        print("   - Accurate ROI drawing at any zoom level")
        print("\n📝 Test procedure:")
        print("   1. Load small image (1 MB)")
        print("   2. Test zoom in → should increase image size")
        print("   3. Test scroll → should scroll when zoomed > 100%")
        print("   4. Draw ROI at 200% zoom → should be accurate")
        print("   5. Zoom out to 100% → ROI should stay at correct position")
        print("   6. Load large image (3 MB)")
        print("   7. Repeat steps 2-5")
        print("="*60 + "\n")

def main():
    app = QApplication(sys.argv)
    window = ZoomTestWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
