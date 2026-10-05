"""
Carregamento de dados de mercado.

Duas fontes:
  1. Yahoo Finance (via yfinance), com tickers da B3 (sufixo .SA).
  2. Dados sintéticos com volatilidade condicional (GARCH(1,1)) e caudas pesadas
     (t de Student), úteis para testar o código sem internet e para mostrar
     por que modelos normais com volatilidade constante falham no backtest.

Todos os retornos são SIMPLES (P_t / P_{t-1} - 1), porque o retorno de uma
carteira é a média ponderada exata dos retornos simples dos ativos:
    r_carteira = soma(w_i * r_i)
Com log-retornos essa soma seria apenas uma aproximação.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def load_yahoo(tickers: list[str], start: str, end: str | None = None) -> pd.DataFrame:
    """Baixa preços ajustados e devolve retornos simples diários (linhas = datas)."""
    import yfinance as yf

    prices = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)["Close"]
    if isinstance(prices, pd.Series):
        prices = prices.to_frame(tickers[0])
    prices = prices[tickers].dropna(how="any")
    if prices.empty:
        raise RuntimeError("Nenhum preço retornado. Verifique tickers, datas e conexão.")
    return prices.pct_change().dropna()


def load_synthetic(n_assets: int = 4, n_days: int = 1500, seed: int = 42) -> pd.DataFrame:
    """
    Gera retornos diários com GARCH(1,1) e inovações t de Student (5 graus de liberdade),
    com correlação entre ativos de 0,5.

    Parâmetros GARCH: omega=2e-6, alpha=0,08, beta=0,90.
    Variância incondicional = omega / (1 - alpha - beta) = 2e-6 / 0,02 = 1e-4
    => volatilidade diária de longo prazo = 1% (~15,9% ao ano com 252 dias).
    """
    rng = np.random.default_rng(seed)
    omega, a, b, nu, rho, drift = 2e-6, 0.08, 0.90, 5, 0.5, 0.0003

    corr = np.full((n_assets, n_assets), rho)
    np.fill_diagonal(corr, 1.0)
    chol = np.linalg.cholesky(corr)

    # t de Student padronizada para variância 1: t * sqrt((nu-2)/nu)
    z = rng.standard_t(nu, size=(n_days, n_assets)) * np.sqrt((nu - 2) / nu)
    z = z @ chol.T

    var = np.full(n_assets, omega / (1 - a - b))
    out = np.empty((n_days, n_assets))
    for t in range(n_days):
        shock = np.sqrt(var) * z[t]
        out[t] = shock + drift
        var = omega + a * shock**2 + b * var

    dates = pd.bdate_range("2020-01-02", periods=n_days)
    return pd.DataFrame(out, index=dates, columns=[f"ATIVO_{i+1}" for i in range(n_assets)])
