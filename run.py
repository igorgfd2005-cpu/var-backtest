"""
Executa o backtest completo e salva resultados em ./results

Exemplos:
    python run.py --synthetic
    python run.py --tickers PETR4.SA VALE3.SA ITUB4.SA BOVA11.SA --start 2019-01-01
    python run.py --tickers PETR4.SA VALE3.SA --weights 0.6 0.4 --alpha 0.975
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src import backtest as bt
from src import data

OUT = Path(__file__).parent / "results"
LABELS = {
    "historico": "Simulação histórica",
    "normal": "Paramétrico normal",
    "ewma": "EWMA (RiskMetrics)",
    "mc_normal": "Monte Carlo normal",
    "mc_t": "Monte Carlo t de Student",
}


def br(txt: str) -> str:
    """Converte separador decimal para o padrão brasileiro (vírgula)."""
    return txt.replace(".", ",")


def parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backtest de VaR e Expected Shortfall")
    p.add_argument("--synthetic", action="store_true", help="usa dados sintéticos (sem internet)")
    p.add_argument("--tickers", nargs="+", default=["PETR4.SA", "VALE3.SA", "ITUB4.SA", "BOVA11.SA"])
    p.add_argument("--weights", nargs="+", type=float, help="pesos (padrão: iguais)")
    p.add_argument("--start", default="2019-01-01")
    p.add_argument("--end", default=None)
    p.add_argument("--alpha", type=float, default=0.99)
    p.add_argument("--window", type=int, default=250)
    p.add_argument("--sims", type=int, default=10_000)
    return p.parse_args()


def plot(fc, alpha, path):
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(fc.index, fc["perda"] * 100, color="#9aa5b1", width=1.0, label="Perda realizada")
    for m, c in zip(("historico", "ewma", "mc_t"), ("#1f4e79", "#c0504d", "#2e7d32")):
        ax.plot(fc.index, fc[f"VaR_{m}"] * 100, lw=1.2, color=c, label=f"VaR {br(f'{alpha:.1%}')} {LABELS[m]}")
    exc = fc["perda"] > fc["VaR_ewma"]
    ax.scatter(fc.index[exc], fc["perda"][exc] * 100, color="#c0504d", s=14, zorder=3, label="Exceções (EWMA)")
    ax.set_ylabel("% do valor da carteira")
    ax.set_title("Perdas diárias x VaR previsto (fora da amostra)")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def report(summary, args, n_assets, weights, period, path):
    fmt = summary.copy()
    lines = [
        "# Relatório de backtest de VaR",
        "",
        f"- Fonte: {'dados sintéticos GARCH(1,1) com caudas t' if args.synthetic else 'Yahoo Finance'}",
        f"- Ativos: {n_assets} | Pesos: {br('; '.join(f'{w:.2%}' for w in weights))}",
        f"- Período fora da amostra: {period[0]:%d/%m/%Y} a {period[1]:%d/%m/%Y}",
        f"- Nível de confiança: {br(f'{args.alpha:.1%}')} | Janela de estimação: {args.window} dias | "
        f"Simulações Monte Carlo: {f'{args.sims:,}'.replace(',', '.')}",
        "",
        "| Modelo | Exceções | Esperado | Taxa | p-valor Kupiec | p-valor Christoffersen (ind.) | "
        "p-valor cobertura condicional | VaR médio | ES médio |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for m, r in fmt.iterrows():
        lines.append(br(
            f"| {LABELS[m]} | {r.excecoes} | {r.esperado:.2f} | {r.taxa_excecao:.2%} | "
            f"{r.p_valor_pof:.3f} | {r.p_valor_ind:.3f} | {r.p_valor_cc:.3f} | "
            f"{r.VaR_medio:.2%} | {r.ES_medio:.2%} |"
        ))
    lines += [
        "",
        "**Leitura:** p-valor abaixo de 0,05 rejeita o modelo ao nível de 5%. "
        "Kupiec testa se a quantidade de exceções está correta; Christoffersen testa "
        "se as exceções aparecem agrupadas (sinal de que o modelo não acompanha a volatilidade).",
    ]
    if "basel_ultimos_250" in fmt:
        lines += ["", "**Semáforo de Basileia (últimos 250 dias, VaR 99%):** " +
                  "; ".join(f"{LABELS[m]}: {z}" for m, z in fmt["basel_ultimos_250"].items())]
    lines += ["", "![Perdas x VaR](var_backtest.png)", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    args = parse()
    # A execução sintética grava em results/sintetico para não sobrescrever os resultados reais.
    out = OUT / "sintetico" if args.synthetic else OUT
    out.mkdir(parents=True, exist_ok=True)
    r = data.load_synthetic() if args.synthetic else data.load_yahoo(args.tickers, args.start, args.end)

    n = r.shape[1]
    weights = np.array(args.weights) if args.weights else np.full(n, 1 / n)
    if len(weights) != n or not np.isclose(weights.sum(), 1.0):
        raise SystemExit(f"Informe {n} pesos que somem 1. Soma recebida: {weights.sum():.4f}")

    print(f"Dados: {len(r)} dias, {n} ativos. Rodando backtest...")
    fc = bt.rolling_forecasts(r, weights, args.alpha, args.window, args.sims)
    summary = bt.evaluate(fc, args.alpha)

    fc.to_csv(out / "previsoes_diarias.csv", float_format="%.6f")
    summary.to_csv(out / "resumo_modelos.csv", float_format="%.6f")
    plot(fc, args.alpha, out / "var_backtest.png")
    report(summary, args, n, weights, (fc.index[0], fc.index[-1]), out / "relatorio.md")

    cols = ["excecoes", "esperado", "taxa_excecao", "p_valor_pof", "p_valor_ind", "VaR_medio", "ES_medio"]
    print(summary[cols].to_string(float_format=lambda v: f"{v:.4f}"))
    print(f"\nResultados salvos em {out}")


if __name__ == "__main__":
    main()
