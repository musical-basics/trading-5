# Bug Record: Risk APT Infinite Zero-Shrinkage Loop (MCR Scaling)

## The Bug
When evaluating strategies (like `Momentum 6M`, `Fortress`, `SMA Crossover`) that returned a subset of assets (e.g. 9 selected stocks), the Level 4 Risk System (`apply_risk_constraints`) aggressively scaled all their weights down to `~0.000000002` (effectively 0). The `portfolio_rebalancer` then floored the target shares calculation, resulting in `0 shares` and `0 intents` routed to the paper broker, causing the dashboard's Live Positions to perpetually show empty despite executing strategies.

## The Cause
The `iterative_mcr_scale` function was attempting to bound the absolute Marginal Contribution to Risk (MCR) to 5% (`MAX_MCR_THRESHOLD = 0.05`). However, mathematical MCR evaluated via $\sigma_w / \sigma_{port}$ is **scale-invariant**. If all weights are scaled down by $c$, the portfolio volatility also scales down by $c$, so MCR is completely unaffected by absolute scaling. 

Because of the scale invariance, the `while` loop evaluated the MCR:
1. Observed MCR > 0.05.
2. Scaled all weights down by e.g. 0.6.
3. Looped, checked MCR again.
4. MCR was mathematically identical (still > 0.05), so it scaled weights down by another 0.6.
5. This repeated 50 times until the portfolio variance hit the epsilon floor `1e-10`, crashing the resulting portfolio weights to infinitesimal fractions.

Furthermore, a hard threshold of 5% Relative Risk (where Component Volatility = $w_i \cdot MCR_i$) mathematically *demands* at least 20 components to satisfy ($1/20 = 5\%$). It is impossible to force a 9-stock portfolio to satisfy a 5% risk cap per asset without violating the sum constraint. 

## Failed Fixes
- Assuming `MAX_PORTFOLIO_VOL` (portfolio volatility cap at 25%) was suppressing the weights incorrectly. Tracing the MCR vector inside the while loop revealed it was the specific MCR bounds check causing 50 iterations of shrinkage, not the portfolio volatility cap.

## The Final Solution
1. **Redefined to Relative Risk Contribution (RRC):** Instead of bounding the absolute MCR, we now evaluate the true unit metric: `rrc = (w * mcr) / port_vol` (the percentage of total risk each asset contributes).
2. **Dynamic Limit Relaxation:** Since an $N$-asset portfolio averages $1/N$ relative risk, enforcing a static 5% limit on $N < 20$ causes crashes. We dynamically bounded the limit: `dynamic_limit = max(max_mcr, 1.25 / max(active_assets, 1))`. This ensures the algorithm mathematically converges even for highly concentrated strategies.
3. The shrinking scale factor became `dynamic_limit / rrc[j]`, explicitly adjusting the *relative* weights of breaching assets. 

The rebalancer pipeline immediately propagated normal integer share allocations post-fix.
