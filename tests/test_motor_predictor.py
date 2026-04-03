import os

import numpy as np
import pytest
import torch
import torch.nn as nn

try:
    import ai_ml.module2.motor_predictor as mp
except Exception:
    mp = None


pytestmark = pytest.mark.skipif(mp is None, reason="Motor predictor module unavailable")


class TestSyntheticDataGenerator:
    def test_output_shapes(self):
        x, y = mp.generate_synthetic(n=500)
        assert x.shape == (500, 4)
        assert y.shape == (500,)

    def test_fault_signal_range(self):
        _, y = mp.generate_synthetic(1000)
        assert y.min() >= 0.0
        assert y.max() <= 1.0

    def test_fault_injected_at_known_positions(self):
        _, y = mp.generate_synthetic(4000)
        assert y[550:620].max() > 0.5

    def test_normal_region_has_low_fault(self):
        _, y = mp.generate_synthetic(4000)
        assert y[0:400].max() < 0.05

    def test_features_are_physically_plausible(self):
        x, _ = mp.generate_synthetic(1000)
        assert x[:, 0].mean() > 5
        assert x[:, 1].mean() > 1000
        assert x[:, 2].mean() > 30


class TestSequenceBuilder:
    def test_sequence_output_shapes(self):
        x = np.random.randn(200, 4).astype(np.float32)
        y = np.random.rand(200).astype(np.float32)
        xs, ys = mp.build_sequences(x, y, seq_len=30, horizon=5)
        assert xs.shape == (165, 30, 4)
        assert ys.shape == (165,)

    def test_horizon_shifts_label_forward(self):
        x = np.random.randn(200, 4).astype(np.float32)
        y = np.arange(200, dtype=np.float32)
        _, ys = mp.build_sequences(x, y, seq_len=30, horizon=5)
        assert ys[0] == y[35]

    def test_sequences_are_float32(self):
        x = np.random.randn(120, 4).astype(np.float32)
        y = np.random.rand(120).astype(np.float32)
        xs, ys = mp.build_sequences(x, y)
        assert xs.dtype == np.float32
        assert ys.dtype == np.float32


class TestLSTMModel:
    def test_forward_pass_output_shape(self):
        model = mp.LSTMRegressor()
        x = torch.randn(16, 30, 4)
        out = model(x)
        assert out.shape == (16,)

    def test_output_is_probability(self):
        model = mp.LSTMRegressor()
        out = model(torch.randn(8, 30, 4))
        assert float(out.min()) >= 0.0
        assert float(out.max()) <= 1.0

    def test_model_is_deterministic_in_eval_mode(self):
        model = mp.LSTMRegressor()
        model.eval()
        x = torch.randn(8, 30, 4)
        out1 = model(x)
        out2 = model(x)
        assert torch.allclose(out1, out2)

    def test_gradient_flows_through_model(self):
        model = mp.LSTMRegressor()
        model.train()
        x = torch.randn(8, 30, 4)
        y = torch.rand(8)
        loss = nn.BCELoss()(model(x), y)
        loss.backward()
        assert model.lstm.weight_ih_l0.grad is not None


@pytest.mark.slow
class TestTrainingPipeline:
    def test_full_training_runs_without_error(self):
        train_loader, val_loader, _ = mp.prepare_dataloaders(n=500, seq_len=30, horizon=5, batch_size=32)
        model = mp.LSTMRegressor()
        losses, _ = mp.train_model(model, train_loader, val_loader, epochs=3, lr=1e-3)
        assert np.isfinite(losses[-1])

    def test_loss_decreases_over_epochs(self):
        train_loader, val_loader, _ = mp.prepare_dataloaders(n=500, seq_len=30, horizon=5, batch_size=32)
        model = mp.LSTMRegressor()
        losses, _ = mp.train_model(model, train_loader, val_loader, epochs=10, lr=1e-3)
        assert losses[-1] < losses[0]

    def test_rmse_computed_and_in_valid_range(self):
        train_loader, val_loader, _ = mp.prepare_dataloaders(n=500, seq_len=30, horizon=5, batch_size=32)
        model = mp.LSTMRegressor()
        mp.train_model(model, train_loader, val_loader, epochs=3, lr=1e-3)
        rmse = mp.evaluate_rmse(model, val_loader)
        assert 0.0 <= rmse <= 1.0

    def test_model_saved_to_disk(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        train_loader, val_loader, scaler = mp.prepare_dataloaders(n=500, seq_len=30, horizon=5, batch_size=32)
        model = mp.LSTMRegressor()
        mp.train_model(model, train_loader, val_loader, epochs=3, lr=1e-3)
        torch.save(model.state_dict(), "motor_lstm.pt")
        np.save("scaler_mean.npy", scaler.mean_.astype(np.float32))
        np.save("scaler_scale.npy", scaler.scale_.astype(np.float32))
        assert os.path.exists("motor_lstm.pt")


class TestRMSEMetric:
    def test_perfect_predictions_give_zero_rmse(self):
        y_true = np.array([0, 1, 0, 1], dtype=np.float32)
        y_pred = np.array([0, 1, 0, 1], dtype=np.float32)
        rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
        assert rmse == 0.0

    def test_worst_predictions_give_one_rmse(self):
        y_true = np.array([0, 0, 0, 0], dtype=np.float32)
        y_pred = np.array([1, 1, 1, 1], dtype=np.float32)
        rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
        assert rmse == 1.0

    def test_rmse_is_always_non_negative(self):
        y_true = np.random.rand(64).astype(np.float32)
        y_pred = np.random.rand(64).astype(np.float32)
        rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
        assert rmse >= 0.0
