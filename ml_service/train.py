import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, models
from PIL import Image
import os


class DocTamperDataset(Dataset):
    def __init__(self, image_dir: str, mask_dir: str = None, transform=None):
        self.image_dir = image_dir
        self.mask_dir = mask_dir
        self.transform = transform
        self.images = [f for f in os.listdir(image_dir) if f.endswith(('.jpg', '.png', '.jpeg'))]

    def __len__(self):
        return len(self.images)

    def __getitem__(self, idx):
        img_name = self.images[idx]
        img_path = os.path.join(self.image_dir, img_name)
        image = Image.open(img_path).convert("RGB")

        label = 0
        if self.mask_dir:
            mask_path = os.path.join(self.mask_dir, img_name.replace('.jpg', '_mask.png'))
            if os.path.exists(mask_path):
                mask = Image.open(mask_path).convert("L")
                import numpy as np
                mask_np = np.array(mask)
                if mask_np.sum() > 0:
                    label = 1

        if self.transform:
            image = self.transform(image)

        return image, label


class Trainer:
    def __init__(self, model, device):
        self.model = model
        self.device = device
        self.criterion = nn.CrossEntropyLoss()
        self.optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)

    def train_epoch(self, dataloader):
        self.model.train()
        total_loss = 0.0
        correct = 0
        total = 0

        for images, labels in dataloader:
            images = images.to(self.device)
            labels = labels.to(self.device)

            self.optimizer.zero_grad()
            outputs = self.model(images)
            loss = self.criterion(outputs, labels)
            loss.backward()
            self.optimizer.step()

            total_loss += loss.item()
            _, predicted = torch.max(outputs, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()

        return total_loss / len(dataloader), correct / total

    def validate(self, dataloader):
        self.model.eval()
        total_loss = 0.0
        correct = 0
        total = 0

        with torch.no_grad():
            for images, labels in dataloader:
                images = images.to(self.device)
                labels = labels.to(self.device)

                outputs = self.model(images)
                loss = self.criterion(outputs, labels)

                total_loss += loss.item()
                _, predicted = torch.max(outputs, 1)
                total += labels.size(0)
                correct += (predicted == labels).sum().item()

        return total_loss / len(dataloader), correct / total

    def save_model(self, path: str):
        torch.save(self.model.state_dict(), path)
