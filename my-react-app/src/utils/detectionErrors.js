/**
 * Map raw API / network detection errors to user-friendly chat copy.
 * Never expose server paths (e.g. /root/yolov5/.../best.pt) in the UI.
 */
export function formatDetectionError(raw) {
  const msg = String(raw || '').trim();
  if (!msg) {
    return 'We could not analyze this image right now. Please try again in a moment.';
  }

  const lower = msg.toLowerCase();

  if (lower.includes('model not found') || lower.includes('best.pt') || lower.includes('yolov')) {
    return (
      '**Component scan is temporarily offline.** Our AI detection model is not available on the server yet. ' +
      'You can still use **Get recommendations** with your budget and purpose, or browse parts on the **Components** page.'
    );
  }

  if (lower.includes('yolo command not found') || lower.includes('ultralytics')) {
    return (
      '**Detection service is being configured.** Please try again later, or continue by filling in your use case and budget on the left.'
    );
  }

  if (lower.includes('unsupported image')) {
    return 'Please upload a **JPG**, **PNG**, or **WebP** photo with the component clearly visible and well lit.';
  }

  if (lower.includes('getapiurl is not defined') || lower.includes('is not defined')) {
    return 'Detection could not start (app configuration). Refresh the page after running START-GENSPARK-DEV.bat.';
  }

  if (
    lower.includes('not found') &&
    (lower.includes('recommend-build') || lower.includes('recommend build'))
  ) {
    return (
      '**AI recommendations are not available on this server.** Restart the app from the project folder: ' +
      'run **`vendor dashboard/run.py`** (port 5000) or **`START-GENSPARK-DEV.bat`**, then refresh **http://localhost:5173/chatbot**.'
    );
  }

  if (
    lower.includes('timed out') ||
    lower.includes('timeout') ||
    lower.includes('econnaborted')
  ) {
    return msg;
  }

  if (
    lower.includes('failed to fetch') ||
    lower.includes('network') ||
    lower.includes('load failed') ||
    lower.includes('could not reach') ||
    lower.includes('connection refused') ||
    lower.includes('err_connection')
  ) {
    const isDev =
      typeof import.meta !== 'undefined' && import.meta.env?.DEV;
    if (isDev) {
      return (
        '**Local API not reachable.** Double-click **`START-GENSPARK-DEV.bat`** in the project root ' +
        '(starts `backend/app.py` on port 5000), then refresh this page and upload again. ' +
        'Use **http://localhost:5173/chatbot** if you opened the site via a LAN IP.'
      );
    }
    return 'Could not reach the GenSpark server. Check your internet connection and try again.';
  }

  if (lower.includes('image file is required')) {
    return 'Please choose an image or capture a photo before running detection.';
  }

  // Strip accidental path leaks from older API responses
  if (/[\\/]root[\\/]|[\\/]runs[\\/]|\.pt\b|genspark_api/i.test(msg)) {
    return (
      'Component detection is unavailable on this server. Use **Get recommendations** or open **Components** to pick parts manually.'
    );
  }

  if (msg.length > 180) {
    return 'Detection could not be completed. Try a clearer photo, or use **Get recommendations** without uploading an image.';
  }

  return msg;
}
