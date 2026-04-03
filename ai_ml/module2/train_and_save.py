from pathlib import Path

import numpy as np
import torch

from motor_predictor import (
    LSTMRegressor,
    evaluate_rmse,
    prepare_dataloaders,
    save_training_curve,
    train_model,
)


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    model_path = script_dir / "motor_lstm.pt"
    mean_path = script_dir / "scaler_mean.npy"
    scale_path = script_dir / "scaler_scale.npy"
    chart_path = script_dir / "training_curve.png"

    print("[1/7] Preparing dataloaders with n=4000...")
    train_loader, val_loader, scaler = prepare_dataloaders(n=4000)

    print("[2/7] Initializing LSTM model...")
    model = LSTMRegressor()

    print("[3/7] Training model for 25 epochs...")
    train_losses, val_losses = train_model(model, train_loader, val_loader, epochs=25, lr=1e-3)

    print("[4/7] Evaluating validation RMSE...")
    rmse = evaluate_rmse(model, val_loader)
    print(f"Final RMSE: {rmse:.4f}")

    print("[5/7] Saving model artifact...")
    torch.save(model.state_dict(), model_path)

    print("[6/7] Saving scaler artifacts...")
    np.save(mean_path, scaler.mean_.astype(np.float32))
    np.save(scale_path, scaler.scale_.astype(np.float32))

    print("[7/7] Saving training curve chart...")
    save_training_curve(train_losses, val_losses, output_path=str(chart_path))

    print("All artifacts saved. Backend /ai/predict/motor is now using the real LSTM model.")


if __name__ == "__main__":
    main()
