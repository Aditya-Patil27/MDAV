import torch
import torch.nn as nn
from torchvision import transforms, models
from PIL import Image
import os


class VisualTamperDetector:
    def __init__(self, model_path: str = None, num_classes: int = 2):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.num_classes = num_classes
        self.model = None
        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

        if model_path and os.path.exists(model_path):
            self.load_model(model_path)

    def build_model(self) -> nn.Module:
        model = models.efficientnet_b0(pretrained=True)
        num_ftrs = model.classifier[1].in_features
        model.classifier[1] = nn.Linear(num_ftrs, self.num_classes)
        return model.to(self.device)

    def load_model(self, model_path: str):
        self.model = self.build_model()
        self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        self.model.eval()

    def predict(self, image_path: str) -> dict:
        if self.model is None:
            return {"error": "Model not loaded"}

        image = Image.open(image_path).convert("RGB")
        input_tensor = self.transform(image).unsqueeze(0).to(self.device)

        with torch.no_grad():
            output = self.model(input_tensor)
            probabilities = torch.nn.functional.softmax(output, dim=1)
            predicted_class = torch.argmax(probabilities, dim=1).item()
            confidence = probabilities[0][predicted_class].item()

        return {
            "predicted_class": predicted_class,
            "class_label": "tampered" if predicted_class == 1 else "clean",
            "confidence": round(confidence, 4),
            "probabilities": {
                "clean": round(probabilities[0][0].item(), 4),
                "tampered": round(probabilities[0][1].item(), 4),
            },
        }
