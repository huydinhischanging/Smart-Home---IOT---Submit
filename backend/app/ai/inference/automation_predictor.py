# app/ai/inference/automation_predictor.py

class AutomationPredictor:
    def __init__(self, loader):
        self.loader = loader

    def predict(self, X_scaled):
        # ✅ SỬA get → get_model
        model = self.loader.get_model("automation_model")

        if not model:
            return "NO_ACTION"

        return model.predict(X_scaled)[0]