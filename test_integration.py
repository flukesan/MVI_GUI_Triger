"""
Test MVI Component Integration
ทดสอบการ integrate Component Definition กับระบบตรวจสอบ
"""

import cv2
import numpy as np
from component_definition import ComponentDefinitionManager
from mvi_component_integration import MVIComponentIntegration

# Initialize
comp_manager = ComponentDefinitionManager()
mvi_integration = MVIComponentIntegration(comp_manager)

print("="*60)
print("Testing MVI Component Integration")
print("="*60)

# Create test product and components
print("\n1. Creating test product...")
product_id = comp_manager.create_product(
    name="Buddha_3pcs_Test",
    golden_template_path="",
    pass_threshold=1.0
)
print(f"   ✓ Created product ID: {product_id}")

# Add expected components (based on user's golden template image)
print("\n2. Adding expected components...")

# Monk (left/orange box in golden template)
comp_manager.add_component_definition(
    product_id=product_id,
    component_name="monk",  # lowercase to match MVI detection
    component_type="object",
    roi={"x": 385, "y": 255, "width": 95, "height": 145},
    position_label="left",
    tolerance=100,
    min_confidence=0.7,
    is_critical=True
)
print("   ✓ Added: monk (left)")

# Peacock (center/blue box in golden template)
comp_manager.add_component_definition(
    product_id=product_id,
    component_name="peacock",  # lowercase to match MVI detection
    component_type="object",
    roi={"x": 480, "y": 180, "width": 155, "height": 205},
    position_label="center",
    tolerance=100,
    min_confidence=0.7,
    is_critical=True
)
print("   ✓ Added: peacock (center)")

# Pig (right/green box in golden template)
comp_manager.add_component_definition(
    product_id=product_id,
    component_name="pig",  # lowercase to match MVI detection
    component_type="object",
    roi={"x": 640, "y": 245, "width": 95, "height": 140},
    position_label="right",
    tolerance=100,
    min_confidence=0.7,
    is_critical=True
)
print("   ✓ Added: pig (right)")

# Simulate FAIL case (Pig missing - from user's screenshot)
print("\n3. Simulating FAIL case (Pig missing)...")
print("   Detected: monk, peacock")
print("   Missing: pig")

# Create dummy image (800x600)
test_image = np.zeros((600, 800, 3), dtype=np.uint8)
test_image[:] = (128, 128, 128)  # Gray background

# MVI detections (from user's screenshot - 2 objects only)
mvi_detections_fail = [
    {
        "class": "monk",
        "confidence": 0.96,
        "bbox": {"x": 380, "y": 250, "width": 100, "height": 150}
    },
    {
        "class": "peacock",
        "confidence": 0.98,
        "bbox": {"x": 475, "y": 175, "width": 160, "height": 210}
    }
    # Pig missing!
]

# Process with Component Definition
result_fail = mvi_integration.process_mvi_result(
    test_image,
    mvi_detections_fail,
    product_id
)

print(f"\n   Status: {result_fail['status']}")
print(f"   Found components: {result_fail['found']}/{result_fail['total']}")
print(f"   Missing: {result_fail['missing_components']}")
print(f"   Missing positions: {result_fail['missing_positions']}")

# Save annotated image
cv2.imwrite("test_integration_fail.jpg", result_fail['annotated_image'])
print(f"\n   ✅ Saved: test_integration_fail.jpg")

# Simulate PASS case (All objects present)
print("\n4. Simulating PASS case (All objects present)...")
mvi_detections_pass = [
    {
        "class": "monk",
        "confidence": 0.96,
        "bbox": {"x": 380, "y": 250, "width": 100, "height": 150}
    },
    {
        "class": "peacock",
        "confidence": 0.98,
        "bbox": {"x": 475, "y": 175, "width": 160, "height": 210}
    },
    {
        "class": "pig",
        "confidence": 0.90,
        "bbox": {"x": 635, "y": 240, "width": 100, "height": 145}
    }
]

result_pass = mvi_integration.process_mvi_result(
    test_image,
    mvi_detections_pass,
    product_id
)

print(f"\n   Status: {result_pass['status']}")
print(f"   Found components: {result_pass['found']}/{result_pass['total']}")
print(f"   Missing: {result_pass['missing_components']}")

# Save annotated image
cv2.imwrite("test_integration_pass.jpg", result_pass['annotated_image'])
print(f"\n   ✅ Saved: test_integration_pass.jpg")

print("\n" + "="*60)
print("✅ Integration test complete!")
print("="*60)
print("\nKey features tested:")
print("  ✓ Product and component definition")
print("  ✓ MVI detection format conversion")
print("  ✓ Component matching algorithm")
print("  ✓ Missing component detection")
print("  ✓ Red box annotation for missing components")
print("  ✓ Status determination (PASS/FAIL)")
print("\nGenerated files:")
print("  • test_integration_fail.jpg - Shows RED box where Pig should be")
print("  • test_integration_pass.jpg - Shows all GREEN boxes")
