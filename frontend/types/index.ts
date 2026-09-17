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
  aadhaar_number?: string | null;
  voter_id?: string | null;
  dl_number?: string | null;
  id_number?: string | null;
  visa_number?: string | null;
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
  expiry_status?: string;
  dob_plausible?: boolean;
  dob_status?: string;
  issues?: string[];
}

export interface ValidationBlacklist {
  blacklisted?: boolean;
  reason?: string | null;
}

export interface ValidationNationalId {
  valid: boolean;
  id_type: string;
  issues: string[];
}

export interface ValidationVizConsistency {
  checked: boolean;
  consistent: boolean;
  mismatches: string[];
}

export interface ValidationRegistry {
  blacklisted: boolean;
  status: string;
  reason: string | null;
}

export interface AadhaarVerification {
  checked: boolean;
  valid_verhoeff?: boolean;
  verhoeff_valid?: boolean;
  uid_format_valid?: boolean;
  expected_checkdigit?: string | number | null;
  computed_checkdigit?: string | number | null;
  sovereign_header_detected?: boolean;
  qr_code_detected?: boolean;
  formatted_uid?: string;
  valid_format?: boolean;
  issues: string[];
  [key: string]: any;
}

export interface VoterIdVerification {
  checked: boolean;
  valid_format?: boolean;
  epic_format_valid?: boolean;
  authority_header_detected?: boolean;
  epic_number?: string;
  issues: string[];
  [key: string]: any;
}

export interface DLVerification {
  checked: boolean;
  valid_format?: boolean;
  sarathi_format_valid?: boolean;
  jurisdiction_verified?: boolean;
  rto_code?: string;
  state_code?: string;
  state_name?: string;
  issues: string[];
  [key: string]: any;
}

export interface VisaVerification {
  checked: boolean;
  valid_window?: boolean;
  visa_number_valid?: boolean;
  consular_stamp_verified?: boolean;
  category?: string;
  visa_type?: string;
  entries?: string;
  issues: string[];
  [key: string]: any;
}

export interface ValidationResult {
  checksum: ValidationChecksum;
  national_id?: ValidationNationalId;
  viz_consistency?: ValidationVizConsistency;
  aadhaar_verification?: AadhaarVerification;
  voter_id_verification?: VoterIdVerification;
  dl_verification?: DLVerification;
  visa_verification?: VisaVerification;
  dates: ValidationDates;
  blacklist: ValidationBlacklist;
  registry?: ValidationRegistry;
  overall_valid: boolean;
  issues: string[];
  preprocessing?: {
    processed_image_path?: string;
    correction_applied?: boolean;
    note?: string;
  };
}

export interface StampForensics {
  stamp_detected: boolean;
  stamp_count: number;
  stamp_boxes: number[][];
  suspicious_stamp_splicing: boolean;
  note?: string;
}

export interface AiDetectionResult {
  label?: string;
  confidence?: number;
  ai_generated_likelihood?: number;
  is_ai_generated?: boolean;
  error?: string;
}

export interface DetectedRegion {
  id: string;
  type: "header" | "mrz" | "mrz_zone" | "face" | "stamp" | "text" | string;
  label: string;
  box: [number, number, number, number];
  confidence: number;
  text?: string;
}

export interface EdgeForensicsResult {
  edge_anomaly_score: number;
  confidence: number;
  suspicious_regions: number[][];
  reason_codes: string[];
  image_quality?: {
    sharpness_var?: number;
    dynamic_range?: number;
    noise_floor?: number;
    quality_status?: string;
    confidence_multiplier?: number;
  };
  status?: string;
  heatmap_path?: string | null;
  heatmap_url?: string | null;
}

export interface TamperingResult {
  ela: {
    ela_score: number;
    ela_image_path?: string;
    ela_image_url?: string;
    tamper_boxes?: number[][];
  };
  metadata: {
    editing_software_detected: boolean;
    software_name?: string | null;
    metadata_stripped: boolean;
    raw_exif_summary?: Record<string, any>;
  };
  ai_detection?: AiDetectionResult;
  stamp_forensics?: StampForensics;
  edge_forensics?: EdgeForensicsResult;
  tampering_likelihood: number;
  risk_level: "low" | "medium" | "high";
  preprocessing?: {
    processed_image_path?: string;
    correction_applied?: boolean;
    note?: string;
  };
}

export interface PortraitFaceInfo {
  face_detected: boolean;
  face_image_path?: string | null;
  face_image_url?: string | null;
  bounding_box?: number[] | null;
  note?: string;
}

export interface BlockchainBlock {
  block_index: number;
  timestamp: string;
  doc_hash: string;
  file_id: string;
  document_type: string;
  risk_score: number;
  risk_level: string;
  biometric_status: string;
  decision: string;
  officer_id: string;
  previous_hash: string;
  block_hash: string;
  canonical_hash?: string;
  event_type?: string;
  anchor_status?: string;
  signature?: string | null;
}

export interface BlockchainAuditResult {
  chain_valid: boolean;
  total_blocks: number;
  tampered_blocks: Array<{ block_index: number; reason: string }>;
  latest_block_hash?: string;
  verified_at?: string;
  signatures_verified?: number;
  merkle_root?: string;
  designation?: string;
  hash_algorithm?: string;
  signature_algorithm?: string;
}

export interface LivenessInfo {
  liveness_score: number;
  laplacian_variance: number;
  mean_saturation: number;
  is_live: boolean;
  issues: string[];
}

export interface AliasMatch {
  record_id: number;
  previous_name: string;
  previous_document_number: string;
  document_type: string;
  nationality: string;
  crossing_point: string;
  crossing_timestamp: string;
  similarity: number;
  is_different_identity: boolean;
}

export interface AliasCheckResult {
  alias_detected: boolean;
  match_count: number;
  top_match?: AliasMatch | null;
  all_matches: AliasMatch[];
}

export interface BiometricVerificationResult {
  verified: boolean;
  status: "MATCH" | "BORDERLINE" | "MISMATCH" | "DUPLICATE_ALIAS_ALERT" | string;
  similarity: number;
  similarity_percentage: number;
  verdict: string;
  liveness: LivenessInfo;
  alias_check: AliasCheckResult;
}

export interface AnalyzeResponse {
  file_id: string;
  document_type: string;
  extracted_fields: ExtractedFields;
  viz_fields?: Record<string, any>;
  portrait_face?: PortraitFaceInfo;
  validation: ValidationResult;
  tampering: TamperingResult;
  overall_risk_score: number;
  overall_risk_level: "low" | "medium" | "high";
  summary_flags: string[];
  scanned_image_url?: string;
  detected_regions?: DetectedRegion[];
  blockchain_receipt?: BlockchainBlock;
}

