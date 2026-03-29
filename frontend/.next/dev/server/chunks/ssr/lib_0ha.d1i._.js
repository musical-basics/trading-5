module.exports = [
"[project]/lib/utils.ts [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "cn",
    ()=>cn
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$clsx$40$2$2e$1$2e$1$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/.pnpm/clsx@2.1.1/node_modules/clsx/dist/clsx.mjs [app-ssr] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$tailwind$2d$merge$40$3$2e$5$2e$0$2f$node_modules$2f$tailwind$2d$merge$2f$dist$2f$bundle$2d$mjs$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/.pnpm/tailwind-merge@3.5.0/node_modules/tailwind-merge/dist/bundle-mjs.mjs [app-ssr] (ecmascript)");
;
;
function cn(...inputs) {
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$tailwind$2d$merge$40$3$2e$5$2e$0$2f$node_modules$2f$tailwind$2d$merge$2f$dist$2f$bundle$2d$mjs$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["twMerge"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f2e$pnpm$2f$clsx$40$2$2e$1$2e$1$2f$node_modules$2f$clsx$2f$dist$2f$clsx$2e$mjs__$5b$app$2d$ssr$5d$__$28$ecmascript$29$__["clsx"])(inputs));
}
}),
"[project]/lib/api.ts [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "combineAlphaStrategies",
    ()=>combineAlphaStrategies,
    "createTrader",
    ()=>createTrader,
    "deleteAlphaExperiment",
    ()=>deleteAlphaExperiment,
    "fetchAlignedProfile",
    ()=>fetchAlignedProfile,
    "fetchAlphaExperiment",
    ()=>fetchAlphaExperiment,
    "fetchAlphaExperiments",
    ()=>fetchAlphaExperiments,
    "fetchAlphaModelTiers",
    ()=>fetchAlphaModelTiers,
    "fetchAuditModels",
    ()=>fetchAuditModels,
    "fetchExperimentTrades",
    ()=>fetchExperimentTrades,
    "fetchIndicators",
    ()=>fetchIndicators,
    "fetchPipelineCoverage",
    ()=>fetchPipelineCoverage,
    "fetchStrategies",
    ()=>fetchStrategies,
    "fetchXrayData",
    ()=>fetchXrayData,
    "fetchXrayTickers",
    ()=>fetchXrayTickers,
    "generateAlphaStrategy",
    ()=>generateAlphaStrategy,
    "getEditorSetting",
    ()=>getEditorSetting,
    "getPipelineLogs",
    ()=>getPipelineLogs,
    "getPipelineStatus",
    ()=>getPipelineStatus,
    "getPortfolios",
    ()=>getPortfolios,
    "getSwarmStreamUrl",
    ()=>getSwarmStreamUrl,
    "getTraders",
    ()=>getTraders,
    "promoteAlphaExperiment",
    ()=>promoteAlphaExperiment,
    "runAlphaBacktest",
    ()=>runAlphaBacktest,
    "runForensicAudit",
    ()=>runForensicAudit,
    "runPipelineFull",
    ()=>runPipelineFull,
    "runPipelineIngest",
    ()=>runPipelineIngest,
    "runPipelineScoring",
    ()=>runPipelineScoring,
    "runStandaloneBacktest",
    ()=>runStandaloneBacktest,
    "runTournament",
    ()=>runTournament,
    "runTraderBacktest",
    ()=>runTraderBacktest,
    "saveEditorSetting",
    ()=>saveEditorSetting,
    "saveSwarmResult",
    ()=>saveSwarmResult,
    "updateAlphaCode",
    ()=>updateAlphaCode,
    "updateConstraints",
    ()=>updateConstraints,
    "updatePortfolioSchedule",
    ()=>updatePortfolioSchedule,
    "updatePortfolioStrategy",
    ()=>updatePortfolioStrategy
]);
/**
 * api.ts — Typed API client for the FastAPI backend.
 *
 * Uses NEXT_PUBLIC_API_URL from .env.local (default: http://localhost:8000).
 */ const API_BASE = ("TURBOPACK compile-time value", "http://localhost:8000") ?? "http://localhost:8000";
async function fetchStrategies() {
    const res = await fetch(`${API_BASE}/api/strategies/list`);
    if (!res.ok) throw new Error(`Failed to fetch strategies: ${res.status}`);
    const data = await res.json();
    return data.strategies;
}
async function runTournament(params) {
    const res = await fetch(`${API_BASE}/api/strategies/tournament`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            strategies: params.strategies ?? null,
            start_date: params.startDate ?? null,
            end_date: params.endDate ?? null,
            starting_capital: params.startingCapital ?? 10000
        })
    });
    if (!res.ok) {
        const text = await res.text().catch(()=>"Unknown error");
        throw new Error(`Tournament failed (${res.status}): ${text}`);
    }
    return await res.json();
}
async function getTraders() {
    const res = await fetch(`${API_BASE}/api/traders/`);
    if (!res.ok) throw new Error(`Failed to fetch traders: ${res.status}`);
    return await res.json();
}
async function createTrader(name, capital, numPortfolios = 10, capitalPerPortfolio) {
    const res = await fetch(`${API_BASE}/api/traders/`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            name,
            total_capital: capital,
            num_portfolios: numPortfolios,
            capital_per_portfolio: capitalPerPortfolio ?? null
        })
    });
    if (!res.ok) {
        const text = await res.text().catch(()=>"Unknown error");
        throw new Error(`Failed to create trader: ${text}`);
    }
    return await res.json();
}
async function updateConstraints(traderId, data) {
    const res = await fetch(`${API_BASE}/api/traders/${traderId}/constraints`, {
        method: "PUT",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error(`Failed to update constraints: ${res.status}`);
}
async function getPortfolios(traderId) {
    const res = await fetch(`${API_BASE}/api/traders/${traderId}/portfolios`);
    if (!res.ok) throw new Error(`Failed to fetch portfolios: ${res.status}`);
    return await res.json();
}
async function updatePortfolioStrategy(portfolioId, strategyId) {
    const res = await fetch(`${API_BASE}/api/portfolios/${portfolioId}/strategy`, {
        method: "PUT",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            strategy_id: strategyId
        })
    });
    if (!res.ok) throw new Error(`Failed to assign strategy: ${res.status}`);
}
async function updatePortfolioSchedule(portfolioId, freq) {
    const res = await fetch(`${API_BASE}/api/portfolios/${portfolioId}/schedule`, {
        method: "PUT",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            rebalance_freq: freq
        })
    });
    if (!res.ok) throw new Error(`Failed to update schedule: ${res.status}`);
}
async function runTraderBacktest(traderId, startDate, endDate) {
    const res = await fetch(`${API_BASE}/api/traders/${traderId}/backtest`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            start_date: startDate ?? null,
            end_date: endDate ?? null
        })
    });
    if (!res.ok) {
        const text = await res.text().catch(()=>"Unknown error");
        throw new Error(`Backtest failed: ${text}`);
    }
    return await res.json();
}
async function fetchXrayTickers() {
    const res = await fetch(`${API_BASE}/api/diagnostics/tickers`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.tickers ?? [];
}
async function fetchXrayData(ticker, date) {
    const res = await fetch(`${API_BASE}/api/diagnostics/xray/${ticker}/${date}`);
    if (!res.ok) {
        const text = await res.text().catch(()=>"Unknown error");
        throw new Error(`X-Ray failed: ${text}`);
    }
    return await res.json();
}
async function fetchPipelineCoverage() {
    const res = await fetch(`${API_BASE}/api/diagnostics/pipeline-coverage`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.tickers ?? [];
}
async function fetchIndicators(ticker, rfrSource = "irx") {
    const res = await fetch(`${API_BASE}/api/indicators/${ticker}?rfr_source=${rfrSource}`);
    if (!res.ok) return null;
    return await res.json();
}
async function fetchAlphaModelTiers() {
    const res = await fetch(`${API_BASE}/api/alpha-lab/tiers`);
    if (!res.ok) return {};
    return await res.json();
}
async function generateAlphaStrategy(prompt, modelTier, strategyStyle = "academic") {
    const res = await fetch(`${API_BASE}/api/alpha-lab/generate?prompt=${encodeURIComponent(prompt)}&model_tier=${modelTier}&strategy_style=${strategyStyle}`, {
        method: "POST"
    });
    return await res.json();
}
function getSwarmStreamUrl(prompt, strategyStyle, agentTiers, agentNotes) {
    const params = new URLSearchParams();
    if (prompt) params.append("prompt", prompt);
    params.append("strategy_style", strategyStyle);
    params.append("agent_tiers", JSON.stringify(agentTiers));
    params.append("agent_notes", JSON.stringify(agentNotes));
    return `${API_BASE}/api/alpha-lab/generate-swarm-stream?${params.toString()}`;
}
async function saveSwarmResult(data) {
    const res = await fetch(`${API_BASE}/api/alpha-lab/generate-swarm-save`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            name: data.name,
            hypothesis: data.hypothesis,
            rationale: data.rationale,
            code: data.code,
            model_tier: data.model_tier,
            input_tokens: data.input_tokens,
            output_tokens: data.output_tokens,
            cost_usd: data.cost_usd
        })
    });
    return await res.json();
}
async function runStandaloneBacktest(code) {
    const res = await fetch(`${API_BASE}/api/alpha-lab/standalone-backtest`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            code
        })
    });
    return await res.json();
}
async function runAlphaBacktest(experimentId) {
    const res = await fetch(`${API_BASE}/api/alpha-lab/${experimentId}/backtest`, {
        method: "POST"
    });
    return await res.json();
}
async function fetchAlphaExperiments() {
    const res = await fetch(`${API_BASE}/api/alpha-lab/experiments`);
    if (!res.ok) return [];
    return await res.json();
}
async function fetchAlphaExperiment(experimentId) {
    const res = await fetch(`${API_BASE}/api/alpha-lab/${experimentId}`);
    if (!res.ok) return null;
    return await res.json();
}
async function deleteAlphaExperiment(experimentId) {
    const res = await fetch(`${API_BASE}/api/alpha-lab/${experimentId}`, {
        method: "DELETE"
    });
    const data = await res.json();
    return data.deleted === true;
}
async function updateAlphaCode(experimentId, code) {
    const res = await fetch(`${API_BASE}/api/alpha-lab/${experimentId}/code`, {
        method: "PATCH",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            code
        })
    });
    return await res.json();
}
async function promoteAlphaExperiment(experimentId) {
    const res = await fetch(`${API_BASE}/api/alpha-lab/${experimentId}/promote`, {
        method: "POST"
    });
    return await res.json();
}
async function combineAlphaStrategies(experimentIds, modelTier = "sonnet", guidance = "") {
    const params = new URLSearchParams({
        experiment_ids: experimentIds.join(","),
        model_tier: modelTier,
        guidance
    });
    const res = await fetch(`${API_BASE}/api/alpha-lab/combine?${params.toString()}`, {
        method: "POST"
    });
    return await res.json();
}
async function getEditorSetting(key) {
    const res = await fetch(`${API_BASE}/api/alpha-lab/settings/${key}`);
    const data = await res.json();
    return data.value;
}
async function saveEditorSetting(key, value) {
    await fetch(`${API_BASE}/api/alpha-lab/settings/${key}`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            value
        })
    });
}
async function runPipelineIngest() {
    const res = await fetch(`${API_BASE}/api/pipeline/run/ingest`, {
        method: "POST"
    });
    return await res.json();
}
async function runPipelineFull() {
    const res = await fetch(`${API_BASE}/api/pipeline/run/full`, {
        method: "POST"
    });
    return await res.json();
}
async function runPipelineScoring() {
    const res = await fetch(`${API_BASE}/api/pipeline/run/pipeline`, {
        method: "POST"
    });
    return await res.json();
}
async function getPipelineStatus() {
    const res = await fetch(`${API_BASE}/api/pipeline/status`);
    return await res.json();
}
async function getPipelineLogs(since = 0) {
    const res = await fetch(`${API_BASE}/api/pipeline/logs?since=${since}`);
    return await res.json();
}
async function fetchAlignedProfile() {
    const res = await fetch(`${API_BASE}/api/alpha-lab/aligned-profile`);
    if (!res.ok) throw new Error(`Failed to fetch profile: ${res.status}`);
    return await res.json();
}
async function fetchAuditModels() {
    const res = await fetch(`${API_BASE}/api/alpha-lab/audit/models`);
    if (!res.ok) throw new Error("Failed to fetch models");
    return await res.json();
}
async function runForensicAudit(experimentId, modelId) {
    const body = modelId ? JSON.stringify({
        model_id: modelId
    }) : undefined;
    const res = await fetch(`${API_BASE}/api/alpha-lab/${experimentId}/audit`, {
        method: "POST",
        headers: body ? {
            "Content-Type": "application/json"
        } : undefined,
        body
    });
    return await res.json();
}
async function fetchExperimentTrades(experimentId) {
    const res = await fetch(`${API_BASE}/api/alpha-lab/${experimentId}/trades`);
    if (!res.ok) return {
        trades: [],
        error: `HTTP ${res.status}`
    };
    return await res.json();
}
}),
"[project]/lib/mock-data.ts [app-ssr] (ecmascript)", ((__turbopack_context__) => {
"use strict";

// Mock data for the quantitative trading terminal
// Strategy data is now fetched from the backend API (see lib/api.ts).
// This file retains mock data for X-Ray, Risk, and Execution components.
// X-Ray Inspector data
__turbopack_context__.s([
    "executionOrders",
    ()=>executionOrders,
    "riskData",
    ()=>riskData,
    "xrayData",
    ()=>xrayData
]);
const xrayData = {
    rawData: {
        ticker: "NVDA",
        date: "2024-03-15",
        price: 878.35,
        volume: 42_500_000,
        q3Revenue: 18_120_000_000,
        totalDebt: 9_700_000_000,
        marketCap: 2_180_000_000_000
    },
    heuristics: {
        evSalesRatio: 12.4,
        zScore: 2.34,
        dynamicDiscountRate: 8.5,
        priceToBook: 45.2,
        debtToEquity: 0.41
    },
    xgboost: {
        predictedReturn: 0.182,
        confidence: 0.76,
        rawDesiredWeight: 0.18,
        featureImportance: [
            {
                feature: "Momentum_30D",
                importance: 0.24
            },
            {
                feature: "EV/Sales",
                importance: 0.19
            },
            {
                feature: "Volume_Surge",
                importance: 0.15
            },
            {
                feature: "Earnings_Surprise",
                importance: 0.14
            },
            {
                feature: "Sector_Momentum",
                importance: 0.11
            },
            {
                feature: "Other",
                importance: 0.17
            }
        ]
    },
    riskBouncer: {
        covariancePenalty: 0.032,
        mcr: 0.068,
        mcrThreshold: 0.05,
        mcrBreach: true,
        originalWeight: 0.18,
        scaledWeight: 0.095,
        reason: "MCR breach detected. Position scaled down to maintain portfolio risk limits."
    },
    finalOrder: {
        targetAllocation: 0.095,
        action: "BUY",
        shares: 235,
        estimatedValue: 206_412
    }
};
const riskData = {
    vix: 14.82,
    vixChange: -0.45,
    tenYearYield: 4.32,
    yieldChange: 0.02,
    macroRegime: "Risk-On",
    regimeConfidence: 0.78,
    // Covariance matrix (simplified 8x8 for visualization)
    covarianceMatrix: [
        [
            1.0,
            0.65,
            0.42,
            0.38,
            0.28,
            0.55,
            0.33,
            0.41
        ],
        [
            0.65,
            1.0,
            0.58,
            0.45,
            0.32,
            0.48,
            0.29,
            0.52
        ],
        [
            0.42,
            0.58,
            1.0,
            0.72,
            0.55,
            0.38,
            0.44,
            0.35
        ],
        [
            0.38,
            0.45,
            0.72,
            1.0,
            0.68,
            0.42,
            0.51,
            0.28
        ],
        [
            0.28,
            0.32,
            0.55,
            0.68,
            1.0,
            0.35,
            0.62,
            0.22
        ],
        [
            0.55,
            0.48,
            0.38,
            0.42,
            0.35,
            1.0,
            0.38,
            0.58
        ],
        [
            0.33,
            0.29,
            0.44,
            0.51,
            0.62,
            0.38,
            1.0,
            0.31
        ],
        [
            0.41,
            0.52,
            0.35,
            0.28,
            0.22,
            0.58,
            0.31,
            1.0
        ]
    ],
    tickers: [
        "NVDA",
        "AAPL",
        "MSFT",
        "GOOGL",
        "AMZN",
        "META",
        "TSLA",
        "AMD"
    ],
    // MCR data
    mcrData: [
        {
            ticker: "NVDA",
            mcr: 6.8,
            threshold: 5.0
        },
        {
            ticker: "TSLA",
            mcr: 5.2,
            threshold: 5.0
        },
        {
            ticker: "AAPL",
            mcr: 4.1,
            threshold: 5.0
        },
        {
            ticker: "MSFT",
            mcr: 3.8,
            threshold: 5.0
        },
        {
            ticker: "META",
            mcr: 3.2,
            threshold: 5.0
        }
    ]
};
const executionOrders = [
    {
        id: 1,
        ticker: "NVDA",
        action: "BUY",
        quantity: 235,
        targetWeight: 9.5,
        currentWeight: 7.2,
        status: "pending"
    },
    {
        id: 2,
        ticker: "AAPL",
        action: "SELL",
        quantity: 150,
        targetWeight: 8.0,
        currentWeight: 10.5,
        status: "pending"
    },
    {
        id: 3,
        ticker: "MSFT",
        action: "BUY",
        quantity: 80,
        targetWeight: 7.5,
        currentWeight: 6.2,
        status: "pending"
    },
    {
        id: 4,
        ticker: "GOOGL",
        action: "BUY",
        quantity: 45,
        targetWeight: 5.5,
        currentWeight: 4.8,
        status: "pending"
    },
    {
        id: 5,
        ticker: "TSLA",
        action: "SELL",
        quantity: 120,
        targetWeight: 3.0,
        currentWeight: 5.8,
        status: "pending"
    },
    {
        id: 6,
        ticker: "META",
        action: "BUY",
        quantity: 65,
        targetWeight: 4.5,
        currentWeight: 3.2,
        status: "pending"
    },
    {
        id: 7,
        ticker: "AMD",
        action: "BUY",
        quantity: 180,
        targetWeight: 4.0,
        currentWeight: 2.5,
        status: "pending"
    },
    {
        id: 8,
        ticker: "AMZN",
        action: "HOLD",
        quantity: 0,
        targetWeight: 6.0,
        currentWeight: 6.1,
        status: "complete"
    }
];
}),
];

//# sourceMappingURL=lib_0ha.d1i._.js.map