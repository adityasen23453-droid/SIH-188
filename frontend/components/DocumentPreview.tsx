"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Image as ImageIcon, Flame, Eye } from "lucide-react";
import { getFullImageUrl } from "@/lib/api";

interface DocumentPreviewProps {
  originalImageUrl?: string;
  elaImageUrl?: string;
}

export const DocumentPreview: React.FC<DocumentPreviewProps> = ({
  originalImageUrl,
  elaImageUrl,
}) => {
  const [activeTab, setActiveTab] = useState<"original" | "ela">("original");
  const fullElaUrl = getFullImageUrl(elaImageUrl);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.1 }}
      className="w-full border border-slate-200/90 bg-white rounded-2xl p-6 shadow-md"
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-5 pb-4 border-b border-slate-100">
        <div>
          <div className="flex items-center gap-2">
            <Eye className="w-4 h-4 text-indigo-600" />
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-900 font-mono">
              Document Visual Inspection
            </h3>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Compare camera upload image with Error Level Analysis (ELA) compression heatmap
          </p>
        </div>

        {/* Animated Segmented Tab Controls */}
        <div className="relative inline-flex p-1 bg-slate-100 border border-slate-200 rounded-xl self-start sm:self-auto">
          <button
            onClick={() => setActiveTab("original")}
            className={`relative z-10 flex items-center gap-2 px-4 py-1.5 text-xs font-mono font-semibold uppercase tracking-wider transition-colors duration-200 ${
              activeTab === "original" ? "text-slate-900 font-bold" : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <ImageIcon className="w-3.5 h-3.5" />
            Original
            {activeTab === "original" && (
              <motion.div
                layoutId="activeTabIndicator"
                className="absolute inset-0 bg-white rounded-lg -z-10 border border-slate-200 shadow-xs"
                transition={{ type: "spring", stiffness: 400, damping: 30 }}
              />
            )}
          </button>

          <button
            onClick={() => setActiveTab("ela")}
            disabled={!elaImageUrl}
            className={`relative z-10 flex items-center gap-2 px-4 py-1.5 text-xs font-mono font-semibold uppercase tracking-wider transition-colors duration-200 ${
              activeTab === "ela"
                ? "text-slate-900 font-bold"
                : "text-slate-600 hover:text-slate-900 disabled:opacity-40 disabled:cursor-not-allowed"
            }`}
          >
            <Flame className="w-3.5 h-3.5 text-rose-500" />
            ELA Heatmap
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

      {/* Image Display Frame */}
      <div className="relative w-full min-h-[360px] max-h-[520px] flex items-center justify-center bg-slate-950 border border-slate-200 rounded-xl overflow-hidden p-4 shadow-inner group">
        <AnimatePresence mode="wait">
          {activeTab === "original" ? (
            originalImageUrl ? (
              <motion.img
                key="original"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.98 }}
                transition={{ duration: 0.25 }}
                src={originalImageUrl}
                alt="Original Document Upload"
                className="max-h-[480px] w-auto object-contain mx-auto rounded-lg shadow-2xl transition-transform duration-300 group-hover:scale-[1.01]"
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
                className="max-h-[480px] w-auto object-contain mx-auto rounded-lg shadow-2xl transition-transform duration-300 group-hover:scale-[1.01]"
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
          {activeTab === "original" ? "Source: Original Camera Binary Upload" : "Source: ELA Compression Heatmap (JPEG Q90)"}
        </span>
      </div>
    </motion.div>
  );
};
