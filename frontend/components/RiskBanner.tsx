"use client";

import React from "react";
import { motion } from "framer-motion";
import { ShieldAlert, AlertTriangle, ShieldCheck, Activity } from "lucide-react";

interface RiskBannerProps {
  riskLevel: "low" | "medium" | "high";
  riskScore: number;
  summaryFlags: string[];
}

export const RiskBanner: React.FC<RiskBannerProps> = ({
  riskLevel,
  riskScore,
  summaryFlags,
}) => {
  const levelUpper = riskLevel.toUpperCase();

  const getStyle = () => {
    switch (riskLevel) {
      case "high":
        return {
          bg: "bg-gradient-to-br from-rose-50/90 via-white to-rose-50/40 border-rose-200 shadow-rose-100/80",
          badge: "bg-rose-100/90 text-rose-800 border-rose-300 ring-rose-500/20",
          iconContainer: "bg-rose-600 text-white shadow-rose-200",
          stroke: "#e11d48",
          textColor: "text-rose-950",
          scoreBg: "bg-rose-50/80 border-rose-200",
          bullet: "bg-rose-500",
        };
      case "medium":
        return {
          bg: "bg-gradient-to-br from-amber-50/90 via-white to-amber-50/40 border-amber-200 shadow-amber-100/80",
          badge: "bg-amber-100/90 text-amber-900 border-amber-300 ring-amber-500/20",
          iconContainer: "bg-amber-600 text-white shadow-amber-200",
          stroke: "#d97706",
          textColor: "text-amber-950",
          scoreBg: "bg-amber-50/80 border-amber-200",
          bullet: "bg-amber-500",
        };
      case "low":
      default:
        return {
          bg: "bg-gradient-to-br from-emerald-50/90 via-white to-emerald-50/40 border-emerald-200 shadow-emerald-100/80",
          badge: "bg-emerald-100/90 text-emerald-800 border-emerald-300 ring-emerald-500/20",
          iconContainer: "bg-emerald-600 text-white shadow-emerald-200",
          stroke: "#059669",
          textColor: "text-emerald-950",
          scoreBg: "bg-emerald-50/80 border-emerald-200",
          bullet: "bg-emerald-500",
        };
    }
  };

  const style = getStyle();
  const radius = 36;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (riskScore / 100) * circumference;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className={`w-full p-6 sm:p-7 border rounded-2xl backdrop-blur-md shadow-lg transition-all duration-300 ${style.bg}`}
    >
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 pb-6 border-b border-slate-200/80">
        <div className="flex items-start gap-4">
          <div className={`p-3.5 rounded-2xl shadow-md ${style.iconContainer}`}>
            {riskLevel === "high" ? (
              <ShieldAlert className="w-7 h-7" />
            ) : riskLevel === "medium" ? (
              <AlertTriangle className="w-7 h-7" />
            ) : (
              <ShieldCheck className="w-7 h-7" />
            )}
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Activity className="w-3.5 h-3.5 text-slate-500" />
              <span className="text-xs uppercase tracking-widest text-slate-500 font-mono font-semibold">
                Aggregated Assessment Status
              </span>
            </div>
            <div className="flex items-center gap-3">
              <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 font-mono">
                RISK LEVEL:
              </h2>
              <span className={`px-3.5 py-1 text-sm font-mono font-black tracking-wider border ring-1 rounded-xl shadow-xs ${style.badge}`}>
                {levelUpper}
              </span>
            </div>
          </div>
        </div>

        {/* Animated Circular Score Meter */}
        <div className={`flex items-center gap-4 px-5 py-3.5 rounded-2xl border shadow-xs self-start md:self-auto ${style.scoreBg}`}>
          <div className="relative w-20 h-20 flex items-center justify-center">
            <svg className="w-20 h-20 transform -rotate-90">
              <circle
                cx="40"
                cy="40"
                r={radius}
                stroke="currentColor"
                strokeWidth="6"
                className="text-slate-200"
                fill="transparent"
              />
              <motion.circle
                cx="40"
                cy="40"
                r={radius}
                stroke={style.stroke}
                strokeWidth="6"
                fill="transparent"
                strokeDasharray={circumference}
                initial={{ strokeDashoffset: circumference }}
                animate={{ strokeDashoffset }}
                transition={{ duration: 1, ease: "easeOut" }}
                strokeLinecap="round"
              />
            </svg>
            <div className="absolute flex flex-col items-center justify-center text-center">
              <span className={`text-2xl font-black font-mono leading-none ${style.textColor}`}>
                {Math.round(riskScore)}
              </span>
              <span className="text-[10px] font-mono text-slate-500 font-semibold">/ 100</span>
            </div>
          </div>

          <div className="flex flex-col">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-600 font-bold">
              Overall Risk Index
            </span>
            <span className="text-xs text-slate-500 max-w-[150px] mt-0.5 leading-snug">
              Multi-signal score based on MRZ, ELA, & AI model.
            </span>
          </div>
        </div>
      </div>

      {/* Summary Flags List */}
      <div className="mt-5">
        <span className="text-xs font-mono uppercase tracking-wider text-slate-500 font-bold block mb-3">
          Key Risk Findings & Summary Flags ({summaryFlags.length})
        </span>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
          {summaryFlags.map((flag, idx) => (
            <motion.div
              key={idx}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: idx * 0.08 + 0.2, duration: 0.3 }}
              className="flex items-start gap-3 p-3 rounded-xl bg-white/90 border border-slate-200/90 text-xs font-medium text-slate-800 shadow-xs hover:border-slate-300 transition-colors"
            >
              <span className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${style.bullet}`} />
              <span className="leading-snug">{flag}</span>
            </motion.div>
          ))}
        </div>
      </div>
    </motion.div>
  );
};
