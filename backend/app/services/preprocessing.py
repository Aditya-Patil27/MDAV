import cv2
import numpy as np
from PIL import Image
import os


def preprocess_document(file_path: str) -> str:
    img = cv2.imread(file_path)
    if img is None:
        raise ValueError("Could not read image")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    denoised = cv2.fastNlMeansDenoising(gray, h=10)

    coords = cv2.findNonZero(255 - denoised)
    if coords is not None:
        rect = cv2.minAreaRect(coords)
        angle = rect[-1]
        if angle < -45:
            angle = 90 + angle
        if abs(angle) > 0.5:
            h, w = denoised.shape
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            denoised = cv2.warpAffine(denoised, M, (w, h), flags=cv2.INTER_CUBIC)

    normalized = cv2.normalize(denoised, None, 0, 255, cv2.NORM_MINMAX)

    output_path = file_path.replace(".", "_preprocessed.")
    cv2.imwrite(output_path, normalized)
    return output_path


def pdf_to_images(pdf_path: str, output_dir: str) -> list:
    try:
        import fitz
        doc = fitz.open(pdf_path)
        images = []
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=300)
            img_path = os.path.join(output_dir, f"page_{page_num}.png")
            pix.save(img_path)
            images.append(img_path)
        return images
    except ImportError:
        raise ImportError("PyMuPDF (fitz) is required for PDF processing")


def resize_image(file_path: str, target_size: tuple = (224, 224)) -> str:
    img = Image.open(file_path)
    img = img.resize(target_size, Image.LANCZOS)
    output_path = file_path.replace(".", "_resized.")
    img.save(output_path)
    return output_path
