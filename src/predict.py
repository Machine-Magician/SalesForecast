from ultralytics import YOLO
import cv2
import numpy as np
from pathlib import Path


class TailDetector:
    def __init__(self, model_path, confidence=0.20):
        self.model = YOLO(model_path)
        self.confidence = confidence

    def predict_with_mask(self, image):
        """Возвращает изображение с полупрозрачной маской и контуром"""
        print(f"Predictor: confidence={self.confidence}")
        print(f"Входное изображение: {image.shape}")

        #конвертируем RGB -> BGR
        if len(image.shape) == 3 and image.shape[2] == 3:
            image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        else:
            image_bgr = image

        #предсказание
        results = self.model(image_bgr, conf=self.confidence, imgsz=640)

        print(f"Найдено объектов: {len(results[0].boxes)}")

        if len(results[0].boxes) == 0:
            print("Ничего не найдено")
            return image  # возвращаем оригинал

        #получаем стандартную разметку с контурами
        result_bgr = results[0].plot()

        #добавляем свою полупрозрачную маску
        if results[0].masks is not None:
            img_copy = result_bgr.copy()
            for mask in results[0].masks.data:
                mask_np = mask.cpu().numpy()
                mask_resized = cv2.resize(mask_np, (image_bgr.shape[1], image_bgr.shape[0]))

                colored_mask = np.zeros_like(result_bgr)
                colored_mask[:, :, 2] = 255 * mask_resized

                # Накладываем с прозрачностью
                result_bgr = cv2.addWeighted(img_copy, 0.6, colored_mask, 0.4, 0)

        #конвертируем BGR -> RGB
        result_rgb = cv2.cvtColor(result_bgr, cv2.COLOR_BGR2RGB)

        return result_rgb