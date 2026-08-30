"use client";

import React from "react";
import { motion } from "framer-motion";
import { Check, X, Minus, ShieldCheck, ShieldAlert, Binary, Sparkles, AlertCircle } from "lucide-react";
import { ValidationResult, ChecksumFieldResult } from "@/types";

interface ValidationResultsProps {
  validation: ValidationResult;
}

export const ValidationResults: React.FC<ValidationResultsProps> = ({
  validation,
}) => {
  const checksum = validation.checksum || {};
  const dates = validation.dates || {};
  const blacklist = validation.blacklist || {};

  const checks: { label: string; data?: ChecksumFieldResult }[] = [
    { label: "Passport Number Checkdigit", data: checksum.passport_number_check },
    { label: "Date of Birth Checkdigit", data: checksum.date_of_birth_check },
    { label: "Date of Expiry Checkdigit", data: checksum.date_of_expiry_check },
    { label: "Composite MRZ Checkdigit", data: checksum.composite_check },
  ];

  const renderStatusBadge = (check?: ChecksumFieldResult) => {
    if (!check || check.valid === undefined) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-mono font-bold uppercase tracking-wider bg-slate-200 text-slate-700 border border-slate-300 rounded-lg">
          <Minus className="w-3.5 h-3.5 text-slate-500" />
          Skipped
        </span>
      );
    }
    if (check.valid === true) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-mono font-bold uppercase tracking-wider bg-emerald-100 text-emerald-800 border border-emerald-300 rounded-lg shadow-xs">
          <Check className="w-3.5 h-3.5 text-emerald-700" />
          Pass
        </span>
      );
    }
    if (check.valid === false) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-mono font-bold uppercase tracking-wider bg-rose-100 text-rose-800 border border-rose-300 rounded-lg shadow-xs">
          <X className="w-3.5 h-3.5 text-rose-700" />
          Fail
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-mono font-bold uppercase tracking-wider bg-slate-200 text-slate-700 border border-slate-300 rounded-lg">
        <Minus className="w-3.5 h-3.5 text-slate-500" />
        Skipped
      </span>
    );
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.3 }}
      className="w-full border border-slate-200 bg-white rounded-2xl p-6 shadow-md space-y-6"
    >
      <div>
        <div className="mb-5 pb-4 border-b border-slate-100 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Binary className="w-4 h-4 text-indigo-600" />
              <h3 className="text-sm font-bold uppercase tracking-wider text-slate-900 font-mono">
                MRZ 7-3-1 Checksum Validation Engine
              </h3>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Field-level modulo 10 checkdigit verification as mandated by ICAO Doc 9303
            </p>
          </div>
        </div>

        {/* Checksum Table */}
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-50/50">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-100/80 text-xs font-mono uppercase tracking-wider text-slate-600">
                <th className="py-3 px-4 font-bold">Check Target</th>
                <th className="py-3 px-4 font-bold">Slice (0-idx)</th>
                <th className="py-3 px-4 font-bold">Extracted Segment</th>
                <th className="py-3 px-4 font-bold text-center">Expected</th>
                <th className="py-3 px-4 font-bold text-center">Computed</th>
                <th className="py-3 px-4 font-bold text-right">Result</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200/70">
              {checks.map(({ label, data }, idx) => (
                <tr key={idx} className="hover:bg-white transition-colors">
                  <td className="py-3.5 px-4 font-mono font-medium text-xs text-slate-700">
                    {label}
                  </td>
                  <td className="py-3.5 px-4 font-mono text-xs text-slate-500">
                    {data?.field_slice || "-"}
                  </td>
                  <td className="py-3.5 px-4 font-mono text-xs font-bold text-slate-900">
                    {data?.value || "-"}
                  </td>
                  <td className="py-3.5 px-4 font-mono text-xs font-extrabold text-center text-slate-900">
                    {data?.expected_digit !== null && data?.expected_digit !== undefined ? data.expected_digit : "-"}
                  </td>
                  <td className="py-3.5 px-4 font-mono text-xs font-extrabold text-center text-slate-900">
                    {data?.computed_digit !== null && data?.computed_digit !== undefined ? data.computed_digit : "-"}
                  </td>
                  <td className="py-3.5 px-4 text-right">
                    {renderStatusBadge(data)}
                    {data?.note && (
                      <span className="block text-[11px] text-slate-500 font-mono mt-1">
                        {data.note}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* OCR Auto-Corrections */}
        {checksum.ocr_corrections_applied && checksum.ocr_corrections_applied.length > 0 && (
          <div className="mt-4 p-4 rounded-xl bg-amber-50/60 border border-amber-200/90">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="w-4 h-4 text-amber-600" />
              <span className="text-xs font-mono font-bold uppercase tracking-wider text-amber-900">
                Transparent Positional OCR Auto-Corrections ({checksum.ocr_corrections_applied.length})
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              {checksum.ocr_corrections_applied.map((corr, idx) => (
                <span key={idx} className="px-2.5 py-1 text-xs font-mono bg-white text-amber-900 border border-amber-300 rounded-md shadow-xs">
                  {corr}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Date & Blacklist Status */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-slate-100">
        {/* Date Plausibility */}
        <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/60 space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-slate-700">
              Date Validity & Expiry
            </span>
          </div>

          <div className="space-y-2 text-xs font-mono pt-1">
            <div className="flex justify-between items-center py-1 border-b border-slate-200/70">
              <span className="text-slate-500">Expiration Status:</span>
              <span className={`px-2.5 py-0.5 font-bold rounded-md ${
                dates.expiry_valid
                  ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                  : "bg-rose-100 text-rose-800 border border-rose-300"
              }`}>
                {dates.expiry_valid ? "VALID / ACTIVE" : "EXPIRED OR UNPARSEABLE"}
              </span>
            </div>

            <div className="flex justify-between items-center py-1">
              <span className="text-slate-500">DOB Plausible:</span>
              <span className="font-bold text-slate-900">
                {dates.dob_plausible ? "YES" : "NO"}
              </span>
            </div>
          </div>
        </div>

        {/* Blacklist Database Check */}
        <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/60 space-y-2">
          <div className="flex items-center gap-2">
            {blacklist.blacklisted ? (
              <ShieldAlert className="w-4 h-4 text-rose-600" />
            ) : (
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
            )}
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-slate-700">
              Interpol / Watchlist Screening
            </span>
          </div>

          <div className="space-y-2 text-xs font-mono pt-1">
            <div className="flex justify-between items-center py-1 border-b border-slate-200/70">
              <span className="text-slate-500">Database Search:</span>
              <span className={`px-2.5 py-0.5 font-bold rounded-md ${
                blacklist.blacklisted
                  ? "bg-rose-100 text-rose-800 border border-rose-300"
                  : "bg-emerald-100 text-emerald-800 border border-emerald-300"
              }`}>
                {blacklist.blacklisted ? "FLAGGED / BLACKLISTED" : "CLEAN (NO MATCH)"}
              </span>
            </div>

            {blacklist.reason && (
              <div className="flex justify-between items-center py-1">
                <span className="text-slate-500">Match Details:</span>
                <span className="font-bold text-rose-700">{blacklist.reason}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Issues Box */}
      {validation.issues && validation.issues.length > 0 && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-xs font-mono">
          <div className="flex items-center gap-2 mb-2 text-rose-800 font-bold uppercase tracking-wider">
            <AlertCircle className="w-4 h-4 shrink-0 text-rose-600" />
            <span>Validation Issues Flagged ({validation.issues.length})</span>
          </div>
          <ul className="space-y-1 text-rose-900 font-medium">
            {validation.issues.map((issue, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="text-rose-600">•</span>
                <span>{issue}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </motion.div>
  );
};
