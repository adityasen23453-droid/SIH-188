"use client";

import React from "react";
import { motion } from "framer-motion";
import {
  Check,
  X,
  Minus,
  ShieldCheck,
  ShieldAlert,
  Binary,
  Sparkles,
  AlertCircle,
  Building2,
  FileCheck,
  QrCode,
  Car,
  Award
} from "lucide-react";
import { ValidationResult, ChecksumFieldResult } from "@/types";

interface ValidationResultsProps {
  validation: ValidationResult;
  documentType?: string;
}

export const ValidationResults: React.FC<ValidationResultsProps> = ({
  validation,
  documentType,
}) => {
  const checksum = validation.checksum || {};
  const dates = validation.dates || {};
  const blacklist = validation.blacklist || {};
  const aadhaar = validation.aadhaar_verification;
  const voter = validation.voter_id_verification;
  const dl = validation.dl_verification;
  const visa = validation.visa_verification;

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

  const renderBoolBadge = (val?: boolean | null, passText = "Verified", failText = "Failed") => {
    return val ? (
      <span className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-mono font-bold uppercase tracking-wider bg-emerald-100 text-emerald-800 border border-emerald-300 rounded-lg shadow-xs">
        <Check className="w-3.5 h-3.5 text-emerald-700" />
        {passText}
      </span>
    ) : (
      <span className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-mono font-bold uppercase tracking-wider bg-rose-100 text-rose-800 border border-rose-300 rounded-lg shadow-xs">
        <X className="w-3.5 h-3.5 text-rose-700" />
        {failText}
      </span>
    );
  };

  const getExpirationBadge = () => {
    const status = dates.expiry_status;
    if (status === "ACTIVE" || (dates.expiry_valid && status !== "NOT_APPLICABLE")) {
      return (
        <span className="px-2.5 py-0.5 font-bold rounded-md bg-emerald-100 text-emerald-800 border border-emerald-300">
          VALID / ACTIVE
        </span>
      );
    }
    if (status === "NOT_APPLICABLE" || documentType === "aadhaar") {
      return (
        <span className="px-2.5 py-0.5 font-bold rounded-md bg-slate-100 text-slate-700 border border-slate-300">
          LIFETIME / NOT APPLICABLE
        </span>
      );
    }
    if (status === "NOT_DETECTED") {
      return (
        <span className="px-2.5 py-0.5 font-bold rounded-md bg-amber-100 text-amber-800 border border-amber-300">
          NOT DETECTED
        </span>
      );
    }
    if (status === "EXPIRED") {
      return (
        <span className="px-2.5 py-0.5 font-bold rounded-md bg-rose-100 text-rose-800 border border-rose-300">
          EXPIRED
        </span>
      );
    }
    return (
      <span className="px-2.5 py-0.5 font-bold rounded-md bg-rose-100 text-rose-800 border border-rose-300">
        {dates.expiry_valid ? "VALID / ACTIVE" : "EXPIRED OR UNPARSEABLE"}
      </span>
    );
  };

  const getDobBadge = () => {
    const status = dates.dob_status;
    if (status === "PLAUSIBLE" || dates.dob_plausible === true) {
      return <span className="font-bold text-emerald-700">YES</span>;
    }
    if (status === "NOT_DETECTED" || dates.dob_plausible === null) {
      return <span className="font-bold text-amber-700">NOT DETECTED</span>;
    }
    return <span className="font-bold text-rose-700">NO</span>;
  };

  const normType = (documentType || "").toLowerCase();
  const isAadhaar = normType === "aadhaar" || !!aadhaar;
  const isVoterId = normType === "voter_id" || !!voter;
  const isDl = normType === "driving_license" || !!dl;
  const isVisa = normType === "visa" || !!visa;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.3 }}
      className="w-full border border-slate-200 bg-white rounded-2xl p-6 shadow-md space-y-6"
    >
      {/* 1. Indian Aadhaar Card Verification Engine */}
      {isAadhaar && aadhaar && (
        <div>
          <div className="mb-5 pb-4 border-b border-slate-100 flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <Building2 className="w-4 h-4 text-emerald-600" />
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-900 font-mono">
                  UIDAI Aadhaar Verhoeff \(D_5\) Mathematical Verification Engine
                </h3>
              </div>
              <p className="text-xs text-slate-500 mt-1">
                Official Government of India Unique Identification Authority mathematical and cryptographic checks
              </p>
            </div>
            <div className="px-3 py-1 bg-emerald-50 border border-emerald-200 rounded-xl text-xs font-mono font-bold text-emerald-700">
              UIDAI Standard Active
            </div>
          </div>

          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-50/50">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-100/80 text-xs font-mono uppercase tracking-wider text-slate-600">
                  <th className="py-3 px-4 font-bold">Verification Target</th>
                  <th className="py-3 px-4 font-bold">Standard / Algorithm</th>
                  <th className="py-3 px-4 font-bold text-center">Expected</th>
                  <th className="py-3 px-4 font-bold text-center">Computed</th>
                  <th className="py-3 px-4 font-bold text-right">Result</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200/70">
                <tr className="hover:bg-white transition-colors">
                  <td className="py-3.5 px-4 font-mono font-medium text-xs text-slate-700">
                    12-Digit UID Format
                  </td>
                  <td className="py-3.5 px-4 font-mono text-xs text-slate-500">
                    UIDAI 12-Digit (Prefix \(\ge 2\))
                  </td>
                  <td className="py-3.5 px-4 font-mono text-xs text-center text-slate-900 font-bold">
                    12 Digits
                  </td>
                  <td className="py-3.5 px-4 font-mono text-xs text-center text-slate-900 font-bold">
                    {aadhaar.uid_format_valid ? "12 Digits" : "Malformed"}
                  </td>
                  <td className="py-3.5 px-4 text-right">
                    {renderBoolBadge(aadhaar.uid_format_valid)}
                  </td>
                </tr>

                <tr className="hover:bg-white transition-colors">
                  <td className="py-3.5 px-4 font-mono font-medium text-xs text-slate-700">
                    Verhoeff Check Digit
                  </td>
                  <td className="py-3.5 px-4 font-mono text-xs text-slate-500">
                    Dihedral Group \(D_5\) Permutation
                  </td>
                  <td className="py-3.5 px-4 font-mono text-xs text-center font-extrabold text-slate-900">
                    {aadhaar.expected_checkdigit || "-"}
                  </td>
                  <td className="py-3.5 px-4 font-mono text-xs text-center font-extrabold text-slate-900">
                    {aadhaar.computed_checkdigit || "-"}
                  </td>
                  <td className="py-3.5 px-4 text-right">
                    {renderBoolBadge(aadhaar.verhoeff_valid, "Pass", "Fail")}
                  </td>
                </tr>

                <tr className="hover:bg-white transition-colors">
                  <td className="py-3.5 px-4 font-mono font-medium text-xs text-slate-700">
                    Sovereign Header / Emblem
                  </td>
                  <td className="py-3.5 px-4 font-mono text-xs text-slate-500">
                    Government of India / UIDAI
                  </td>
                  <td className="py-3.5 px-4 font-mono text-xs text-center text-slate-900 font-bold">
                    Present
                  </td>
                  <td className="py-3.5 px-4 font-mono text-xs text-center text-slate-900 font-bold">
                    {aadhaar.sovereign_header_detected ? "Detected" : "Not Found"}
                  </td>
                  <td className="py-3.5 px-4 text-right">
                    {renderBoolBadge(aadhaar.sovereign_header_detected, "Detected", "Missing")}
                  </td>
                </tr>

                <tr className="hover:bg-white transition-colors">
                  <td className="py-3.5 px-4 font-mono font-medium text-xs text-slate-700">
                    Secure 2D Matrix / QR Code
                  </td>
                  <td className="py-3.5 px-4 font-mono text-xs text-slate-500">
                    UIDAI High-Density QR Barcode
                  </td>
                  <td className="py-3.5 px-4 font-mono text-xs text-center text-slate-900 font-bold">
                    Optional
                  </td>
                  <td className="py-3.5 px-4 font-mono text-xs text-center text-slate-900 font-bold">
                    {aadhaar.qr_code_detected ? "Detected" : "Not Detected"}
                  </td>
                  <td className="py-3.5 px-4 text-right">
                    {aadhaar.qr_code_detected ? (
                      renderBoolBadge(true, "Detected")
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-mono font-bold uppercase tracking-wider bg-slate-200 text-slate-700 border border-slate-300 rounded-lg">
                        <Minus className="w-3.5 h-3.5 text-slate-500" />
                        Not Present
                      </span>
                    )}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 2. Indian Voter ID (EPIC) Verification Engine */}
      {isVoterId && voter && (
        <div>
          <div className="mb-5 pb-4 border-b border-slate-100 flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <Award className="w-4 h-4 text-indigo-600" />
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-900 font-mono">
                  ECI Elector Photo Identity Card (EPIC) Verification Engine
                </h3>
              </div>
              <p className="text-xs text-slate-500 mt-1">
                Election Commission of India alphanumeric standard and jurisdiction validation
              </p>
            </div>
            <div className="px-3 py-1 bg-indigo-50 border border-indigo-200 rounded-xl text-xs font-mono font-bold text-indigo-700">
              ECI Standard Active
            </div>
          </div>

          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-50/50">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-100/80 text-xs font-mono uppercase tracking-wider text-slate-600">
                  <th className="py-3 px-4 font-bold">Verification Target</th>
                  <th className="py-3 px-4 font-bold">Standard Format</th>
                  <th className="py-3 px-4 font-bold text-center">Extracted Value</th>
                  <th className="py-3 px-4 font-bold text-right">Result</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200/70">
                <tr className="hover:bg-white transition-colors">
                  <td className="py-3.5 px-4 font-mono font-medium text-xs text-slate-700">
                    EPIC Alphanumeric Format
                  </td>
                  <td className="py-3.5 px-4 font-mono text-xs text-slate-500">
                    3 Letters + 7 Numeric Digits
                  </td>
                  <td className="py-3.5 px-4 font-mono text-xs text-center font-bold text-slate-900">
                    {voter.epic_number || "-"}
                  </td>
                  <td className="py-3.5 px-4 text-right">
                    {renderBoolBadge(voter.epic_format_valid)}
                  </td>
                </tr>

                <tr className="hover:bg-white transition-colors">
                  <td className="py-3.5 px-4 font-mono font-medium text-xs text-slate-700">
                    ECI Authority Header
                  </td>
                  <td className="py-3.5 px-4 font-mono text-xs text-slate-500">
                    Election Commission of India / Bharat Nirvachan Ayog
                  </td>
                  <td className="py-3.5 px-4 font-mono text-xs text-center font-bold text-slate-900">
                    {voter.authority_header_detected ? "Detected" : "Not Found"}
                  </td>
                  <td className="py-3.5 px-4 text-right">
                    {renderBoolBadge(voter.authority_header_detected, "Verified", "Missing")}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 3. Indian Driving License (Sarathi) Verification Engine */}
      {isDl && dl && (
        <div>
          <div className="mb-5 pb-4 border-b border-slate-100 flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <Car className="w-4 h-4 text-amber-600" />
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-900 font-mono">
                  MoRTH Sarathi Driving License Verification Engine
                </h3>
              </div>
              <p className="text-xs text-slate-500 mt-1">
                Ministry of Road Transport and Highways 16-character standard and 36-state RTO registry
              </p>
            </div>
            <div className="px-3 py-1 bg-amber-50 border border-amber-200 rounded-xl text-xs font-mono font-bold text-amber-700">
              Sarathi MoRTH Active
            </div>
          </div>

          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-50/50">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-100/80 text-xs font-mono uppercase tracking-wider text-slate-600">
                  <th className="py-3 px-4 font-bold">Verification Target</th>
                  <th className="py-3 px-4 font-bold">Sarathi Specification</th>
                  <th className="py-3 px-4 font-bold text-center">Extracted Details</th>
                  <th className="py-3 px-4 font-bold text-right">Result</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200/70">
                <tr className="hover:bg-white transition-colors">
                  <td className="py-3.5 px-4 font-mono font-medium text-xs text-slate-700">
                    Sarathi Alphanumeric Format
                  </td>
                  <td className="py-3.5 px-4 font-mono text-xs text-slate-500">
                    SS-RR-YYYY-NNNNNNN
                  </td>
                  <td className="py-3.5 px-4 font-mono text-xs text-center font-bold text-slate-900">
                    {dl.state_code ? `State: ${dl.state_code}, RTO: ${dl.rto_code}` : "-"}
                  </td>
                  <td className="py-3.5 px-4 text-right">
                    {renderBoolBadge(dl.sarathi_format_valid)}
                  </td>
                </tr>

                <tr className="hover:bg-white transition-colors">
                  <td className="py-3.5 px-4 font-mono font-medium text-xs text-slate-700">
                    State & RTO Jurisdiction
                  </td>
                  <td className="py-3.5 px-4 font-mono text-xs text-slate-500">
                    36 Indian States & UTs Registry
                  </td>
                  <td className="py-3.5 px-4 font-mono text-xs text-center font-bold text-slate-900">
                    {dl.jurisdiction_verified ? "Recognized State Code" : "Unknown Jurisdiction"}
                  </td>
                  <td className="py-3.5 px-4 text-right">
                    {renderBoolBadge(dl.jurisdiction_verified, "Verified", "Invalid")}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 4. Visa & Consular Travel Authorization Verification Engine */}
      {isVisa && visa && (
        <div>
          <div className="mb-5 pb-4 border-b border-slate-100 flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <FileCheck className="w-4 h-4 text-indigo-600" />
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-900 font-mono">
                  Consular Visa & Travel Authorization Verification Engine
                </h3>
              </div>
              <p className="text-xs text-slate-500 mt-1">
                Border entry clearance, validity period window, and consular stamp integrity
              </p>
            </div>
            <div className="px-3 py-1 bg-indigo-50 border border-indigo-200 rounded-xl text-xs font-mono font-bold text-indigo-700">
              Consular Authorization Active
            </div>
          </div>

          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-50/50">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-100/80 text-xs font-mono uppercase tracking-wider text-slate-600">
                  <th className="py-3 px-4 font-bold">Verification Target</th>
                  <th className="py-3 px-4 font-bold">Standard Specification</th>
                  <th className="py-3 px-4 font-bold text-center">Extracted Record</th>
                  <th className="py-3 px-4 font-bold text-right">Result</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200/70">
                <tr className="hover:bg-white transition-colors">
                  <td className="py-3.5 px-4 font-mono font-medium text-xs text-slate-700">
                    Visa Control Number
                  </td>
                  <td className="py-3.5 px-4 font-mono text-xs text-slate-500">
                    Alphanumeric Control Code
                  </td>
                  <td className="py-3.5 px-4 font-mono text-xs text-center font-bold text-slate-900">
                    {visa.category ? `Category: ${visa.category}` : "Standard"}
                  </td>
                  <td className="py-3.5 px-4 text-right">
                    {renderBoolBadge(visa.visa_number_valid)}
                  </td>
                </tr>

                <tr className="hover:bg-white transition-colors">
                  <td className="py-3.5 px-4 font-mono font-medium text-xs text-slate-700">
                    Consular Stamp Forensics
                  </td>
                  <td className="py-3.5 px-4 font-mono text-xs text-slate-500">
                    Digital Border Stamp Splicing Check
                  </td>
                  <td className="py-3.5 px-4 font-mono text-xs text-center font-bold text-slate-900">
                    {visa.consular_stamp_verified ? "Tamper-Free" : "Suspicious Splicing"}
                  </td>
                  <td className="py-3.5 px-4 text-right">
                    {renderBoolBadge(visa.consular_stamp_verified, "Passed", "Tampered")}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 5. Passport MRZ 7-3-1 Checksum Table (Shown if Passport or MRZ signals present) */}
      {(!isAadhaar && !isVoterId && !isDl && !isVisa) && (
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

          {/* Note if MRZ unreadable or Line 1 passed */}
          {checksum.note && (
            <div className="mt-3 p-3 rounded-xl bg-slate-100 border border-slate-200 text-xs font-mono text-slate-600 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-slate-500 shrink-0" />
              <span>{checksum.note}</span>
            </div>
          )}

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
      )}

      {/* Date & Blacklist Status (Universal across all document types) */}
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
              {getExpirationBadge()}
            </div>

            <div className="flex justify-between items-center py-1">
              <span className="text-slate-500">DOB Plausible:</span>
              {getDobBadge()}
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
