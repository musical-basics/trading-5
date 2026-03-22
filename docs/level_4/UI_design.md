You are an expert Next.js, Tailwind CSS, and shadcn/ui frontend engineer designing an institutional quantitative trading terminal. 

Create a comprehensive, dark-mode dashboard. The vibe should be "Modern Bloomberg Terminal meets Vercel" — high density, highly technical, but beautifully clean with high contrast (slate-950 backgrounds, neon accents for data). Use Lucide React for icons.

I need a Sidebar Navigation layout with a top Command Bar, and 4 distinct view states (Pages) that I can toggle between:

1. **"Strategy Studio" (The Sandbox)**
   - Left panel: A list of 12 strategies with checkboxes (e.g., "EV/Sales", "L/S Z-Score", "XGBoost AI") and a "Run Backtest" primary button.
   - Main panel: A large, beautiful area chart (using Recharts) showing the equity curves of the selected strategies superimposed over a dashed SPY benchmark.
   - Bottom panel: A dense shadcn/ui Table showing metrics for the selected strategies: Total Return, Sharpe, Max Drawdown, CAGR. 

2. **"X-Ray Inspector" (Verification Engine)**
   - Purpose: To verify ML and Risk math on a specific day for a specific stock.
   - Top bar: A Date Picker input and a Ticker Search input (e.g., "NVDA").
   - The Funnel Layout: A vertical sequence of cards connected by arrows (downward flow) showing the pipeline mathematical transformation:
     - Card 1 (Raw Data): Price, Volume, Q3 Revenue, Debt.
     - Card 2 (Heuristics): EV/Sales Ratio, Z-Score, Dynamic Discount Rate.
     - Card 3 (XGBoost): Predicted Forward Return, Feature Importance breakdown. Shows "Raw Desired Weight: 18%".
     - Card 4 (Risk APT Bouncer): Shows Covariance Penalty and MCR. Example text: "MCR breach detected. Scaled Weight: 18% -> 9.5%". Highlight this card in amber/red if scaled down.
     - Card 5 (Final Order): "Target Allocation: 9.5%".

3. **"Risk War Room" (Macro & Covariance)**
   - Top cards: Latest VIX, 10Y Yield, Current Macro Regime (e.g., "Risk-On").
   - Left side: A visual heatmap (using a grid of colored squares) representing the Covariance Matrix of the current portfolio.
   - Right side: A bar chart showing the "Top 5 Marginal Contributors to Risk (MCR)" in the current portfolio, with a red dashed threshold line at 5%.

4. **"Execution Ledger"**
   - A clear, wide table showing pending orders: Ticker, Action (Buy/Sell tag with green/red colors), Quantity, Target Weight.
   - A large, prominent "Route Paper Trades" action button at the top right.

Please generate the complete React code for this shell. Ensure it looks incredibly professional, handles responsive layout, and uses mocked JSON data so I can see how it looks immediately.
