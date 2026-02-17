"""
Anomaly Detection Engine — PatchCore Algorithm (Production Grade)
ตรวจจับความผิดปกติโดยไม่ต้องกำหนด Component Definition

หลักการ:
1. เก็บภาพ "ปกติ" (10-30 ภาพ) → Extract patch features (WideResNet50)
2. สร้าง Memory Bank จาก patch features (Greedy K-Center Coreset)
3. ภาพใหม่ → Extract features → เทียบกับ Memory Bank (K-nearest neighbor)
4. ถ้า distance สูง = Anomaly → แสดง heatmap บริเวณที่ผิดปกติ

รองรับ:
- Standalone mode (ตรวจทั้งภาพ)
- YOLO Hybrid mode (YOLO crop ก่อน แล้วตรวจ anomaly บน crop — ทนตำแหน่งขยับ)

Level 1 Upgrades:
- WideResNet50 backbone (1536 features vs 384 for ResNet18)
- Greedy K-Center coreset (ครอบคลุม feature space ดีกว่า random)
- Full-inference auto-threshold calibration
- Configurable image size (224/256/320/448)
- L2 feature normalization + K-nearest neighbor averaging

Level 2 Upgrades:
- Score normalization (0-100 scale)
- Training data augmentation (brightness/contrast jitter)
- Per-class anomaly models (separate PatchCore per YOLO class)
- Validation API (test model with good/bad images)
"""

import time
import pickle
from pathlib import Path
from typing import Optional, Tuple, List, Dict

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


# ═══════════════════════════════════════════════════
#  Backbone configurations
# ═══════════════════════════════════════════════════

BACKBONE_CONFIG = {
    "wide_resnet50": {
        "model_fn": lambda: models.wide_resnet50_2(weights=None),
        "model_fn_pretrained": lambda: models.wide_resnet50_2(
            weights=models.Wide_ResNet50_2_Weights.DEFAULT),
        "weight_filename": "wide_resnet50_2-95faca4d.pth",
        "layers": ["layer2", "layer3"],
        # layer2: 512 channels, layer3: 1024 channels → total 1536
        "feature_dim": 1536,
    },
    "resnet18": {
        "model_fn": lambda: models.resnet18(weights=None),
        "model_fn_pretrained": lambda: models.resnet18(
            weights=models.ResNet18_Weights.DEFAULT),
        "weight_filename": "resnet18-f37072fd.pth",
        "layers": ["layer2", "layer3"],
        # layer2: 128 channels, layer3: 256 channels → total 384
        "feature_dim": 384,
    },
}

WEIGHT_SEARCH_PATHS = [
    Path.home() / ".cache" / "torch" / "hub" / "checkpoints",
    Path(__file__).parent / "models",
    Path.cwd() / "models",
]


class AnomalyEngine(QObject):
    """PatchCore-based Anomaly Detection Engine (Production Grade)"""

    # Signals
    training_progress = Signal(str)  # status message
    model_ready = Signal(str)        # model info

    def __init__(self):
        super().__init__()
        self.feature_extractor = None
        self.memory_bank: Optional[torch.Tensor] = None
        self.device: str = "cpu"
        self.threshold: float = 2.5
        self.is_trained: bool = False

        # Configuration (configurable before initialize)
        self.backbone_name: str = "wide_resnet50"
        self.image_size: Tuple[int, int] = (256, 256)
        self.num_neighbors: int = 3  # K for KNN scoring

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

        # Level 2: Training augmentation
        self.use_augmentation: bool = True
        self.augmentation_factor: int = 2  # augmented copies per image

        # Level 2: Score normalization calibration
        self._calibration_stats: dict = {}  # {mean, std, max_score}

        # Level 2: Per-class models (YOLO Hybrid)
        self._per_class_features: Dict[str, List[torch.Tensor]] = {}
        self._per_class_banks: Dict[str, torch.Tensor] = {}
        self._per_class_thresholds: Dict[str, float] = {}

    # ═══════════════════════════════════════════
    #  INITIALIZATION
    # ═══════════════════════════════════════════

    def _load_backbone(self, config: dict):
        """
        โหลด backbone — รองรับ offline (ไม่มี internet)

        ลำดับ: pretrained (cache/download) → local .pth → random weights
        """
        name = self.backbone_name
        weight_file = config["weight_filename"]

        # --- Attempt 1: standard load (uses cache or downloads) ---
        try:
            backbone = config["model_fn_pretrained"]()
            print(f"{name}: loaded with pre-trained weights (cache/download)")
            return backbone
        except Exception as e:
            print(f"{name}: standard load failed — {e}")

        # --- Attempt 2: load from local .pth file ---
        for search_dir in WEIGHT_SEARCH_PATHS:
            weight_path = search_dir / weight_file
            if weight_path.is_file():
                try:
                    backbone = config["model_fn"]()
                    state_dict = torch.load(
                        str(weight_path), map_location="cpu", weights_only=True
                    )
                    backbone.load_state_dict(state_dict)
                    print(f"{name}: loaded weights from {weight_path}")
                    return backbone
                except Exception as e2:
                    print(f"{name}: failed to load from {weight_path} — {e2}")

        # --- Attempt 3: random weights ---
        self.training_progress.emit(
            f"Warning: {name} ใช้ random weights — "
            f"ควรคัดลอก {weight_file} มาวางที่ models/"
        )
        print(f"{name}: WARNING — using random weights (no pre-trained).")
        backbone = config["model_fn"]()
        return backbone

    def initialize(self, device: str = "auto",
                   backbone: str = "", image_size: int = 0) -> bool:
        """
        โหลด pre-trained backbone สำหรับ feature extraction

        Args:
            device: "auto", "cuda", "cpu", or GPU index "0"
            backbone: "wide_resnet50" or "resnet18" (empty = use current setting)
            image_size: 224, 256, 320, 448 (0 = use current setting)
        """
        if not TORCH_AVAILABLE:
            self.training_progress.emit("Error: PyTorch not installed")
            return False

        try:
            # Device
            if device == "auto":
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            elif device.isdigit():
                self.device = f"cuda:{device}" if torch.cuda.is_available() else "cpu"
            else:
                self.device = device

            # Backbone
            if backbone and backbone in BACKBONE_CONFIG:
                self.backbone_name = backbone
            config = BACKBONE_CONFIG[self.backbone_name]

            # Image size
            if image_size > 0:
                self.image_size = (image_size, image_size)

            self.training_progress.emit(
                f"Loading {self.backbone_name} ({config['feature_dim']}D features, "
                f"image {self.image_size[0]}px)...")

            # Load backbone
            net = self._load_backbone(config)
            net.eval()
            net.to(self.device)

            # Hook intermediate layers
            self._hook_features = {}

            def make_hook(name):
                def hook(_module, _input, output):
                    self._hook_features[name] = output
                return hook

            for h in self._hook_handles:
                h.remove()

            self._hook_handles = []
            for layer_name in config["layers"]:
                layer = getattr(net, layer_name)
                handle = layer.register_forward_hook(make_hook(layer_name))
                self._hook_handles.append(handle)

            self.feature_extractor = net

            # Image preprocessing (ImageNet normalization)
            self._transform = transforms.Compose([
                transforms.ToPILImage(),
                transforms.Resize(self.image_size),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225]
                )
            ])

            msg = (f"Anomaly Engine ready ({self.backbone_name} "
                   f"{config['feature_dim']}D, {self.image_size[0]}px, {self.device})")
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
        Extract multi-scale patch features จากภาพ + L2 normalize

        Returns:
            patches: (H*W, D) tensor — L2-normalized
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

        config = BACKBONE_CONFIG[self.backbone_name]
        layer_names = config["layers"]

        # Get features from first layer (reference spatial size)
        feat_first = self._hook_features[layer_names[0]]
        target_size = feat_first.shape[-2:]

        # Collect and upsample all layers to same spatial size
        feats = []
        for layer_name in layer_names:
            feat = self._hook_features[layer_name]
            if feat.shape[-2:] != target_size:
                feat = F.interpolate(
                    feat, size=target_size,
                    mode="bilinear", align_corners=False
                )
            feats.append(feat)

        # Concatenate multi-scale features
        features = torch.cat(feats, dim=1)

        B, D, H, W = features.shape
        patches = features.permute(0, 2, 3, 1).reshape(-1, D)

        # L2 normalize — makes distance computation more stable
        patches = F.normalize(patches, p=2, dim=1)

        return patches, (H, W)

    # ═══════════════════════════════════════════
    #  DATA AUGMENTATION
    # ═══════════════════════════════════════════

    def _augment_image(self, image: np.ndarray) -> List[np.ndarray]:
        """
        Generate subtle augmented copies for training robustness
        ช่วยให้ทนต่อแสงเปลี่ยนในไลน์ผลิต
        """
        augmented = []

        # Brightness +10%
        augmented.append(cv2.convertScaleAbs(image, alpha=1.1, beta=8))

        # Brightness -10%
        augmented.append(cv2.convertScaleAbs(image, alpha=0.9, beta=-8))

        if self.augmentation_factor > 2:
            # Horizontal flip
            augmented.append(cv2.flip(image, 1))

        if self.augmentation_factor > 3:
            # Slight Gaussian blur (simulates slight defocus)
            augmented.append(cv2.GaussianBlur(image, (3, 3), 0.5))

        return augmented[:self.augmentation_factor]

    # ═══════════════════════════════════════════
    #  TRAINING
    # ═══════════════════════════════════════════

    def add_normal_image(self, image: np.ndarray, class_name: str = "") -> int:
        """
        เพิ่มภาพ "ปกติ" สำหรับเทรน (+ augmentation ถ้าเปิด)

        Args:
            image: BGR image
            class_name: YOLO class name สำหรับ per-class model (optional)
        """
        if not self.is_initialized():
            raise RuntimeError("Engine not initialized")

        patches, _ = self._extract_features(image)
        self._features_list.append(patches.cpu())

        # Per-class tracking
        if class_name:
            if class_name not in self._per_class_features:
                self._per_class_features[class_name] = []
            self._per_class_features[class_name].append(patches.cpu())

        # Augmentation
        aug_count = 0
        if self.use_augmentation:
            for aug_img in self._augment_image(image):
                aug_patches, _ = self._extract_features(aug_img)
                self._features_list.append(aug_patches.cpu())
                if class_name:
                    self._per_class_features[class_name].append(aug_patches.cpu())
                aug_count += 1

        self._training_images_count += 1

        msg = f"Added normal image #{self._training_images_count} ({patches.shape[0]} patches"
        if aug_count > 0:
            msg += f" + {aug_count} augmented"
        if class_name:
            msg += f" [{class_name}]"
        msg += ")"
        self.training_progress.emit(msg)
        print(msg)

        return self._training_images_count

    def add_normal_images_from_folder(self, folder_path: str) -> int:
        """โหลดภาพปกติจาก folder"""
        folder = Path(folder_path)
        extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff', '.tif'}
        count = 0

        for img_path in sorted(folder.iterdir()):
            if img_path.suffix.lower() in extensions:
                image = cv2.imread(str(img_path))
                if image is not None:
                    self.add_normal_image(image)
                    count += 1

        return count

    def train(self, max_memory_size: int = 0) -> bool:
        """
        สร้าง Memory Bank จากภาพปกติที่เก็บไว้

        Args:
            max_memory_size: จำนวน patch สูงสุดใน memory bank
                             0 = auto (เก็บ 25% หรือขั้นต่ำ 5000)
        """
        if not self._features_list:
            self.training_progress.emit("Error: No normal images added")
            return False

        self.training_progress.emit("Training: building memory bank...")

        # Concatenate all patch features
        all_patches = torch.cat(self._features_list, dim=0)
        total = all_patches.shape[0]
        print(f"Total patches from {self._training_images_count} images: {total} "
              f"(dim={all_patches.shape[1]})")

        # Auto memory size: keep 25% of patches (min 5000, max GPU-safe)
        if max_memory_size <= 0:
            max_memory_size = max(5000, total // 4)
            max_memory_size = min(max_memory_size, 50000)

        # ═══ Greedy K-Center Coreset (Global) ═══
        target = min(max_memory_size, total)
        if total > target:
            self.training_progress.emit(
                f"Training: greedy coreset {total} → {target} patches...")
            indices = self._greedy_coreset(all_patches, target)
            self.memory_bank = all_patches[indices].to(self.device)
        else:
            self.memory_bank = all_patches.to(self.device)

        self.is_trained = True

        # ═══ Per-class Memory Banks ═══
        self._per_class_banks = {}
        self._per_class_thresholds = {}
        if self._per_class_features:
            self._build_per_class_banks()

        # ═══ Full-inference auto-threshold ═══
        self.training_progress.emit("Calibrating threshold on training images...")
        self._auto_calibrate_threshold_full(all_patches)

        # ═══ Per-class threshold calibration ═══
        if self._per_class_features:
            self._calibrate_per_class_thresholds()

        self._features_list = []  # Free memory

        # Build info string
        info = (f"Trained: {self._training_images_count} images, "
                f"bank {self.memory_bank.shape[0]}x{self.memory_bank.shape[1]}, "
                f"backbone={self.backbone_name}, img={self.image_size[0]}px, "
                f"K={self.num_neighbors}, threshold={self.threshold:.1f}")
        if self._per_class_banks:
            cls_info = ", ".join(
                f"{k}({v.shape[0]})" for k, v in self._per_class_banks.items())
            info += f", per-class=[{cls_info}]"
        if self.use_augmentation:
            info += f", aug={self.augmentation_factor}x"

        self.training_progress.emit(f"OK: {info}")
        self.model_ready.emit(info)
        print(info)
        return True

    def _build_per_class_banks(self):
        """Build separate memory banks for each YOLO class"""
        for cls_name, feat_list in self._per_class_features.items():
            cls_patches = torch.cat(feat_list, dim=0)
            cls_total = cls_patches.shape[0]

            # Smaller coreset per class
            cls_target = max(1000, cls_total // 4)
            cls_target = min(cls_target, 20000)

            self.training_progress.emit(
                f"Building per-class bank: {cls_name} ({cls_total} patches)...")

            if cls_total > cls_target:
                indices = self._greedy_coreset(cls_patches, cls_target)
                self._per_class_banks[cls_name] = cls_patches[indices].to(self.device)
            else:
                self._per_class_banks[cls_name] = cls_patches.to(self.device)

            print(f"Per-class bank [{cls_name}]: {self._per_class_banks[cls_name].shape[0]} patches")

    def _calibrate_per_class_thresholds(self):
        """Calibrate threshold for each per-class bank"""
        spatial = self.image_size[0] // 8
        patches_per_image = spatial * spatial

        for cls_name, feat_list in self._per_class_features.items():
            if cls_name not in self._per_class_banks:
                continue

            bank = self._per_class_banks[cls_name]
            cls_patches = torch.cat(feat_list, dim=0)
            n_images = cls_patches.shape[0] // patches_per_image

            scores = []
            for i in range(n_images):
                start = i * patches_per_image
                end = start + patches_per_image
                if end > cls_patches.shape[0]:
                    break
                img_p = cls_patches[start:end].to(self.device)
                score = self._compute_anomaly_score_with_bank(img_p, bank)
                scores.append(score)

            if scores:
                max_s = max(scores)
                mean_s = sum(scores) / len(scores)
                std_s = (sum((s - mean_s) ** 2 for s in scores) / len(scores)) ** 0.5
                thr = round(max(mean_s + 3 * std_s, max_s * 1.5), 1)
                self._per_class_thresholds[cls_name] = thr
                print(f"Per-class threshold [{cls_name}]: {thr:.1f} "
                      f"(mean={mean_s:.2f}, max={max_s:.2f})")

    def _greedy_coreset(self, all_patches: torch.Tensor, target: int) -> list:
        """
        Greedy K-Center Coreset Selection

        เลือก patches ที่ครอบคลุม feature space ดีที่สุด:
        1. เริ่มจาก random patch 1 ตัว
        2. วนเลือก patch ที่ห่างจาก selected set มากที่สุด
        3. ทำซ้ำจนได้ target จำนวน

        ใช้ GPU + chunk processing เพื่อประสิทธิภาพ
        """
        n = all_patches.shape[0]
        device = self.device

        # Move to GPU for fast distance computation
        patches_gpu = all_patches.to(device)

        # Start with random seed
        selected = [np.random.randint(0, n)]
        min_dists = torch.full((n,), float('inf'), device=device)

        for i in range(1, target):
            # Update min distances with last selected patch
            last = patches_gpu[selected[-1]].unsqueeze(0)  # (1, D)

            # Chunk to avoid OOM
            chunk_size = 10000
            for start in range(0, n, chunk_size):
                end = min(start + chunk_size, n)
                chunk = patches_gpu[start:end]
                dists = torch.cdist(chunk, last).squeeze(1)  # (chunk,)
                min_dists[start:end] = torch.minimum(min_dists[start:end], dists)

            # Select patch with maximum min-distance
            next_idx = int(min_dists.argmax().item())
            selected.append(next_idx)

            # Progress every 500 steps
            if i % 500 == 0:
                self.training_progress.emit(
                    f"Coreset: {i}/{target} ({i*100//target}%)")

        return selected

    def _auto_calibrate_threshold_full(self, all_patches: torch.Tensor):
        """
        Full-inference auto-threshold:
        จำลอง inference จริงบนภาพเทรนแต่ละภาพ → วัด max score → ตั้ง threshold
        """
        if self.memory_bank is None:
            return

        # Calculate patches per image from image_size
        # For ResNet-like: spatial = image_size / 8 (after layer2)
        spatial = self.image_size[0] // 8
        patches_per_image = spatial * spatial

        all_scores = []
        n_images = all_patches.shape[0] // patches_per_image

        for img_idx in range(n_images):
            start = img_idx * patches_per_image
            end = start + patches_per_image
            if end > all_patches.shape[0]:
                break

            img_patches = all_patches[start:end].to(self.device)

            # KNN scoring (same as predict)
            score = self._compute_anomaly_score_with_bank(img_patches, self.memory_bank)
            all_scores.append(score)

        if all_scores:
            max_normal = max(all_scores)
            mean_normal = sum(all_scores) / len(all_scores)
            std_normal = (sum((s - mean_normal)**2 for s in all_scores)
                         / len(all_scores)) ** 0.5

            # Store calibration stats for score normalization
            self._calibration_stats = {
                "mean": mean_normal,
                "std": std_normal,
                "max_score": max_normal,
            }

            # Threshold = mean + 3*std (or max*1.5, whichever is larger)
            threshold_stat = mean_normal + 3 * std_normal
            threshold_max = max_normal * 1.5
            self.threshold = round(max(threshold_stat, threshold_max), 1)

            print(f"Auto-threshold (full inference on {len(all_scores)} images): "
                  f"mean={mean_normal:.2f}, std={std_normal:.2f}, "
                  f"max={max_normal:.2f} → threshold={self.threshold:.1f}")
        else:
            self.threshold = 5.0
            self._calibration_stats = {}
            print("Auto-threshold: no images to calibrate, using default 5.0")

    def _compute_anomaly_score_with_bank(self, patches: torch.Tensor,
                                          bank: torch.Tensor) -> float:
        """Compute anomaly score from patches against a specific memory bank"""
        chunk_size = 256
        min_distances = []
        for i in range(0, patches.shape[0], chunk_size):
            chunk = patches[i:i + chunk_size]
            dists = torch.cdist(chunk, bank)  # (chunk, N)

            if self.num_neighbors > 1:
                # Top-K nearest neighbor: average of K smallest distances
                k = min(self.num_neighbors, dists.shape[1])
                topk, _ = dists.topk(k, dim=1, largest=False)
                mins = topk.mean(dim=1)
            else:
                mins, _ = dists.min(dim=1)

            min_distances.append(mins)

        min_distances = torch.cat(min_distances)

        # Score = max patch distance (most anomalous patch)
        return float(min_distances.max().item())

    def _compute_distances_with_bank(self, patches: torch.Tensor,
                                      bank: torch.Tensor) -> torch.Tensor:
        """Compute per-patch distances against a memory bank (for heatmap)"""
        chunk_size = 256
        min_distances = []
        for i in range(0, patches.shape[0], chunk_size):
            chunk = patches[i:i + chunk_size]
            dists = torch.cdist(chunk, bank)

            if self.num_neighbors > 1:
                k = min(self.num_neighbors, dists.shape[1])
                topk, _ = dists.topk(k, dim=1, largest=False)
                mins = topk.mean(dim=1)
            else:
                mins, _ = dists.min(dim=1)

            min_distances.append(mins)

        return torch.cat(min_distances)

    @staticmethod
    def _random_coreset(total: int, target: int) -> list:
        """Random subsampling (legacy fallback)"""
        return np.random.choice(total, size=target, replace=False).tolist()

    def get_training_count(self) -> int:
        return self._training_images_count

    def reset_training(self):
        """ล้างข้อมูลเทรนทั้งหมด"""
        self._features_list = []
        self._training_images_count = 0
        self.memory_bank = None
        self.is_trained = False
        self._per_class_features = {}
        self._per_class_banks = {}
        self._per_class_thresholds = {}
        self._calibration_stats = {}
        self.training_progress.emit("Training data cleared")

    # ═══════════════════════════════════════════
    #  SCORE NORMALIZATION
    # ═══════════════════════════════════════════

    def normalize_score(self, raw_score: float) -> float:
        """
        Convert raw anomaly score to 0-100 scale

        0   = mean of normal images (baseline)
        100 = threshold (decision boundary)
        >100 = anomaly
        """
        if self._calibration_stats:
            mean = self._calibration_stats.get("mean", 0)
            denom = max(self.threshold - mean, 0.01)
            pct = (raw_score - mean) / denom * 100
        else:
            # Fallback: threshold = 100%
            pct = (raw_score / max(self.threshold, 0.01)) * 100
        return round(max(0, min(200, pct)), 1)

    # ═══════════════════════════════════════════
    #  PREDICTION
    # ═══════════════════════════════════════════

    def predict(self, image: np.ndarray,
                bank: Optional[torch.Tensor] = None,
                threshold: Optional[float] = None) -> dict:
        """
        ตรวจจับ anomaly ในภาพ

        Args:
            image: BGR image
            bank: memory bank to use (None = global bank)
            threshold: threshold to use (None = global threshold)

        Returns:
            {
                "anomaly_score": float,
                "score_normalized": float (0-100 scale),
                "is_anomaly": bool,
                "heatmap": np.ndarray (H, W, 3) — color heatmap
                "heatmap_raw": np.ndarray (H, W) — raw distances
                "inference_time_ms": float
            }
        """
        use_bank = bank if bank is not None else self.memory_bank
        use_threshold = threshold if threshold is not None else self.threshold

        if not self.is_trained or use_bank is None:
            return {
                "anomaly_score": 0.0,
                "score_normalized": 0.0,
                "is_anomaly": False,
                "heatmap": None,
                "heatmap_raw": None,
                "inference_time_ms": 0.0
            }

        start_time = time.time()

        patches, (H, W) = self._extract_features(image)

        # KNN distance computation
        min_distances = self._compute_distances_with_bank(patches, use_bank)

        anomaly_score = float(min_distances.max().item())
        score_normalized = self.normalize_score(anomaly_score)

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

        heatmap_color = cv2.applyColorMap(heatmap_norm, cv2.COLORMAP_JET)

        inference_ms = (time.time() - start_time) * 1000

        return {
            "anomaly_score": round(anomaly_score, 3),
            "score_normalized": score_normalized,
            "is_anomaly": anomaly_score > use_threshold,
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
        """วาด annotated image: overlay heatmap + score + status"""
        heatmap = result.get("heatmap")
        if heatmap is not None:
            annotated = self.create_overlay(image, heatmap, alpha)
        else:
            annotated = image.copy()

        score = result.get("anomaly_score", 0)
        score_pct = result.get("score_normalized", 0)
        is_anomaly = result.get("is_anomaly", False)

        status_text = (f"ANOMALY {score:.2f} ({score_pct:.0f}%)" if is_anomaly
                       else f"NORMAL {score:.2f} ({score_pct:.0f}%)")
        color = (0, 0, 220) if is_anomaly else (0, 200, 0)

        label_size, _ = cv2.getTextSize(
            status_text, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 3)
        cv2.rectangle(
            annotated, (5, 5),
            (15 + label_size[0], 15 + label_size[1] + 10),
            color, -1)
        cv2.putText(
            annotated, status_text, (10, 10 + label_size[1]),
            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 3)

        thr_text = (f"Thr: {self.threshold:.1f} | Standalone | "
                    f"{self.backbone_name} {self.image_size[0]}px")
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
        ใช้ per-class bank ถ้ามี, ไม่งั้นใช้ global bank
        """
        if not detections:
            print("predict_on_crops: no detections — returning empty result")
            return {
                "anomaly_score": 0.0,
                "score_normalized": 0.0,
                "is_anomaly": False,
                "crop_results": [],
                "inference_time_ms": 0.0
            }

        start_time = time.time()
        crop_results = []
        max_score = 0.0
        img_h, img_w = image.shape[:2]

        for det in detections:
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

            # Per-class bank selection
            cls = det.get("class_name", "")
            if cls and cls in self._per_class_banks:
                bank = self._per_class_banks[cls]
                threshold = self._per_class_thresholds.get(cls, self.threshold)
                result = self.predict(crop, bank=bank, threshold=threshold)
            else:
                result = self.predict(crop)

            crop_results.append({
                "bbox": {"x": x, "y": y, "w": x2 - x, "h": y2 - y},
                "class_name": cls,
                "anomaly_score": result["anomaly_score"],
                "score_normalized": result["score_normalized"],
                "is_anomaly": result["is_anomaly"],
                "heatmap": result["heatmap"],
            })

            max_score = max(max_score, result["anomaly_score"])

        inference_ms = (time.time() - start_time) * 1000

        return {
            "anomaly_score": round(max_score, 3),
            "score_normalized": self.normalize_score(max_score),
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
            score_pct = crop_res.get("score_normalized", 0)

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
            label = f"{'ANOMALY' if is_anomaly else 'OK'} {score:.2f} ({score_pct:.0f}%)"
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
        max_pct = crops_result.get("score_normalized", 0)
        is_anomaly = crops_result.get("is_anomaly", False)
        n_crops = len(crops_result.get("crop_results", []))
        status = (f"ANOMALY {max_score:.2f} ({max_pct:.0f}%)" if is_anomaly
                  else f"NORMAL {max_score:.2f} ({max_pct:.0f}%)")
        color = (0, 0, 220) if is_anomaly else (0, 200, 0)
        cv2.rectangle(annotated, (5, 5), (520, 65), color, -1)
        cv2.putText(annotated, status, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        n_cls = len(self._per_class_banks)
        mode_extra = f" | {n_cls} class models" if n_cls > 0 else ""
        mode_text = (f"YOLO Hybrid | {n_crops} crops | Thr: {self.threshold:.1f} | "
                     f"{self.backbone_name} {self.image_size[0]}px{mode_extra}")
        cv2.putText(annotated, mode_text, (10, 55),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

        return annotated

    # ═══════════════════════════════════════════
    #  VALIDATION
    # ═══════════════════════════════════════════

    def validate(self, normal_images: List[np.ndarray] = None,
                 abnormal_images: List[np.ndarray] = None) -> dict:
        """
        Validate model performance with labeled images

        Args:
            normal_images: list of known-good (normal) images
            abnormal_images: list of known-bad (anomaly) images

        Returns:
            {
                "normal_scores": [...],
                "abnormal_scores": [...],
                "normal_correct": int,
                "normal_total": int,
                "abnormal_correct": int,
                "abnormal_total": int,
                "accuracy": float (0-100%),
                "suggested_threshold": float,
            }
        """
        result = {
            "normal_scores": [],
            "abnormal_scores": [],
            "normal_correct": 0,
            "normal_total": 0,
            "abnormal_correct": 0,
            "abnormal_total": 0,
            "accuracy": 0.0,
            "suggested_threshold": self.threshold,
        }

        if not self.is_trained:
            return result

        # Test normal images
        if normal_images:
            for i, img in enumerate(normal_images):
                pred = self.predict(img)
                score = pred["anomaly_score"]
                result["normal_scores"].append(score)
                result["normal_total"] += 1
                if not pred["is_anomaly"]:
                    result["normal_correct"] += 1
                if (i + 1) % 5 == 0:
                    self.training_progress.emit(
                        f"Validating normal: {i+1}/{len(normal_images)}")

        # Test abnormal images
        if abnormal_images:
            for i, img in enumerate(abnormal_images):
                pred = self.predict(img)
                score = pred["anomaly_score"]
                result["abnormal_scores"].append(score)
                result["abnormal_total"] += 1
                if pred["is_anomaly"]:
                    result["abnormal_correct"] += 1
                if (i + 1) % 5 == 0:
                    self.training_progress.emit(
                        f"Validating abnormal: {i+1}/{len(abnormal_images)}")

        # Calculate accuracy
        total_correct = result["normal_correct"] + result["abnormal_correct"]
        total_all = result["normal_total"] + result["abnormal_total"]
        if total_all > 0:
            result["accuracy"] = round(total_correct / total_all * 100, 1)

        # Suggest optimal threshold (only if both normal and abnormal provided)
        if result["normal_scores"] and result["abnormal_scores"]:
            max_normal = max(result["normal_scores"])
            min_abnormal = min(result["abnormal_scores"])
            if min_abnormal > max_normal:
                # Perfect separation: threshold between max-normal and min-abnormal
                result["suggested_threshold"] = round(
                    (max_normal + min_abnormal) / 2, 1)
            else:
                # Overlap: use mean + 2*std of normal scores
                mean_n = sum(result["normal_scores"]) / len(result["normal_scores"])
                std_n = (sum((s - mean_n) ** 2 for s in result["normal_scores"])
                        / len(result["normal_scores"])) ** 0.5
                result["suggested_threshold"] = round(mean_n + 2 * std_n, 1)

        self.training_progress.emit(
            f"Validation done: accuracy={result['accuracy']:.1f}%")

        return result

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
            "image_size": self.image_size,
            "training_images_count": self._training_images_count,
            "use_yolo_crop": self.use_yolo_crop,
            "crop_class_name": self.crop_class_name,
            "backbone_name": self.backbone_name,
            "num_neighbors": self.num_neighbors,
            # Level 2 fields
            "calibration_stats": self._calibration_stats,
            "per_class_banks": {k: v.cpu() for k, v in self._per_class_banks.items()},
            "per_class_thresholds": self._per_class_thresholds,
            "use_augmentation": self.use_augmentation,
            "augmentation_factor": self.augmentation_factor,
            "version": 3,  # v3 = Level 2 upgrade
        }

        with open(path, 'wb') as f:
            pickle.dump(data, f)

        msg = f"Anomaly model saved: {path}"
        self.training_progress.emit(msg)
        print(msg)
        return True

    def load_model(self, path: str) -> bool:
        """โหลด trained model (backward compatible กับ v1/v2)"""
        try:
            with open(path, 'rb') as f:
                data = pickle.load(f)

            # Restore settings from saved model
            saved_backbone = data.get("backbone_name", "resnet18")
            saved_image_size = data.get("image_size", (224, 224))

            # Initialize with saved settings
            if not self.is_initialized() or self.backbone_name != saved_backbone:
                self.backbone_name = saved_backbone
                if isinstance(saved_image_size, tuple):
                    self.image_size = saved_image_size
                self.initialize(self.device)

            self.memory_bank = data["memory_bank"].to(self.device)
            self.threshold = data.get("threshold", 2.5)
            self._training_images_count = data.get("training_images_count", 0)
            self.use_yolo_crop = data.get("use_yolo_crop", True)
            self.crop_class_name = data.get("crop_class_name", "")
            self.num_neighbors = data.get("num_neighbors", 3)

            # Level 2 fields
            self._calibration_stats = data.get("calibration_stats", {})
            per_class = data.get("per_class_banks", {})
            self._per_class_banks = {
                k: v.to(self.device) for k, v in per_class.items()}
            self._per_class_thresholds = data.get("per_class_thresholds", {})
            self.use_augmentation = data.get("use_augmentation", True)
            self.augmentation_factor = data.get("augmentation_factor", 2)

            self.is_trained = True

            version = data.get("version", 1)
            info = (f"Loaded v{version}: {self._training_images_count} images, "
                    f"bank {self.memory_bank.shape[0]}x{self.memory_bank.shape[1]}, "
                    f"{self.backbone_name} {self.image_size[0]}px")
            if self._per_class_banks:
                cls_list = ", ".join(self._per_class_banks.keys())
                info += f", per-class=[{cls_list}]"

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

    def set_image_size(self, size: int):
        """เปลี่ยน image size (ต้อง re-initialize หลังเปลี่ยน)"""
        self.image_size = (size, size)

    def set_backbone(self, name: str):
        """เปลี่ยน backbone (ต้อง re-initialize หลังเปลี่ยน)"""
        if name in BACKBONE_CONFIG:
            self.backbone_name = name

    def set_augmentation(self, enabled: bool, factor: int = 2):
        """เปิด/ปิด training augmentation"""
        self.use_augmentation = enabled
        self.augmentation_factor = max(1, min(4, factor))

    def get_per_class_info(self) -> Dict[str, dict]:
        """Get info about per-class models"""
        info = {}
        for cls_name, bank in self._per_class_banks.items():
            info[cls_name] = {
                "bank_size": bank.shape[0],
                "threshold": self._per_class_thresholds.get(cls_name, self.threshold),
            }
        return info
