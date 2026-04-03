import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.metrics import mean_squared_error
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt

np.random.seed(42)
torch.manual_seed(42)


def generate_synthetic(n=3500):
    t = np.arange(n)
    load = 0.6 + 0.35 * np.sin(t / 45.0)
    current = 12 + 7 * load + np.random.normal(0, 0.6, size=n)
    rpm = 2500 + 900 * load + np.random.normal(0, 35, size=n)
    temp = 45 + 18 * load + np.random.normal(0, 0.9, size=n)
    vibration = 0.12 + 0.08 * np.sin(t / 20.0) + np.random.normal(0, 0.015, size=n)

    fault_signal = np.zeros(n)
    for start in [500, 1100, 1800, 2500, 3000]:
        span = min(120, n - start)
        if span <= 0:
            continue
        ramp = np.linspace(0, 1, span)
        temp[start:start + span] += 8 * ramp
        vibration[start:start + span] += 0.22 * ramp
        current[start:start + span] += 3.2 * ramp
        fault_signal[start:start + span] = np.maximum(fault_signal[start:start + span], ramp)

    x = np.stack([current, rpm, temp, vibration], axis=1)
    y = np.clip(fault_signal, 0, 1)
    return x.astype(np.float32), y.astype(np.float32)


def build_sequences(x, y, seq_len=30, horizon=5):
    xs, ys = [], []
    for i in range(len(x) - seq_len - horizon):
        xs.append(x[i:i + seq_len])
        ys.append(y[i + seq_len + horizon])
    return np.array(xs, dtype=np.float32), np.array(ys, dtype=np.float32)


class LSTMRegressor(nn.Module):
    def __init__(self, input_size=4, hidden_size=48):
        super().__init__()
        self.lstm = nn.LSTM(input_size=input_size, hidden_size=hidden_size, num_layers=1, batch_first=True)
        self.head = nn.Sequential(
            nn.Linear(hidden_size, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid(),
        )

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.head(out[:, -1, :]).squeeze(1)


def bar(prob):
    blocks = 20
    on = int(round(prob * blocks))
    return "[" + "█" * on + "░" * (blocks - on) + "]"


def synth_row(mode: str, step: int) -> np.ndarray:
    if mode == "normal":
        current = 12.5 + np.random.normal(0, 0.5)
        rpm = 2900 + np.random.normal(0, 40)
        temp = 54 + np.random.normal(0, 0.8)
        vibration = 0.10 + np.random.normal(0, 0.01)
    elif mode == "high_performance":
        current = 20.5 + np.random.normal(0, 0.6)
        rpm = 3500 + np.random.normal(0, 45)
        temp = 72 + np.random.normal(0, 0.9)
        vibration = 0.12 + np.random.normal(0, 0.01)
    else:
        ramp = min(1.0, step / 120.0)
        current = 21.0 + 3.2 * ramp + np.random.normal(0, 0.5)
        rpm = 3300 - 900 * ramp + np.random.normal(0, 35)
        temp = 72 + 13.0 * ramp + np.random.normal(0, 0.8)
        vibration = 0.12 + 0.32 * ramp + np.random.normal(0, 0.012)
    return np.array([current, rpm, temp, vibration], dtype=np.float32)


def prepare_dataloaders(n=4000, seq_len=30, horizon=5, batch_size=32):
    x, y = generate_synthetic(n=n)
    split_idx = int(len(x) * 0.8)
    x_train_raw, x_val_raw = x[:split_idx], x[split_idx:]
    y_train_raw, y_val_raw = y[:split_idx], y[split_idx:]

    scaler = StandardScaler()
    x_train_scaled = scaler.fit_transform(x_train_raw).astype(np.float32)
    x_val_scaled = scaler.transform(x_val_raw).astype(np.float32)

    x_train_seq, y_train_seq = build_sequences(x_train_scaled, y_train_raw, seq_len=seq_len, horizon=horizon)
    x_val_seq, y_val_seq = build_sequences(x_val_scaled, y_val_raw, seq_len=seq_len, horizon=horizon)

    train_ds = TensorDataset(torch.tensor(x_train_seq), torch.tensor(y_train_seq))
    val_ds = TensorDataset(torch.tensor(x_val_seq), torch.tensor(y_val_seq))

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=False)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
    return train_loader, val_loader, scaler


def train_model(model, train_loader, val_loader, epochs=25, lr=1e-3):
    criterion = nn.BCELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    train_losses = []
    val_losses = []

    for epoch in range(1, epochs + 1):
        model.train()
        train_running = 0.0
        train_count = 0

        for xb, yb in train_loader:
            xb = xb.float()
            yb = yb.float()
            optimizer.zero_grad()
            pred = model(xb)
            loss = criterion(pred, yb)
            loss.backward()
            optimizer.step()
            train_running += loss.item() * xb.size(0)
            train_count += xb.size(0)

        train_loss = train_running / max(train_count, 1)

        model.eval()
        val_running = 0.0
        val_count = 0
        with torch.no_grad():
            for xb, yb in val_loader:
                xb = xb.float()
                yb = yb.float()
                pred = model(xb)
                val_loss_batch = criterion(pred, yb)
                val_running += val_loss_batch.item() * xb.size(0)
                val_count += xb.size(0)

        val_loss = val_running / max(val_count, 1)
        train_losses.append(train_loss)
        val_losses.append(val_loss)
        print(f"Epoch {epoch:2d}/{epochs}  train={train_loss:.4f}  val={val_loss:.4f}")

    return train_losses, val_losses


def evaluate_rmse(model, val_loader):
    model.eval()
    y_true_all = []
    y_pred_all = []
    with torch.no_grad():
        for xb, yb in val_loader:
            xb = xb.float()
            yb = yb.float()
            pred = model(xb)
            y_true_all.extend(yb.numpy().tolist())
            y_pred_all.extend(pred.numpy().tolist())

    y_true_np = np.array(y_true_all, dtype=np.float32)
    y_pred_np = np.array(y_pred_all, dtype=np.float32)
    return float(np.sqrt(mean_squared_error(y_true_np, y_pred_np)))


def save_training_curve(train_losses, val_losses, output_path="training_curve.png"):
    plt.figure(figsize=(8, 4))
    plt.plot(train_losses, label="train_loss", linewidth=2)
    plt.plot(val_losses, label="val_loss", linewidth=2)
    plt.title("Motor Failure LSTM - Training Curve")
    plt.xlabel("Epoch")
    plt.ylabel("BCE Loss")
    plt.legend()
    plt.grid(alpha=0.2)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)


def run_live_demo(model, scaler, seq_len=30):
    print("[5/6] LIVE INFERENCE DEMO")
    timeline = (["normal"] * 60) + (["high_performance"] * 60) + (["failure"] * 120)
    buffer = []

    model.eval()
    with torch.no_grad():
        for i, mode in enumerate(timeline):
            row = synth_row(mode, i)
            buffer.append(row)
            if len(buffer) > seq_len:
                buffer.pop(0)

            if len(buffer) < seq_len:
                continue

            window = np.array(buffer, dtype=np.float32)
            window_norm = scaler.transform(window)
            x_in = torch.tensor(window_norm[None, :, :], dtype=torch.float32)
            prob = float(model(x_in).item())
            label = "🚨 FAILURE ALERT" if prob > 0.5 else "✅ Normal"
            phase = mode.ljust(16)
            print(f"  [{phase}] Failure Prob: {bar(prob)} {prob * 100:5.1f}%  {label}")


def main():
    print("[1/6] Generating synthetic telemetry...")
    train_loader, val_loader, scaler = prepare_dataloaders(n=4000, seq_len=30, horizon=5, batch_size=32)

    model = LSTMRegressor()

    print("[2/6] Dataloaders ready")
    print("[3/6] Training LSTM...")
    train_losses, val_losses = train_model(model, train_loader, val_loader, epochs=25, lr=1e-3)

    rmse = evaluate_rmse(model, val_loader)
    print(f"[4/6] Validation RMSE: {rmse:.4f}")
    print("(Target: RMSE < 0.30 for production use)")

    save_training_curve(train_losses, val_losses, output_path="training_curve.png")
    print("Plot saved: training_curve.png")

    torch.save(model.state_dict(), "motor_lstm.pt")
    np.save("scaler_mean.npy", scaler.mean_.astype(np.float32))
    np.save("scaler_scale.npy", scaler.scale_.astype(np.float32))
    print("Model saved: motor_lstm.pt")
    print("Scaler stats saved: scaler_mean.npy, scaler_scale.npy")

    run_live_demo(model, scaler, seq_len=30)

    print("[6/6] Recalibration Strategy for New Motor Brand")
    print("1) Fine-tune the last two layers on a small labeled dataset from the new motor.")
    print("2) Use transfer learning: keep early temporal feature layers frozen and adapt only the head.")
    print("3) Apply domain adaptation by normalizing features with motor-specific operating ranges.")
    print("   This preserves learned failure patterns while adapting to new baseline behavior.")
    print("Done.")


if __name__ == "__main__":
    main()
