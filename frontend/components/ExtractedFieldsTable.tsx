"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, Copy, Check, FileSpreadsheet } from "lucide-react";
import { ExtractedFields } from "@/types";

interface ExtractedFieldsTableProps {
  fields: ExtractedFields;
  documentType?: string;
}

export const ExtractedFieldsTable: React.FC<ExtractedFieldsTableProps> = ({
  fields,
  documentType,
}) => {
  const [copied, setCopied] = useState(false);

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

  const idNumberVal = fields.passport_number || fields.id_number || fields.aadhaar_number || fields.voter_id || fields.dl_number || fields.visa_number;
  const expiryVal = (fields.date_of_expiry === "LIFETIME" || (documentType === "aadhaar" && !fields.date_of_expiry))
    ? "Lifetime Validity (Per UIDAI Act)"
    : fields.date_of_expiry;

  const displayFields = [
    { label: "Full Name", key: "name", value: fields.name, confKey: "name_confidence" },
    { label: getDocNumberLabel(), key: "id_number", value: idNumberVal, confKey: "passport_number_confidence" },
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
    if (fields.mrz_line2) {
      navigator.clipboard.writeText(fields.mrz_line2);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.2 }}
      className="w-full border border-slate-200 bg-white rounded-2xl p-6 shadow-md"
    >
      <div className="mb-5 pb-4 border-b border-slate-100 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <FileSpreadsheet className="w-4 h-4 text-indigo-600" />
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-900 font-mono">
              Extracted Identity Metadata
            </h3>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Structured field data extracted via PassportEye MRZ parser and OCR fallback engine
          </p>
        </div>

        {fields.mrz_valid_score !== undefined && (
          <div className="px-3.5 py-1.5 bg-slate-100 border border-slate-200 rounded-xl text-xs font-mono">
            <span className="text-slate-500 uppercase tracking-wider mr-1.5 font-medium">MRZ Match Score:</span>
            <span className="font-extrabold text-slate-900">{fields.mrz_valid_score}%</span>
          </div>
        )}
      </div>

      {/* Grid of Fields */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {displayFields.map(({ label, key, value, confKey, noteKey }, idx) => {
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

              <div className="font-mono text-sm font-extrabold text-slate-900 tracking-wide truncate">
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
            <span className="text-xs font-mono uppercase tracking-wider text-slate-600 font-bold">
              Raw MRZ Line 2 (ICAO TD3 Standard)
            </span>
            <button
              onClick={handleCopyMrz}
              className="inline-flex items-center gap-1.5 px-3 py-1 text-[11px] font-mono font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg border border-slate-200 transition-colors"
            >
              {copied ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
              {copied ? "Copied" : "Copy String"}
            </button>
          </div>
          <div className="p-3.5 bg-slate-900 text-emerald-400 font-mono text-xs tracking-widest break-all border border-slate-800 rounded-xl shadow-inner selection:bg-emerald-900 selection:text-white">
            {fields.mrz_line2}
          </div>
        </div>
      )}
    </motion.div>
  );
};
