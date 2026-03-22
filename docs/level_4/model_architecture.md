# Level 4 Model Architecture: X-Ray Transparency & The Risk Fix

The core financial logic established in Level 3 remains identical. We are optimizing how the math executes and forcing it to leave an audit trail.

## 1. The Iterative Risk Matrix Fix
In Level 3, the Bouncer scaled down risky tech stocks (lowering total weight), and then naively divided everyone by the new total to reach 95% exposure. This violently inflated the weights of "safe" stocks, causing their MCR to explode to 48%.

**Level 4 Solution:** The Risk System must use a convergence loop.
1. Calculate MCR.
2. If breach: scale down ONLY the breaching assets.
3. Re-allocate excess cash to non-breaching assets *only up to the point where they hit the MCR limit*.
4. Repeat until all assets MCR < 5% and Total Weight <= 95%.

## 2. Solving the "Verification Problem" (The X-Ray)
To trust the XGBoost and Risk matrix calculations, the pipeline MUST emit intermediate calculation artifacts to DuckDB so the UI can reconstruct the math on demand.

**The Entity X-Ray Endpoint:**
We will expose a FastAPI endpoint: `GET /api/xray/{entity_id}/{date}`.
Because our data is purely columnar, this endpoint fetches an instantaneous vertical slice of the pipeline for Apple on Sept 14th:
* **Raw:** Price=$150, Revenue=$80B
* **Factor:** Beta_SPY=1.1, Beta_VIX=-0.2
* **XGBoost:** Predicted_Return = 0.04 -> Raw_Weight = 12%
* **Risk APT:** MCR = 0.08 (Breached > 0.05) -> Scaled weight from 12% to 7.5%.

The UI will literally show this waterfall, destroying the "Black Box."
