"""
Backtesting de VaR em janela móvel e testes estatísticos de cobertura.

Para cada dia t (a partir de 'window'), o modelo é estimado só com os 'window'
dias ANTERIORES a t (sem olhar o futuro) e a previsão é comparada com a perda
realizada em t. Uma "exceção" ocorre quando a perda realizada > VaR previsto.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from . import risk_models as rm

MODELS = ("historico", "normal", "ewma", "mc_normal", "mc_t")


def _xlogy(x: float, y: float) -> float:
    """x * ln(y), com a convenção 0 * ln(0) = 0."""
    return 0.0 if x == 0 else float(x * np.log(y))


def kupiec_pof(n_exc: int, n_obs: int, alpha: float) -> dict:
    """
    Teste de proporção de falhas de Kupiec (1995).
    H0: a frequência de exceções é igual a p = 1 - alpha.
        LR = -2 [ (n-x) ln(1-p) + x ln(p) ] + 2 [ (n-x) ln(1-x/n) + x ln(x/n) ]
    Sob H0, LR ~ qui-quadrado com 1 grau de liberdade.
    """
    p, x, n = 1 - alpha, n_exc, n_obs
    phat = x / n
    lr = -2 * (_xlogy(n - x, 1 - p) + _xlogy(x, p)) + 2 * (_xlogy(n - x, 1 - phat) + _xlogy(x, phat))
    lr = max(lr, 0.0)
    return {"LR_pof": lr, "p_valor_pof": float(stats.chi2.sf(lr, 1))}


def christoffersen(exc: np.ndarray, alpha: float) -> dict:
    """
    Teste de independência de Christoffersen (1998): exceções não devem vir
    agrupadas. Conta transições n_ij (estado i ontem -> estado j hoje).
        LR_ind = -2 ln L(pi) + 2 ln L(pi01, pi11)   ~ qui-quadrado(1)
    Cobertura condicional: LR_cc = LR_pof + LR_ind   ~ qui-quadrado(2)
    """
    e = np.asarray(exc, dtype=int)
    prev, curr = e[:-1], e[1:]
    n00 = int(np.sum((prev == 0) & (curr == 0)))
    n01 = int(np.sum((prev == 0) & (curr == 1)))
    n10 = int(np.sum((prev == 1) & (curr == 0)))
    n11 = int(np.sum((prev == 1) & (curr == 1)))

    pi01 = n01 / (n00 + n01) if (n00 + n01) else 0.0
    pi11 = n11 / (n10 + n11) if (n10 + n11) else 0.0
    pi = (n01 + n11) / (n00 + n01 + n10 + n11)

    ll_h0 = _xlogy(n00 + n10, 1 - pi) + _xlogy(n01 + n11, pi)
    ll_h1 = _xlogy(n00, 1 - pi01) + _xlogy(n01, pi01) + _xlogy(n10, 1 - pi11) + _xlogy(n11, pi11)
    lr_ind = max(-2 * ll_h0 + 2 * ll_h1, 0.0)

    pof = kupiec_pof(int(e.sum()), len(e), alpha)
    lr_cc = pof["LR_pof"] + lr_ind
    return {
        "LR_ind": lr_ind,
        "p_valor_ind": float(stats.chi2.sf(lr_ind, 1)),
        "LR_cc": lr_cc,
        "p_valor_cc": float(stats.chi2.sf(lr_cc, 2)),
    }


def basel_zone(n_exc_last_250: int) -> str:
    """Semáforo de Basileia para VaR 99% em 250 dias: verde 0-4, amarelo 5-9, vermelho 10+."""
    if n_exc_last_250 <= 4:
        return "verde"
    return "amarelo" if n_exc_last_250 <= 9 else "vermelho"


def rolling_forecasts(
    asset_r: pd.DataFrame,
    weights: np.ndarray,
    alpha: float = 0.99,
    window: int = 250,
    n_sims: int = 10_000,
    seed: int = 7,
) -> pd.DataFrame:
    """Gera previsões de VaR e ES de cada modelo para cada dia fora da amostra."""
    rng = np.random.default_rng(seed)
    a = asset_r.to_numpy()
    port = rm.portfolio_returns(a, weights)
    rows = []
    for t in range(window, len(a)):
        win_a, win_p = a[t - window:t], port[t - window:t]
        row = {"data": asset_r.index[t], "retorno": port[t], "perda": -port[t]}
        estimates = {
            "historico": rm.historical(win_p, alpha),
            "normal": rm.parametric_normal(win_p, alpha),
            "ewma": rm.ewma_normal(win_p, alpha),
            "mc_normal": rm.monte_carlo(win_a, weights, alpha, n_sims, "normal", rng=rng),
            "mc_t": rm.monte_carlo(win_a, weights, alpha, n_sims, "t", rng=rng),
        }
        for name, (var, es) in estimates.items():
            row[f"VaR_{name}"], row[f"ES_{name}"] = var, es
        rows.append(row)
    return pd.DataFrame(rows).set_index("data")


def evaluate(fc: pd.DataFrame, alpha: float) -> pd.DataFrame:
    """Resume exceções e testes estatísticos por modelo."""
    n = len(fc)
    out = []
    for m in MODELS:
        exc = (fc["perda"] > fc[f"VaR_{m}"]).to_numpy()
        x = int(exc.sum())
        res = {
            "modelo": m,
            "observacoes": n,
            "excecoes": x,
            "esperado": round(n * (1 - alpha), 2),
            "taxa_excecao": x / n,
            **kupiec_pof(x, n, alpha),
            **christoffersen(exc, alpha),
            "VaR_medio": fc[f"VaR_{m}"].mean(),
            "ES_medio": fc[f"ES_{m}"].mean(),
        }
        if abs(alpha - 0.99) < 1e-9:
            res["basel_ultimos_250"] = basel_zone(int(exc[-250:].sum()))
        out.append(res)
    return pd.DataFrame(out).set_index("modelo")
