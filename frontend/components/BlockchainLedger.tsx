"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ShieldCheck,
  ShieldAlert,
  Layers,
  CheckCircle2,
  RefreshCw,
  Hash,
  Clock,
  UserCheck,
  FileText,
  Lock,
  X,
  ExternalLink,
  ChevronRight,
  Key,
  Server,
  Database,
  Info
} from "lucide-react";
import { BlockchainBlock, BlockchainAuditResult } from "@/types";

interface BlockchainLedgerProps {
  isOpen: boolean;
  onClose: () => void;
  latestBlock?: BlockchainBlock | null;
}

export const BlockchainLedger: React.FC<BlockchainLedgerProps> = ({
  isOpen,
  onClose,
  latestBlock,
}) => {
  const [blocks, setBlocks] = useState<BlockchainBlock[]>([]);
  const [auditReport, setAuditReport] = useState<BlockchainAuditResult | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [verifying, setVerifying] = useState<boolean>(false);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);
  const [showNbfSpec, setShowNbfSpec] = useState<boolean>(false);
  const [nbfSpec, setNbfSpec] = useState<any | null>(null);

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const fetchBlocks = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${apiBase}/api/ledger/blocks?limit=25`);
      if (res.ok) {
        const data = await res.json();
        setBlocks(data.blocks || []);
      }
    } catch (err) {
      console.error("Failed to fetch ledger blocks:", err);
    } finally {
      setLoading(false);
    }
  };

  const runChainAudit = async () => {
    setVerifying(true);
    try {
      const res = await fetch(`${apiBase}/api/ledger/verify`);
      if (res.ok) {
        const report = await res.json();
        setAuditReport(report);
      }
    } catch (err) {
      console.error("Failed to verify audit ledger:", err);
    } finally {
      setVerifying(false);
    }
  };

  const fetchNbfSpecification = async () => {
    try {
      const res = await fetch(`${apiBase}/api/ledger/nbf-specification`);
      if (res.ok) {
        const data = await res.json();
        setNbfSpec(data);
      }
    } catch (err) {
      console.error("Failed to fetch NBF specification:", err);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchBlocks();
      runChainAudit();
      fetchNbfSpecification();
    }
  }, [isOpen, latestBlock]);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(text);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-sm">
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 10 }}
          transition={{ duration: 0.2 }}
          className="relative w-full max-w-5xl max-h-[90vh] bg-white rounded-3xl shadow-2xl border border-slate-200 overflow-hidden flex flex-col"
        >
          {/* Modal Header */}
          <div className="p-6 bg-slate-900 text-white flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-indigo-600/30 border border-indigo-400/40 text-indigo-400">
                <Layers className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="text-base font-bold font-mono tracking-tight text-white">
                    Cryptographically Chained Audit Ledger
                  </h3>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                    ZERO-PII ENFORCED
                  </span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30">
                    NBF / VISHVASYA ALIGNED
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  Append-only sovereign screening audit trail with SHA-256 Merkle linkage and Ed25519 digital signatures.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setShowNbfSpec(!showNbfSpec)}
                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs font-mono text-indigo-300 rounded-xl flex items-center gap-1.5 cursor-pointer transition-colors border border-indigo-500/30"
                title="View National Blockchain Framework (NBF / Vishvasya) Alignment Specification"
              >
                <Info className="w-3.5 h-3.5 text-indigo-400" />
                <span>NBF Spec</span>
              </button>
              <button
                type="button"
                onClick={runChainAudit}
                disabled={verifying}
                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:bg-slate-800 text-xs font-mono text-slate-200 rounded-xl flex items-center gap-1.5 cursor-pointer transition-colors border border-slate-700"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${verifying ? "animate-spin" : ""}`} />
                {verifying ? "Verifying..." : "Verify Chain"}
              </button>
              <button
                type="button"
                onClick={onClose}
                className="p-1.5 text-slate-400 hover:text-white rounded-xl hover:bg-slate-800 transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Dual Anchor Status Bar */}
          <div className="px-6 py-3 bg-slate-100/90 border-b border-slate-200 flex flex-wrap items-center justify-between gap-3 text-xs font-mono">
            <div className="flex items-center gap-4 flex-wrap">
              {/* Local Anchor Indicator */}
              <div className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-white border border-slate-200 shadow-2xs">
                <Database className="w-3.5 h-3.5 text-indigo-600" />
                <span className="text-slate-500">Local Ledger:</span>
                <span className="font-bold text-emerald-700 flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3 text-emerald-600" /> Anchored (SQLite)
                </span>
              </div>

              {/* Permissioned DLT / NBF Indicator */}
              <div className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-white border border-slate-200 shadow-2xs">
                <Server className="w-3.5 h-3.5 text-blue-600" />
                <span className="text-slate-500">Permissioned DLT (NBF):</span>
                <span className="font-bold text-blue-700">
                  Integration-Ready (Vishvasya BaaS)
                </span>
              </div>

              {/* Ed25519 Signature Status */}
              <div className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-white border border-slate-200 shadow-2xs">
                <Key className="w-3.5 h-3.5 text-amber-600" />
                <span className="text-slate-500">Signatures:</span>
                <span className="font-bold text-slate-800">
                  Ed25519 (RFC 8032)
                </span>
              </div>
            </div>

            <div className="flex items-center gap-1.5 text-slate-500 text-[11px]">
              <Lock className="w-3.5 h-3.5 text-indigo-600" />
              <span>Zero PII On-Chain: Hashes & Signatures Only</span>
            </div>
          </div>

          {/* NBF Specification Dropdown / Drawer */}
          {showNbfSpec && nbfSpec && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="px-6 py-4 bg-indigo-950/90 text-indigo-100 border-b border-indigo-800 text-xs font-mono space-y-2"
            >
              <div className="flex items-center justify-between pb-2 border-b border-indigo-800/80">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-white uppercase tracking-wider">
                    {nbfSpec.framework}
                  </span>
                  <span className="px-2 py-0.5 text-[10px] bg-indigo-800 text-indigo-200 rounded">
                    {nbfSpec.guidelines_reference}
                  </span>
                </div>
                <button
                  onClick={() => setShowNbfSpec(false)}
                  className="text-indigo-400 hover:text-white"
                >
                  Close
                </button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-1 text-[11px]">
                <div>
                  <span className="text-indigo-400 block font-semibold">Governance & Authority:</span>
                  <span>{nbfSpec.authority}</span>
                </div>
                <div>
                  <span className="text-indigo-400 block font-semibold">Deployment Tier:</span>
                  <span className="text-amber-300 font-bold">{nbfSpec.integration_status}</span>
                </div>
                <div>
                  <span className="text-indigo-400 block font-semibold">Cryptographic Standards:</span>
                  <span>SHA-256 • RFC 8785 (JCS) • Ed25519</span>
                </div>
              </div>
              <p className="text-[10px] text-indigo-300/90 pt-1">
                Notice: Conforms to MeitY September 2024 Vishvasya BaaS specifications. Production onboarding requires authorized ministry credentials and air-gapped border enclave deployment.
              </p>
            </motion.div>
          )}

          {/* Audit Verification Summary Bar */}
          <div className="px-6 py-3 bg-slate-50 border-b border-slate-200 flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-6">
              <div>
                <span className="text-[10px] font-mono uppercase text-slate-500 block">Chain Integrity</span>
                <div className="flex items-center gap-1.5 mt-0.5">
                  {auditReport?.chain_valid ? (
                    <>
                      <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                      <span className="text-xs font-mono font-bold text-emerald-800">
                        100% Cryptographically Intact
                      </span>
                    </>
                  ) : (
                    <>
                      <ShieldAlert className="w-4 h-4 text-rose-600" />
                      <span className="text-xs font-mono font-bold text-rose-800">
                        Chain Integrity Alert!
                      </span>
                    </>
                  )}
                </div>
              </div>

              <div>
                <span className="text-[10px] font-mono uppercase text-slate-500 block">Total Blocks</span>
                <span className="text-xs font-mono font-bold text-slate-900">
                  {auditReport?.total_blocks || blocks.length} Mined Blocks
                </span>
              </div>

              {auditReport?.signatures_verified !== undefined && (
                <div>
                  <span className="text-[10px] font-mono uppercase text-slate-500 block">Verified Signatures</span>
                  <span className="text-xs font-mono font-bold text-indigo-700">
                    {auditReport.signatures_verified} Ed25519 Signed
                  </span>
                </div>
              )}

              <div className="hidden sm:block">
                <span className="text-[10px] font-mono uppercase text-slate-500 block">Consensus / Serialization</span>
                <span className="text-xs font-mono font-semibold text-slate-700">
                  SHA-256 Merkle • RFC 8785 Canonical JSON
                </span>
              </div>
            </div>
          </div>

          {/* Blocks List */}
          <div className="flex-1 overflow-y-auto p-6 space-y-4">
            {loading ? (
              <div className="py-20 flex flex-col items-center justify-center text-slate-400">
                <RefreshCw className="w-8 h-8 animate-spin text-indigo-600 mb-2" />
                <span className="text-xs font-mono">Loading cryptographically chained blocks...</span>
              </div>
            ) : blocks.length === 0 ? (
              <div className="py-20 text-center text-slate-400 font-mono text-xs">
                No blocks recorded yet. Scan a document to mine Block #1.
              </div>
            ) : (
              blocks.map((b) => {
                const eventType = b.event_type || "SCREENING_EVENT";
                const isOverride = eventType === "OFFICER_OVERRIDE_EVENT";
                const isBiometric = eventType === "BIOMETRIC_EVENT";
                const anchorStatus = b.anchor_status || "LOCAL_ANCHORED";

                return (
                  <div
                    key={b.block_index}
                    className={`p-5 rounded-2xl border bg-white shadow-xs transition-colors space-y-3 ${
                      isOverride
                        ? "border-amber-300 hover:border-amber-400 bg-amber-50/20"
                        : isBiometric
                        ? "border-purple-200 hover:border-purple-300"
                        : "border-slate-200 hover:border-indigo-300"
                    }`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-slate-100">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="px-2.5 py-1 rounded-lg bg-slate-900 text-white text-xs font-mono font-bold">
                          Block #{b.block_index}
                        </span>

                        {/* Event Type Badge */}
                        <span
                          className={`px-2 py-0.5 text-[10px] font-mono font-bold uppercase rounded border ${
                            isOverride
                              ? "bg-amber-100 text-amber-900 border-amber-300"
                              : isBiometric
                              ? "bg-purple-100 text-purple-900 border-purple-300"
                              : "bg-indigo-50 text-indigo-800 border-indigo-200"
                          }`}
                        >
                          {eventType.replace(/_/g, " ")}
                        </span>

                        {/* Anchor Status Badge */}
                        <span
                          className={`px-2 py-0.5 text-[10px] font-mono font-semibold uppercase rounded border ${
                            anchorStatus === "NBF_ANCHORED"
                              ? "bg-emerald-50 text-emerald-800 border-emerald-300"
                              : anchorStatus === "ANCHOR_PENDING"
                              ? "bg-amber-50 text-amber-800 border-amber-200"
                              : "bg-slate-100 text-slate-700 border-slate-200"
                          }`}
                        >
                          {anchorStatus}
                        </span>

                        <span className="text-xs font-mono text-slate-500 flex items-center gap-1">
                          <Clock className="w-3.5 h-3.5" />
                          {new Date(b.timestamp).toLocaleString()}
                        </span>
                        <span className="text-xs font-mono text-slate-400">•</span>
                        <span className="text-xs font-mono font-semibold text-slate-700">
                          {b.document_type}
                        </span>
                      </div>

                      <div className="flex items-center gap-2">
                        <span
                          className={`px-2.5 py-0.5 text-[11px] font-mono font-bold uppercase rounded border ${
                            b.decision === "CLEARED"
                              ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                              : b.decision === "FLAGGED_FOR_INSPECTION"
                              ? "bg-amber-50 text-amber-800 border-amber-200"
                              : "bg-rose-50 text-rose-700 border-rose-200"
                          }`}
                        >
                          {b.decision}
                        </span>
                        <span className="text-[11px] font-mono text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
                          Risk: {Number(b.risk_score).toFixed(1)}
                        </span>
                      </div>
                    </div>

                    {/* Hashes & Cryptographic Proof */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-[11px] font-mono">
                      <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200">
                        <div className="flex items-center justify-between text-slate-500 mb-1">
                          <span className="font-bold uppercase text-[10px]">Document SHA-256 Hash</span>
                          <button
                            type="button"
                            onClick={() => copyToClipboard(b.doc_hash)}
                            className="hover:text-indigo-600 cursor-pointer"
                          >
                            {copiedHash === b.doc_hash ? "Copied!" : "Copy"}
                          </button>
                        </div>
                        <span className="text-slate-800 break-all select-all font-mono">
                          {b.doc_hash}
                        </span>
                      </div>

                      <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200">
                        <div className="flex items-center justify-between text-slate-500 mb-1">
                          <span className="font-bold uppercase text-[10px]">Merkle Block Hash</span>
                          <button
                            type="button"
                            onClick={() => copyToClipboard(b.block_hash)}
                            className="hover:text-indigo-600 cursor-pointer"
                          >
                            {copiedHash === b.block_hash ? "Copied!" : "Copy"}
                          </button>
                        </div>
                        <span className="text-indigo-700 break-all select-all font-mono font-semibold">
                          {b.block_hash}
                        </span>
                      </div>
                    </div>

                    {/* Ed25519 Digital Signature & Canonical Hash (Phases 8-12) */}
                    {(b.signature || b.canonical_hash) && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-[11px] font-mono pt-1">
                        {b.canonical_hash && (
                          <div className="p-2 rounded-lg bg-indigo-50/50 border border-indigo-100">
                            <div className="flex items-center justify-between text-indigo-900 mb-0.5 text-[10px]">
                              <span className="font-bold uppercase">Canonical JCS Hash (RFC 8785)</span>
                              <button
                                type="button"
                                onClick={() => copyToClipboard(b.canonical_hash || "")}
                                className="hover:text-indigo-600 cursor-pointer"
                              >
                                {copiedHash === b.canonical_hash ? "Copied!" : "Copy"}
                              </button>
                            </div>
                            <span className="text-indigo-900 break-all select-all text-[10px]">
                              {b.canonical_hash}
                            </span>
                          </div>
                        )}

                        {b.signature && (
                          <div className="p-2 rounded-lg bg-emerald-50/50 border border-emerald-100">
                            <div className="flex items-center justify-between text-emerald-900 mb-0.5 text-[10px]">
                              <span className="font-bold uppercase flex items-center gap-1">
                                <Key className="w-2.5 h-2.5 text-emerald-700" />
                                Station Ed25519 Signature
                              </span>
                              <button
                                type="button"
                                onClick={() => copyToClipboard(b.signature || "")}
                                className="hover:text-emerald-700 cursor-pointer"
                              >
                                {copiedHash === b.signature ? "Copied!" : "Copy"}
                              </button>
                            </div>
                            <span className="text-emerald-900 break-all select-all text-[10px]">
                              {b.signature}
                            </span>
                          </div>
                        )}
                      </div>
                    )}

                    <div className="flex flex-wrap items-center justify-between text-[11px] font-mono text-slate-500 pt-1">
                      <div className="flex items-center gap-1.5 truncate max-w-md">
                        <span className="text-slate-400">Prev Hash:</span>
                        <span className="truncate">{b.previous_hash}</span>
                      </div>
                      <div>
                        <span>Officer ID: </span>
                        <span className="font-bold text-slate-700">{b.officer_id}</span>
                        <span className="mx-2">•</span>
                        <span>Biometric: </span>
                        <span className="font-bold text-slate-700">{b.biometric_status}</span>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Modal Footer */}
          <div className="p-4 bg-slate-50 border-t border-slate-200 flex items-center justify-between text-xs font-mono text-slate-500">
            <span>BorderShield Sovereign Audit Node • SSB Checkpoint #26188</span>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-xl transition-colors cursor-pointer font-bold"
            >
              Close Ledger Explorer
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};
