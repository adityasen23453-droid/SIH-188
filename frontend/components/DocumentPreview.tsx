"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Image as ImageIcon, Flame, Eye, Scan, ChevronDown, ChevronUp, CheckCircle2, Layers } from "lucide-react";
import { getFullImageUrl } from "@/lib/api";
import { DetectedRegion } from "@/types";

interface DocumentPreviewProps {
  originalImageUrl?: string;
  elaImageUrl?: string;
  scannedImageUrl?: string;
  detectedRegions?: DetectedRegion[];
}

export const DocumentPreview: React.FC<DocumentPreviewProps> = ({
  originalImageUrl,
  elaImageUrl,
  scannedImageUrl,
  detectedRegions = [],
}) => {
  const [activeTab, setActiveTab] = useState<"scanned" | "original" | "ela">(
    scannedImageUrl ? "scanned" : "original"
  );
  const [showRegionsList, setShowRegionsList] = useState(false);

  useEffect(() => {
    if (scannedImageUrl) {
      setActiveTab("scanned");
    }
  }, [scannedImageUrl]);

  const fullElaUrl = getFullImageUrl(elaImageUrl);
  const fullScannedUrl = getFullImageUrl(scannedImageUrl);

  // Categorized counts
  const textRegions = detectedRegions.filter((r) => r.type === "text" || r.type === "header");
  const mrzRegions = detectedRegions.filter((r) => r.type === "mrz" || r.type === "mrz_zone");
  const faceRegions = detectedRegions.filter((r) => r.type === "face");
  const stampRegions = detectedRegions.filter((r) => r.type === "stamp");

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.1 }}
      className="w-full border border-slate-200/90 bg-white rounded-2xl p-6 shadow-md"
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4 pb-4 border-b border-slate-100">
        <div>
          <div className="flex items-center gap-2">
            <Eye className="w-4 h-4 text-indigo-600" />
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-900 font-mono">
              Document Visual Inspection & Scanning Map
            </h3>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Deep scene text detection, biometric face localization, and forensic error level analysis
          </p>
        </div>

        {/* Segmented 3-Way Tab Controls */}
        <div className="relative inline-flex p-1 bg-slate-100 border border-slate-200 rounded-xl self-start sm:self-auto">
          {/* AI Scanned Map Tab */}
          <button
            onClick={() => setActiveTab("scanned")}
            disabled={!scannedImageUrl}
            className={`relative z-10 flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-mono font-semibold uppercase tracking-wider transition-colors duration-200 ${
              activeTab === "scanned"
                ? "text-emerald-950 font-bold"
                : "text-slate-600 hover:text-slate-900 disabled:opacity-40 disabled:cursor-not-allowed"
            }`}
          >
            <Scan className={`w-3.5 h-3.5 ${activeTab === "scanned" ? "text-emerald-600" : "text-emerald-500"}`} />
            <span>AI Scanned Map</span>
            {activeTab === "scanned" && (
              <motion.div
                layoutId="activeTabIndicator"
                className="absolute inset-0 bg-white rounded-lg -z-10 border border-emerald-200 shadow-xs"
                transition={{ type: "spring", stiffness: 400, damping: 30 }}
              />
            )}
          </button>

          {/* Original Tab */}
          <button
            onClick={() => setActiveTab("original")}
            className={`relative z-10 flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-mono font-semibold uppercase tracking-wider transition-colors duration-200 ${
              activeTab === "original" ? "text-slate-900 font-bold" : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <ImageIcon className="w-3.5 h-3.5 text-indigo-600" />
            <span>Original</span>
            {activeTab === "original" && (
              <motion.div
                layoutId="activeTabIndicator"
                className="absolute inset-0 bg-white rounded-lg -z-10 border border-slate-200 shadow-xs"
                transition={{ type: "spring", stiffness: 400, damping: 30 }}
              />
            )}
          </button>

          {/* ELA Heatmap Tab */}
          <button
            onClick={() => setActiveTab("ela")}
            disabled={!elaImageUrl}
            className={`relative z-10 flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-mono font-semibold uppercase tracking-wider transition-colors duration-200 ${
              activeTab === "ela"
                ? "text-slate-900 font-bold"
                : "text-slate-600 hover:text-slate-900 disabled:opacity-40 disabled:cursor-not-allowed"
            }`}
          >
            <Flame className="w-3.5 h-3.5 text-rose-500" />
            <span>ELA Heatmap</span>
            {activeTab === "ela" && (
              <motion.div
                layoutId="activeTabIndicator"
                className="absolute inset-0 bg-white rounded-lg -z-10 border border-slate-200 shadow-xs"
                transition={{ type: "spring", stiffness: 400, damping: 30 }}
              />
            )}
          </button>
        </div>
      </div>

      {/* AI Scanned Map HUD Info Header */}
      {activeTab === "scanned" && (
        <div className="mb-3 px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl flex flex-wrap items-center justify-between gap-2.5 text-xs font-mono text-slate-200">
          <div className="flex items-center gap-2">
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
            </span>
            <span className="font-bold text-emerald-400 tracking-wider uppercase text-[11px]">
              Full-Document Deep Scan Active
            </span>
            <span className="text-slate-500">|</span>
            <span className="text-slate-300 font-medium">
              {detectedRegions.length} Regions Localized
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-2 text-[11px]">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-emerald-950/80 border border-emerald-700 text-emerald-300 font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              VIZ Text ({textRegions.length})
            </span>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-cyan-950/80 border border-cyan-700 text-cyan-300 font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
              MRZ Zone ({mrzRegions.length})
            </span>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-teal-950/80 border border-teal-700 text-teal-300 font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-teal-400" />
              Portrait Face ({faceRegions.length})
            </span>
            {stampRegions.length > 0 && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-amber-950/80 border border-amber-700 text-amber-300 font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                Stamps ({stampRegions.length})
              </span>
            )}
          </div>
        </div>
      )}

      {/* Image Display Frame */}
      <div className="relative w-full min-h-[380px] max-h-[560px] flex items-center justify-center bg-slate-950 border border-slate-200 rounded-xl overflow-hidden p-4 shadow-inner group">
        <AnimatePresence mode="wait">
          {activeTab === "scanned" ? (
            fullScannedUrl ? (
              <motion.img
                key="scanned"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.98 }}
                transition={{ duration: 0.25 }}
                src={fullScannedUrl}
                alt="AI Scanned Green Lines Map"
                className="max-h-[520px] w-auto object-contain mx-auto rounded-lg shadow-2xl transition-transform duration-300 group-hover:scale-[1.01]"
              />
            ) : (
              <motion.div
                key="no-scanned"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="text-xs text-slate-400 font-mono"
              >
                No scanned green overlay generated
              </motion.div>
            )
          ) : activeTab === "original" ? (
            originalImageUrl ? (
              <motion.img
                key="original"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.98 }}
                transition={{ duration: 0.25 }}
                src={originalImageUrl}
                alt="Original Document Upload"
                className="max-h-[520px] w-auto object-contain mx-auto rounded-lg shadow-2xl transition-transform duration-300 group-hover:scale-[1.01]"
              />
            ) : (
              <motion.div
                key="no-original"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="text-xs text-slate-400 font-mono"
              >
                No original image preview available
              </motion.div>
            )
          ) : (
            fullElaUrl ? (
              <motion.img
                key="ela"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.98 }}
                transition={{ duration: 0.25 }}
                src={fullElaUrl}
                alt="Error Level Analysis Heatmap"
                className="max-h-[520px] w-auto object-contain mx-auto rounded-lg shadow-2xl transition-transform duration-300 group-hover:scale-[1.01]"
              />
            ) : (
              <motion.div
                key="no-ela"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="text-xs text-slate-400 font-mono"
              >
                ELA heatmap not generated
              </motion.div>
            )
          )}
        </AnimatePresence>
      </div>

      <div className="mt-3 flex items-center justify-between text-[11px] font-mono text-slate-500">
        <span>High-Definition Inspection View</span>
        <span className="uppercase tracking-widest text-slate-500 font-semibold">
          {activeTab === "scanned"
            ? "Source: PaddleOCR DBNet Full-Frame Geometric Scene Map"
            : activeTab === "original"
            ? "Source: Original Camera Binary Upload"
            : "Source: ELA Compression Heatmap (JPEG Q90)"}
        </span>
      </div>

      {/* Detected Regions Collapsible Breakdown */}
      {detectedRegions.length > 0 && (
        <div className="mt-4 pt-3 border-t border-slate-100">
          <button
            onClick={() => setShowRegionsList(!showRegionsList)}
            className="w-full flex items-center justify-between text-xs font-mono text-slate-700 hover:text-slate-900 transition-colors py-1 cursor-pointer"
          >
            <div className="flex items-center gap-2 font-bold uppercase tracking-wider">
              <Layers className="w-3.5 h-3.5 text-emerald-600" />
              <span>Detected Scanning Regions Breakdown ({detectedRegions.length})</span>
            </div>
            {showRegionsList ? (
              <ChevronUp className="w-4 h-4 text-slate-400" />
            ) : (
              <ChevronDown className="w-4 h-4 text-slate-400" />
            )}
          </button>

          <AnimatePresence>
            {showRegionsList && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-3 overflow-hidden"
              >
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2 max-h-56 overflow-y-auto pr-1">
                  {detectedRegions.map((region, idx) => {
                    const isMrz = region.type === "mrz" || region.type === "mrz_zone";
                    const isFace = region.type === "face";
                    const isStamp = region.type === "stamp";
                    return (
                      <div
                        key={region.id || idx}
                        className={`p-2 rounded-lg border text-[11px] font-mono ${
                          isMrz
                            ? "bg-cyan-50/50 border-cyan-200 text-cyan-950"
                            : isFace
                            ? "bg-teal-50/50 border-teal-200 text-teal-950"
                            : isStamp
                            ? "bg-amber-50/50 border-amber-200 text-amber-950"
                            : "bg-slate-50 border-slate-200 text-slate-800"
                        }`}
                      >
                        <div className="flex items-center justify-between font-bold mb-1">
                          <span className="uppercase text-[10px] tracking-wider text-slate-500">
                            {region.label || region.type}
                          </span>
                          {region.confidence && (
                            <span className="text-[10px] text-emerald-700 font-semibold">
                              {(region.confidence * 100).toFixed(0)}%
                            </span>
                          )}
                        </div>
                        {region.text && (
                          <div className="font-medium text-slate-900 truncate" title={region.text}>
                            &quot;{region.text}&quot;
                          </div>
                        )}
                        <div className="text-[9px] text-slate-400 mt-1">
                          Box: [{region.box.join(", ")}]
                        </div>
                      </div>
                    );
                  })}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
    </motion.div>
  );
};
