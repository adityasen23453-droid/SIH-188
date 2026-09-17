"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  CheckCircle2,
  Copy,
  Check,
  FileSpreadsheet,
  ShieldCheck,
  ShieldAlert,
  Eye,
  EyeOff,
  Lock
} from "lucide-react";
import { ExtractedFields } from "@/types";

interface ExtractedFieldsTableProps {
  fields: ExtractedFields;
  documentType?: string;
  officerRole?: string;
}

/**
 * Section 29 Aadhaar Act & DPDP Act 2023 Masking Helpers
 * Prevents shoulder-surfing in public border checkpoints.
 */
export function maskAadhaar(val: string): string {
  if (!val) return val;
  const digits = val.replace(/\D/g, "");
  if (digits.length >= 12) {
    const last4 = digits.slice(-4);
    return `XXXX-XXXX-${last4}`;
  }
  if (digits.length > 4) {
    const last4 = digits.slice(-4);
    const maskLen = digits.length - 4;
    return `${"X".repeat(maskLen)}-${last4}`;
  }
  return val;
}

export function maskPassport(val: string): string {
  if (!val) return val;
  const trimmed = val.trim();
  if (trimmed.length <= 3) return trimmed;
  const firstChar = trimmed[0];
  const lastTwo = trimmed.slice(-2);
  const maskCount = Math.max(trimmed.length - 3, 4);
  return `${firstChar}${"*".repeat(maskCount)}${lastTwo}`;
}

export function maskGenericDocNumber(val: string, docType?: string): string {
  if (!val) return val;
  const dt = (docType || "").toLowerCase();
  const digitsOnly = val.replace(/\D/g, "");
  if (dt === "aadhaar" || digitsOnly.length === 12) {
    return maskAadhaar(val);
  }
  if (dt === "passport" || /^[A-Z][0-9]{7,8}$/i.test(val.trim())) {
    return maskPassport(val);
  }
  if (val.length > 4) {
    const first = val.slice(0, 2);
    const last = val.slice(-2);
    return `${first}${"*".repeat(Math.max(val.length - 4, 3))}${last}`;
  }
  return val;
}

export function maskMrzLine(mrz: string): string {
  if (!mrz || mrz.length < 10) return mrz;
  // Mask document number positions (chars 0..9) with asterisks preserving check digit
  const docPart = mrz.slice(0, 9);
  const first = docPart[0];
  const last = docPart.slice(-1);
  const maskedDoc = `${first}${"*".repeat(Math.max(docPart.length - 2, 5))}${last}`;
  return maskedDoc + mrz.slice(9);
}

export const ExtractedFieldsTable: React.FC<ExtractedFieldsTableProps> = ({
  fields,
  documentType,
  officerRole = "SCREENING_OFFICER"
}) => {
  const [copied, setCopied] = useState(false);
  const [isRevealed, setIsRevealed] = useState(false);

  const getDocNumberLabel = () => {
    const dt = (documentType || "").toLowerCase();
    if (dt === "aadhaar") return "Aadhaar UID Number";
    if (dt === "voter_id") return "Voter ID (EPIC) Number";
    if (dt === "driving_license") return "Driving License Number";
    if (dt === "visa") return "Visa Control Number";
    return "Passport / ID Number";
  };

  const getNationalityLabel = () => {
    const dt = (documentType || "").toLowerCase();
    if (dt === "aadhaar") return "Country / Authority (UIDAI)";
    if (dt === "voter_id") return "Country / Authority (ECI)";
    if (dt === "driving_license") return "Country / Authority (MoRTH)";
    return "Nationality Code";
  };

  const rawIdNumber = fields.passport_number || fields.id_number || fields.aadhaar_number || fields.voter_id || fields.dl_number || fields.visa_number || "";
  const maskedIdNumber = rawIdNumber ? maskGenericDocNumber(String(rawIdNumber), documentType) : "";
  const displayIdNumber = isRevealed ? rawIdNumber : maskedIdNumber;

  const expiryVal = (fields.date_of_expiry === "LIFETIME" || (documentType === "aadhaar" && !fields.date_of_expiry))
    ? "Lifetime Validity (Per UIDAI Act)"
    : fields.date_of_expiry;

  const displayFields = [
    { label: "Full Name", key: "name", value: fields.name, confKey: "name_confidence" },
    {
      label: getDocNumberLabel(),
      key: "id_number",
      value: displayIdNumber,
      confKey: "passport_number_confidence",
      isMaskable: true,
      rawVal: rawIdNumber
    },
    { label: getNationalityLabel(), key: "nationality", value: fields.nationality, confKey: "nationality_confidence" },
    { label: "Date of Birth", key: "date_of_birth", value: fields.date_of_birth },
    { label: "Date of Expiry / Validity", key: "date_of_expiry", value: expiryVal },
    {
      label: "Gender",
      key: "gender",
      value: fields.gender === "M" ? "MALE (M)" : fields.gender === "F" ? "FEMALE (F)" : fields.gender,
      noteKey: "gender_note"
    },
  ];

  const handleCopyMrz = () => {
    const stringToCopy = isRevealed ? fields.mrz_line2 : (fields.mrz_line2 ? maskMrzLine(fields.mrz_line2) : "");
    if (stringToCopy) {
      navigator.clipboard.writeText(stringToCopy);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const displayMrzLine2 = fields.mrz_line2
    ? (isRevealed ? fields.mrz_line2 : maskMrzLine(fields.mrz_line2))
    : null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.2 }}
      className="w-full border border-slate-200 bg-white rounded-2xl p-6 shadow-md"
    >
      <div className="mb-5 pb-4 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <FileSpreadsheet className="w-4 h-4 text-indigo-600" />
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-900 font-mono">
              Extracted Identity Metadata
            </h3>

            {/* Privacy Shield Badge */}
            {!isRevealed ? (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 text-[10px] font-mono font-bold uppercase tracking-wider bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-md">
                <ShieldCheck className="w-3 h-3 text-emerald-600" />
                Privacy Shield Active (Sec 29)
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 text-[10px] font-mono font-bold uppercase tracking-wider bg-amber-50 text-amber-800 border border-amber-300 rounded-md">
                <ShieldAlert className="w-3 h-3 text-amber-600" />
                Officer Inspection View (Unmasked)
              </span>
            )}
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Protected sovereign extraction conforming to Section 29 Aadhaar Act & DPDP Act 2023 anti-shoulder-surfing mandates
          </p>
        </div>

        <div className="flex items-center gap-2.5 self-start sm:self-auto flex-wrap">
          {/* Authorized Officer Reveal Toggle */}
          <button
            type="button"
            onClick={() => setIsRevealed(!isRevealed)}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono font-semibold rounded-xl border transition-all shadow-xs ${
              isRevealed
                ? "bg-amber-50 hover:bg-amber-100 text-amber-800 border-amber-300"
                : "bg-slate-100 hover:bg-slate-200 text-slate-700 border-slate-200"
            }`}
            title={isRevealed ? "Mask PII for public screen privacy" : "Reveal full PII for official officer inspection"}
          >
            {isRevealed ? (
              <>
                <EyeOff className="w-3.5 h-3.5 text-amber-600" />
                <span>Mask PII</span>
              </>
            ) : (
              <>
                <Eye className="w-3.5 h-3.5 text-slate-600" />
                <span>Officer View</span>
              </>
            )}
          </button>

          {fields.mrz_valid_score !== undefined && (
            <div className="px-3.5 py-1.5 bg-slate-100 border border-slate-200 rounded-xl text-xs font-mono">
              <span className="text-slate-500 uppercase tracking-wider mr-1.5 font-medium">MRZ Score:</span>
              <span className="font-extrabold text-slate-900">{fields.mrz_valid_score}%</span>
            </div>
          )}
        </div>
      </div>

      {/* Grid of Fields */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {displayFields.map(({ label, key, value, confKey, noteKey, isMaskable }, idx) => {
          const rawVal = value !== undefined ? value : fields[key];
          const confVal = confKey ? fields[confKey] : undefined;
          const noteVal = noteKey ? fields[noteKey] : undefined;

          const isLowConf = confVal === "low" || rawVal === null || rawVal === undefined || !!noteVal;

          return (
            <motion.div
              key={key}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.05 + 0.25 }}
              className={`p-4 rounded-xl border transition-all duration-200 ${
                isLowConf
                  ? "bg-amber-50/50 border-amber-200/90 shadow-amber-100/50"
                  : "bg-slate-50/80 border-slate-200/90 hover:border-slate-300 hover:shadow-xs"
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-mono uppercase tracking-wider text-slate-500 font-bold">
                  {label}
                </span>

                <div className="flex items-center gap-1.5">
                  {isMaskable && !isRevealed && (
                    <span className="inline-flex items-center gap-0.5 px-1.5 py-0.2 text-[9px] font-mono font-semibold uppercase bg-slate-200/80 text-slate-600 rounded">
                      <Lock className="w-2.5 h-2.5" /> Masked
                    </span>
                  )}
                  {isLowConf ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-mono font-bold uppercase tracking-wider bg-amber-100/90 text-amber-800 border border-amber-300 rounded-md">
                      <AlertTriangle className="w-3 h-3 text-amber-600" />
                      {noteVal ? "Unverified" : "Low Confidence"}
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-mono font-bold uppercase tracking-wider bg-emerald-100/90 text-emerald-800 border border-emerald-300 rounded-md">
                      <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                      High
                    </span>
                  )}
                </div>
              </div>

              <div className={`font-mono text-sm font-extrabold tracking-wide truncate ${isMaskable && !isRevealed ? "text-indigo-900" : "text-slate-900"}`}>
                {rawVal !== null && rawVal !== undefined && rawVal !== "" ? (
                  String(rawVal)
                ) : (
                  <span className="italic text-slate-400 font-normal text-xs">Not Extracted / Null</span>
                )}
              </div>

              {noteVal && (
                <p className="text-[11px] font-mono text-amber-800/90 mt-1.5 leading-snug">
                  {noteVal}
                </p>
              )}
            </motion.div>
          );
        })}
      </div>

      {/* Raw MRZ Line 2 Code Box */}
      {fields.mrz_line2 && (
        <div className="mt-6 pt-4 border-t border-slate-100">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono uppercase tracking-wider text-slate-600 font-bold">
                Raw MRZ Line 2 (ICAO TD3 Standard)
              </span>
              {!isRevealed && (
                <span className="text-[10px] font-mono text-slate-400 font-normal">
                  (Document number masked)
                </span>
              )}
            </div>
            <button
              type="button"
              onClick={handleCopyMrz}
              className="inline-flex items-center gap-1.5 px-3 py-1 text-[11px] font-mono font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg border border-slate-200 transition-colors"
            >
              {copied ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
              {copied ? "Copied" : "Copy String"}
            </button>
          </div>
          <div className="p-3.5 bg-slate-900 text-emerald-400 font-mono text-xs tracking-widest break-all border border-slate-800 rounded-xl shadow-inner selection:bg-emerald-900 selection:text-white">
            {displayMrzLine2}
          </div>
        </div>
      )}
    </motion.div>
  );
};
