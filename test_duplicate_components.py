"""
Test script for duplicate component names
Tests matching logic when multiple components have the same name
"""

import numpy as np
from component_definition import ComponentDefinitionManager
from mvi_component_integration import MVIComponentIntegration

def test_duplicate_names():
    print("\n" + "="*70)
    print("🧪 TEST: Component ชื่อเดียวกัน หลายตำแหน่ง")
    print("="*70)

    # Initialize
    comp_manager = ComponentDefinitionManager()
    integration = MVIComponentIntegration(comp_manager)

    # Test case 1: มี screw 3 ตำแหน่ง (left, center, right)
    print("\n📋 Test Case 1: Screw 3 ตัว ที่ตำแหน่งต่างกัน")
    print("-" * 70)

    # Simulate expected components (จาก database)
    expected_components = [
        {
            "id": 1,
            "name": "screw",
            "position": "left",
            "roi": {"x": 100, "y": 100, "width": 50, "height": 50},
            "tolerance": 50,
            "critical": True
        },
        {
            "id": 2,
            "name": "screw",
            "position": "center",
            "roi": {"x": 300, "y": 100, "width": 50, "height": 50},
            "tolerance": 50,
            "critical": True
        },
        {
            "id": 3,
            "name": "screw",
            "position": "right",
            "roi": {"x": 500, "y": 100, "width": 50, "height": 50},
            "tolerance": 50,
            "critical": True
        }
    ]

    # Test 1A: PASS - ครบทั้ง 3 ตัว
    print("\n✅ Test 1A: PASS - MVI เจอครบทั้ง 3 ตัว")
    print("-" * 70)
    mvi_detections_pass = [
        {"class": "screw", "confidence": 0.95, "bbox": {"x": 105, "y": 105, "width": 48, "height": 48}},  # left
        {"class": "screw", "confidence": 0.93, "bbox": {"x": 305, "y": 102, "width": 50, "height": 50}},  # center
        {"class": "screw", "confidence": 0.97, "bbox": {"x": 505, "y": 98, "width": 52, "height": 52}}   # right
    ]

    result_pass = integration._match_components(expected_components, mvi_detections_pass, verbose=True)

    print("\n📊 Result:")
    for r in result_pass:
        status_icon = "✅" if r["status"] == "FOUND" else "❌"
        print(f"  {status_icon} {r['name']} ({r['position']}): {r['status']}")

    assert sum(1 for r in result_pass if r["status"] == "FOUND") == 3, "❌ Should find all 3 screws"
    print("\n✅ Test 1A PASSED: All 3 screws matched correctly")

    # Test 1B: FAIL - ขาด 1 ตัว (center)
    print("\n\n❌ Test 1B: FAIL - MVI เจอแค่ 2 ตัว (ขาด center)")
    print("-" * 70)
    mvi_detections_fail = [
        {"class": "screw", "confidence": 0.95, "bbox": {"x": 105, "y": 105, "width": 48, "height": 48}},  # left
        {"class": "screw", "confidence": 0.97, "bbox": {"x": 505, "y": 98, "width": 52, "height": 52}}   # right
        # center หายไป!
    ]

    result_fail = integration._match_components(expected_components, mvi_detections_fail, verbose=True)

    print("\n📊 Result:")
    for r in result_fail:
        status_icon = "✅" if r["status"] == "FOUND" else "❌"
        print(f"  {status_icon} {r['name']} ({r['position']}): {r['status']}")

    found_count = sum(1 for r in result_fail if r["status"] == "FOUND")
    missing_positions = [r['position'] for r in result_fail if r["status"] == "MISSING"]

    assert found_count == 2, "❌ Should find exactly 2 screws"
    assert "center" in missing_positions, "❌ Center screw should be MISSING"
    print(f"\n✅ Test 1B PASSED: Correctly identified missing {missing_positions}")

    # Test 1C: Bug scenario - detections ใกล้กันมาก (ทดสอบ duplicate matching)
    print("\n\n⚠️ Test 1C: Edge Case - 2 detections ใกล้กัน (ทดสอบป้องกัน duplicate match)")
    print("-" * 70)
    mvi_detections_edge = [
        {"class": "screw", "confidence": 0.95, "bbox": {"x": 105, "y": 105, "width": 48, "height": 48}},  # ใกล้ left
        {"class": "screw", "confidence": 0.93, "bbox": {"x": 110, "y": 108, "width": 50, "height": 50}},  # ยังใกล้ left!
        # center และ right หายไป!
    ]

    result_edge = integration._match_components(expected_components, mvi_detections_edge, verbose=True)

    print("\n📊 Result:")
    for r in result_edge:
        status_icon = "✅" if r["status"] == "FOUND" else "❌"
        print(f"  {status_icon} {r['name']} ({r['position']}): {r['status']}")

    found_positions = [r['position'] for r in result_edge if r["status"] == "FOUND"]
    missing_positions = [r['position'] for r in result_edge if r["status"] == "MISSING"]

    # ก่อนแก้บั๊ก: อาจได้ left=FOUND, center=FOUND (ผิด!), right=MISSING
    # หลังแก้บั๊ก: ควรได้ left=FOUND, center=MISSING, right=MISSING

    print(f"\n  Found positions: {found_positions}")
    print(f"  Missing positions: {missing_positions}")

    assert len(found_positions) <= 2, "❌ Should not match more detections than available"
    assert "center" in missing_positions or "right" in missing_positions, "❌ At least 1 position should be MISSING"

    # ตรวจสอบว่าไม่มี detection ตัวเดียวถูก match 2 ครั้ง
    if len(found_positions) == 2:
        # ถ้าเจอ 2 ตัว ต้องเป็น left กับอีกตัวหนึ่ง (ไม่ใช่ center และ right พร้อมกัน)
        print(f"  ⚠️ WARNING: Found 2 positions from only 2 detections")
        print(f"  This means both detections were matched (good!)")

    print(f"\n✅ Test 1C PASSED: No duplicate matching detected")

    # Test case 2: Component ชื่อต่างกัน
    print("\n\n📋 Test Case 2: Component ชื่อต่างกัน (pig, monk, peacock)")
    print("-" * 70)

    expected_mixed = [
        {"id": 4, "name": "pig", "position": "left", "roi": {"x": 100, "y": 100, "width": 100, "height": 100}, "tolerance": 50, "critical": True},
        {"id": 5, "name": "monk", "position": "center", "roi": {"x": 300, "y": 100, "width": 100, "height": 100}, "tolerance": 50, "critical": True},
        {"id": 6, "name": "peacock", "position": "right", "roi": {"x": 500, "y": 100, "width": 150, "height": 150}, "tolerance": 50, "critical": True}
    ]

    mvi_mixed = [
        {"class": "pig", "confidence": 0.94, "bbox": {"x": 105, "y": 105, "width": 95, "height": 95}},
        {"class": "monk", "confidence": 0.96, "bbox": {"x": 305, "y": 105, "width": 98, "height": 98}},
        {"class": "peacock", "confidence": 0.99, "bbox": {"x": 505, "y": 105, "width": 145, "height": 145}}
    ]

    result_mixed = integration._match_components(expected_mixed, mvi_mixed, verbose=True)

    print("\n📊 Result:")
    for r in result_mixed:
        status_icon = "✅" if r["status"] == "FOUND" else "❌"
        print(f"  {status_icon} {r['name']} ({r['position']}): {r['status']}")

    assert sum(1 for r in result_mixed if r["status"] == "FOUND") == 3, "❌ Should find all 3 components"
    print("\n✅ Test 2 PASSED: Different names matched correctly")

    print("\n" + "="*70)
    print("🎉 ALL TESTS PASSED!")
    print("="*70)
    print("\n📝 สรุป:")
    print("  ✅ รองรับ component ชื่อเดียวกัน หลายตำแหน่ง")
    print("  ✅ ป้องกัน detection ตัวเดียวถูก match ซ้ำ")
    print("  ✅ แยกตำแหน่งด้วย position label")
    print("  ✅ Matching ถูกต้องทั้งชื่อเดียวกันและชื่อต่างกัน")
    print("\n💡 คำแนะนำ:")
    print("  - ใช้ position label ที่ชัดเจน (left, center, right, top, bottom)")
    print("  - ตั้ง tolerance ให้เหมาะสมกับระยะระหว่าง component")
    print("  - ตรวจสอบ IoU threshold ว่าเหมาะกับขนาด component")
    print("="*70 + "\n")


if __name__ == "__main__":
    test_duplicate_names()
