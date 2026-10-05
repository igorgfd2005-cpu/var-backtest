"""
Modelos de Value at Risk (VaR) e Expected Shortfall (ES).

Convenção usada em todo o projeto:
  - Perda L = -r (retorno negativo vira perda positiva).
  - alpha = nível de confiança (ex.: 0,99).
  - VaR_alpha = quantil alpha da distribuição de perdas.
  - ES_alpha  = média das perdas que ultrapassam o VaR_alpha.
  - Ambos são devolvidos como números positivos, em fração da carteira
    (0,025 = perda de 2,5% do valor da carteira em 1 dia).
"""
from __future__ import annotations

import numpy as np
from scipy import stats


def portfolio_returns(asset_returns: np.ndarray, weights: np.ndarray) -> np.ndarray:
    return asset_returns @ weights


# ---------------------------------------------------------------- Histórico
def historical(port_r: np.ndarray, alpha: float) -> tuple[float, float]:
    """Simulação histórica: usa a distribuição empírica das perdas da janela."""
    losses = -np.asarray(port_r)
    var = float(np.quantile(losses, alpha))
    tail = losses[losses >= var]
    return var, float(tail.mean())


# ---------------------------------------------------------------- Paramétrico normal
def parametric_normal(port_r: np.ndarray, alpha: float) -> tuple[float, float]:
    """
    Supõe r ~ Normal(mu, sigma). Então L ~ Normal(-mu, sigma) e:
        VaR = -mu + sigma * z_alpha
        ES  = -mu + sigma * phi(z_alpha) / (1 - alpha)
    em que z_alpha = quantil da normal padrão e phi = densidade da normal padrão.
    """
    mu, sigma = float(np.mean(port_r)), float(np.std(port_r, ddof=1))
    z = stats.norm.ppf(alpha)
    return -mu + sigma * z, -mu + sigma * stats.norm.pdf(z) / (1 - alpha)


# ---------------------------------------------------------------- EWMA (RiskMetrics)
def ewma_normal(port_r: np.ndarray, alpha: float, lam: float = 0.94) -> tuple[float, float]:
    """
    Volatilidade EWMA (RiskMetrics, lambda = 0,94), média suposta zero:
        sigma2_t = lam * sigma2_{t-1} + (1 - lam) * r_{t-1}^2
    Dá mais peso a observações recentes e reage a choques de volatilidade.
    A variância inicial é a variância amostral das 30 primeiras observações.
    """
    r = np.asarray(port_r)
    s2 = float(np.var(r[:30], ddof=1))
    for x in r:
        s2 = lam * s2 + (1 - lam) * x * x
    sigma, z = np.sqrt(s2), stats.norm.ppf(alpha)
    return sigma * z, sigma * stats.norm.pdf(z) / (1 - alpha)


# ---------------------------------------------------------------- Monte Carlo
def monte_carlo(
    asset_r: np.ndarray,
    weights: np.ndarray,
    alpha: float,
    n_sims: int = 10_000,
    dist: str = "normal",
    nu: float = 5.0,
    rng: np.random.Generator | None = None,
) -> tuple[float, float]:
    """
    Simula retornos conjuntos dos ativos a partir da média e da matriz de
    covariância estimadas na janela, agrega na carteira e mede VaR/ES empíricos.

    dist="normal": normal multivariada.
    dist="t":      t de Student multivariada com nu graus de liberdade, escalada
                   para ter a MESMA covariância da janela:
                   X = mu + sqrt((nu-2)/nu) * (L z) / sqrt(W/nu),  W ~ qui-quadrado(nu)
                   (a t multivariada pura tem covariância nu/(nu-2) * Sigma,
                   por isso o fator de correção).
    """
    rng = rng or np.random.default_rng()
    mu = asset_r.mean(axis=0)
    cov = np.cov(asset_r, rowvar=False)
    chol = np.linalg.cholesky(cov + 1e-12 * np.eye(len(mu)))

    z = rng.standard_normal((n_sims, len(mu))) @ chol.T
    if dist == "t":
        w = rng.chisquare(nu, size=(n_sims, 1))
        z = z * np.sqrt((nu - 2) / nu) / np.sqrt(w / nu)
    elif dist != "normal":
        raise ValueError("dist deve ser 'normal' ou 't'")

    sims = (mu + z) @ weights
    return historical(sims, alpha)
