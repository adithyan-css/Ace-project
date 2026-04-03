import math
import random
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class StrategyInput:
    tire_age: float
    track_temp: float
    fuel_load: float
    safety_car_probability: float = 0.1


def _lap_time_penalty(tire_age: float, track_temp: float, fuel_load: float) -> float:
    tire_penalty = 0.015 * max(0.0, tire_age)
    temp_penalty = 0.008 * max(0.0, track_temp - 30.0)
    fuel_penalty = 0.03 * max(0.0, fuel_load)
    return tire_penalty + temp_penalty + fuel_penalty


def _simulate_strategy(base: StrategyInput, pit_lap: int, laps: int = 30, simulations: int = 250) -> Dict[str, float]:
    total_times: List[float] = []
    for _ in range(simulations):
        tire_age = base.tire_age
        fuel = base.fuel_load
        race_time = 0.0

        for lap in range(1, laps + 1):
            if lap == pit_lap:
                race_time += 20.0 + random.uniform(-2.0, 2.0)
                tire_age = 1.0

            safety_car = random.random() < base.safety_car_probability
            sc_penalty = random.uniform(8.0, 20.0) if safety_car else 0.0

            lap_time = 90.0 + _lap_time_penalty(tire_age, base.track_temp, fuel) + random.uniform(-0.35, 0.35)
            race_time += lap_time + sc_penalty

            tire_age += 1.0
            fuel = max(0.0, fuel - 1.7)

        total_times.append(race_time)

    avg_time = sum(total_times) / len(total_times)
    variance = sum((t - avg_time) ** 2 for t in total_times) / len(total_times)
    std_dev = math.sqrt(variance)
    return {
        "pit_lap": pit_lap,
        "expected_race_time": round(avg_time, 3),
        "risk_std_dev": round(std_dev, 3),
    }


def optimize_strategy(payload: Dict[str, float]) -> Dict[str, object]:
    base = StrategyInput(
        tire_age=float(payload.get("tire_age", 8.0)),
        track_temp=float(payload.get("track_temp", 34.0)),
        fuel_load=float(payload.get("fuel_load", 28.0)),
        safety_car_probability=float(payload.get("safety_car_probability", 0.1)),
    )

    candidates = [_simulate_strategy(base, pit_lap=lap) for lap in range(8, 22)]
    best = min(candidates, key=lambda x: x["expected_race_time"])

    return {
        "status": "ok",
        "optimizer": "monte_carlo",
        "goal": "minimize_race_time",
        "best_strategy": {
            "pit_lap": best["pit_lap"],
            "expected_race_time": best["expected_race_time"],
            "risk_std_dev": best["risk_std_dev"],
        },
        "candidates": candidates,
    }
