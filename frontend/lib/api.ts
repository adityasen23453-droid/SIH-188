import { AnalyzeResponse } from "@/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export async function uploadAndAnalyzeDocument(
  file: File,
  documentType: string
): Promise<AnalyzeResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("document_type", documentType);

  let uploadRes: Response;
  try {
    uploadRes = await fetch(`${API_BASE_URL}/api/upload`, {
      method: "POST",
      body: formData,
    });
  } catch (err: any) {
    throw new Error(
      `Cannot connect to backend server at ${API_BASE_URL}. Please ensure the FastAPI backend is running (python -m uvicorn main:app --reload --port 8000).`
    );
  }

  if (!uploadRes.ok) {
    const errorData = await uploadRes.json().catch(() => ({}));
    throw new Error(errorData.error || `Upload failed with status ${uploadRes.status}`);
  }

  const uploadData = await uploadRes.json();
  const fileId = uploadData.file_id;
  if (!fileId) {
    throw new Error("Invalid response from server: missing file_id");
  }

  let analyzeRes: Response;
  try {
    analyzeRes = await fetch(`${API_BASE_URL}/api/analyze/${fileId}`, {
      method: "POST",
    });
  } catch (err: any) {
    throw new Error(
      `Cannot connect to backend server at ${API_BASE_URL}. Please ensure the FastAPI backend is running.`
    );
  }

  if (!analyzeRes.ok) {
    const errorData = await analyzeRes.json().catch(() => ({}));
    throw new Error(errorData.error || `Analysis failed with status ${analyzeRes.status}`);
  }

  const analyzeData: AnalyzeResponse = await analyzeRes.json();
  return analyzeData;
}

export function getFullImageUrl(relativePath?: string): string {
  if (!relativePath) return "";
  if (relativePath.startsWith("http://") || relativePath.startsWith("https://")) {
    return relativePath;
  }
  return `${API_BASE_URL}${relativePath.startsWith("/") ? "" : "/"}${relativePath}`;
}
