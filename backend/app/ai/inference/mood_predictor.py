# app/ai/inference/mood_predictor.py

class MoodPredictor:
    def __init__(self, loader):
        self.loader = loader

    def predict(self, X_scaled):
        # ✅ SỬA get → get_model
        model = self.loader.get_model("mood_model")

        if not model:
            return "VIGILANT"

        return model.predict(X_scaled)[0]