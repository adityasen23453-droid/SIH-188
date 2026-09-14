"use client";

import React, { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Camera,
  UserCheck,
  UserX,
  AlertTriangle,
  RefreshCw,
  Upload,
  ShieldCheck,
  Fingerprint,
  Zap,
  Layers,
  Sparkles,
  Info
} from "lucide-react";
import { BiometricVerificationResult, BlockchainBlock, PortraitFaceInfo } from "@/types";

interface BiometricVerificationProps {
  fileId: string;
  portraitFace?: PortraitFaceInfo | null;
  onVerificationComplete?: (result: BiometricVerificationResult, updatedBlock?: BlockchainBlock) => void;
}

export const BiometricVerification: React.FC<BiometricVerificationProps> = ({
  fileId,
  portraitFace,
  onVerificationComplete,
}) => {
  const [cameraActive, setCameraActive] = useState<boolean>(false);
  const [liveImage, setLiveImage] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [result, setResult] = useState<BiometricVerificationResult | null>(null);
  const [blockchainBlock, setBlockchainBlock] = useState<BlockchainBlock | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const docFaceUrl = portraitFace?.face_image_url
    ? `${apiBase}${portraitFace.face_image_url}`
    : null;

  // Cleanup camera stream on unmount
  useEffect(() => {
    return () => {
      stopCamera();
    };
  }, []);

  const startCamera = async () => {
    setErrorMsg(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
      }
      setCameraActive(true);
      setLiveImage(null);
    } catch (err: any) {
      console.warn("Webcam access error:", err);
      setErrorMsg("Camera access unavailable. You can upload a live passenger photo instead.");
      setCameraActive(false);
    }
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    setCameraActive(false);
  };

  const captureFrame = () => {
    if (!videoRef.current) return;
    const canvas = document.createElement("canvas");
    canvas.width = videoRef.current.videoWidth || 640;
    canvas.height = videoRef.current.videoHeight || 480;
    const ctx = canvas.getContext("2d");
    if (ctx) {
      ctx.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
      const dataUrl = canvas.toDataURL("image/jpeg", 0.92);
      setLiveImage(dataUrl);
      stopCamera();
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      const reader = new FileReader();
      reader.onload = () => {
        setLiveImage(reader.result as string);
        stopCamera();
      };
      reader.readAsDataURL(file);
    }
  };

  const runBiometricVerification = async () => {
    if (!liveImage) {
      setErrorMsg("Please capture or upload a live face image first.");
      return;
    }
    setLoading(true);
    setErrorMsg(null);

    try {
      const formData = new FormData();
      formData.append("live_image_base64", liveImage);

      const res = await fetch(`${apiBase}/api/face-verify/${fileId}`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errJson = await res.json();
        throw new Error(errJson.error || "Biometric verification request failed.");
      }

      const data = await res.json();
      setResult(data.verification);
      if (data.blockchain_receipt) {
        setBlockchainBlock(data.blockchain_receipt);
      }
      if (onVerificationComplete) {
        onVerificationComplete(data.verification, data.blockchain_receipt);
      }
    } catch (err: any) {
      setErrorMsg(err.message || "An unexpected error occurred during biometric verification.");
    } finally {
      setLoading(false);
    }
  };

  const resetCapture = () => {
    setLiveImage(null);
    setResult(null);
    setErrorMsg(null);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="w-full border border-slate-200 bg-white rounded-2xl p-6 shadow-md space-y-6"
    >
      {/* Header */}
      <div className="pb-4 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Fingerprint className="w-5 h-5 text-indigo-600" />
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-900 font-mono">
              Biometric Verification & 1:N Cross-Border Vector Search
            </h3>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Compares document portrait face with live checkpoint camera & scans historical registry for duplicate aliases.
          </p>
        </div>

        {result && (
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-slate-500 font-semibold uppercase">Verdict:</span>
            <span
              className={`px-3 py-1 text-xs font-mono font-black uppercase tracking-wider rounded-lg border ${
                result.status === "MATCH"
                  ? "bg-emerald-100 text-emerald-800 border-emerald-300"
                  : result.status === "BORDERLINE"
                  ? "bg-amber-100 text-amber-900 border-amber-300"
                  : "bg-rose-100 text-rose-800 border-rose-300"
              }`}
            >
              {result.status === "MATCH" ? "VERIFIED MATCH" : result.status === "DUPLICATE_ALIAS_ALERT" ? "ALIAS DETECTED" : result.status}
            </span>
          </div>
        )}
      </div>

      {/* Dual Face Comparison Layout */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Left: Document Portrait */}
        <div className="flex flex-col items-center justify-center p-6 rounded-2xl border border-slate-200 bg-slate-50/60 min-h-[280px]">
          <span className="text-xs font-mono font-bold uppercase tracking-wider text-slate-600 mb-4 flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-indigo-600" />
            Document Extracted Portrait
          </span>

          {docFaceUrl ? (
            <div className="relative group">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={docFaceUrl}
                alt="Document Portrait"
                className="w-44 h-44 object-cover rounded-2xl border-2 border-indigo-200 shadow-sm transition-transform duration-300 group-hover:scale-105"
              />
              <span className="absolute bottom-2 left-2 bg-slate-900/80 text-white text-[10px] font-mono px-2 py-0.5 rounded backdrop-blur-xs">
                Auto-Cropped ROI
              </span>
            </div>
          ) : (
            <div className="w-44 h-44 rounded-2xl border-2 border-dashed border-slate-300 flex flex-col items-center justify-center text-slate-400 p-4 text-center">
              <UserX className="w-10 h-10 mb-2 stroke-1" />
              <span className="text-xs font-mono">No face detected in document</span>
            </div>
          )}

          <p className="text-[11px] text-slate-500 font-mono mt-4 text-center">
            {portraitFace?.face_detected
              ? "Face detected via Haar cascade & perspective-corrected."
              : "Document portrait analysis pending or unreadable."}
          </p>
        </div>

        {/* Right: Live Checkpoint Camera / Capture */}
        <div className="flex flex-col items-center justify-center p-6 rounded-2xl border border-slate-200 bg-slate-50/60 min-h-[280px]">
          <span className="text-xs font-mono font-bold uppercase tracking-wider text-slate-600 mb-4 flex items-center gap-2">
            <Camera className="w-4 h-4 text-emerald-600" />
            Live Checkpoint Camera Feed
          </span>

          {cameraActive ? (
            <div className="relative w-full max-w-[280px] aspect-4/3 rounded-2xl overflow-hidden border-2 border-emerald-400 bg-black shadow-inner">
              <video ref={videoRef} autoPlay playsInline muted className="w-full h-full object-cover mirror" />
              <button
                type="button"
                onClick={captureFrame}
                className="absolute bottom-3 left-1/2 -translate-x-1/2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-mono font-bold px-4 py-1.5 rounded-full shadow-lg flex items-center gap-1.5 cursor-pointer transition-colors"
              >
                <Camera className="w-3.5 h-3.5" />
                Capture Face
              </button>
            </div>
          ) : liveImage ? (
            <div className="relative group">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={liveImage}
                alt="Captured Live Face"
                className="w-44 h-44 object-cover rounded-2xl border-2 border-emerald-400 shadow-sm"
              />
              <button
                type="button"
                onClick={resetCapture}
                className="absolute top-2 right-2 bg-slate-900/80 hover:bg-slate-900 text-white p-1.5 rounded-full backdrop-blur-xs cursor-pointer transition-colors"
                title="Retake Photo"
              >
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            </div>
          ) : (
            <div className="w-full max-w-[280px] h-44 rounded-2xl border-2 border-dashed border-slate-300 flex flex-col items-center justify-center gap-3 p-4 text-center">
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={startCamera}
                  className="px-3.5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-mono font-semibold rounded-xl flex items-center gap-1.5 cursor-pointer transition-colors shadow-xs"
                >
                  <Camera className="w-4 h-4" />
                  Start Webcam
                </button>
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="px-3.5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-mono font-semibold rounded-xl flex items-center gap-1.5 cursor-pointer transition-colors"
                >
                  <Upload className="w-4 h-4" />
                  Upload Photo
                </button>
                <input
                  type="file"
                  ref={fileInputRef}
                  accept="image/*"
                  onChange={handleFileUpload}
                  className="hidden"
                />
              </div>
              <span className="text-[11px] text-slate-400 font-mono">
                Capture live traveler face from checkpoint camera or upload file.
              </span>
            </div>
          )}

          {errorMsg && (
            <p className="text-xs text-rose-600 font-mono mt-3 text-center">{errorMsg}</p>
          )}

          {liveImage && !result && (
            <button
              type="button"
              onClick={runBiometricVerification}
              disabled={loading}
              className="mt-4 px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 text-white text-xs font-mono font-bold uppercase tracking-wider rounded-xl cursor-pointer transition-all flex items-center gap-2 shadow-md hover:shadow-indigo-500/20"
            >
              {loading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  Computing Neural Cosine Vectors...
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  Execute Biometric Match & 1:N Search
                </>
              )}
            </button>
          )}
        </div>
      </div>

      {/* Verification Results Panel */}
      <AnimatePresence>
        {result && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="space-y-4 pt-2"
          >
            {/* Primary Verdict Banner */}
            <div
              className={`p-5 rounded-2xl border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 ${
                result.status === "MATCH"
                  ? "bg-emerald-50/80 border-emerald-200"
                  : result.status === "BORDERLINE"
                  ? "bg-amber-50/80 border-amber-200"
                  : "bg-rose-50/80 border-rose-200"
              }`}
            >
              <div className="flex items-start gap-3.5">
                {result.status === "MATCH" ? (
                  <div className="p-2.5 rounded-xl bg-emerald-500 text-white">
                    <UserCheck className="w-5 h-5" />
                  </div>
                ) : (
                  <div className="p-2.5 rounded-xl bg-rose-500 text-white">
                    <UserX className="w-5 h-5" />
                  </div>
                )}
                <div>
                  <h4 className="text-sm font-bold font-mono text-slate-900">
                    {result.status === "MATCH"
                      ? "Biometric Identity Confirmed"
                      : result.status === "DUPLICATE_ALIAS_ALERT"
                      ? "CRITICAL FRAUD ALERT: Duplicate Identity / Alias Detected"
                      : "Identity Impersonation Suspected"}
                  </h4>
                  <p className="text-xs text-slate-600 mt-0.5 leading-relaxed">
                    {result.verdict}
                  </p>
                </div>
              </div>

              <div className="text-right sm:self-center shrink-0">
                <span className="text-2xl font-black font-mono text-slate-900">
                  {result.similarity_percentage.toFixed(1)}%
                </span>
                <span className="text-[11px] font-mono block text-slate-500 font-semibold">
                  Cosine Match Score
                </span>
              </div>
            </div>

            {/* 1:N Alias Cross-Border Warning Card */}
            {result.alias_check?.alias_detected && result.alias_check.top_match && (
              <div className="p-5 rounded-2xl border-2 border-rose-400 bg-rose-50/90 shadow-sm space-y-3">
                <div className="flex items-center gap-2 text-rose-900 font-mono font-black text-xs uppercase tracking-wider">
                  <AlertTriangle className="w-4 h-4 text-rose-600" />
                  1:N Cross-Border Vector Search Alert (Multiple Identities Detected)
                </div>
                <p className="text-xs text-rose-800 leading-relaxed font-sans">
                  The traveler’s biometric facial embedding matches a different individual previously recorded in the
                  cross-border immigration database. This violates SSB border defense protocols.
                </p>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
                  <div className="bg-white/80 p-2.5 rounded-xl border border-rose-200">
                    <span className="text-[10px] font-mono uppercase text-slate-500 block">Previous Identity</span>
                    <span className="text-xs font-mono font-bold text-slate-900">
                      {result.alias_check.top_match.previous_name}
                    </span>
                  </div>
                  <div className="bg-white/80 p-2.5 rounded-xl border border-rose-200">
                    <span className="text-[10px] font-mono uppercase text-slate-500 block">Previous Document</span>
                    <span className="text-xs font-mono font-bold text-slate-900">
                      {result.alias_check.top_match.previous_document_number}
                    </span>
                  </div>
                  <div className="bg-white/80 p-2.5 rounded-xl border border-rose-200">
                    <span className="text-[10px] font-mono uppercase text-slate-500 block">Crossing Location</span>
                    <span className="text-xs font-mono font-bold text-slate-900">
                      {result.alias_check.top_match.crossing_point}
                    </span>
                  </div>
                  <div className="bg-white/80 p-2.5 rounded-xl border border-rose-200">
                    <span className="text-[10px] font-mono uppercase text-slate-500 block">Biometric Match</span>
                    <span className="text-xs font-mono font-bold text-rose-700">
                      {(result.alias_check.top_match.similarity * 100).toFixed(1)}% Sim
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Metrics Breakdown: Liveness & Blockchain Receipts */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Metric 1: Liveness */}
              <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/70 flex items-center justify-between">
                <div>
                  <span className="text-xs font-mono font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                    <Zap className="w-3.5 h-3.5 text-amber-500" />
                    Physical Liveness Heuristic
                  </span>
                  <span className="text-[11px] text-slate-500 font-mono block mt-1">
                    Laplacian sharpness: {result.liveness.laplacian_variance} • Saturation: {result.liveness.mean_saturation}
                  </span>
                </div>
                <span
                  className={`px-2.5 py-1 text-xs font-mono font-bold rounded-lg border ${
                    result.liveness.is_live
                      ? "bg-emerald-100 text-emerald-800 border-emerald-300"
                      : "bg-rose-100 text-rose-800 border-rose-300"
                  }`}
                >
                  {result.liveness.is_live ? "PASSED" : "FLAGGED"}
                </span>
              </div>

              {/* Metric 2: Blockchain Block Commit */}
              <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/70 flex items-center justify-between">
                <div>
                  <span className="text-xs font-mono font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                    <Layers className="w-3.5 h-3.5 text-indigo-600" />
                    SHA-256 Ledger State
                  </span>
                  <span className="text-[11px] text-slate-500 font-mono block mt-1">
                    {blockchainBlock
                      ? `Block #${blockchainBlock.block_index} minted: ${blockchainBlock.decision}`
                      : "Cryptographic audit block recorded"}
                  </span>
                </div>
                <span className="px-2.5 py-1 text-xs font-mono font-bold bg-indigo-100 text-indigo-800 border border-indigo-300 rounded-lg">
                  COMMITTED
                </span>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};

