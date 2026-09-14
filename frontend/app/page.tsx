"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Upload, FileText, Loader2, ArrowLeft, AlertCircle, Shield, CheckCircle2, Award, Layers } from "lucide-react";
import { AnalyzeResponse } from "@/types";
import { uploadAndAnalyzeDocument } from "@/lib/api";
import { RiskBanner } from "@/components/RiskBanner";
import { DocumentPreview } from "@/components/DocumentPreview";
import { ExtractedFieldsTable } from "@/components/ExtractedFieldsTable";
import { ValidationResults } from "@/components/ValidationResults";
import { TamperingAnalysis } from "@/components/TamperingAnalysis";
import { BiometricVerification } from "@/components/BiometricVerification";
import { BlockchainLedger } from "@/components/BlockchainLedger";

export default function Home() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [filePreviewUrl, setFilePreviewUrl] = useState<string | null>(null);
  const [documentType, setDocumentType] = useState<string>("auto");
  const [isDragOver, setIsDragOver] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analysisResult, setAnalysisResult] = useState<AnalyzeResponse | null>(null);
  const [ledgerOpen, setLedgerOpen] = useState<boolean>(false);

  const handleFileChange = (file: File | null) => {
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      setError("Please select a valid image file (JPEG, PNG, WEBP).");
      return;
    }
    setError(null);
    setSelectedFile(file);
    const url = URL.createObjectURL(file);
    setFilePreviewUrl(url);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileChange(e.dataTransfer.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile || !documentType) return;

    setLoading(true);
    setError(null);

    try {
      const result = await uploadAndAnalyzeDocument(selectedFile, documentType);
      setAnalysisResult(result);
    } catch (err: any) {
      setError(err.message || "An unexpected error occurred during document analysis.");
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setAnalysisResult(null);
    setSelectedFile(null);
    setFilePreviewUrl(null);
    setError(null);
  };

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 pb-20 font-sans bg-grid-pattern-light relative">
      {/* Top Ambient Glow */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-7xl h-96 bg-light-ambient pointer-events-none -z-10" />

      {/* Official Government / SIH Header */}
      <header className="w-full bg-slate-900 text-white shadow-xl px-6 py-4 sticky top-0 z-50 border-b border-slate-800">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-blue-700 flex items-center justify-center shadow-md border border-indigo-400/30">
              <Shield className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-sm font-extrabold tracking-wider uppercase font-mono text-white">
                  Document Screening & Identity Verification System
                </h1>
                <span className="flex h-2 w-2 relative">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
                </span>
              </div>
              <p className="text-[11px] text-slate-300 font-mono flex items-center gap-1.5 mt-0.5">
                <span>Ministry of Home Affairs</span>
                <span>•</span>
                <span className="text-indigo-300 font-semibold">Smart India Hackathon (PS 26188)</span>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setLedgerOpen(true)}
              className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-mono font-bold uppercase tracking-wider bg-slate-800 hover:bg-slate-700 text-indigo-300 rounded-xl border border-slate-700 transition-colors shadow-xs cursor-pointer"
            >
              <Layers className="w-4 h-4 text-indigo-400" />
              <span className="hidden sm:inline">Audit Ledger</span>
              {analysisResult?.blockchain_receipt && (
                <span className="px-1.5 py-0.5 bg-emerald-500/20 text-emerald-300 text-[10px] rounded font-mono">
                  #{analysisResult.blockchain_receipt.block_index}
                </span>
              )}
            </button>

            {analysisResult && (
              <motion.button
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                onClick={handleReset}
                className="inline-flex items-center gap-2 px-4 py-2 text-xs font-mono font-bold uppercase tracking-wider bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl shadow-md transition-colors cursor-pointer"
              >
                <ArrowLeft className="w-4 h-4" />
                New Screening
              </motion.button>
            )}
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 pt-8 sm:pt-10">
        <AnimatePresence mode="wait">
          {!analysisResult ? (
            /* PAGE 1: Upload Screen */
            <motion.div
              key="upload-screen"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              transition={{ duration: 0.3 }}
              className="max-w-2xl mx-auto pt-2"
            >
              <div className="text-center mb-8">
                <div className="inline-flex items-center gap-2 px-3.5 py-1.5 bg-white border border-slate-200 rounded-full text-xs font-mono text-slate-700 shadow-xs mb-3 font-medium">
                  <Award className="w-4 h-4 text-indigo-600" />
                  <span>SIH PS 26188 • AI Identity Verification Engine</span>
                </div>
                <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900 font-mono uppercase">
                  Document Identity Screening
                </h2>
                <p className="text-xs sm:text-sm text-slate-600 mt-2 max-w-lg mx-auto leading-relaxed">
                  Upload passport, visa, or national ID images for automated OCR parsing, 7-3-1 MRZ checkdigit validation, and AI forgery detection.
                </p>
              </div>

              {error && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="mb-6 p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-900 text-xs font-mono flex items-start gap-3 shadow-sm"
                >
                  <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold block uppercase tracking-wider mb-0.5 text-rose-800">
                      Connection / Analysis Error
                    </span>
                    <span className="leading-relaxed">{error}</span>
                  </div>
                </motion.div>
              )}

              <form onSubmit={handleSubmit} className="space-y-6 bg-white p-8 border border-slate-200/90 rounded-2xl shadow-xl">
                {/* 1. Document Type Selector */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <label className="text-xs font-mono font-bold uppercase tracking-wider text-slate-700">
                      1. Document Type
                    </label>
                    <span className="text-[11px] font-mono text-indigo-600 bg-indigo-50 border border-indigo-200 px-2 py-0.5 rounded-md font-semibold">
                      Auto-Detect Supported
                    </span>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                    {[
                      { id: "auto", label: "✨ Auto-Detect" },
                      { id: "passport", label: "Passport (MRZ)" },
                      { id: "visa", label: "Visa / Permit" },
                      { id: "id_card", label: "National ID" },
                    ].map((type) => (
                      <motion.button
                        key={type.id}
                        type="button"
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={() => setDocumentType(type.id)}
                        className={`py-3 px-2 text-xs font-mono font-bold uppercase tracking-wider border rounded-xl transition-all duration-200 text-center ${
                          documentType === type.id
                            ? "bg-indigo-600 text-white border-indigo-600 shadow-md font-black"
                            : "bg-slate-50 text-slate-700 border-slate-200 hover:border-slate-300 hover:bg-slate-100"
                        }`}
                      >
                        {type.label}
                      </motion.button>
                    ))}
                  </div>
                </div>

                {/* 2. File Dropzone */}
                <div>
                  <label className="block text-xs font-mono font-bold uppercase tracking-wider text-slate-700 mb-3">
                    2. Upload Document Image
                  </label>

                  <div
                    onDragOver={(e) => {
                      e.preventDefault();
                      setIsDragOver(true);
                    }}
                    onDragLeave={() => setIsDragOver(false)}
                    onDrop={handleDrop}
                    onClick={() => document.getElementById("file-input")?.click()}
                    className={`border-2 border-dashed rounded-2xl p-8 text-center transition-all duration-200 cursor-pointer ${
                      isDragOver
                        ? "border-indigo-600 bg-indigo-50/50 shadow-indigo-100"
                        : selectedFile
                        ? "border-slate-400 bg-slate-50"
                        : "border-slate-300 bg-slate-50/50 hover:border-indigo-400 hover:bg-slate-100/50"
                    }`}
                  >
                    <input
                      id="file-input"
                      type="file"
                      accept="image/*"
                      className="hidden"
                      onChange={(e) => {
                        if (e.target.files && e.target.files[0]) {
                          handleFileChange(e.target.files[0]);
                        }
                      }}
                    />

                    {selectedFile ? (
                      <div className="flex flex-col items-center gap-3">
                        {filePreviewUrl && (
                          <div className="relative group">
                            <img
                              src={filePreviewUrl}
                              alt="File Preview"
                              className="h-36 w-auto object-contain rounded-xl border border-slate-300 bg-white p-2 shadow-md transition-transform group-hover:scale-105"
                            />
                          </div>
                        )}
                        <div className="flex items-center gap-2 font-mono text-xs font-bold text-slate-900 bg-white px-3.5 py-1.5 rounded-lg border border-slate-200 shadow-xs">
                          <FileText className="w-4 h-4 text-indigo-600" />
                          {selectedFile.name}
                        </div>
                        <span className="text-[11px] font-mono text-slate-500">
                          {(selectedFile.size / 1024).toFixed(1)} KB • Click to choose another image
                        </span>
                      </div>
                    ) : (
                      <div className="flex flex-col items-center gap-3 py-4">
                        <div className="p-4 rounded-2xl bg-indigo-50 text-indigo-600 shadow-inner">
                          <Upload className="w-8 h-8" />
                        </div>
                        <span className="text-xs font-mono font-bold uppercase tracking-wider text-slate-800">
                          Drag and drop document image here, or click to browse
                        </span>
                        <span className="text-[11px] text-slate-500 font-mono">
                          Supports JPEG, PNG, and WEBP document scans
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                {/* 3. Submit Button */}
                <motion.button
                  type="submit"
                  whileHover={{ scale: selectedFile && documentType && !loading ? 1.01 : 1 }}
                  whileTap={{ scale: selectedFile && documentType && !loading ? 0.99 : 1 }}
                  disabled={!selectedFile || !documentType || loading}
                  className="w-full py-4 px-6 bg-gradient-to-r from-indigo-600 via-indigo-700 to-blue-800 hover:from-indigo-700 hover:to-blue-900 text-white font-mono text-xs font-black uppercase tracking-widest rounded-xl shadow-xl transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-4.5 h-4.5 animate-spin text-white" />
                      <span>Analyzing Document Pipeline...</span>
                    </>
                  ) : (
                    <span>Analyze Document</span>
                  )}
                </motion.button>
              </form>
            </motion.div>
          ) : (
            /* PAGE 2: Results Dashboard */
            <motion.div
              key="results-dashboard"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              transition={{ duration: 0.3 }}
              className="space-y-8"
            >
              {/* Document Classification Header Bar */}
              <div className="flex flex-wrap items-center justify-between gap-3 bg-white p-4 border border-slate-200 rounded-2xl shadow-xs">
                <div className="flex items-center gap-2.5">
                  <span className="text-xs font-mono font-bold uppercase tracking-wider text-slate-500">
                    Document Category:
                  </span>
                  <span className="px-3 py-1 rounded-xl bg-indigo-50 border border-indigo-200 text-indigo-700 font-mono text-xs font-black uppercase tracking-wider">
                    {analysisResult.blockchain_receipt?.document_type?.replace(/_/g, " ") || "AUTO-DETECTED"}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-slate-500 text-[11px] font-mono">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  <span>Hugging Face ViT & Multi-Signal Forensics Active</span>
                </div>
              </div>

              {/* Section 1: Risk Banner */}
              <RiskBanner
                riskLevel={analysisResult.overall_risk_level}
                riskScore={analysisResult.overall_risk_score}
                summaryFlags={analysisResult.summary_flags}
              />

              {/* Section 2: Document Preview */}
              <DocumentPreview
                originalImageUrl={filePreviewUrl || undefined}
                elaImageUrl={analysisResult.tampering?.ela?.ela_image_url}
                scannedImageUrl={analysisResult.scanned_image_url || undefined}
                detectedRegions={analysisResult.detected_regions}
              />

              {/* Section 3: Extracted Fields Table */}
              <ExtractedFieldsTable
                fields={analysisResult.extracted_fields}
                documentType={analysisResult.document_type}
              />

              {/* Section 4: Validation Results */}
              <ValidationResults
                validation={analysisResult.validation}
                documentType={analysisResult.document_type}
              />

              {/* Section 5: Tampering Analysis */}
              <TamperingAnalysis tampering={analysisResult.tampering} />

              {/* Section 6: Biometric Verification & 1:N Cross-Border Search */}
              <BiometricVerification
                fileId={analysisResult.file_id}
                portraitFace={analysisResult.portrait_face}
                onVerificationComplete={(_, updatedBlock) => {
                  if (updatedBlock) {
                    setAnalysisResult((prev) =>
                      prev ? { ...prev, blockchain_receipt: updatedBlock } : null
                    );
                  }
                }}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Blockchain SHA-256 Merkle Ledger Explorer Modal */}
      <BlockchainLedger
        isOpen={ledgerOpen}
        onClose={() => setLedgerOpen(false)}
        latestBlock={analysisResult?.blockchain_receipt}
      />
    </main>
  );
}
