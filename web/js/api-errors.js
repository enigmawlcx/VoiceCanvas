function isMissingApiKeyError(detail) {
  return typeof detail === "string" && detail.includes("尚未配置 API Key");
}

function handleApiError(detail) {
  if (isMissingApiKeyError(detail) && window.VoiceMaxNavigate?.toSettings) {
    window.VoiceMaxNavigate.toSettings(detail);
    return true;
  }
  return false;
}

window.VoiceMaxApiErrors = { isMissingApiKeyError, handleApiError };
