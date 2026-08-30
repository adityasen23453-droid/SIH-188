"use client";

import React from "react";
import { motion } from "framer-motion";
import { Flame, Cpu, FileCode2, ShieldAlert } from "lucide-react";
import { TamperingResult } from "@/types";

interface TamperingAnalysisProps {
  tampering: TamperingResult;
}

export const TamperingAnalysis: React.FC<TamperingAnalysisProps> = ({
  tampering,
}) => {
  const ela = tampering.ela || { ela_score: 0 };
  const metadata = tampering.metadata || { editing_software_detected: false, metadata_stripped: false };
  const ai = tampering.ai_detection || { label: "real", confidence: 0, ai_generated_likelihood: 0 };

  const getRiskStyle = () => {
    switch (tampering.risk_level) {
      case "high":
        return "bg-rose-100 text-rose-800 border-rose-300 ring-1 ring-rose-500/20";
      case "medium":
        return "bg-amber-100 text-amber-900 border-amber-300 ring-1 ring-amber-500/20";
      case "low":
      default:
        return "bg-emerald-100 text-emerald-800 border-emerald-300 ring-1 ring-emerald-500/20";
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.4 }}
      className="w-full border border-slate-200 bg-white rounded-2xl p-6 shadow-md space-y-6"
    >
      <div className="pb-4 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Flame className="w-4 h-4 text-indigo-600" />
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-900 font-mono">
              Digital Forgery & Multi-Signal Tampering Engine
            </h3>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Combines ELA pixel variance (30%), EXIF metadata inspection (20%), and Hugging Face ViT Classifier (50%)
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <span className="text-xs font-mono text-slate-500 font-semibold uppercase">Module Risk:</span>
          <span className={`px-3.5 py-1 text-xs font-mono font-black uppercase tracking-wider rounded-lg border ${getRiskStyle()}`}>
            {tampering.risk_level} ({tampering.tampering_likelihood.toFixed(1)})
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Signal 1: ELA Score */}
        <div className="p-5 rounded-xl border border-slate-200 bg-slate-50/70 flex flex-col justify-between shadow-xs">
          <div>
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-mono font-bold uppercase tracking-wider text-slate-700 flex items-center gap-2">
                <Flame className="w-4 h-4 text-rose-500" />
                ELA Compression Score
              </span>
            </div>
            <div className="mt-1">
              <div className="flex items-baseline gap-1">
                <span className="text-3xl font-black font-mono text-slate-900 tracking-tight">
                  {ela.ela_score.toFixed(1)}
                </span>
                <span className="text-xs font-mono text-slate-500 font-semibold">/ 100</span>
              </div>
              {/* ELA Score Bar */}
              <div className="w-full h-2.5 bg-slate-200 rounded-full mt-3 overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${Math.min(100, ela.ela_score)}%` }}
                  transition={{ duration: 0.8, ease: "easeOut" }}
                  className={`h-full rounded-full ${
                    ela.ela_score > 40 ? "bg-rose-500" : ela.ela_score > 20 ? "bg-amber-500" : "bg-emerald-500"
                  }`}
                />
              </div>
            </div>
          </div>
          <p className="text-[11px] text-slate-500 font-mono mt-4 leading-relaxed">
            Measures JPEG quality 90 pixel error delta across image regions.
          </p>
        </div>

        {/* Signal 2: AI Forgery Model */}
        <div className="p-5 rounded-xl border border-slate-200 bg-slate-50/70 flex flex-col justify-between shadow-xs">
          <div>
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-mono font-bold uppercase tracking-wider text-slate-700 flex items-center gap-2">
                <Cpu className="w-4 h-4 text-indigo-600" />
                AI Deepfake Model (ViT)
              </span>
            </div>
            <div className="mt-1">
              <div className="flex items-baseline justify-between">
                <span className="text-2xl font-black font-mono text-slate-900 uppercase">
                  {ai.label || "Real"}
                </span>
                <span className="text-xs font-mono font-bold text-slate-700">
                  {(ai.confidence * 100).toFixed(1)}% Conf
                </span>
              </div>
              {/* AI Confidence Bar */}
              <div className="w-full h-2.5 bg-slate-200 rounded-full mt-3 overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${Math.min(100, ai.ai_generated_likelihood)}%` }}
                  transition={{ duration: 0.8, ease: "easeOut" }}
                  className={`h-full rounded-full ${
                    ai.ai_generated_likelihood > 50 ? "bg-rose-500" : "bg-emerald-500"
                  }`}
                />
              </div>
            </div>
          </div>
          <p className="text-[11px] text-slate-500 font-mono mt-4 leading-relaxed">
            Hugging Face ViT model forgery likelihood: {ai.ai_generated_likelihood.toFixed(1)}%.
          </p>
        </div>

        {/* Signal 3: EXIF Metadata */}
        <div className="p-5 rounded-xl border border-slate-200 bg-slate-50/70 flex flex-col justify-between shadow-xs">
          <div>
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-mono font-bold uppercase tracking-wider text-slate-700 flex items-center gap-2">
                <FileCode2 className="w-4 h-4 text-emerald-600" />
                EXIF Metadata Inspection
              </span>
            </div>

            <div className="space-y-2 text-xs font-mono mt-2">
              <div className="flex justify-between items-center py-1 border-b border-slate-200">
                <span className="text-slate-500 font-semibold">Editing Software:</span>
                <span className={`font-bold ${metadata.editing_software_detected ? "text-rose-700" : "text-emerald-700"}`}>
                  {metadata.editing_software_detected ? metadata.software_name || "DETECTED" : "NONE"}
                </span>
              </div>
              <div className="flex justify-between items-center py-1">
                <span className="text-slate-500 font-semibold">EXIF Stripped:</span>
                <span className="font-bold text-slate-900">
                  {metadata.metadata_stripped ? "YES" : "NO"}
                </span>
              </div>
            </div>
          </div>

          <p className="text-[11px] text-slate-500 font-mono mt-4 leading-relaxed">
            Scans EXIF tags for Photoshop, GIMP, or Canva signatures.
          </p>
        </div>
      </div>

      {tampering.preprocessing && (
        <div className="p-4 rounded-xl bg-slate-100 border border-slate-200 text-xs font-mono flex items-center justify-between text-slate-700 shadow-xs">
          <div className="flex items-center gap-2.5">
            <ShieldAlert className="w-4 h-4 text-indigo-600 shrink-0" />
            <span>
              Pre-OCR Document Preprocessor: {tampering.preprocessing.note}
            </span>
          </div>
          <span className="px-3 py-1 bg-white border border-slate-300 text-slate-900 font-bold rounded-lg shadow-xs">
            {tampering.preprocessing.correction_applied ? "DESKEWED & WARPED" : "NATIVE"}
          </span>
        </div>
      )}
    </motion.div>
  );
};
