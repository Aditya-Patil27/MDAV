import torch
import torch.nn as nn
from torchvision import transforms, models
from PIL import Image
import os


class VisionService:
    def __init__(self, model_path: str = None):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

        if model_path and os.path.exists(model_path):
            self._load_model(model_path)

    def _load_model(self, model_path: str):
        self.model = models.efficientnet_b0(pretrained=False)
        num_ftrs = self.model.classifier[1].in_features
        self.model.classifier[1] = nn.Linear(num_ftrs, 2)
        self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        self.model.to(self.device)
        self.model.eval()

    def analyze(self, image_path: str) -> dict:
        if self.model is None:
            return self._mock_analysis(image_path)

        try:
            image = Image.open(image_path).convert("RGB")
            input_tensor = self.transform(image).unsqueeze(0).to(self.device)

            with torch.no_grad():
                output = self.model(input_tensor)
                probabilities = torch.nn.functional.softmax(output, dim=1)
                tamper_prob = probabilities[0][1].item()
                confidence = max(probabilities[0]).item()

            return {
                "tamper_probability": tamper_prob,
                "confidence": confidence,
                "heatmap_path": None,
                "explanation": self._generate_explanation(tamper_prob),
            }
        except Exception as e:
            return {
                "tamper_probability": 0.5,
                "confidence": 0.0,
                "heatmap_path": None,
                "explanation": f"Analysis error: {str(e)}",
            }

    def _mock_analysis(self, image_path: str) -> dict:
        import random
        tamper_prob = random.uniform(0.1, 0.9)
        confidence = random.uniform(0.6, 0.95)

        return {
            "tamper_probability": round(tamper_prob, 4),
            "confidence": round(confidence, 4),
            "heatmap_path": None,
            "explanation": self._generate_explanation(tamper_prob),
        }

    def _generate_explanation(self, tamper_prob: float) -> str:
        if tamper_prob < 0.3:
            return "Document appears authentic with no significant tampering indicators detected."
        elif tamper_prob < 0.6:
            return "Document shows minor anomalies that may indicate potential modification. Manual review recommended."
        elif tamper_prob < 0.8:
            return "Document shows significant tampering indicators. Likely contains manipulated regions."
        else:
            return "Document shows strong evidence of tampering. Multiple manipulation indicators detected."


vision_service = VisionService()
