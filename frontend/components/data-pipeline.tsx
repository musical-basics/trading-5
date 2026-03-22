"use client"

import { useState, useEffect, useCallback } from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Loader2, Database, CheckCircle2, AlertTriangle, XCircle, Play, RefreshCw } from "lucide-react"
import { cn } from "@/lib/utils"
import { fetchPipelineCoverage, runPipelineIngest, runPipelineFull, getPipelineStatus, type TickerCoverage, type ComponentCoverage } from "@/lib/api"

const STAGES = [
  { key: "market_data", label: "Market Data", cols: ["adj_close", "volume", "daily_return"] },
  { key: "fundamental", label: "Fundamentals", cols: ["revenue", "total_debt", "cash", "shares_out"] },
  { key: "feature", label: "Features", cols: ["ev_sales_zscore", "beta_spy", "dcf_npv_gap", "dynamic_discount_rate"] },
  { key: "action_intent", label: "Strategy Intent", cols: ["strategy_id", "raw_weight"] },
  { key: "target_portfolio", label: "Risk / Target", cols: ["target_weight", "mcr"] },
] as const

type StageKey = (typeof STAGES)[number]["key"]

function coverageStatus(c: ComponentCoverage | null): "full" | "partial" | "empty" {
  if (!c || c.rows === 0) return "empty"
  if (c.null_pct) {
    const hasGaps = Object.values(c.null_pct).some((p) => p > 20)
    return hasGaps ? "partial" : "full"
  }
  return "full"
}

function StatusDot({ status }: { status: "full" | "partial" | "empty" }) {
  if (status === "full") return <CheckCircle2 className="w-3.5 h-3.5 text-green-400" />
  if (status === "partial") return <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
  return <XCircle className="w-3.5 h-3.5 text-red-400/50" />
}

export function DataPipeline() {
  const [data, setData] = useState<TickerCoverage[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null)
  const [pipelineRunning, setPipelineRunning] = useState(false)
  const [pipelinePhase, setPipelinePhase] = useState<string | null>(null)
  const [pipelineError, setPipelineError] = useState<string | null>(null)
  const [pipelineMessage, setPipelineMessage] = useState<string | null>(null)

  const loadCoverage = useCallback(() => {
    fetchPipelineCoverage().then((d) => {
      setData(d)
      setLoading(false)
    })
  }, [])

  useEffect(() => { loadCoverage() }, [loadCoverage])

  // Poll pipeline status when running
  useEffect(() => {
    if (!pipelineRunning) return
    const interval = setInterval(async () => {
      try {
        const status = await getPipelineStatus()
        if (!status.running) {
          setPipelineRunning(false)
          setPipelinePhase(null)
          if (status.error) {
            setPipelineError(status.error)
            setPipelineMessage(null)
          } else {
            setPipelineMessage("✅ Pipeline completed successfully!")
            setPipelineError(null)
            loadCoverage() // Refresh data
          }
          clearInterval(interval)
        }
      } catch { /* ignore polling errors */ }
    }, 3000)
    return () => clearInterval(interval)
  }, [pipelineRunning, loadCoverage])

  const handleRunIngest = async () => {
    setPipelineError(null)
    setPipelineMessage(null)
    const result = await runPipelineIngest()
    if (result.ok) {
      setPipelineRunning(true)
      setPipelinePhase("ingest")
      setPipelineMessage(result.message ?? "Ingesting data...")
    } else {
      setPipelineError(result.error ?? "Failed to start")
    }
  }

  const handleRunFull = async () => {
    setPipelineError(null)
    setPipelineMessage(null)
    const result = await runPipelineFull()
    if (result.ok) {
      setPipelineRunning(true)
      setPipelinePhase("full")
      setPipelineMessage(result.message ?? "Running full pipeline...")
    } else {
      setPipelineError(result.error ?? "Failed to start")
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // Summary counters
  const totalTickers = data.length
  const fullCoverage = data.filter((t) =>
    STAGES.every((s) => coverageStatus(t[s.key as StageKey] as ComponentCoverage | null) === "full")
  ).length
  const partialCoverage = totalTickers - fullCoverage

  const selected = data.find((t) => t.ticker === selectedTicker)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-primary/10">
            <Database className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h2 className="text-lg font-semibold">Data Pipeline</h2>
            <p className="text-xs text-muted-foreground">
              Coverage across {totalTickers} tickers — {fullCoverage} fully covered, {partialCoverage} with gaps
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={loadCoverage}
            disabled={pipelineRunning}
          >
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Refresh
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleRunIngest}
            disabled={pipelineRunning}
          >
            {pipelineRunning && pipelinePhase === "ingest" ? (
              <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
            ) : (
              <Play className="w-3.5 h-3.5 mr-1.5" />
            )}
            Ingest Data
          </Button>
          <Button
            size="sm"
            onClick={handleRunFull}
            disabled={pipelineRunning}
            className="bg-emerald-600 hover:bg-emerald-700 text-white"
          >
            {pipelineRunning && pipelinePhase === "full" ? (
              <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
            ) : (
              <Play className="w-3.5 h-3.5 mr-1.5" />
            )}
            Run Full Pipeline
          </Button>
        </div>
      </div>

      {/* Pipeline Status Banner */}
      {(pipelineMessage || pipelineError) && (
        <div className={cn(
          "rounded-lg px-4 py-2 text-sm",
          pipelineError ? "bg-red-500/10 text-red-400 border border-red-500/20" : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
        )}>
          {pipelineRunning && <Loader2 className="w-3.5 h-3.5 inline mr-2 animate-spin" />}
          {pipelineError || pipelineMessage}
        </div>
      )}

      {/* Coverage Matrix */}
      <Card className="border-border/50 bg-card/50">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Coverage Matrix</CardTitle>
          <CardDescription className="text-xs">
            <span className="inline-flex items-center gap-1"><CheckCircle2 className="w-3 h-3 text-green-400" /> Full</span>
            <span className="inline-flex items-center gap-1 ml-3"><AlertTriangle className="w-3 h-3 text-amber-400" /> Gaps (&gt;20% null)</span>
            <span className="inline-flex items-center gap-1 ml-3"><XCircle className="w-3 h-3 text-red-400/50" /> Empty</span>
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border/30">
                  <th className="text-left px-4 py-2 text-muted-foreground font-medium sticky left-0 bg-card/50 z-10">
                    Ticker
                  </th>
                  {STAGES.map((s) => (
                    <th key={s.key} className="text-center px-3 py-2 text-muted-foreground font-medium whitespace-nowrap">
                      {s.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.map((ticker) => (
                  <tr
                    key={ticker.ticker}
                    onClick={() => setSelectedTicker(ticker.ticker === selectedTicker ? null : ticker.ticker)}
                    className={cn(
                      "border-b border-border/10 cursor-pointer transition-colors",
                      selectedTicker === ticker.ticker
                        ? "bg-primary/5"
                        : "hover:bg-card/80"
                    )}
                  >
                    <td className="px-4 py-2 font-mono font-semibold text-foreground sticky left-0 bg-card/50 z-10">
                      {ticker.ticker}
                    </td>
                    {STAGES.map((s) => {
                      const comp = ticker[s.key as StageKey] as ComponentCoverage | null
                      const status = coverageStatus(comp)
                      return (
                        <td key={s.key} className="text-center px-3 py-2">
                          <div className="flex items-center justify-center gap-1.5">
                            <StatusDot status={status} />
                            <span className="font-mono text-muted-foreground">
                              {comp?.rows?.toLocaleString() ?? "0"}
                            </span>
                          </div>
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Ticker Detail Panel */}
      {selected && (
        <Card className="border-primary/30 bg-primary/5">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-mono">{selectedTicker} — Detail Breakdown</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {STAGES.map((stage) => {
                const comp = selected[stage.key as StageKey] as ComponentCoverage | null
                const status = coverageStatus(comp)
                return (
                  <div
                    key={stage.key}
                    className={cn(
                      "rounded-lg border p-3 space-y-2",
                      status === "full" && "border-green-500/30 bg-green-500/5",
                      status === "partial" && "border-amber-500/30 bg-amber-500/5",
                      status === "empty" && "border-border/30 bg-card/30"
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-foreground">{stage.label}</span>
                      <StatusDot status={status} />
                    </div>
                    {comp && comp.rows > 0 ? (
                      <>
                        <div className="text-xs text-muted-foreground space-y-0.5">
                          <div className="flex justify-between">
                            <span>Rows</span>
                            <span className="font-mono">{comp.rows.toLocaleString()}</span>
                          </div>
                          <div className="flex justify-between">
                            <span>Period</span>
                            <span className="font-mono">{comp.date_start} → {comp.date_end}</span>
                          </div>
                        </div>
                        {comp.null_pct && (
                          <div className="pt-1 border-t border-border/20 space-y-0.5">
                            <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Column Fill</p>
                            {Object.entries(comp.null_pct).map(([col, pct]) => (
                              <div key={col} className="flex items-center justify-between text-xs">
                                <span className="text-muted-foreground font-mono truncate mr-2">{col}</span>
                                <Badge
                                  variant="outline"
                                  className={cn(
                                    "text-[9px] h-4 px-1.5 font-mono",
                                    pct === 0 && "border-green-500/30 text-green-400",
                                    pct > 0 && pct <= 20 && "border-amber-500/30 text-amber-400",
                                    pct > 20 && "border-red-500/30 text-red-400"
                                  )}
                                >
                                  {pct === 0 ? "100%" : `${(100 - pct).toFixed(0)}%`}
                                </Badge>
                              </div>
                            ))}
                          </div>
                        )}
                      </>
                    ) : (
                      <p className="text-xs text-muted-foreground">No data</p>
                    )}
                  </div>
                )
              })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
