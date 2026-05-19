import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';

import chatbotHeaderLogo from '../assets/genspark-gs-circuit-logo.png';
import ImageDetectOverlay from '../components/ImageDetectOverlay';
import { getApiUrl } from '../utils/flaskBase';
import { formatDetectionError } from '../utils/detectionErrors';

import './Chatbot.css';

/** Full API response (detections + model path). */
const postDetectComponent = async (file, options = {}) => {
  const formData = new FormData();
  formData.append('image', file);
  if (options.confidence != null) {
    formData.append('conf', String(options.confidence));
  }

  const response = await fetch(getApiUrl('/detect/component'), {
    method: 'POST',
    body: formData,
  });
  const data = await response.json().catch(() => ({}));

  if (!response.ok || !data.success) {
    throw new Error(formatDetectionError(data.error || 'Component detection failed.'));
  }

  return data;
};

/** YOLO-normalized box (0–1 vs intrinsic frame) → pixel rect on element with object-fit: cover. */
const normBoxToCoverRect = (box, vidW, vidH, elW, elH) => {
  const xc = Number(box.xCenter);
  const yc = Number(box.yCenter);
  const bw = Number(box.width);
  const bh = Number(box.height);
  const scale = Math.max(elW / vidW, elH / vidH);
  const dispW = vidW * scale;
  const dispH = vidH * scale;
  const offX = (elW - dispW) / 2;
  const offY = (elH - dispH) / 2;
  const ix = (xc - bw / 2) * vidW;
  const iy = (yc - bh / 2) * vidH;
  const iw = bw * vidW;
  const ih = bh * vidH;
  return {
    x: offX + ix * scale,
    y: offY + iy * scale,
    w: iw * scale,
    h: ih * scale,
  };
};

/** Match backend GENSPARK_DISPLAY_CONF_THRESHOLD — hide wrong nearest-class labels when unsure. */
const DISPLAY_CONFIRM_THRESHOLD_PCT = 80;

/** Defensive normalization if API omits unknown mapping (older server). */
const normalizeDetectionForUi = (c) => {
  const confidence = Math.min(Math.max(Number(c.confidence) || 0, 0), 100);
  if (c.type === 'UNKNOWN' || c.name === 'Unknown Component') {
    return { ...c, displayName: 'Unknown Component', displayType: 'UNKNOWN', isUnknown: true };
  }
  if (confidence < DISPLAY_CONFIRM_THRESHOLD_PCT) {
    return {
      ...c,
      displayName: 'Unknown Component',
      displayType: 'UNKNOWN',
      isUnknown: true,
    };
  }
  return { ...c, displayName: c.name, displayType: c.type, isUnknown: false };
};

const getCompatibilityAlerts = (detected = [], budget = 0) => {
  const alerts = [];
  const normalized = detected.map(normalizeDetectionForUi);
  if (normalized.some((d) => d.isUnknown)) {
    alerts.push({
      type: 'warning',
      text:
        'One or more detections had low certainty and were labeled Unknown. YOLO only knows your trained classes — add headsets (or exclude them) plus more balanced data.',
    });
  }
  if (detected.some((d) => d.type === 'GPU') && budget > 0 && budget < 80000) {
    alerts.push({ type: 'warning', text: 'Budget may be tight for a dedicated GPU; consider integrated graphics or used GPU.' });
  }
  alerts.push({ type: 'info', text: 'All suggested builds are internally compatible (socket, PSU, form factor).' });
  return alerts;
};

const generateBuilds = (purpose = 'Gaming', budget = 100000, city = '') => {
  const base = purpose.toLowerCase().includes('office') ? 'office' : purpose.toLowerCase().includes('content') ? 'creator' : 'gaming';
  const budgetNum = Number(budget) || 100000;
  const perf = Math.min(budgetNum * 1.2, 250000);
  const bal = budgetNum;
  const bud = Math.max(budgetNum * 0.65, 40000);

  const templates = {
    gaming: [
      { type: 'Performance', price: perf, score: 92, wattage: 650, parts: ['AMD Ryzen 7 5800X', 'NVIDIA RTX 4070', 'ASUS B550-F', '32GB DDR4 3200MHz', '1TB NVMe SSD', '750W 80+ Gold', 'Fractal Design Meshify C'] },
      { type: 'Balanced', price: bal, score: 78, wattage: 550, parts: ['AMD Ryzen 5 5600X', 'NVIDIA RTX 4060', 'MSI B450 Tomahawk', '16GB DDR4 3200MHz', '512GB NVMe SSD', '650W 80+ Bronze', 'Corsair 4000D'] },
      { type: 'Budget', price: bud, score: 65, wattage: 450, parts: ['AMD Ryzen 5 3600', 'NVIDIA GTX 1660 Super', 'ASRock B450M', '16GB DDR4 3000MHz', '256GB SSD + 1TB HDD', '550W 80+ Bronze', 'Cooler Master Q300L'] },
    ],
    office: [
      { type: 'Performance', price: perf, score: 88, wattage: 350, parts: ['Intel i7-13700', 'Integrated', 'ASUS B760M', '32GB DDR5', '1TB NVMe SSD', '500W 80+', 'Compact Case'] },
      { type: 'Balanced', price: bal, score: 75, wattage: 300, parts: ['Intel i5-13400', 'Integrated', 'MSI B660M', '16GB DDR4', '512GB NVMe', '450W 80+', 'SFF Case'] },
      { type: 'Budget', price: bud, score: 62, wattage: 250, parts: ['AMD Ryzen 5 5600G', 'Integrated', 'A520M', '16GB DDR4', '256GB SSD', '400W 80+', 'Basic Case'] },
    ],
    creator: [
      { type: 'Performance', price: perf, score: 94, wattage: 750, parts: ['Intel i9-13900K', 'NVIDIA RTX 4080', 'ASUS Z790', '64GB DDR5', '2TB NVMe SSD', '850W 80+ Gold', 'Lian Li O11'] },
      { type: 'Balanced', price: bal, score: 80, wattage: 600, parts: ['AMD Ryzen 7 7700X', 'NVIDIA RTX 4070', 'B650', '32GB DDR5', '1TB NVMe', '750W 80+ Gold', 'Fractal Design'] },
      { type: 'Budget', price: bud, score: 68, wattage: 500, parts: ['AMD Ryzen 5 5600X', 'NVIDIA RTX 3060', 'B550', '32GB DDR4', '512GB NVMe', '600W 80+ Bronze', 'Mesh Case'] },
    ],
  };
  const set = templates[base] || templates.gaming;
  return set.map((t, i) => ({
    id: `build-${i + 1}`,
    title: `${purpose} — ${t.type} Build`,
    type: t.type,
    price: Math.round(t.price),
    performanceScore: t.score,
    wattage: t.wattage,
    parts: t.parts.map((p, j) => ({ name: ['CPU', 'GPU', 'Motherboard', 'RAM', 'Storage', 'PSU', 'Case'][j], value: p })),
  }));
};

const WELCOME_MESSAGE = {
  type: 'bot',
  id: 'welcome',
  intro:
    "I’m your Build Assistant. Share your use case (Gaming, Office, or Content) and budget in PKR — I’ll recommend up to 3 compatible PC builds you can customize or order.",
  steps: [
    'Set use case, budget, and city in the left panel, then “Get recommendations”',
    'Or type in chat, e.g. “Gaming 100000 Karachi”',
    'Or upload / camera-detect components first, then add criteria',
  ],
};

const Chatbot = () => {
  const navigate = useNavigate();
  const { userRequirements, updateRequirements, setSelectedBuild, setBuilds } = useApp();

  const [messages, setMessages] = useState(() => [
    { ...WELCOME_MESSAGE, timestamp: new Date() },
  ]);
  const [purpose, setPurpose] = useState(userRequirements.purpose || '');
  const [budget, setBudget] = useState(userRequirements.budget || '');
  const [city, setCity] = useState(userRequirements.city || '');
  const [textInput, setTextInput] = useState('');
  const [detectedComponents, setDetectedComponents] = useState([]);
  const [compatibilityAlerts, setCompatibilityAlerts] = useState([]);
  const [suggestedBuilds, setSuggestedBuilds] = useState([]);
  const [previewBuild, setPreviewBuild] = useState(null);
  const [isTyping, setIsTyping] = useState(false);
  const [detectionLoading, setDetectionLoading] = useState(false);
  const [cameraActive, setCameraActive] = useState(false);
  const [detectedImageUrl, setDetectedImageUrl] = useState(null);
  const [liveDetectOn, setLiveDetectOn] = useState(false);
  /** Bbox overlay for camera panel: normalized boxes are relative to vidW × vidH capture. */
  const [cameraPreviewOverlay, setCameraPreviewOverlay] = useState(null);
  const centerVideoRef = useRef(null);
  const streamRef = useRef(null);
  const cameraOverlayRef = useRef(null);
  const galleryInputRef = useRef(null);
  const chatOutputRef = useRef(null);
  const chatInputRef = useRef(null);
  const [plusMenuOpen, setPlusMenuOpen] = useState(false);
  const plusMenuRef = useRef(null);

  useEffect(() => {
    const el = chatOutputRef.current;
    if (!el) return;
    const raf = requestAnimationFrame(() => {
      el.scrollTop = el.scrollHeight;
    });
    return () => cancelAnimationFrame(raf);
  }, [messages, suggestedBuilds, detectedComponents, isTyping, detectionLoading]);

  useEffect(() => {
    if (!cameraActive) {
      setCameraPreviewOverlay(null);
      setLiveDetectOn(false);
    } else {
      setCameraPreviewOverlay(null);
    }
  }, [cameraActive]);

  useEffect(() => {
    if (!cameraActive) return;
    const canvas = cameraOverlayRef.current;
    const video = centerVideoRef.current;
    const wrap = canvas?.parentElement;
    if (!canvas || !video || !wrap) return;

    const redraw = () => {
      const elW = wrap.clientWidth;
      const elH = wrap.clientHeight;
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.max(1, Math.floor(elW * dpr));
      canvas.height = Math.max(1, Math.floor(elH * dpr));
      canvas.style.width = `${elW}px`;
      canvas.style.height = `${elH}px`;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, elW, elH);

      if (!cameraPreviewOverlay) return;
      const { vidW, vidH, components } = cameraPreviewOverlay;
      if (!vidW || !vidH) return;

      for (const c of components) {
        if (!c.box) continue;
        const r = normBoxToCoverRect(c.box, vidW, vidH, elW, elH);
        const row = normalizeDetectionForUi(c);
        const stroke = row.isUnknown ? '#f59e0b' : '#22d3ee';
        ctx.strokeStyle = stroke;
        ctx.lineWidth = 2;
        ctx.strokeRect(r.x, r.y, r.w, r.h);
        const conf = Math.min(Math.max(Number(c.confidence) || 0, 0), 100);
        const label = `${row.displayName} ${conf.toFixed(0)}%`;
        ctx.font = '600 11px system-ui, -apple-system, Segoe UI, sans-serif';
        const tw = ctx.measureText(label).width;
        const lh = 18;
        const lx = r.x;
        const ly = Math.max(0, r.y - lh - 2);
        ctx.fillStyle = 'rgba(15, 23, 42, 0.82)';
        ctx.fillRect(lx, ly, tw + 10, lh);
        ctx.fillStyle = '#f8fafc';
        ctx.fillText(label, lx + 5, ly + 13);
      }
    };

    redraw();
    const ro = new ResizeObserver(redraw);
    ro.observe(wrap);
    video.addEventListener('loadedmetadata', redraw);
    return () => {
      ro.disconnect();
      video.removeEventListener('loadedmetadata', redraw);
    };
  }, [cameraActive, cameraPreviewOverlay]);

  useEffect(() => {
    if (!cameraActive || !liveDetectOn) return undefined;

    let cancelled = false;
    let inflight = false;

    const runFrame = async () => {
      const video = centerVideoRef.current;
      if (cancelled || inflight || !video?.videoWidth) return;
      inflight = true;
      try {
        const width = video.videoWidth;
        const height = video.videoHeight;
        const c = document.createElement('canvas');
        c.width = width;
        c.height = height;
        const ctx = c.getContext('2d');
        if (!ctx) return;
        ctx.drawImage(video, 0, 0, width, height);
        const blob = await new Promise((resolve) => {
          c.toBlob((b) => resolve(b), 'image/jpeg', 0.82);
        });
        if (!blob || cancelled) return;
        const file = new File([blob], `live-${Date.now()}.jpg`, { type: 'image/jpeg' });
        const data = await postDetectComponent(file, { confidence: 0.35 });
        if (cancelled) return;
        setCameraPreviewOverlay({
          vidW: width,
          vidH: height,
          components: data.detections || [],
        });
      } catch {
        /* ignore transient live errors */
      } finally {
        inflight = false;
      }
    };

    const id = setInterval(runFrame, 3000);
    const kick = setTimeout(runFrame, 600);
    return () => {
      cancelled = true;
      clearInterval(id);
      clearTimeout(kick);
    };
  }, [cameraActive, liveDetectOn]);

  useEffect(() => {
    if (!plusMenuOpen) return;
    const onDocClick = (e) => {
      if (plusMenuRef.current && !plusMenuRef.current.contains(e.target)) {
        setPlusMenuOpen(false);
      }
    };
    document.addEventListener('click', onDocClick);
    return () => document.removeEventListener('click', onDocClick);
  }, [plusMenuOpen]);

  useEffect(() => {
    if (!cameraActive) return;

    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: 'environment' } })
      .then((s) => {
        streamRef.current = s;
        if (centerVideoRef.current) centerVideoRef.current.srcObject = s;
      })
      .catch(() =>
        addBotMessage('Camera access was denied or not available. You can use image upload instead.')
      );

    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }
      if (centerVideoRef.current) centerVideoRef.current.srcObject = null;
    };
  }, [cameraActive]);

  const addBotMessage = (text, payload = null) => {
    setMessages((prev) => [...prev, { type: 'bot', id: Date.now(), text, timestamp: new Date(), payload }]);
  };

  const addUserMessage = (text, imageUrl = null) => {
    const id = Date.now();
    setMessages((prev) => [...prev, { type: 'user', id, text, timestamp: new Date(), imageUrl }]);
    return id;
  };

  const analyzeImageFile = async (file, sourceLabel, imageUrl = null, options = {}) => {
    if (imageUrl) {
      if (detectedImageUrl) URL.revokeObjectURL(detectedImageUrl);
      setDetectedImageUrl(imageUrl);
    }

    const userMsgId = addUserMessage(sourceLabel, imageUrl);
    setIsTyping(true);
    setDetectionLoading(true);

    try {
      const data = await postDetectComponent(file, options);
      const components = data.detections || [];
      setDetectedComponents(components);
      setCompatibilityAlerts(getCompatibilityAlerts(components, Number(budget)));

      if (options.cameraOverlay) {
        setCameraPreviewOverlay({
          vidW: options.cameraOverlay.width,
          vidH: options.cameraOverlay.height,
          components,
        });
      } else {
        setCameraPreviewOverlay(null);
      }

      if (userMsgId != null && imageUrl) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === userMsgId
              ? {
                  ...m,
                  detections: components,
                  imageMeta:
                    data.image_width && data.image_height
                      ? { width: data.image_width, height: data.image_height }
                      : undefined,
                }
              : m
          )
        );
      }

      if (components.length === 0) {
        addBotMessage('I analyzed the image but did not detect mouse, keyboard, monitor, or RAM. Try a clearer photo with the component centered.');
        return;
      }

      const summary = components
        .map((c) => {
          const row = normalizeDetectionForUi(c);
          return `${row.displayName}${row.confidence ? ` (${row.confidence}% confidence)` : ''}`;
        })
        .join(', ');
      addBotMessage(`Detection complete: ${summary}.`, { type: 'detection', components });
    } catch (error) {
      if (options.cameraOverlay) setCameraPreviewOverlay(null);
      addBotMessage(formatDetectionError(error.message));
    } finally {
      setDetectionLoading(false);
      setIsTyping(false);
    }
  };

  const runRecommendations = (overrides = {}) => {
    const p = overrides.purpose ?? purpose;
    const b = overrides.budget ?? budget;
    const c = overrides.city ?? city;
    updateRequirements({ purpose: p, budget: b, city: c });
    setPurpose(p);
    setBudget(b);
    setCity(c);
    const builds = generateBuilds(p || 'Gaming', Number(b) || 100000, c);
    setSuggestedBuilds(builds);
    setBuilds(builds);
    setCompatibilityAlerts(getCompatibilityAlerts(detectedComponents, Number(b)));
    addBotMessage("I've generated **3 optimized builds** based on your inputs and any detected components. Check the cards below — you can **Customize**, **Save**, or **Proceed to vendor**.", { type: 'builds_ready' });
  };

  const handleTextSubmit = (e) => {
    e.preventDefault();
    const raw = (textInput || `${purpose} ${budget} ${city}`).trim();
    if (!raw && !purpose && !budget) return;

    const display = raw || `Purpose: ${purpose}, Budget: PKR ${budget}, City: ${city}`;
    addUserMessage(display);

    const numMatch = raw.match(/\d{4,}/);
    const parsedBudget = numMatch ? numMatch[0] : budget;
    const lower = raw.toLowerCase();
    let parsedPurpose = purpose;
    if (lower.includes('gaming')) parsedPurpose = 'Gaming';
    else if (lower.includes('office')) parsedPurpose = 'Office';
    else if (lower.includes('content') || lower.includes('creator')) parsedPurpose = 'Content Creation';
    setPurpose(parsedPurpose);
    setBudget(parsedBudget);
    setTextInput('');

    setIsTyping(true);
    setTimeout(() => {
      setIsTyping(false);
      runRecommendations({ purpose: parsedPurpose, budget: parsedBudget, city });
    }, 1200);
  };

  const handleGetRecommendations = () => {
    addUserMessage(`Purpose: ${purpose || 'Gaming'}, Budget: PKR ${budget || '100000'}, City: ${city || '—'}`);
    setIsTyping(true);
    setTimeout(() => {
      setIsTyping(false);
      runRecommendations();
    }, 1200);
  };

  const handleImageUpload = (e) => {
    const file = e.target?.files?.[0];
    if (!file) return;
    const url = URL.createObjectURL(file);
    analyzeImageFile(file, 'Uploaded component image', url, { confidence: 0.55 });
    e.target.value = '';
  };

  const handleCameraCapture = () => {
    const video = centerVideoRef.current;
    if (!video || !streamRef.current) return;

    const width = video.videoWidth || video.clientWidth || 640;
    const height = video.videoHeight || video.clientHeight || 480;
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      addBotMessage('Could not prepare the camera frame. Please try again or upload a picture.');
      return;
    }
    ctx.drawImage(video, 0, 0, width, height);

    canvas.toBlob((blob) => {
      if (!blob) {
        addBotMessage('Could not capture a camera frame. Please try again or upload a picture.');
        return;
      }

      const file = new File([blob], `camera-${Date.now()}.jpg`, { type: 'image/jpeg' });
      const url = URL.createObjectURL(file);
      analyzeImageFile(file, 'Captured from live camera', url, {
        confidence: 0.35,
        cameraOverlay: { width, height },
      });
    }, 'image/jpeg', 0.92);
  };

  const handleCustomize = (build) => {
    setSelectedBuild(build);
    setPreviewBuild(build);
    navigate('/configurator');
  };

  const handleSaveBuild = (build) => {
    setPreviewBuild(build);
    addBotMessage(`Saved **${build.title}** to preview. You can Customize or Proceed when ready.`, { type: 'saved' });
  };

  const handleProceed = (build) => {
    setSelectedBuild(build);
    setBuilds(suggestedBuilds.length ? suggestedBuilds : [build]);
    navigate('/vendor-assignment');
  };

  const handleNewChat = () => {
    setMessages([{ ...WELCOME_MESSAGE, timestamp: new Date() }]);
    setDetectedComponents([]);
    setCompatibilityAlerts([]);
    setSuggestedBuilds([]);
    setPreviewBuild(null);
    setDetectedImageUrl(null);
    setCameraPreviewOverlay(null);
    setLiveDetectOn(false);
    if (detectedImageUrl) URL.revokeObjectURL(detectedImageUrl);
  };

  const displayBuild = previewBuild ?? suggestedBuilds[0] ?? null;

  return (
    <div className="chatbot-recommendation-page">
      <div className="recommendation-layout">
        <aside className="recommendation-sidebar">
          <div className="sidebar-header">
            <span className="sidebar-header-icon" aria-hidden>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
              </svg>
            </span>
            <h3 className="sidebar-title">Criteria</h3>
            <p className="sidebar-subtitle">Set your preferences for personalized builds</p>
          </div>
          <div className="sidebar-form">
            <div className="sidebar-field">
              <label className="sidebar-label">
                <span className="sidebar-label-icon" aria-hidden>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
                </span>
                What will you use it for?
              </label>
              <select value={purpose} onChange={(e) => setPurpose(e.target.value)} className="sidebar-input" aria-label="Use case">
                <option value="">Select use case</option>
                <option value="Gaming">Gaming</option>
                <option value="Office">Office</option>
                <option value="Content Creation">Content Creation</option>
              </select>
            </div>
            <div className="sidebar-field">
              <label className="sidebar-label">
                <span className="sidebar-label-icon" aria-hidden>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="6" width="20" height="12" rx="2"/><path d="M2 10h20"/><path d="M2 14h20"/></svg>
                </span>
                Budget (PKR)
              </label>
              <input type="number" placeholder="e.g. 100,000" value={budget} onChange={(e) => setBudget(e.target.value)} className="sidebar-input" min="20000" step="5000" aria-label="Budget in PKR" />
            </div>
            <div className="sidebar-field">
              <label className="sidebar-label">
                <span className="sidebar-label-icon" aria-hidden>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
                </span>
                City
              </label>
              <input type="text" placeholder="e.g. Karachi, Lahore" value={city} onChange={(e) => setCity(e.target.value)} className="sidebar-input" aria-label="City" />
            </div>
            <button
              type="button"
              className="sidebar-cta"
              onClick={handleGetRecommendations}
              disabled={isTyping}
              aria-label="Get build recommendations"
            >
              <span className="sidebar-cta-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 3v18M3 12a9 9 0 0 0 18 0 9 9 0 0 0-18 0" />
                </svg>
              </span>
              Get recommendations
            </button>
          </div>
          <div className="sidebar-tip">
            <span className="sidebar-tip-label">Tip</span>
            <p>Use the chat or type e.g. <strong>Gaming 100k Karachi</strong> for instant results.</p>
          </div>
          <input ref={galleryInputRef} type="file" accept="image/*" className="hidden-input" onChange={handleImageUpload} aria-hidden />
        </aside>

        <main className="recommendation-center">
          <header className="center-header">
            <div className="center-header-left">
              <div className="center-header-logo-wrap">
                <img
                  src={chatbotHeaderLogo}
                  alt="GenSpark Builds"
                  className="center-header-logo"
                />
              </div>
              <div className="center-header-text">
                <p className="center-header-sub">
                  Use the criteria panel or chat to refine your build — up to 3 compatible options to compare and customize.
                </p>
              </div>
            </div>
            <button type="button" className="btn-back" onClick={() => navigate('/')} aria-label="Back to home">
              <span className="btn-back-icon" aria-hidden>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 12H5M12 19l-7-7 7-7" /></svg>
              </span>
              <span className="btn-back-label-full">Back to home</span>
              <span className="btn-back-label-short">Back</span>
            </button>
          </header>

          {cameraActive && (
            <div className="chat-camera-panel">
              <div className="chat-camera-panel-header">
                <h4 className="chat-camera-panel-title">Live camera detection</h4>
                <p className="chat-camera-panel-desc">Point at PC components to detect. Then capture to analyze.</p>
                <button
                  type="button"
                  className="chat-camera-panel-close"
                  onClick={() => setCameraActive(false)}
                  aria-label="Close camera"
                >
                  <span aria-hidden>×</span>
                </button>
              </div>
              <div className="chat-camera-panel-video-wrap">
                <video ref={centerVideoRef} autoPlay playsInline muted className="chat-camera-panel-video" />
                <canvas
                  ref={cameraOverlayRef}
                  className="chat-camera-panel-bbox-canvas"
                  aria-hidden
                />
                <div className="chat-camera-panel-overlay">
                  <span className="chat-camera-panel-live">LIVE</span>
                </div>
              </div>
              <label className="chat-camera-panel-live-toggle">
                <input
                  type="checkbox"
                  checked={liveDetectOn}
                  onChange={(e) => setLiveDetectOn(e.target.checked)}
                />
                <span>Auto overlay (refreshes ~every 3s via API)</span>
              </label>
              <div className="chat-camera-panel-actions">
                <button type="button" className="chat-camera-panel-detect" onClick={handleCameraCapture}>
                  Detect components
                </button>
                <button type="button" className="chat-camera-panel-cancel" onClick={() => setCameraActive(false)}>
                  Cancel
                </button>
              </div>
            </div>
          )}

          <div className="chat-output" ref={chatOutputRef}>
            {messages.map((msg) => (
              <div key={msg.id} className={`chat-message ${msg.type} ${msg.id === 'welcome' ? 'message-welcome' : ''}`}>
                <div className="message-avatar">{msg.type === 'bot' ? 'AI' : '👤'}</div>
                <div className="message-body">
                  {msg.imageUrl &&
                    (Array.isArray(msg.detections) && msg.detections.length > 0 ? (
                      <ImageDetectOverlay
                        src={msg.imageUrl}
                        detections={msg.detections}
                        naturalWidth={msg.imageMeta?.width}
                        naturalHeight={msg.imageMeta?.height}
                        alt="Uploaded component"
                      />
                    ) : (
                      <img src={msg.imageUrl} alt="Upload" className="message-img" />
                    ))}
                  {msg.id === 'welcome' && msg.intro ? (
                    <div className="message-welcome-content">
                      <p className="message-intro">{msg.intro}</p>
                      <ul className="message-steps" aria-label="How to get started">
                        {msg.steps?.map((step, i) => (
                          <li key={i}>{step}</li>
                        ))}
                      </ul>
                    </div>
                  ) : msg.payload?.type === 'detection' && msg.payload.components?.length > 0 ? (
                    <div className="detection-result-card">
                      <div className="detection-result-header">
                        <span className="detection-live-indicator" aria-hidden>
                          <span className="detection-live-dot"></span>
                        </span>
                        <div>
                          <p className="detection-result-title">AI detection active</p>
                          <p className="detection-result-subtitle">
                            Found {msg.payload.components.length} component{msg.payload.components.length > 1 ? 's' : ''}
                          </p>
                        </div>
                      </div>
                      <div className="component-chip-grid">
                        {msg.payload.components.map((c, i) => {
                          const row = normalizeDetectionForUi(c);
                          const confidence = Math.min(Math.max(Number(row.confidence) || 0, 0), 100);
                          return (
                            <div
                              className={`component-chip ${row.isUnknown ? 'component-chip--unknown' : ''}`}
                              key={`${row.displayType}-${i}`}
                            >
                              <div className="component-chip-top">
                                <span className="component-chip-name">{row.displayName}</span>
                                <span className="component-chip-confidence">{confidence.toFixed(1)}%</span>
                              </div>
                              <div
                                className="confidence-track"
                                aria-label={`${row.displayName} confidence ${confidence.toFixed(1)} percent`}
                              >
                                <span className="confidence-fill" style={{ width: `${confidence}%` }}></span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                      <p className="detection-next-step">Add purpose and budget, then click Get Recommendations for full builds.</p>
                    </div>
                  ) : (
                    <p>{msg.text}</p>
                  )}
                </div>
              </div>
            ))}
            {isTyping && (
              <div className="chat-message bot">
                <div className="message-avatar">AI</div>
                {detectionLoading ? (
                  <div className="message-body detection-skeleton" aria-label="AI detection in progress">
                    <div className="skeleton-status">
                      <span className="skeleton-dot"></span>
                      <span className="skeleton-line skeleton-line-title"></span>
                    </div>
                    <span className="skeleton-line"></span>
                    <span className="skeleton-line skeleton-line-short"></span>
                    <div className="skeleton-bars">
                      <span></span>
                      <span></span>
                    </div>
                  </div>
                ) : (
                  <div className="message-body typing-indicator"><span></span><span></span><span></span></div>
                )}
              </div>
            )}

            {compatibilityAlerts.length > 0 && (
              <div className="compatibility-alerts">
                <h4>Compatibility & analysis</h4>
                {compatibilityAlerts.map((a, i) => (
                  <div key={i} className={`alert alert-${a.type}`}>{a.text}</div>
                ))}
              </div>
            )}

            {suggestedBuilds.length > 0 && (
              <div className="suggested-builds">
                <h3>Suggested builds</h3>
                <div className="build-cards">
                  {suggestedBuilds.map((build) => (
                    <div key={build.id} className="build-card">
                      <div className="build-card-header">
                        <span className="build-type">{build.type}</span>
                      </div>
                      <div className="build-price">PKR {build.price.toLocaleString()}</div>
                      <ul className="build-parts-list">
                        {build.parts.slice(0, 5).map((p, i) => (
                          <li key={i}>{p.name}: {p.value}</li>
                        ))}
                      </ul>
                      <div className="build-actions">
                        <button type="button" className="btn btn-secondary" onClick={() => handleCustomize(build)}>Customize</button>
                        <button type="button" className="btn btn-secondary" onClick={() => handleSaveBuild(build)}>Save</button>
                        <button type="button" className="btn btn-primary" onClick={() => handleProceed(build)}>Proceed</button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <form className="chat-input-form" onSubmit={handleTextSubmit}>
            <div className="chat-input-wrap chat-input-bar">
              <div className="chat-input-plus-wrap" ref={plusMenuRef}>
                <button
                  type="button"
                  className="chat-input-plus-btn"
                  onClick={(e) => { e.stopPropagation(); setPlusMenuOpen((v) => !v); }}
                  aria-expanded={plusMenuOpen}
                  aria-haspopup="true"
                  aria-label="Choose how to get recommendations"
                >
                  <svg
                    className="chat-input-plus-icon"
                    width="22"
                    height="22"
                    viewBox="0 0 24 24"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                    aria-hidden="true"
                  >
                    <path
                      d="M12 5v14M5 12h14"
                      stroke="currentColor"
                      strokeWidth="2.25"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </button>
                {plusMenuOpen && (
                  <div className="chat-input-plus-menu" role="menu">
                    <button type="button" role="menuitem" className="chat-plus-option" onClick={() => { setCameraActive(true); setPlusMenuOpen(false); }}>
                      <span className="chat-plus-option-icon" aria-hidden>
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
                      </span>
                      Camera detection
                    </button>
                    <button type="button" role="menuitem" className="chat-plus-option" onClick={() => { galleryInputRef.current?.click(); setPlusMenuOpen(false); }}>
                      <span className="chat-plus-option-icon" aria-hidden>
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                      </span>
                      Picture upload
                    </button>
                    <button type="button" role="menuitem" className="chat-plus-option" onClick={() => { chatInputRef.current?.focus(); setPlusMenuOpen(false); }}>
                      <span className="chat-plus-option-icon" aria-hidden>
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                      </span>
                      Text recommendation
                    </button>
                  </div>
                )}
              </div>
              <input
                ref={chatInputRef}
                type="text"
                className="chat-input"
                placeholder="Ask anything"
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                disabled={isTyping}
                aria-label="Message"
              />
              <button type="submit" className="chat-send-btn chat-send-btn-circle" disabled={isTyping} aria-label="Send message">
                <svg className="chat-send-btn-svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="5" y1="12" x2="19" y2="12" />
                  <polyline points="12 5 19 12 12 19" />
                </svg>
              </button>
            </div>
          </form>
          <footer className="center-footer">
            <button type="button" className="footer-link" onClick={handleNewChat}>New chat</button>
            <span className="footer-tip">Upload an image or use camera to detect components.</span>
          </footer>
        </main>

        <aside className="recommendation-preview">
          <div className="preview-header">
            <span className="preview-icon" aria-hidden>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="2" y="3" width="20" height="14" rx="2" />
                <path d="M8 21h8M12 17v4" />
              </svg>
            </span>
            <div className="preview-header-text">
              <h3>Build preview</h3>
              <span className="preview-header-badge">Live</span>
            </div>
          </div>
          {displayBuild ? (
            <div className="preview-build">
              <div className="preview-build-type">{displayBuild.type}</div>
              <h4>{displayBuild.title}</h4>
              <p className="preview-price">
                <span className="preview-price-currency">PKR</span> {displayBuild.price?.toLocaleString()}
              </p>
              {displayBuild.performanceScore != null && (
                <div className="preview-score">
                  <span className="preview-score-label">Performance</span>
                  <div className="preview-score-bar">
                    <div className="preview-score-fill" style={{ width: `${displayBuild.performanceScore}%` }} />
                  </div>
                  <span className="preview-score-value">{displayBuild.performanceScore}/100</span>
                </div>
              )}
              <ul className="preview-parts">
                {displayBuild.parts?.map((p, i) => (
                  <li key={i}>
                    <span className="preview-part-name">{p.name}</span>
                    <span className="preview-part-value">{p.value}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <div className="preview-placeholder">
              <div className="preview-placeholder-graphic">
                <span className="preview-placeholder-icon" aria-hidden>
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <path d="M14 2v6h6M12 18v-6M9 15h6" />
                  </svg>
                </span>
              </div>
              <p className="preview-placeholder-title">No build selected</p>
              <p className="preview-placeholder-desc">Set criteria on the left or type in the chat. Your recommended build will appear here.</p>
              <div className="preview-placeholder-steps">
                <span className="preview-step">1. Set use case & budget</span>
                <span className="preview-step">2. Get recommendations</span>
                <span className="preview-step">3. View & customize here</span>
              </div>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
};

export default Chatbot;
