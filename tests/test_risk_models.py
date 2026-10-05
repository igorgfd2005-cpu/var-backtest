"""
Testes de validação numérica. Rodar com:  python -m pytest -q
Cada teste compara a implementação com um valor calculado à mão ou com teoria conhecida.
"""
import numpy as np
from scipy import stats

from src import backtest as bt
from src import risk_models as rm


def test_parametric_normal_formula():
    # Amostra construída com média exatamente 0 e desvio exatamente 1%.
    rng = np.random.default_rng(0)
    x = rng.standard_normal(1000)
    x = (x - x.mean()) / x.std(ddof=1) * 0.01
    var, es = rm.parametric_normal(x, 0.99)
    # VaR = 0,01 * 2,326348 = 0,02326348 ; ES = 0,01 * phi(2,326348) / 0,01 = 0,0266521
    assert abs(var - 0.01 * stats.norm.ppf(0.99)) < 1e-12
    assert abs(var - 0.02326348) < 1e-7
    assert abs(es - 0.0266521) < 1e-6


def test_historical_matches_theory_on_large_normal_sample():
    rng = np.random.default_rng(1)
    x = rng.normal(0, 0.01, 2_000_000)
    var, es = rm.historical(x, 0.99)
    assert abs(var - 0.02326348) < 2e-4
    assert abs(es - 0.0266521) < 2e-4


def test_monte_carlo_normal_converges_to_parametric():
    rng = np.random.default_rng(2)
    a = rng.multivariate_normal([0, 0], [[1e-4, 5e-5], [5e-5, 1e-4]], size=5000)
    w = np.array([0.5, 0.5])
    var_mc, _ = rm.monte_carlo(a, w, 0.99, n_sims=400_000, rng=np.random.default_rng(3))
    var_p, _ = rm.parametric_normal(a @ w, 0.99)
    assert abs(var_mc - var_p) / var_p < 0.01  # diferença relativa < 1%


def test_monte_carlo_t_preserves_variance_and_fattens_tail():
    rng = np.random.default_rng(4)
    a = rng.normal(0, 0.01, size=(3000, 1))
    w = np.array([1.0])
    var_n, es_n = rm.monte_carlo(a, w, 0.99, 400_000, "normal", rng=np.random.default_rng(5))
    var_t, es_t = rm.monte_carlo(a, w, 0.99, 400_000, "t", rng=np.random.default_rng(5))
    assert es_t > es_n  # cauda mais pesada => ES maior


def test_kupiec_hand_calculation():
    # n=250, x=10, p=0,01 => phat = 0,04
    # ln L0 = 240 ln(0,99) + 10 ln(0,01) = -48,46378
    # ln L1 = 240 ln(0,96) + 10 ln(0,04) = -41,98605
    # LR = -2(-48,46378) + 2(-41,98605) = 12,95546
    r = bt.kupiec_pof(10, 250, 0.99)
    assert abs(r["LR_pof"] - 12.95546) < 1e-4
    assert r["p_valor_pof"] < 0.001


def test_kupiec_zero_when_rate_is_exact():
    assert abs(bt.kupiec_pof(5, 500, 0.99)["LR_pof"]) < 1e-10


def test_christoffersen_detects_clustering():
    spread = np.zeros(500, dtype=int)
    spread[::100] = 1  # 5 exceções isoladas
    clustered = np.zeros(500, dtype=int)
    clustered[200:205] = 1  # 5 exceções seguidas
    assert bt.christoffersen(spread, 0.99)["p_valor_ind"] > 0.05
    assert bt.christoffersen(clustered, 0.99)["p_valor_ind"] < 0.01


def test_basel_zones():
    assert [bt.basel_zone(k) for k in (0, 4, 5, 9, 10)] == ["verde", "verde", "amarelo", "amarelo", "vermelho"]
