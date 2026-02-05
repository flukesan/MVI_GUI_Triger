"""
Test script for name-based color mapping
Demonstrates that components with same name get same color
"""

import sys
try:
    from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QTextEdit
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont, QColor
except ImportError:
    from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QTextEdit
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont, QColor

from component_definition_widget import ComponentDefinitionWidget

class ColorMappingTestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎨 Color Mapping Test - Component ชื่อเดียวกันใช้สีเดียวกัน")
        self.setGeometry(100, 100, 1400, 900)

        # Main widget
        main_widget = QWidget()
        layout = QVBoxLayout()

        # Header
        header = QLabel("🎨 Name-Based Color Mapping Test")
        header.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: #2c3e50; padding: 10px; background-color: #ecf0f1;")
        layout.addWidget(header)

        # Test instructions
        instructions = QTextEdit()
        instructions.setReadOnly(True)
        instructions.setMaximumHeight(250)
        instructions.setHtml("""
        <h3>📝 วิธีทดสอบ Color Mapping:</h3>
        <ol>
            <li><b>สร้าง Product ใหม่:</b> คลิก 'New' → กรอกชื่อ → โหลด Golden Template</li>
            <li><b>เพิ่ม Component ชื่อเดียวกัน หลายตำแหน่ง:</b>
                <ul>
                    <li>กรอก Name: <b>Weld Nut M10</b>, Position: <b>left</b> → วาด ROI → Add</li>
                    <li>กรอก Name: <b>Weld Nut M10</b>, Position: <b>center</b> → วาด ROI → Add</li>
                    <li>กรอก Name: <b>Weld Nut M10</b>, Position: <b>right</b> → วาด ROI → Add</li>
                </ul>
            </li>
            <li><b>เพิ่ม Component ชื่ออื่น:</b>
                <ul>
                    <li>กรอก Name: <b>Weld Nut M12</b>, Position: <b>left</b> → วาด ROI → Add</li>
                    <li>กรอก Name: <b>Weld Nut M16</b>, Position: <b>right</b> → วาด ROI → Add</li>
                </ul>
            </li>
        </ol>

        <h3>✅ ผลลัพธ์ที่คาดหวัง:</h3>
        <table border="1" cellpadding="5" style="border-collapse: collapse;">
            <tr style="background-color: #3498db; color: white; font-weight: bold;">
                <th>Component Name</th>
                <th>Position</th>
                <th>ROI Color</th>
            </tr>
            <tr>
                <td>Weld Nut M10</td>
                <td>left</td>
                <td style="background-color: red; color: white;"><b>Red</b> (เหมือนกัน)</td>
            </tr>
            <tr>
                <td>Weld Nut M10</td>
                <td>center</td>
                <td style="background-color: red; color: white;"><b>Red</b> (เหมือนกัน)</td>
            </tr>
            <tr>
                <td>Weld Nut M10</td>
                <td>right</td>
                <td style="background-color: red; color: white;"><b>Red</b> (เหมือนกัน)</td>
            </tr>
            <tr>
                <td>Weld Nut M12</td>
                <td>left</td>
                <td style="background-color: blue; color: white;"><b>Blue</b> (ต่างจาก M10)</td>
            </tr>
            <tr>
                <td>Weld Nut M16</td>
                <td>right</td>
                <td style="background-color: orange; color: white;"><b>Orange</b> (ต่างจาก M10, M12)</td>
            </tr>
        </table>

        <h3>🎯 จุดประสงค์:</h3>
        <ul>
            <li>✅ Component ชื่อเดียวกัน → ใช้<b>สีเดียวกัน</b> (แม้จะอยู่ตำแหน่งต่างกัน)</li>
            <li>✅ Component ชื่อต่างกัน → ใช้<b>สีต่างกัน</b></li>
            <li>✅ ง่ายต่อการมองเห็นและจัดกลุ่ม component</li>
            <li>✅ สามารถแยก component ด้วย position label</li>
        </ul>

        <h3>🔍 Algorithm:</h3>
        <pre style="background-color: #f0f0f0; padding: 10px; border-radius: 5px;">
# Color mapping เก็บไว้ใน dict
name_to_color_map = {}

def get_color_for_name(component_name):
    if component_name in name_to_color_map:
        return name_to_color_map[component_name]  # ใช้สีเดิม

    # Assign สีใหม่จาก palette
    color_index = len(name_to_color_map) % len(color_palette)
    color = color_palette[color_index]
    name_to_color_map[component_name] = color
    return color
        </pre>
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

        print("\n" + "="*70)
        print("🎨 COLOR MAPPING TEST")
        print("="*70)
        print("✅ Color mapping implemented:")
        print("   - Component ชื่อเดียวกัน → สีเดียวกัน")
        print("   - Component ชื่อต่างกัน → สีต่างกัน")
        print("   - สี palette: 10 สี (Red, Blue, Orange, Magenta, Cyan, Green, Yellow, Purple, Pink, Brown)")
        print("\n📝 Test scenario:")
        print("   1. Add 'Weld Nut M10' (left, center, right) → ควรได้สีแดงทั้ง 3")
        print("   2. Add 'Weld Nut M12' (left) → ควรได้สีน้ำเงิน")
        print("   3. Add 'Weld Nut M16' (right) → ควรได้สีส้ม")
        print("="*70 + "\n")

def main():
    app = QApplication(sys.argv)
    window = ColorMappingTestWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
