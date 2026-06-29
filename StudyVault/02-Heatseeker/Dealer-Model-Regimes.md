---
source_pdf: TSLA_KCU_Skylit_Master_Backtesting_Playbook.pdf
part: section 4
keywords: dealer model, GEX, VEX, gamma regime, long gamma, short gamma
---

# Dealer Pressure Model & Regimes ★★★

#heatseeker #node

## Core Concept

Heatseeker maps **dealer hedging obligations**. Dealers are not predicting — they are FORCED to buy/sell to manage their gamma exposure. Price behaves differently depending on whether dealers are stabilizing (long gamma) or accelerating (short gamma).

---

## Regime Table

| Regime | Dealer action | Price behavior | Trading implication |
|--------|--------------|----------------|---------------------|
| **Long Gamma / +GEX** | Buy dips, sell rips | Chop, mean reversion, fake breakouts, sticky nodes | Fade edges, take profits faster, don't chase |
| **Short Gamma / -GEX** | Sell weakness, buy strength | Breakouts/breakdowns continue, moves accelerate | Trade with momentum, respect air pockets, hold runners only with confirmation |
| **Vanna / VEX** | Volatility changes alter dealer delta | Nodes become magnets, especially when VIX elevated | Use VEX more when VIX > ~20; reduce trust in simple GEX floors/ceilings |

---

## VIX Threshold

- VIX > ~20: VEX/VANNA influence rises significantly
- When VIX > 20: reduce trust in GEX floor/ceiling reads alone; nodes can flip to magnets more aggressively
- When VIX < 20: standard GEX regime reads more reliable

---

## ASCII: Regime Identification Flow

```
At market open:
│
├── Look at dominant node color/magnitude
│   ├── +GEX dominates → Long Gamma regime
│   │   └── Fade edges, faster PTs, watch for chop
│   ├── -GEX dominates → Short Gamma regime
│   │   └── Momentum continues, hold runners with confirmation
│   └── Mixed / competing → Check King node for tie-break
│
└── Check VIX
    ├── VIX > 20 → VEX influence, nodes as magnets
    └── VIX < 20 → Standard GEX reads
```

---

## Key Implication for TSLA 0DTE

- In +GEX regime: mean-reversion is real — don't hold runners expecting continuation without fresh fuel confirmation
- In -GEX regime: momentum is real — air pockets mean fast moves, don't fade
- Never assume regime from yesterday carries to today — check the map fresh

## Related Notes
- [[Node-Taxonomy]]
- [[Node-Direction-Rules]]
- [[Heatseeker-Entry-vs-Target]]
