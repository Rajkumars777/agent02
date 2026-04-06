"use client";
/**
 * ChartBlock.tsx
 * ==============
 * Renders interactive Recharts charts from a structured JSON config.
 * The AI agent emits this JSON inside a ```chart ... ``` code fence,
 * and this component renders it beautifully in the chat timeline.
 *
 * Supported chart types:
 *   bar | line | area | pie | donut | composed
 *
 * JSON Schema (what the AI outputs):
 * {
 *   "type": "bar" | "line" | "area" | "pie" | "donut",
 *   "title": "string",
 *   "description": "string (optional)",
 *   "data": [{ "label": "Jan", "value": 120, "otherKey": 80 }, ...],
 *   "xKey": "label",          // field used for x-axis (bar/line/area)
 *   "yKeys": ["value", ...],  // one or more y-axis fields
 *   "colors": ["#6366f1"],    // optional custom colors
 *   "unit": "$"               // optional value unit suffix
 * }
 */

import React, { useState } from "react";
import { motion } from "framer-motion";
import {
  BarChart, Bar,
  LineChart, Line,
  AreaChart, Area,
  PieChart, Pie, Cell,
  ComposedChart,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { BarChart2, TrendingUp, PieChart as PieIcon, Activity, Download, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

// ─── Types ───────────────────────────────────────────────────────────────────

export interface ChartConfig {
  type: "bar" | "line" | "area" | "pie" | "donut" | "composed";
  title?: string;
  description?: string;
  data: Record<string, any>[];
  xKey?: string;           // x-axis field (bar/line/area)
  yKeys?: string[];        // y-axis fields
  colors?: string[];       // custom colours
  unit?: string;           // value suffix e.g. "$", "%", "k"
  stacked?: boolean;       // stacked bars/areas
}

// ─── Colour palette ──────────────────────────────────────────────────────────

const DEFAULT_COLORS = [
  "#6366f1", // indigo
  "#8b5cf6", // violet
  "#ec4899", // pink
  "#06b6d4", // cyan
  "#10b981", // emerald
  "#f59e0b", // amber
  "#ef4444", // red
  "#3b82f6", // blue
];

// ─── Custom Tooltip ──────────────────────────────────────────────────────────

function NexusTooltip({ active, payload, label, unit }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="rounded-xl px-3 py-2.5 text-xs shadow-xl"
      style={{
        background: "rgba(15,17,23,0.95)",
        border: "1px solid rgba(99,102,241,0.3)",
        backdropFilter: "blur(12px)",
      }}
    >
      {label && <p className="text-indigo-300 font-bold mb-1.5">{label}</p>}
      {payload.map((entry: any, i: number) => (
        <div key={i} className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full inline-block" style={{ background: entry.color }} />
          <span className="text-slate-300">{entry.name}:</span>
          <span className="text-white font-semibold">
            {unit && unit !== "suffix" ? unit : ""}
            {typeof entry.value === "number" ? entry.value.toLocaleString() : entry.value}
            {unit === "suffix" ? "" : ""}
          </span>
        </div>
      ))}
    </div>
  );
}

// ─── Pie custom label ─────────────────────────────────────────────────────────

function PieLabel({ cx, cy, midAngle, innerRadius, outerRadius, percent, name }: any) {
  const RADIAN = Math.PI / 180;
  const radius = innerRadius + (outerRadius - innerRadius) * 0.6;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);
  if (percent < 0.05) return null; // skip tiny slices
  return (
    <text x={x} y={y} fill="white" textAnchor="middle" dominantBaseline="central" fontSize={10} fontWeight={600}>
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  );
}

// ─── Chart type icon ─────────────────────────────────────────────────────────

function ChartIcon({ type }: { type: string }) {
  const cls = "w-4 h-4";
  if (type === "bar") return <BarChart2 className={cls} />;
  if (type === "pie" || type === "donut") return <PieIcon className={cls} />;
  if (type === "line") return <TrendingUp className={cls} />;
  return <Activity className={cls} />;
}

// ─── Export helper ────────────────────────────────────────────────────────────

function exportCSV(data: Record<string, any>[], title = "chart") {
  if (!data.length) return;
  const keys = Object.keys(data[0]);
  const rows = [keys.join(","), ...data.map(r => keys.map(k => r[k]).join(","))];
  const blob = new Blob([rows.join("\n")], { type: "text/csv" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${title.replace(/\s+/g, "_")}.csv`;
  a.click();
}

// ─── Main component ───────────────────────────────────────────────────────────

interface ChartBlockProps {
  raw: string; // raw JSON string from the ``` chart ``` fence
}

export function ChartBlock({ raw }: ChartBlockProps) {
  const [activeType, setActiveType] = useState<ChartConfig["type"] | null>(null);

  // Parse JSON
  let config: ChartConfig;
  try {
    config = JSON.parse(raw) as ChartConfig;
  } catch {
    return (
      <div className="flex items-center gap-2 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-xs my-2">
        <AlertTriangle className="w-4 h-4 flex-shrink-0" />
        <span>Failed to parse chart data. Check JSON syntax.</span>
      </div>
    );
  }

  const { type: configType, title, description, data, xKey, yKeys = [], colors = [], unit = "", stacked } = config;
  const chartType = activeType ?? configType;

  if (!data || !data.length) {
    return (
      <div className="text-xs text-slate-500 italic my-2 px-2">Chart: no data provided.</div>
    );
  }

  // Resolve colours
  const palette = colors.length ? colors : DEFAULT_COLORS;

  // Auto-detect xKey and yKeys if not provided
  const resolvedXKey = xKey ?? Object.keys(data[0])[0];
  const resolvedYKeys =
    yKeys.length > 0
      ? yKeys
      : Object.keys(data[0]).filter((k) => k !== resolvedXKey && typeof data[0][k] === "number");

  const isTimeSeries = chartType === "line" || chartType === "area" || chartType === "bar" || chartType === "composed";
  const isPie = chartType === "pie" || chartType === "donut";

  // Height based on data length
  const chartH = Math.max(220, Math.min(320, data.length * 28 + 80));

  // ── Type switcher tabs ──
  const types: { id: ChartConfig["type"]; label: string }[] = [
    { id: "bar", label: "Bar" },
    { id: "line", label: "Line" },
    { id: "area", label: "Area" },
    { id: "pie", label: "Pie" },
  ];

  const commonCartesian = {
    data,
    margin: { top: 10, right: 16, left: 0, bottom: 6 },
  };

  const axisStyle = { fill: "#64748b", fontSize: 11 };
  const gridStyle = { stroke: "rgba(255,255,255,0.05)" };

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="my-3 rounded-2xl overflow-hidden"
      style={{
        background: "linear-gradient(135deg, rgba(15,17,23,0.95), rgba(17,24,39,0.95))",
        border: "1px solid rgba(99,102,241,0.2)",
        boxShadow: "0 8px 40px rgba(0,0,0,0.4)",
      }}
    >
      {/* Header */}
      <div
        className="px-4 py-3 flex items-center justify-between"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}
      >
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 rounded-lg" style={{ background: "rgba(99,102,241,0.2)" }}>
            <ChartIcon type={chartType} />
          </div>
          <div>
            <h4 className="text-sm font-bold text-white">{title ?? "Data Chart"}</h4>
            {description && (
              <p className="text-[10px] text-slate-500 mt-0.5">{description}</p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Type switcher */}
          <div className="flex gap-0.5 bg-white/5 rounded-lg p-0.5">
            {types.map((t) => (
              <button
                key={t.id}
                onClick={() => setActiveType(t.id)}
                className={cn(
                  "px-2 py-1 text-[10px] font-semibold rounded-md transition-all",
                  chartType === t.id
                    ? "bg-indigo-500/30 text-indigo-300"
                    : "text-slate-500 hover:text-slate-300"
                )}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* Export */}
          <button
            onClick={() => exportCSV(data, title)}
            className="p-1.5 rounded-lg text-slate-500 hover:text-indigo-400 hover:bg-indigo-500/10 transition-all"
            title="Export as CSV"
          >
            <Download className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Chart area */}
      <div className="px-2 py-4 w-full" style={{ height: chartH + 40 }}>
        <ResponsiveContainer width="100%" height={chartH}>

          {/* ── Bar Chart ── */}
          {chartType === "bar" ? (
            <BarChart {...commonCartesian}>
              <CartesianGrid strokeDasharray="3 3" {...gridStyle} />
              <XAxis dataKey={resolvedXKey} tick={axisStyle} axisLine={false} tickLine={false} />
              <YAxis tick={axisStyle} axisLine={false} tickLine={false} width={40} />
              <Tooltip content={<NexusTooltip unit={unit} />} />
              {resolvedYKeys.length > 1 && <Legend wrapperStyle={{ fontSize: 11, color: "#94a3b8" }} />}
              {resolvedYKeys.map((key, i) => (
                <Bar
                  key={key}
                  dataKey={key}
                  fill={palette[i % palette.length]}
                  radius={[4, 4, 0, 0]}
                  stackId={stacked ? "stack" : undefined}
                  maxBarSize={48}
                />
              ))}
            </BarChart>

          ) : chartType === "line" ? (
            /* ── Line Chart ── */
            <LineChart {...commonCartesian}>
              <CartesianGrid strokeDasharray="3 3" {...gridStyle} />
              <XAxis dataKey={resolvedXKey} tick={axisStyle} axisLine={false} tickLine={false} />
              <YAxis tick={axisStyle} axisLine={false} tickLine={false} width={40} />
              <Tooltip content={<NexusTooltip unit={unit} />} />
              {resolvedYKeys.length > 1 && <Legend wrapperStyle={{ fontSize: 11, color: "#94a3b8" }} />}
              {resolvedYKeys.map((key, i) => (
                <Line
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stroke={palette[i % palette.length]}
                  strokeWidth={2.5}
                  dot={{ r: 3, fill: palette[i % palette.length] }}
                  activeDot={{ r: 5 }}
                />
              ))}
            </LineChart>

          ) : chartType === "area" ? (
            /* ── Area Chart ── */
            <AreaChart {...commonCartesian}>
              <defs>
                {resolvedYKeys.map((key, i) => (
                  <linearGradient key={key} id={`grad_${i}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={palette[i % palette.length]} stopOpacity={0.4} />
                    <stop offset="95%" stopColor={palette[i % palette.length]} stopOpacity={0.02} />
                  </linearGradient>
                ))}
              </defs>
              <CartesianGrid strokeDasharray="3 3" {...gridStyle} />
              <XAxis dataKey={resolvedXKey} tick={axisStyle} axisLine={false} tickLine={false} />
              <YAxis tick={axisStyle} axisLine={false} tickLine={false} width={40} />
              <Tooltip content={<NexusTooltip unit={unit} />} />
              {resolvedYKeys.length > 1 && <Legend wrapperStyle={{ fontSize: 11, color: "#94a3b8" }} />}
              {resolvedYKeys.map((key, i) => (
                <Area
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stroke={palette[i % palette.length]}
                  strokeWidth={2}
                  fill={`url(#grad_${i})`}
                  stackId={stacked ? "stack" : undefined}
                />
              ))}
            </AreaChart>

          ) : (
            /* ── Pie / Donut Chart ── */
            <PieChart>
              <Tooltip content={<NexusTooltip unit={unit} />} />
              <Legend wrapperStyle={{ fontSize: 11, color: "#94a3b8" }} />
              <Pie
                data={data}
                dataKey={resolvedYKeys[0] ?? "value"}
                nameKey={resolvedXKey}
                cx="50%"
                cy="50%"
                outerRadius={chartType === "donut" ? 100 : 110}
                innerRadius={chartType === "donut" ? 55 : 0}
                labelLine={false}
                label={<PieLabel />}
                strokeWidth={2}
                stroke="rgba(0,0,0,0.3)"
              >
                {data.map((_, i) => (
                  <Cell key={i} fill={palette[i % palette.length]} />
                ))}
              </Pie>
            </PieChart>
          )}

        </ResponsiveContainer>
      </div>

      {/* Data summary footer */}
      <div
        className="px-4 py-2 flex items-center justify-between"
        style={{ borderTop: "1px solid rgba(255,255,255,0.04)" }}
      >
        <span className="text-[10px] text-slate-600">
          {data.length} data points · {resolvedYKeys.join(", ")}
        </span>
        <span className="text-[10px] text-indigo-600 uppercase tracking-widest font-bold">
          NEXUS Chart
        </span>
      </div>
    </motion.div>
  );
}
