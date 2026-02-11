"""
Anomaly Detection Engine — PatchCore Algorithm
ตรวจจับความผิดปกติโดยไม่ต้องกำหนด Component Definition

หลักการ:
1. เก็บภาพ "ปกติ" (10-30 ภาพ) → Extract patch features (ResNet)
2. สร้าง Memory Bank จาก patch features ทั้งหมด
3. ภาพใหม่ → Extract features → เทียบกับ Memory Bank
4. ถ้า distance สูง = Anomaly → แสดง heatmap บริเวณที่ผิดปกติ

รองรับ:
- Standalone mode (ตรวจทั้งภาพ)
- YOLO Hybrid mode (YOLO crop ก่อน แล้วตรวจ anomaly บน crop — ทนตำแหน่งขยับ)
"""

import time
import pickle
from pathlib import Path
from typing import Optional, Tuple, List

import cv2
import numpy as np

TORCH_AVAILABLE = False
try:
    import torch
    import torch.nn.functional as F
    from torchvision import models, transforms
    TORCH_AVAILABLE = True
except ImportError:
    pass

try:
    from PyQt6.QtCore import QObject, pyqtSignal as Signal
except ImportError:
    from PySide6.QtCore import QObject, Signal


class AnomalyEngine(QObject):
    """PatchCore-based Anomaly Detection Engine"""

    # Signals
    training_progress = Signal(str)  # status message
    model_ready = Signal(str)        # model info

    # Feature extraction settings
    IMAGE_SIZE = (224, 224)
    BACKBONE = "resnet18"

    def __init__(self):
        super().__init__()
        self.feature_extractor = None
        self.memory_bank: Optional[torch.Tensor] = None
        self.device: str = "cpu"
        self.threshold: float = 2.5
        self.is_trained: bool = False

        # Training state
        self._features_list: List[torch.Tensor] = []
        self._training_images_count: int = 0
        self._hook_handles: list = []
        self._hook_features: dict = {}
        self._transform = None

        # YOLO crop settings
        self.use_yolo_crop: bool = True
        self.crop_class_name: str = ""  # empty = crop any detection
        self.crop_padding: int = 20     # pixels padding around crop

    # ═══════════════════════════════════════════
    #  INITIALIZATION
    # ═══════════════════════════════════════════

    # Common locations to search for ResNet18 weights
    RESNET18_WEIGHT_FILENAME = "resnet18-f37072fd.pth"
    RESNET18_WEIGHT_SEARCH_PATHS = [
        # Torch hub cache (default download location)
        Path.home() / ".cache" / "torch" / "hub" / "checkpoints",
        # Project-local models directory
        Path(__file__).parent / "models",
        # Working directory
        Path.cwd() / "models",
    ]

    def _load_resnet18_backbone(self):
        """
        โหลด ResNet18 backbone — รองรับ offline (ไม่มี internet)

        ลำดับการโหลด:
        1. ลอง weights=DEFAULT (ใช้ cache ถ้ามี, หรือ download ถ้ามีเน็ต)
        2. ถ้าล้มเหลว → หาไฟล์ .pth ใน local paths
        3. ถ้าไม่เจอ → ใช้ random weights (ผลลัพธ์แย่ลง แต่ยังทำงานได้)
        """
        # --- Attempt 1: standard load (uses cache or downloads) ---
        try:
            backbone = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
            print("ResNet18: loaded with pre-trained weights (cache/download)")
            return backbone
        except Exception as e:
            print(f"ResNet18: standard load failed — {e}")

        # --- Attempt 2: load from local .pth file ---
        for search_dir in self.RESNET18_WEIGHT_SEARCH_PATHS:
            weight_path = search_dir / self.RESNET18_WEIGHT_FILENAME
            if weight_path.is_file():
                try:
                    backbone = models.resnet18(weights=None)
                    state_dict = torch.load(
                        str(weight_path), map_location="cpu", weights_only=True
                    )
                    backbone.load_state_dict(state_dict)
                    print(f"ResNet18: loaded weights from {weight_path}")
                    return backbone
                except Exception as e2:
                    print(f"ResNet18: failed to load from {weight_path} — {e2}")

        # --- Attempt 3: random weights (functional but less accurate) ---
        self.training_progress.emit(
            "Warning: ใช้ random weights (ไม่มี pre-trained) — "
            "ผลลัพธ์อาจแย่ลง ควรคัดลอก resnet18-f37072fd.pth มาวางที่ models/"
        )
        print(
            "ResNet18: WARNING — using random weights (no pre-trained).\n"
            "  To fix: copy resnet18-f37072fd.pth to one of:\n"
            f"  {[str(p / self.RESNET18_WEIGHT_FILENAME) for p in self.RESNET18_WEIGHT_SEARCH_PATHS]}"
        )
        backbone = models.resnet18(weights=None)
        return backbone

    def initialize(self, device: str = "auto") -> bool:
        """โหลด pre-trained ResNet สำหรับ feature extraction"""
        if not TORCH_AVAILABLE:
            self.training_progress.emit("Error: PyTorch not installed")
            return False

        try:
            if device == "auto":
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            else:
                self.device = device

            # Load ResNet18 (supports offline / no-internet machines)
            backbone = self._load_resnet18_backbone()
            backbone.eval()
            backbone.to(self.device)

            # Hook intermediate layers for multi-scale features
            self._hook_features = {}

            def make_hook(name):
                def hook(_module, _input, output):
                    self._hook_features[name] = output
                return hook

            # Clear old hooks
            for h in self._hook_handles:
                h.remove()

            self._hook_handles = [
                backbone.layer2.register_forward_hook(make_hook("layer2")),
                backbone.layer3.register_forward_hook(make_hook("layer3")),
            ]

            self.feature_extractor = backbone

            # Image preprocessing (ImageNet normalization)
            self._transform = transforms.Compose([
                transforms.ToPILImage(),
                transforms.Resize(self.IMAGE_SIZE),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225]
                )
            ])

            msg = f"Anomaly Engine ready ({self.BACKBONE} on {self.device})"
            self.training_progress.emit(msg)
            print(msg)
            return True

        except Exception as e:
            self.training_progress.emit(f"Init error: {e}")
            print(f"Anomaly Engine init error: {e}")
            return False

    def is_initialized(self) -> bool:
        return self.feature_extractor is not None

    # ═══════════════════════════════════════════
    #  FEATURE EXTRACTION
    # ═══════════════════════════════════════════

    def _extract_features(self, image: np.ndarray) -> Tuple[torch.Tensor, Tuple[int, int]]:
        """
        Extract multi-scale patch features จากภาพ

        Returns:
            patches: (H*W, D) tensor — D=384 (128+256 from layer2+layer3)
            spatial_size: (H, W) — spatial dimensions ของ patch grid
        """
        # BGR → RGB
        if len(image.shape) == 3 and image.shape[2] == 3:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            rgb = image

        tensor = self._transform(rgb).unsqueeze(0).to(self.device)

        with torch.no_grad():
            _ = self.feature_extractor(tensor)

        # layer2: (1, 128, 28, 28), layer3: (1, 256, 14, 14)
        feat2 = self._hook_features["layer2"]
        feat3 = self._hook_features["layer3"]

        # Upsample layer3 to match layer2 spatial size
        feat3_up = F.interpolate(
            feat3, size=feat2.shape[-2:],
            mode="bilinear", align_corners=False
        )

        # Concatenate: (1, 384, 28, 28)
        features = torch.cat([feat2, feat3_up], dim=1)

        B, D, H, W = features.shape
        patches = features.permute(0, 2, 3, 1).reshape(-1, D)  # (784, 384)

        return patches, (H, W)

    # ═══════════════════════════════════════════
    #  TRAINING
    # ═══════════════════════════════════════════

    def add_normal_image(self, image: np.ndarray) -> int:
        """
        เพิ่มภาพ "ปกติ" สำหรับเทรน

        Args:
            image: BGR image (numpy array)

        Returns:
            จำนวนภาพที่เก็บแล้วทั้งหมด
        """
        if not self.is_initialized():
            raise RuntimeError("Engine not initialized")

        patches, _ = self._extract_features(image)
        self._features_list.append(patches.cpu())
        self._training_images_count += 1

        msg = f"Added normal image #{self._training_images_count} ({patches.shape[0]} patches)"
        self.training_progress.emit(msg)
        print(msg)

        return self._training_images_count

    def add_normal_images_from_folder(self, folder_path: str) -> int:
        """โหลดภาพปกติจาก folder"""
        folder = Path(folder_path)
        extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
        count = 0

        for img_path in sorted(folder.iterdir()):
            if img_path.suffix.lower() in extensions:
                image = cv2.imread(str(img_path))
                if image is not None:
                    self.add_normal_image(image)
                    count += 1

        return count

    def train(self, max_memory_size: int = 1500) -> bool:
        """
        สร้าง Memory Bank จากภาพปกติที่เก็บไว้

        Args:
            max_memory_size: จำนวน patch สูงสุดใน memory bank
        """
        if not self._features_list:
            self.training_progress.emit("Error: No normal images added")
            return False

        self.training_progress.emit("Training: building memory bank...")

        # Concatenate all patch features
        all_patches = torch.cat(self._features_list, dim=0)  # (N*784, 384)
        total = all_patches.shape[0]
        print(f"Total patches from {self._training_images_count} images: {total}")

        # Coreset subsampling
        target = min(max_memory_size, total)
        if total > target:
            self.training_progress.emit(
                f"Training: subsampling {total} → {target} patches..."
            )
            indices = self._random_coreset(total, target)
            self.memory_bank = all_patches[indices].to(self.device)
        else:
            self.memory_bank = all_patches.to(self.device)

        self.is_trained = True
        self._features_list = []  # Free memory

        info = (f"Trained: {self._training_images_count} images, "
                f"memory bank {self.memory_bank.shape[0]}x{self.memory_bank.shape[1]}")
        self.training_progress.emit(f"OK: {info}")
        self.model_ready.emit(info)
        print(info)
        return True

    @staticmethod
    def _random_coreset(total: int, target: int) -> list:
        """Random subsampling (fast, works well in practice)"""
        return np.random.choice(total, size=target, replace=False).tolist()

    def get_training_count(self) -> int:
        return self._training_images_count

    def reset_training(self):
        """ล้างข้อมูลเทรนทั้งหมด"""
        self._features_list = []
        self._training_images_count = 0
        self.memory_bank = None
        self.is_trained = False
        self.training_progress.emit("Training data cleared")

    # ═══════════════════════════════════════════
    #  PREDICTION
    # ═══════════════════════════════════════════

    def predict(self, image: np.ndarray) -> dict:
        """
        ตรวจจับ anomaly ในภาพ

        Returns:
            {
                "anomaly_score": float,
                "is_anomaly": bool,
                "heatmap": np.ndarray (H, W, 3) — color heatmap
                "heatmap_raw": np.ndarray (H, W) — raw distances
                "inference_time_ms": float
            }
        """
        if not self.is_trained or self.memory_bank is None:
            return {
                "anomaly_score": 0.0,
                "is_anomaly": False,
                "heatmap": None,
                "heatmap_raw": None,
                "inference_time_ms": 0.0
            }

        start_time = time.time()

        patches, (H, W) = self._extract_features(image)

        # KNN: distance to nearest neighbor in memory bank
        # patches: (M, D), memory_bank: (N, D)
        # Process in chunks to save GPU memory
        chunk_size = 256
        min_distances = []
        for i in range(0, patches.shape[0], chunk_size):
            chunk = patches[i:i + chunk_size]
            dists = torch.cdist(chunk, self.memory_bank)  # (chunk, N)
            mins, _ = dists.min(dim=1)
            min_distances.append(mins)

        min_distances = torch.cat(min_distances)  # (M,)

        # Anomaly score = max patch distance
        anomaly_score = float(min_distances.max().item())

        # Heatmap: reshape to spatial dimensions
        heatmap_raw = min_distances.reshape(H, W).cpu().numpy()

        # Resize heatmap to original image size
        img_h, img_w = image.shape[:2]
        heatmap_resized = cv2.resize(heatmap_raw, (img_w, img_h))

        # Normalize to 0-255
        if heatmap_resized.max() > 0:
            heatmap_norm = (heatmap_resized / heatmap_resized.max() * 255).astype(np.uint8)
        else:
            heatmap_norm = np.zeros((img_h, img_w), dtype=np.uint8)

        # Apply JET colormap
        heatmap_color = cv2.applyColorMap(heatmap_norm, cv2.COLORMAP_JET)

        inference_ms = (time.time() - start_time) * 1000

        return {
            "anomaly_score": round(anomaly_score, 3),
            "is_anomaly": anomaly_score > self.threshold,
            "heatmap": heatmap_color,
            "heatmap_raw": heatmap_resized,
            "inference_time_ms": round(inference_ms, 1)
        }

    def create_overlay(self, image: np.ndarray, heatmap_color: np.ndarray,
                       alpha: float = 0.4) -> np.ndarray:
        """สร้างภาพ overlay: ภาพต้นฉบับ + heatmap"""
        if heatmap_color is None:
            return image.copy()
        return cv2.addWeighted(image, 1 - alpha, heatmap_color, alpha, 0)

    def annotate_result(self, image: np.ndarray, result: dict,
                        alpha: float = 0.4) -> np.ndarray:
        """
        วาด annotated image: overlay heatmap + score + status

        Args:
            image: BGR image
            result: dict from predict()
            alpha: heatmap opacity
        """
        heatmap = result.get("heatmap")
        if heatmap is not None:
            annotated = self.create_overlay(image, heatmap, alpha)
        else:
            annotated = image.copy()

        score = result.get("anomaly_score", 0)
        is_anomaly = result.get("is_anomaly", False)

        # Draw score badge
        status_text = f"ANOMALY {score:.2f}" if is_anomaly else f"NORMAL {score:.2f}"
        color = (0, 0, 220) if is_anomaly else (0, 200, 0)

        # Background box
        label_size, _ = cv2.getTextSize(
            status_text, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 3)
        cv2.rectangle(
            annotated, (5, 5),
            (15 + label_size[0], 15 + label_size[1] + 10),
            color, -1)
        cv2.putText(
            annotated, status_text, (10, 10 + label_size[1]),
            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 3)

        # Threshold line
        thr_text = f"Threshold: {self.threshold:.1f}"
        cv2.putText(
            annotated, thr_text,
            (10, 30 + label_size[1] + 20),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        return annotated

    # ═══════════════════════════════════════════
    #  YOLO HYBRID — Crop + Anomaly
    # ═══════════════════════════════════════════

    def predict_on_crops(self, image: np.ndarray,
                         detections: list) -> dict:
        """
        YOLO Hybrid: ตรวจ anomaly บน YOLO-cropped regions

        Args:
            image: full BGR image
            detections: list of YOLO detections [{bbox, class_name, ...}]

        Returns:
            {
                "anomaly_score": float (max across all crops),
                "is_anomaly": bool,
                "crop_results": [{crop, score, heatmap, bbox}, ...],
                "inference_time_ms": float
            }
        """
        if not detections:
            return self.predict(image)

        start_time = time.time()
        crop_results = []
        max_score = 0.0
        img_h, img_w = image.shape[:2]

        for det in detections:
            # Filter by class name if specified
            if self.crop_class_name and det.get("class_name") != self.crop_class_name:
                continue

            bbox = det["bbox"]
            x = max(0, bbox["x"] - self.crop_padding)
            y = max(0, bbox["y"] - self.crop_padding)
            x2 = min(img_w, bbox["x"] + bbox["w"] + self.crop_padding)
            y2 = min(img_h, bbox["y"] + bbox["h"] + self.crop_padding)

            crop = image[y:y2, x:x2]
            if crop.size == 0:
                continue

            result = self.predict(crop)

            crop_results.append({
                "bbox": {"x": x, "y": y, "w": x2 - x, "h": y2 - y},
                "class_name": det.get("class_name", ""),
                "anomaly_score": result["anomaly_score"],
                "is_anomaly": result["is_anomaly"],
                "heatmap": result["heatmap"],
            })

            max_score = max(max_score, result["anomaly_score"])

        inference_ms = (time.time() - start_time) * 1000

        return {
            "anomaly_score": round(max_score, 3),
            "is_anomaly": max_score > self.threshold,
            "crop_results": crop_results,
            "inference_time_ms": round(inference_ms, 1)
        }

    def annotate_crops_result(self, image: np.ndarray,
                              crops_result: dict,
                              alpha: float = 0.4) -> np.ndarray:
        """วาด annotated image สำหรับ YOLO Hybrid mode"""
        annotated = image.copy()

        for crop_res in crops_result.get("crop_results", []):
            bbox = crop_res["bbox"]
            x, y, w, h = bbox["x"], bbox["y"], bbox["w"], bbox["h"]
            is_anomaly = crop_res["is_anomaly"]
            score = crop_res["anomaly_score"]

            # Overlay heatmap on crop region
            heatmap = crop_res.get("heatmap")
            if heatmap is not None:
                heatmap_resized = cv2.resize(heatmap, (w, h))
                roi = annotated[y:y + h, x:x + w]
                blended = cv2.addWeighted(roi, 1 - alpha, heatmap_resized, alpha, 0)
                annotated[y:y + h, x:x + w] = blended

            # Draw bbox
            color = (0, 0, 220) if is_anomaly else (0, 200, 0)
            cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)

            # Label
            label = f"{'ANOMALY' if is_anomaly else 'OK'} {score:.2f}"
            cls = crop_res.get("class_name", "")
            if cls:
                label = f"{cls}: {label}"
            label_size, _ = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            label_y = max(y - 10, label_size[1] + 5)
            cv2.rectangle(
                annotated,
                (x, label_y - label_size[1] - 5),
                (x + label_size[0] + 5, label_y + 5),
                color, -1)
            cv2.putText(
                annotated, label, (x + 2, label_y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Global status badge
        max_score = crops_result.get("anomaly_score", 0)
        is_anomaly = crops_result.get("is_anomaly", False)
        status = f"ANOMALY {max_score:.2f}" if is_anomaly else f"NORMAL {max_score:.2f}"
        color = (0, 0, 220) if is_anomaly else (0, 200, 0)
        cv2.rectangle(annotated, (5, 5), (250, 40), color, -1)
        cv2.putText(annotated, status, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        return annotated

    # ═══════════════════════════════════════════
    #  SAVE / LOAD
    # ═══════════════════════════════════════════

    def save_model(self, path: str) -> bool:
        """บันทึก trained model"""
        if not self.is_trained:
            return False

        data = {
            "memory_bank": self.memory_bank.cpu(),
            "threshold": self.threshold,
            "image_size": self.IMAGE_SIZE,
            "training_images_count": self._training_images_count,
            "use_yolo_crop": self.use_yolo_crop,
            "crop_class_name": self.crop_class_name,
        }

        with open(path, 'wb') as f:
            pickle.dump(data, f)

        msg = f"Anomaly model saved: {path}"
        self.training_progress.emit(msg)
        print(msg)
        return True

    def load_model(self, path: str) -> bool:
        """โหลด trained model"""
        try:
            with open(path, 'rb') as f:
                data = pickle.load(f)

            if not self.is_initialized():
                self.initialize()

            self.memory_bank = data["memory_bank"].to(self.device)
            self.threshold = data.get("threshold", 2.5)
            self._training_images_count = data.get("training_images_count", 0)
            self.use_yolo_crop = data.get("use_yolo_crop", True)
            self.crop_class_name = data.get("crop_class_name", "")
            self.is_trained = True

            info = (f"Loaded: {self._training_images_count} images, "
                    f"bank {self.memory_bank.shape[0]}x{self.memory_bank.shape[1]}")
            self.training_progress.emit(info)
            self.model_ready.emit(info)
            print(f"Anomaly model loaded: {path} — {info}")
            return True

        except Exception as e:
            self.training_progress.emit(f"Load error: {e}")
            print(f"Anomaly model load error: {e}")
            return False

    # ═══════════════════════════════════════════
    #  SETTINGS
    # ═══════════════════════════════════════════

    def set_threshold(self, threshold: float):
        self.threshold = max(0.1, threshold)

    def set_yolo_crop(self, enabled: bool, class_name: str = ""):
        self.use_yolo_crop = enabled
        self.crop_class_name = class_name
