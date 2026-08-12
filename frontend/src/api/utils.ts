export function formatApiError(errorData: any, defaultMessage: string = "Request failed"): string {
  if (!errorData || !errorData.detail) {
    return defaultMessage;
  }

  const detail = errorData.detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((err: any) => {
        const field = err.loc ? err.loc.slice(1).join(".") : "";
        const fieldPrefix = field ? `${field}: ` : "";
        return `${fieldPrefix}${err.msg}`;
      })
      .join("; ");
  }

  if (typeof detail === "object" && detail !== null) {
    return detail.message || detail.error || JSON.stringify(detail);
  }

  return defaultMessage;
}
