import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import train_test_split
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


print("[1/4] Generating synthetic telemetry...")
x, y = generate_synthetic()

print("[2/4] Building sequences...")
seq_len = 30
horizon = 5
xs, ys = build_sequences(x, y, seq_len=seq_len, horizon=horizon)

x_train, x_val, y_train, y_val = train_test_split(xs, ys, test_size=0.2, random_state=42, shuffle=True)

x_train_t = torch.tensor(x_train)
y_train_t = torch.tensor(y_train)
x_val_t = torch.tensor(x_val)
y_val_t = torch.tensor(y_val)

model = LSTMRegressor()
criterion = nn.MSELoss()
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

train_losses = []
val_losses = []

print("[3/4] Training LSTM...")
epochs = 30
batch_size = 64

for epoch in range(1, epochs + 1):
    model.train()
    perm = torch.randperm(x_train_t.size(0))
    running = 0.0

    for i in range(0, x_train_t.size(0), batch_size):
        idx = perm[i:i + batch_size]
        xb = x_train_t[idx]
        yb = y_train_t[idx]

        optimizer.zero_grad()
        pred = model(xb)
        loss = criterion(pred, yb)
        loss.backward()
        optimizer.step()
        running += loss.item() * xb.size(0)

    train_loss = running / x_train_t.size(0)

    model.eval()
    with torch.no_grad():
        val_pred = model(x_val_t)
        val_loss = criterion(val_pred, y_val_t).item()

    train_losses.append(train_loss)
    val_losses.append(val_loss)

    if epoch % 5 == 0 or epoch == 1:
        print(f"  Epoch {epoch:2d}/{epochs}  train_loss={train_loss:.4f}  val_loss={val_loss:.4f}")

model.eval()
with torch.no_grad():
    y_hat = model(x_val_t).numpy()

rmse = mean_squared_error(y_val, y_hat, squared=False)
print(f"RMSE (validation): {rmse:.4f}")

plt.figure(figsize=(8, 4))
plt.plot(train_losses, label="train_loss")
plt.plot(val_losses, label="val_loss")
plt.title("LSTM Training Curve")
plt.xlabel("Epoch")
plt.ylabel("Loss")
plt.legend()
plt.tight_layout()
plt.savefig("training_curve.png", dpi=150)

normal_window = x[200:200 + seq_len]
failure_window = x[3050:3050 + seq_len]

with torch.no_grad():
    p_normal = float(model(torch.tensor(normal_window[None, :, :])).item())
    p_failure = float(model(torch.tensor(failure_window[None, :, :])).item())

print("=== LIVE INFERENCE DEMO ===")
print(f"  [normal  ] Failure Prob: {bar(p_normal)} {p_normal * 100:.1f}%  ✅ Normal")
print(f"  [failure ] Failure Prob: {bar(p_failure)} {p_failure * 100:.1f}% 🚨 FAILURE ALERT")
print("[4/4] Done. Saved training_curve.png")
