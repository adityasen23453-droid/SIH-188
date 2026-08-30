export interface ExtractedFields {
  name?: string | null;
  name_confidence?: "high" | "low";
  passport_number?: string | null;
  passport_number_confidence?: "high" | "low";
  nationality?: string | null;
  nationality_confidence?: "high" | "low";
  date_of_birth?: string | null;
  date_of_expiry?: string | null;
  gender?: "M" | "F" | "<" | null;
  gender_note?: string | null;
  mrz_valid_score?: number;
  mrz_line2?: string | null;
  [key: string]: any;
}

export interface ChecksumFieldResult {
  value?: string | null;
  expected_digit?: string | null;
  computed_digit?: string | null;
  valid?: boolean | null;
  field_slice?: string;
  check_digit_pos?: number;
  note?: string;
}

export interface ValidationChecksum {
  passport_number_check?: ChecksumFieldResult;
  date_of_birth_check?: ChecksumFieldResult;
  date_of_expiry_check?: ChecksumFieldResult;
  composite_check?: ChecksumFieldResult;
  overall_checksum_valid?: boolean | null;
  failed_fields?: string[];
  ocr_corrections_applied?: string[];
  note?: string;
}

export interface ValidationDates {
  expiry_valid?: boolean;
  dob_plausible?: boolean;
  issues?: string[];
}

export interface ValidationBlacklist {
  blacklisted?: boolean;
  reason?: string | null;
}

export interface ValidationResult {
  checksum: ValidationChecksum;
  dates: ValidationDates;
  blacklist: ValidationBlacklist;
  overall_valid: boolean;
  issues: string[];
  preprocessing?: {
    processed_image_path?: string;
    correction_applied?: boolean;
    note?: string;
  };
}

export interface TamperingResult {
  ela: {
    ela_score: number;
    ela_image_path?: string;
    ela_image_url?: string;
  };
  metadata: {
    editing_software_detected: boolean;
    software_name?: string | null;
    metadata_stripped: boolean;
    raw_exif_summary?: Record<string, any>;
  };
  ai_detection?: {
    label: string;
    confidence: number;
    ai_generated_likelihood: number;
  };
  tampering_likelihood: number;
  risk_level: "low" | "medium" | "high";
  preprocessing?: {
    processed_image_path?: string;
    correction_applied?: boolean;
    note?: string;
  };
}

export interface AnalyzeResponse {
  file_id: string;
  document_type: string;
  extracted_fields: ExtractedFields;
  validation: ValidationResult;
  tampering: TamperingResult;
  overall_risk_score: number;
  overall_risk_level: "low" | "medium" | "high";
  summary_flags: string[];
}
