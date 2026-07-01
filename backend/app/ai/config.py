import os

AI_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_PATH = os.path.join(AI_BASE_DIR, "models")

# Real patient dataset (UCI Heart Disease, Cleveland 1988).
# Download from Kaggle: https://www.kaggle.com/datasets/johnsmith88/heart-disease-dataset
# Save as: backend/data/heart_disease.csv
_BACKEND_DIR = os.path.dirname(os.path.dirname(AI_BASE_DIR))   # backend/
HEART_DISEASE_CSV = os.path.join(_BACKEND_DIR, "data", "heart_disease.csv")

# 🔴 THỨ TỰ CỘT CỐ ĐỊNH - Tuyệt đối không thay đổi
FEATURE_COLUMNS = [
    'heart_rate',
    'room_temp',
    'humidity',
    'light_level',
    'hour',
    'is_night',
    'is_dark'
]