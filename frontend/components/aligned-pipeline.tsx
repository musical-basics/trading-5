"use client"

import { useState, useEffect } from "react"
import {
  Layers,
  Database,
  BarChart3,
  TrendingUp,
  Globe,
  ChevronDown,
  ChevronRight,
  RefreshCw,
  AlertCircle,
  Info,
} from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"
import { fetchAlignedProfile, type ColumnProfile, type AlignedProfileMeta } from "@/lib/api"

// Source metadata
const SOURCE_CONFIG: Record<string, { label: string; icon: typeof Database; color: string; description: string }> = {
  market_data: {
    label: "Market Data",
    icon: TrendingUp,
    color: "text-emerald-400",
    description: "Price, volume, and return data from daily market feeds",
  },
  feature: {
    label: "Feature Store",
    icon: BarChart3,
    color: "text-blue-400",
    description: "Computed indicators: z-scores, betas, DCF, discount rates",
  },
  macro: {
    label: "Macro Factors",
    icon: Globe,
    color: "text-amber-400",
    description: "VIX, Treasury yields, S&P 500 — regime detection inputs",
  },
  fundamental: {
    label: "Fundamental Data",
    icon: Database,
    color: "text-purple-400",
    description: "Balance sheet items: debt, cash, revenue, shares outstanding",
  },
}

const CATEGORY_COLORS: Record<string, string> = {
  market: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  fundamental: "bg-purple-500/15 text-purple-400 border-purple-500/30",
  statistical: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  macro: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  other: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
}

function formatNumber(val: number | undefined): string {
  if (val === undefined || val === null) return "—"
  if (Math.abs(val) >= 1_000_000_000) return `${(val / 1_000_000_000).toFixed(2)}B`
  if (Math.abs(val) >= 1_000_000) return `${(val / 1_000_000).toFixed(2)}M`
  if (Math.abs(val) >= 1_000) return `${(val / 1_000).toFixed(1)}K`
  if (Math.abs(val) < 0.01 && val !== 0) return val.toExponential(2)
  return val.toFixed(val % 1 === 0 ? 0 : 3)
}

function NullBar({ pct }: { pct: number }) {
  const color = pct === 0 ? "bg-emerald-500" : pct < 10 ? "bg-amber-500" : "bg-red-500"
  return (
    <div className="flex items-center gap-2 min-w-[100px]">
      <div className="flex-1 h-1.5 bg-secondary rounded-full overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all", color)}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <span className="text-xs tabular-nums text-muted-foreground w-10 text-right">
        {pct.toFixed(1)}%
      </span>
    </div>
  )
}

function SourceSection({
  sourceKey,
  columns,
  defaultOpen = false,
}: {
  sourceKey: string
  columns: Record<string, ColumnProfile>
  defaultOpen?: boolean
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen)
  const config = SOURCE_CONFIG[sourceKey]
  if (!config) return null

  const Icon = config.icon
  const colEntries = Object.entries(columns).sort(([a], [b]) => a.localeCompare(b))
  const numericCount = colEntries.filter(([, c]) => c.stats.min !== undefined).length

  return (
    <Card className="border-border/50 bg-card/50">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full text-left"
      >
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={cn("p-2 rounded-lg bg-secondary/50", config.color)}>
                <Icon className="w-4 h-4" />
              </div>
              <div>
                <CardTitle className="text-sm font-semibold">{config.label}</CardTitle>
                <p className="text-xs text-muted-foreground mt-0.5">{config.description}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Badge variant="outline" className="text-xs border-border/50">
                {colEntries.length} columns
              </Badge>
              <Badge variant="outline" className="text-xs border-border/50">
                {numericCount} numeric
              </Badge>
              {isOpen ? (
                <ChevronDown className="w-4 h-4 text-muted-foreground" />
              ) : (
                <ChevronRight className="w-4 h-4 text-muted-foreground" />
              )}
            </div>
          </div>
        </CardHeader>
      </button>

      {isOpen && (
        <CardContent className="pt-0">
          <div className="rounded-lg border border-border/50 overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="border-border/50 hover:bg-transparent">
                  <TableHead className="text-xs font-medium w-[160px]">Column</TableHead>
                  <TableHead className="text-xs font-medium w-[70px]">Type</TableHead>
                  <TableHead className="text-xs font-medium w-[90px]">Category</TableHead>
                  <TableHead className="text-xs font-medium">Description</TableHead>
                  <TableHead className="text-xs font-medium w-[80px] text-right">Min</TableHead>
                  <TableHead className="text-xs font-medium w-[80px] text-right">Max</TableHead>
                  <TableHead className="text-xs font-medium w-[80px] text-right">Mean</TableHead>
                  <TableHead className="text-xs font-medium w-[80px] text-right">Std</TableHead>
                  <TableHead className="text-xs font-medium w-[120px]">Null %</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {colEntries.map(([colName, col]) => (
                  <TableRow
                    key={colName}
                    className="border-border/30 hover:bg-secondary/30 transition-colors"
                  >
                    <TableCell className="font-mono text-xs text-foreground">
                      {colName}
                    </TableCell>
                    <TableCell>
                      <code className="text-[10px] bg-secondary/60 px-1.5 py-0.5 rounded text-muted-foreground">
                        {col.dtype}
                      </code>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className={cn("text-[10px] px-1.5 py-0", CATEGORY_COLORS[col.category] || CATEGORY_COLORS.other)}
                      >
                        {col.category}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground max-w-[240px] truncate">
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span className="cursor-help">{col.description}</span>
                          </TooltipTrigger>
                          <TooltipContent side="top" className="max-w-xs">
                            <p className="text-xs">{col.description}</p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </TableCell>
                    <TableCell className="text-xs tabular-nums text-right text-muted-foreground">
                      {formatNumber(col.stats.min)}
                    </TableCell>
                    <TableCell className="text-xs tabular-nums text-right text-muted-foreground">
                      {formatNumber(col.stats.max)}
                    </TableCell>
                    <TableCell className="text-xs tabular-nums text-right text-muted-foreground">
                      {formatNumber(col.stats.mean)}
                    </TableCell>
                    <TableCell className="text-xs tabular-nums text-right text-muted-foreground">
                      {formatNumber(col.stats.std)}
                    </TableCell>
                    <TableCell>
                      <NullBar pct={col.stats.null_pct} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      )}
    </Card>
  )
}

export function AlignedPipeline() {
  const [profile, setProfile] = useState<Record<string, Record<string, ColumnProfile>> | null>(null)
  const [meta, setMeta] = useState<AlignedProfileMeta | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadProfile = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchAlignedProfile()
      if (data.status === "error") {
        setError(data.error || "Failed to load profile")
        return
      }
      const { meta: metaData, ...sources } = data.profile
      setProfile(sources as Record<string, Record<string, ColumnProfile>>)
      setMeta(metaData || null)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadProfile()
  }, [])

  // Count totals
  const totalColumns = profile
    ? Object.values(profile).reduce((sum, cols) => sum + Object.keys(cols).length, 0)
    : 0
  const totalSources = profile ? Object.keys(profile).length : 0

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex items-center gap-3 text-muted-foreground">
          <RefreshCw className="w-5 h-5 animate-spin" />
          <span className="text-sm">Loading aligned data profile...</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3">
        <div className="flex items-center gap-2 text-red-400">
          <AlertCircle className="w-5 h-5" />
          <span className="text-sm">{error}</span>
        </div>
        <Button variant="outline" size="sm" onClick={loadProfile}>
          Retry
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header stats */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Info className="w-4 h-4" />
            <span className="text-xs">
              {totalSources} data sources · {totalColumns} columns
              {meta && ` · ${meta.total_tickers} tickers`}
            </span>
          </div>
          {meta && meta.sample_tickers.length > 0 && (
            <div className="flex items-center gap-1.5">
              {meta.sample_tickers.slice(0, 6).map((t) => (
                <Badge
                  key={t}
                  variant="outline"
                  className="text-[10px] px-1.5 py-0 border-border/50 text-muted-foreground"
                >
                  {t}
                </Badge>
              ))}
              {meta.total_tickers > 6 && (
                <span className="text-[10px] text-muted-foreground">
                  +{meta.total_tickers - 6} more
                </span>
              )}
            </div>
          )}
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={loadProfile}
          className="text-xs gap-1.5"
        >
          <RefreshCw className="w-3 h-3" />
          Refresh
        </Button>
      </div>

      {/* Data source sections */}
      {profile && ["market_data", "feature", "macro", "fundamental"].map((sourceKey) => {
        const cols = profile[sourceKey]
        if (!cols) return null
        return (
          <SourceSection
            key={sourceKey}
            sourceKey={sourceKey}
            columns={cols}
            defaultOpen={sourceKey === "feature"}
          />
        )
      })}
    </div>
  )
}
