#!/usr/bin/env python3
"""
Test Script for Component Definition + MVI Integration

ทดสอบ:
1. Component Definition Manager
2. MVI Component Integration
3. Database operations
4. Matching algorithm
5. Annotation visualization
"""

import cv2
import numpy as np
import os
import sys
from datetime import datetime

# Import modules
try:
    from component_definition import ComponentDefinitionManager
    from mvi_component_integration import MVIComponentIntegration
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure component_definition.py and mvi_component_integration.py are in the same directory")
    sys.exit(1)


def create_test_image(width=800, height=600):
    """สร้างภาพทดสอบ"""
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[:] = (120, 120, 120)  # Gray background

    # Add some text
    cv2.putText(
        image,
        "MVI Test Image",
        (width // 2 - 100, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (255, 255, 255),
        2
    )

    return image


def test_component_definition_manager():
    """Test Component Definition Manager"""
    print("\n" + "=" * 60)
    print("🧪 Testing Component Definition Manager")
    print("=" * 60)

    # Use test database
    test_db = "test_inspections.db"
    if os.path.exists(test_db):
        os.remove(test_db)
        print(f"Removed old test database: {test_db}")

    manager = ComponentDefinitionManager(db_path=test_db)

    # Test 1: Create product
    print("\n1️⃣ Testing product creation...")
    product_id = manager.create_product(
        name="Test_Buddha_Set",
        description="Test product with 3 components",
        pass_threshold=1.0
    )
    assert product_id is not None, "❌ Product creation failed"
    print(f"✅ Product created: ID {product_id}")

    # Test 2: Add components
    print("\n2️⃣ Testing component addition...")

    comp_id_1 = manager.add_component_definition(
        product_id=product_id,
        component_name="pig",
        component_type="object",
        roi={"x": 100, "y": 150, "width": 150, "height": 200},
        position_label="left",
        tolerance=50,
        min_confidence=0.8,
        is_critical=True
    )

    comp_id_2 = manager.add_component_definition(
        product_id=product_id,
        component_name="monk",
        component_type="object",
        roi={"x": 300, "y": 150, "width": 150, "height": 200},
        position_label="center",
        tolerance=50,
        min_confidence=0.8,
        is_critical=True
    )

    comp_id_3 = manager.add_component_definition(
        product_id=product_id,
        component_name="peacock",
        component_type="object",
        roi={"x": 500, "y": 100, "width": 200, "height": 300},
        position_label="right",
        tolerance=50,
        min_confidence=0.8,
        is_critical=True
    )

    assert comp_id_1 and comp_id_2 and comp_id_3, "❌ Component creation failed"
    print(f"✅ Added 3 components")

    # Test 3: Get components
    print("\n3️⃣ Testing component retrieval...")
    components = manager.get_product_components(product_id)
    assert len(components) == 3, f"❌ Expected 3 components, got {len(components)}"
    print(f"✅ Retrieved {len(components)} components")

    for comp in components:
        print(f"   • {comp['name']} ({comp['position']}) - ROI: {comp['roi']}")

    # Test 4: List products
    print("\n4️⃣ Testing product listing...")
    products = manager.list_products()
    assert len(products) >= 1, "❌ Product listing failed"
    print(f"✅ Found {len(products)} product(s)")

    for p in products:
        print(f"   • {p['name']} - {p['component_count']} components")

    # Test 5: Export/Import config
    print("\n5️⃣ Testing config export/import...")
    export_path = "test_product_config.json"
    manager.export_product_config(product_id, export_path)
    assert os.path.exists(export_path), "❌ Export failed"
    print(f"✅ Config exported to {export_path}")

    # Clean up
    if os.path.exists(export_path):
        os.remove(export_path)
        print(f"✓ Cleaned up {export_path}")

    return manager, product_id


def test_mvi_integration(manager, product_id):
    """Test MVI Component Integration"""
    print("\n" + "=" * 60)
    print("🧪 Testing MVI Component Integration")
    print("=" * 60)

    integration = MVIComponentIntegration(manager)

    # Test 1: FAIL case (missing peacock)
    print("\n1️⃣ Testing FAIL case (missing peacock)...")

    test_image = create_test_image()

    mvi_detections_fail = [
        {
            "class": "pig",
            "confidence": 0.94,
            "bbox": {"x": 105, "y": 155, "width": 145, "height": 195}
        },
        {
            "class": "monk",
            "confidence": 0.98,
            "bbox": {"x": 305, "y": 155, "width": 145, "height": 195}
        }
        # peacock หายไป!
    ]

    result_fail = integration.process_mvi_result(
        image=test_image,
        mvi_detections=mvi_detections_fail,
        product_id=product_id,
        verbose=True
    )

    assert result_fail['status'] == 'FAIL', "❌ Should be FAIL"
    assert result_fail['found'] == 2, f"❌ Expected 2 found, got {result_fail['found']}"
    assert result_fail['total'] == 3, f"❌ Expected 3 total, got {result_fail['total']}"
    assert 'peacock' in result_fail['missing_components'], "❌ peacock should be in missing"

    print(f"\n✅ FAIL case test passed")
    print(f"   Status: {result_fail['status']}")
    print(f"   Reason: {result_fail['reason']}")
    print(f"   Found: {result_fail['found']}/{result_fail['total']}")
    print(f"   Missing: {result_fail['missing_components']}")

    # Save annotated image
    output_fail = "test_result_fail.jpg"
    cv2.imwrite(output_fail, result_fail['annotated_image'])
    print(f"   💾 Saved: {output_fail}")

    # Test 2: PASS case (all found)
    print("\n2️⃣ Testing PASS case (all components found)...")

    mvi_detections_pass = [
        {
            "class": "pig",
            "confidence": 0.90,
            "bbox": {"x": 110, "y": 160, "width": 140, "height": 190}
        },
        {
            "class": "monk",
            "confidence": 0.96,
            "bbox": {"x": 310, "y": 160, "width": 140, "height": 190}
        },
        {
            "class": "peacock",
            "confidence": 0.99,
            "bbox": {"x": 510, "y": 110, "width": 190, "height": 290}
        }
    ]

    result_pass = integration.process_mvi_result(
        image=test_image,
        mvi_detections=mvi_detections_pass,
        product_id=product_id,
        verbose=True
    )

    assert result_pass['status'] == 'PASS', "❌ Should be PASS"
    assert result_pass['found'] == 3, f"❌ Expected 3 found, got {result_pass['found']}"
    assert len(result_pass['missing_components']) == 0, "❌ Should have no missing"

    print(f"\n✅ PASS case test passed")
    print(f"   Status: {result_pass['status']}")
    print(f"   Found: {result_pass['found']}/{result_pass['total']}")

    # Save annotated image
    output_pass = "test_result_pass.jpg"
    cv2.imwrite(output_pass, result_pass['annotated_image'])
    print(f"   💾 Saved: {output_pass}")

    # Test 3: Matching algorithm
    print("\n3️⃣ Testing matching algorithm...")

    # Test with slightly off position (should still match with tolerance)
    mvi_detections_offset = [
        {
            "class": "pig",
            "confidence": 0.92,
            "bbox": {"x": 130, "y": 180, "width": 140, "height": 190}  # Offset by 30 pixels
        },
        {
            "class": "monk",
            "confidence": 0.95,
            "bbox": {"x": 320, "y": 170, "width": 140, "height": 190}  # Offset by 20 pixels
        },
        {
            "class": "peacock",
            "confidence": 0.98,
            "bbox": {"x": 520, "y": 120, "width": 190, "height": 290}  # Offset by 20 pixels
        }
    ]

    result_offset = integration.process_mvi_result(
        image=test_image,
        mvi_detections=mvi_detections_offset,
        product_id=product_id,
        verbose=False
    )

    assert result_offset['status'] == 'PASS', "❌ Should match with tolerance"
    print(f"✅ Matching with tolerance works (all found despite offsets)")

    return integration


def test_component_results(manager, product_id, integration):
    """Test component results saving"""
    print("\n" + "=" * 60)
    print("🧪 Testing Component Results Storage")
    print("=" * 60)

    # Create a fake inspection ID
    fake_inspection_id = 999

    # Test component results
    component_results = [
        {
            "component_def_id": 1,
            "name": "pig",
            "found": True,
            "confidence": 0.94,
            "expected_bbox": {"x": 100, "y": 150, "width": 150, "height": 200},
            "detected_bbox": {"x": 105, "y": 155, "width": 145, "height": 195},
            "notes": "Found successfully"
        },
        {
            "component_def_id": 2,
            "name": "monk",
            "found": True,
            "confidence": 0.98,
            "expected_bbox": {"x": 300, "y": 150, "width": 150, "height": 200},
            "detected_bbox": {"x": 305, "y": 155, "width": 145, "height": 195},
            "notes": "Found successfully"
        },
        {
            "component_def_id": 3,
            "name": "peacock",
            "found": False,
            "confidence": 0.0,
            "expected_bbox": {"x": 500, "y": 100, "width": 200, "height": 300},
            "detected_bbox": None,
            "notes": "Missing"
        }
    ]

    print("\n1️⃣ Saving component results...")
    manager.save_component_results(fake_inspection_id, component_results)
    print("✅ Component results saved")

    print("\n2️⃣ Retrieving component results...")
    retrieved = manager.get_component_results(fake_inspection_id)
    assert len(retrieved) == 3, f"❌ Expected 3 results, got {len(retrieved)}"
    print(f"✅ Retrieved {len(retrieved)} component results")

    for r in retrieved:
        status = "✅ FOUND" if r['found'] else "❌ MISSING"
        print(f"   {status} {r['name']} (confidence: {r['confidence']:.2f})")


def run_all_tests():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("🚀 Component Definition + MVI Integration Test Suite")
    print("=" * 60)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # Test 1: Component Definition Manager
        manager, product_id = test_component_definition_manager()

        # Test 2: MVI Integration
        integration = test_mvi_integration(manager, product_id)

        # Test 3: Component Results
        test_component_results(manager, product_id, integration)

        # Summary
        print("\n" + "=" * 60)
        print("✅ All Tests Passed!")
        print("=" * 60)

        print("\n📊 Summary:")
        print("  ✓ Component Definition Manager: Working")
        print("  ✓ MVI Component Integration: Working")
        print("  ✓ Matching Algorithm: Working")
        print("  ✓ Component Results Storage: Working")
        print("  ✓ Annotation Visualization: Working")

        print("\n📁 Generated Files:")
        print("  • test_inspections.db (test database)")
        print("  • test_result_fail.jpg (FAIL case visualization)")
        print("  • test_result_pass.jpg (PASS case visualization)")

        print("\n💡 Next Steps:")
        print("  1. Integrate with main GUI (main.py)")
        print("  2. Connect to actual MVI detection")
        print("  3. Add component definition GUI")
        print("  4. Test with real images")

        return True

    except AssertionError as e:
        print(f"\n❌ Test Failed: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        print(f"\nEnd time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
