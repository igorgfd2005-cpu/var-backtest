# Relatório de backtest de VaR

- Fonte: dados sintéticos GARCH(1,1) com caudas t
- Ativos: 4 | Pesos: 25,00%; 25,00%; 25,00%; 25,00%
- Período fora da amostra: 17/12/2020 a 01/10/2025
- Nível de confiança: 99,0% | Janela de estimação: 250 dias | Simulações Monte Carlo: 10.000

| Modelo | Exceções | Esperado | Taxa | p-valor Kupiec | p-valor Christoffersen (ind.) | p-valor cobertura condicional | VaR médio | ES médio |
|---|---|---|---|---|---|---|---|---|
| Simulação histórica | 16 | 12,50 | 1,28% | 0,340 | 0,519 | 0,516 | 2,03% | 2,44% |
| Paramétrico normal | 26 | 12,50 | 2,08% | 0,001 | 0,567 | 0,003 | 1,84% | 2,11% |
| EWMA (RiskMetrics) | 22 | 12,50 | 1,76% | 0,015 | 0,058 | 0,008 | 1,78% | 2,04% |
| Monte Carlo normal | 26 | 12,50 | 2,08% | 0,001 | 0,567 | 0,003 | 1,84% | 2,11% |
| Monte Carlo t de Student | 14 | 12,50 | 1,12% | 0,676 | 0,573 | 0,782 | 2,06% | 2,72% |

**Leitura:** p-valor abaixo de 0,05 rejeita o modelo ao nível de 5%. Kupiec testa se a quantidade de exceções está correta; Christoffersen testa se as exceções aparecem agrupadas (sinal de que o modelo não acompanha a volatilidade).

**Semáforo de Basileia (últimos 250 dias, VaR 99%):** Simulação histórica: verde; Paramétrico normal: verde; EWMA (RiskMetrics): verde; Monte Carlo normal: verde; Monte Carlo t de Student: verde

![Perdas x VaR](var_backtest.png)
