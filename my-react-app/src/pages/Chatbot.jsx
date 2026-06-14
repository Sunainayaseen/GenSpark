import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { useCart } from '../context/CartContext';
import { addBuildPartsBulk, addBuildPartsToCart } from '../utils/buildPartMatcher';
import { resolveBuildParts, addResolvedBuildToCart } from '../utils/buildResolver';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { User } from 'lucide-react';

import chatbotHeaderLogo from '../assets/genspark-gs-circuit-logo.png';
import ImageDetectOverlay from '../components/ImageDetectOverlay';
import BuildRecommendationCard from '../components/BuildRecommendationCard';
import BuildCustomizer from '../components/BuildCustomizer';
import {
  postRecommendBuild,
  postCreateBuild,
  postDetectComponent,
  extractGeminiBuildSlots,
} from '../api/builderApi';
import { formatDetectionError } from '../utils/detectionErrors';
import {
  parseChatIntent,
  parseBudgetFromChat,
  parsePurposeFromChat,
  parseRefinement,
  hasBuildIntentFromChat,
  isPureGreetingMessage,
  formatBudgetPkr,
  getAiSourceBadge,
  formatGeminiFallbackNotice,
  buildGuideGreetingResponse,
  buildMarkdownFromFallbackBuild,
  GUIDE_GREETING_MARKDOWN,
  AI_SOURCE,
} from '../utils/chatIntentParse';

import './Chatbot.css';

/** Use-case options for the criteria-panel dropdown. */
const PURPOSE_OPTIONS = [
  { value: 'Gaming', label: 'Gaming', icon: '🎮' },
  { value: 'Office', label: 'Office', icon: '💼' },
  { value: 'Content Creation', label: 'Content Creation', icon: '🎬' },
];

/** Minimum “thinking” pause before bot replies (feels natural, not instant). */
const CHAT_REPLY_MIN_MS = 2000;
const CHAT_REPLY_MAX_MS = 3000;

function chatReplyDelayMs() {
  return (
    CHAT_REPLY_MIN_MS +
    Math.floor(Math.random() * (CHAT_REPLY_MAX_MS - CHAT_REPLY_MIN_MS + 1))
  );
}

async function waitForChatReply(startedAt) {
  const wait = chatReplyDelayMs() - (Date.now() - startedAt);
  if (wait > 0) {
    await new Promise((resolve) => setTimeout(resolve, wait));
  }
}

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

/** Match backend GENSPARK_DISPLAY_CONF_THRESHOLD (45). Studio/upload photos often
 *  score 45–70% on real parts, so a higher gate hid genuine detections. */
const DISPLAY_CONFIRM_THRESHOLD_PCT = 45;
const LIVE_DETECT_CONF = 0.25;
const UPLOAD_DETECT_CONF = 0.4;

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

/** Sharper JPEG + sane max size for YOLO on live webcam frames. */
const captureFrameFromVideo = (video, maxDim = 1280, jpegQuality = 0.92) => {
  let width = video.videoWidth;
  let height = video.videoHeight;
  if (!width || !height) return null;
  if (width > maxDim || height > maxDim) {
    const scale = maxDim / Math.max(width, height);
    width = Math.round(width * scale);
    height = Math.round(height * scale);
  }
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  if (!ctx) return null;
  ctx.drawImage(video, 0, 0, width, height);
  return { canvas, width, height };
};

const generateBuilds = (purpose = 'Gaming', budget = 100000, city = '') => {
  const base = purpose.toLowerCase().includes('office') ? 'office' : purpose.toLowerCase().includes('content') ? 'creator' : 'gaming';
  const budgetNum = Number(budget) || 100000;
  const perf = Math.min(budgetNum * 1.2, 250000);
  const bal = budgetNum;
  const bud = Math.max(budgetNum * 0.65, 40000);

  // Part names below are aligned to the seeded ERP catalog (seed_prebuilt_parts.py)
  // so buildResolver matches each slot 7/7 (office GPU = Integrated, which resolves
  // to "skipped"). Each value uniquely substring-matches one catalog component.
  const templates = {
    gaming: [
      { type: 'Performance', price: perf, score: 92, wattage: 650, parts: ['AMD Ryzen 7 7700X', 'NVIDIA GeForce RTX 4070', 'MSI PRO B650-P WiFi', 'Corsair Vengeance 32GB DDR5 6000MHz', 'Samsung 980 1TB NVMe SSD', 'Corsair RM750e 750W 80+ Gold', 'NZXT H5 Flow'] },
      { type: 'Balanced', price: bal, score: 78, wattage: 550, parts: ['AMD Ryzen 5 7600', 'NVIDIA GeForce RTX 4060 Ti 16GB', 'MSI PRO B650M-A WiFi', 'Corsair Vengeance 16GB DDR5 5600MHz', 'Kingston NV2 512GB NVMe SSD', 'Cooler Master MWE 650W 80+ Gold', 'Montech AIR 903'] },
      { type: 'Budget', price: bud, score: 65, wattage: 450, parts: ['AMD Ryzen 5 5600G', 'NVIDIA GeForce RTX 4060 8GB', 'Gigabyte A520M DS3H', 'Corsair Vengeance LPX 16GB DDR4 3200MHz', 'Kingston NV2 512GB NVMe SSD', 'Cooler Master MWE 550W 80+ Bronze', 'Cooler Master MasterBox Q300L'] },
    ],
    office: [
      { type: 'Performance', price: perf, score: 88, wattage: 350, parts: ['AMD Ryzen 5 5600G', 'Integrated', 'Gigabyte A520M DS3H', 'Corsair Vengeance LPX 16GB DDR4 3200MHz', 'Samsung 980 1TB NVMe SSD', 'Cooler Master MWE 450W 80+ Bronze', 'Cooler Master MasterBox Q300L'] },
      { type: 'Balanced', price: bal, score: 75, wattage: 300, parts: ['AMD Ryzen 5 5600G', 'Integrated', 'Gigabyte A520M DS3H', 'Corsair Vengeance LPX 16GB DDR4 3200MHz', 'Kingston NV2 512GB NVMe SSD', 'Cooler Master MWE 450W 80+ Bronze', 'Montech X3 Mesh'] },
      { type: 'Budget', price: bud, score: 62, wattage: 250, parts: ['AMD Ryzen 5 5600G', 'Integrated', 'Gigabyte A520M DS3H', 'Corsair Vengeance LPX 16GB DDR4 3200MHz', 'Kingston NV2 512GB NVMe SSD', 'Cooler Master MWE 450W 80+ Bronze', 'Cooler Master MasterBox Q300L'] },
    ],
    creator: [
      { type: 'Performance', price: perf, score: 94, wattage: 750, parts: ['AMD Ryzen 9 7950X3D', 'NVIDIA GeForce RTX 4090', 'ASUS ROG Strix X670E-E Gaming', 'G.Skill Trident Z5 64GB DDR5', 'WD Black SN770 2TB NVMe SSD', 'Corsair RM1000e 1000W 80+ Gold', 'Lian Li PC-O11'] },
      { type: 'Balanced', price: bal, score: 80, wattage: 600, parts: ['AMD Ryzen 7 7700X', 'NVIDIA GeForce RTX 4070', 'MSI PRO B650-P WiFi', 'Corsair Vengeance 32GB DDR5 6000MHz', 'Samsung 980 1TB NVMe SSD', 'Corsair RM850e 850W 80+ Gold', 'be quiet! Pure Base 500DX'] },
      { type: 'Budget', price: bud, score: 68, wattage: 500, parts: ['AMD Ryzen 5 7600', 'NVIDIA GeForce RTX 4060 Ti 16GB', 'MSI PRO B650M-A WiFi', 'Corsair Vengeance 16GB DDR5 5600MHz', 'Kingston NV2 512GB NVMe SSD', 'Cooler Master MWE 650W 80+ Gold', 'Montech X3 Mesh'] },
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

const QUICK_CHAT_EXAMPLE = 'Gaming pc build 1.20 lakh Karachi';

function ChatOnboarding({ onPanelRecommend, onChatExample, onUpload, onCamera }) {
  return (
    <div className="chat-onboarding" role="region" aria-label="How to get started">
      <div className="chat-onboarding-hero">
        <img
          src={chatbotHeaderLogo}
          alt=""
          className="chat-onboarding-logo"
          aria-hidden="true"
        />
        <p className="chat-onboarding-eyebrow">GenSpark Build Assistant</p>
        <h2 className="chat-onboarding-title">Start your custom PC build</h2>
        <p className="chat-onboarding-lead">
          Share your use case and budget — get compatible parts, AI recommendations, and up to three
          curated builds you can compare and order.
        </p>
      </div>

      <div className="chat-onboarding-grid">
        <button type="button" className="chat-onboarding-card" onClick={onPanelRecommend}>
          <span className="chat-onboarding-card-icon" aria-hidden="true">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 3v18M3 12a9 9 0 0 0 18 0 9 9 0 0 0-18 0" />
            </svg>
          </span>
          <span className="chat-onboarding-card-title">Criteria panel</span>
          <span className="chat-onboarding-card-desc">
            Set use case, budget & city on the left, then run Get recommendations.
          </span>
        </button>

        <button type="button" className="chat-onboarding-card" onClick={onChatExample}>
          <span className="chat-onboarding-card-icon" aria-hidden="true">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          </span>
          <span className="chat-onboarding-card-title">Chat in natural language</span>
          <span className="chat-onboarding-card-desc">
            Try: <em>Gaming 1.20 lakh Karachi</em> — we parse budget and purpose automatically.
          </span>
        </button>

        <button type="button" className="chat-onboarding-card chat-onboarding-card--wide" onClick={onUpload}>
          <span className="chat-onboarding-card-icon" aria-hidden="true">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
          </span>
          <span className="chat-onboarding-card-title">Upload a component photo</span>
          <span className="chat-onboarding-card-desc">
            Detect CPU, GPU, RAM, motherboard, PSU, cooler or storage — then add budget for a tailored quote.
          </span>
        </button>

        <button type="button" className="chat-onboarding-card chat-onboarding-card--wide" onClick={onCamera}>
          <span className="chat-onboarding-card-icon" aria-hidden="true">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
              <circle cx="12" cy="13" r="4" />
            </svg>
          </span>
          <span className="chat-onboarding-card-title">Live camera detection</span>
          <span className="chat-onboarding-card-desc">
            Point your camera at hardware; bounding boxes show what we recognize in real time.
          </span>
        </button>
      </div>

      <p className="chat-onboarding-hint">
        Type a message below or use <strong>+</strong> for upload and camera options.
      </p>
    </div>
  );
}

const SLOT_LABELS = {
  cpu: 'CPU',
  gpu: 'GPU',
  motherboard: 'Motherboard',
  ram: 'RAM',
  storage: 'Storage',
  psu: 'PSU',
  case: 'Case',
};

// One-tap starter prompts shown above the chat input (guides first-time users).
const QUICK_PROMPTS = [
  { label: 'Gaming PC under 120K', text: 'Gaming PC under 120000' },
  { label: 'Editing PC under 150K', text: 'Editing PC under 150000' },
  { label: 'Office PC Build', text: 'Office PC build 60000' },
  { label: 'Detect components from image', image: true },
];

const Chatbot = () => {
  const navigate = useNavigate();
  const { userRequirements, updateRequirements, setSelectedBuild, setBuilds } = useApp();
  const { addToCart, applyCartFromServer } = useCart();

  const [messages, setMessages] = useState([]);
  const showOnboarding = !messages.some((m) => m.type === 'user');
  const [purpose, setPurpose] = useState(userRequirements.purpose || '');
  const [budget, setBudget] = useState(userRequirements.budget || '');
  const [city, setCity] = useState(userRequirements.city || '');
  const [textInput, setTextInput] = useState('');
  const [detectedComponents, setDetectedComponents] = useState([]);
  const [suggestedBuilds, setSuggestedBuilds] = useState([]);
  /** Template cards (Performance / Balanced / Budget) — only after explicit recommend request */
  const [showSuggestedBuilds, setShowSuggestedBuilds] = useState(false);
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
  const [purposeOpen, setPurposeOpen] = useState(false);
  const purposeRef = useRef(null);
  /** OpenAI Markdown from /api/recommend-build */
  const [aiRecommendationMarkdown, setAiRecommendationMarkdown] = useState(null);
  // Deterministic rule-based compatibility verdict from the backend (recommend-build).
  const [aiCompatibility, setAiCompatibility] = useState(null);
  const [geminiPartsPayload, setGeminiPartsPayload] = useState(null);
  // Real DB component rows from the DB-driven recommend-build (build_components).
  // When present, "Add to cart" uses these IDs directly — no name re-resolution.
  const [buildComponents, setBuildComponents] = useState(null);
  const [erpSaving, setErpSaving] = useState(false);
  const [erpBanner, setErpBanner] = useState(null);

  /** Keep left-panel criteria synced with global app requirements. */
  useEffect(() => {
    updateRequirements({ purpose, budget, city });
  }, [purpose, budget, city, updateRequirements]);

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
        const frame = captureFrameFromVideo(video);
        if (!frame || cancelled) return;
        const { canvas, width, height } = frame;
        const blob = await new Promise((resolve) => {
          canvas.toBlob((b) => resolve(b), 'image/jpeg', 0.92);
        });
        if (!blob || cancelled) return;
        const file = new File([blob], `live-${Date.now()}.jpg`, { type: 'image/jpeg' });
        const data = await postDetectComponent(file, { confidence: LIVE_DETECT_CONF });
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

    const id = setInterval(runFrame, 2000);
    const kick = setTimeout(runFrame, 600);
    return () => {
      cancelled = true;
      clearInterval(id);
      clearTimeout(kick);
    };
  }, [cameraActive, liveDetectOn]);

  useEffect(() => {
    if (!plusMenuOpen) return undefined;
    const onDocClick = (e) => {
      if (plusMenuRef.current && !plusMenuRef.current.contains(e.target)) {
        setPlusMenuOpen(false);
      }
    };
    // Defer so the same click that opened the menu does not immediately close it
    const timer = window.setTimeout(() => {
      document.addEventListener('click', onDocClick, true);
    }, 0);
    return () => {
      window.clearTimeout(timer);
      document.removeEventListener('click', onDocClick, true);
    };
  }, [plusMenuOpen]);

  useEffect(() => {
    if (!purposeOpen) return undefined;
    const onDocClick = (e) => {
      if (purposeRef.current && !purposeRef.current.contains(e.target)) {
        setPurposeOpen(false);
      }
    };
    const onKey = (e) => {
      if (e.key === 'Escape') setPurposeOpen(false);
    };
    const timer = window.setTimeout(() => {
      document.addEventListener('click', onDocClick, true);
      document.addEventListener('keydown', onKey);
    }, 0);
    return () => {
      window.clearTimeout(timer);
      document.removeEventListener('click', onDocClick, true);
      document.removeEventListener('keydown', onKey);
    };
  }, [purposeOpen]);

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
    setShowSuggestedBuilds(false);
    setSuggestedBuilds([]);
    setPreviewBuild(null);
    setIsTyping(true);
    setDetectionLoading(true);
    const replyStartedAt = Date.now();

    try {
      const data = await postDetectComponent(file, options);
      const components = data.detections || [];
      setDetectedComponents(components);
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
        await waitForChatReply(replyStartedAt);
        addBotMessage(
          'I analyzed the image but did not detect a recognizable PC part (CPU, GPU, RAM, motherboard, PSU, cooler or storage). Upload the component photo directly (not a chat screenshot), with the part centered on a plain background and good lighting.'
        );
        return;
      }

      const summary = components
        .map((c) => {
          const row = normalizeDetectionForUi(c);
          return `${row.displayName}${row.confidence ? ` (${row.confidence}% confidence)` : ''}`;
        })
        .join(', ');
      await waitForChatReply(replyStartedAt);
      addBotMessage(`Detection complete: ${summary}.`, { type: 'detection', components });
    } catch (error) {
      if (options.cameraOverlay) setCameraPreviewOverlay(null);
      await waitForChatReply(replyStartedAt);
      addBotMessage(formatDetectionError(error.message));
    } finally {
      setDetectionLoading(false);
      setIsTyping(false);
    }
  };

  const getCurrentDetectedPart = () => {
    const labels = detectedComponents
      .map(normalizeDetectionForUi)
      .filter((c) => !c.isUnknown)
      .map((c) => c.displayName || c.class_name || c.rawGuess)
      .filter(Boolean);
    return labels.length ? labels.join(', ') : 'None';
  };

  const fetchAiRecommendations = async (overrides = {}) => {
    const replyStartedAt = Date.now();
    const msg = (overrides.message || '').trim();
    const pureGreeting = Boolean(msg && isPureGreetingMessage(msg));
    const parsedBudgetFromMsg = msg ? parseBudgetFromChat(msg) : '';
    const parsedPurposeFromMsg = msg ? parsePurposeFromChat(msg) : '';

    const buildRequested = pureGreeting
      ? false
      : Boolean(
          overrides.build_requested || (msg ? hasBuildIntentFromChat(msg) : false)
        );

    // Instant greeting — no network wait (backend is ~10ms but UI felt slow)
    if (pureGreeting && !buildRequested) {
      const guide = buildGuideGreetingResponse();
      const badge = getAiSourceBadge(AI_SOURCE.GUIDE);
      await waitForChatReply(replyStartedAt);
      addBotMessage('', {
        type: 'ai_recommendation',
        markdown: guide.recommendation_markdown,
        source: AI_SOURCE.GUIDE,
        sourceLabel: `${badge.icon} ${badge.label}`,
        geminiActive: false,
        isFallback: false,
      });
      setSuggestedBuilds([]);
      setShowSuggestedBuilds(false);
      return;
    }

    const p = pureGreeting
      ? parsedPurposeFromMsg || ''
      : overrides.purpose ||
        parsedPurposeFromMsg ||
        (buildRequested ? purpose || 'Gaming' : '');
    const b = pureGreeting
      ? parsedBudgetFromMsg || ''
      : overrides.budget || parsedBudgetFromMsg || (buildRequested ? budget : '');
    const c = overrides.city ?? city;

    if (p && !pureGreeting) setPurpose(p);
    if (b && !pureGreeting) setBudget(b);
    setCity(c);
    updateRequirements({
      purpose: p || purpose,
      budget: b || budget,
      city: c,
    });

    try {
      const payload = {
        detected_part: getCurrentDetectedPart(),
        build_requested: buildRequested,
        message: msg || undefined,
      };
      const budgetLabel = b ? formatBudgetPkr(b) : '';
      if (budgetLabel) payload.budget = budgetLabel;
      if (p) payload.purpose = p;

      let data;
      try {
        data = await postRecommendBuild(payload);
      } catch (apiError) {
        if (pureGreeting && !buildRequested) {
          data = buildGuideGreetingResponse();
        } else {
          throw apiError;
        }
      }

      if (data.conversational && !data.recommendation_markdown) {
        data.recommendation_markdown = GUIDE_GREETING_MARKDOWN;
      }

      let markdown = String(data.recommendation_markdown || '').trim();
      if (!markdown && !data.conversational) {
        markdown = buildMarkdownFromFallbackBuild(
          data.fallback_build,
          data.purpose || p,
          data.budget || budgetLabel
        );
      }
      if (!markdown && !data.conversational) {
        markdown =
          '## Summary\n\nCould not load the build table. Restart with **START-GENSPARK-DEV.bat**, hard-refresh (**Ctrl+F5**), then send your budget and purpose again.';
      }
      const { parts: parsedParts } = extractGeminiBuildSlots(markdown);
      const mergedParts =
        data.fallback_build && typeof data.fallback_build === 'object'
          ? { ...data.fallback_build, ...parsedParts }
          : parsedParts;
      if (data.conversational) {
        setAiRecommendationMarkdown(null);
        setGeminiPartsPayload(null);
        setBuildComponents(null);
        setAiCompatibility(null);
      } else {
        setAiRecommendationMarkdown(markdown);
        setAiCompatibility(data.compatibility || null);
        setGeminiPartsPayload(
          Object.keys(mergedParts).length ? mergedParts : null
        );
        setBuildComponents(
          Array.isArray(data.build_components) && data.build_components.length
            ? data.build_components
            : null
        );
      }

      const fallbackNotice = data.fallback
        ? formatGeminiFallbackNotice(data.fallback_reason)
        : null;
      const badge = getAiSourceBadge(data.source, {
        conversational: data.conversational,
        fallback: data.fallback,
        openaiConfigured: Boolean(data.openai_configured),
        fallbackReason: data.fallback_reason,
        intentBadge: data.intent_badge,
      });
      await waitForChatReply(replyStartedAt);
      addBotMessage('', {
        type: 'ai_recommendation',
        markdown,
        source: badge.source,
        geminiActive: badge.geminiActive,
        isFallback: Boolean(data.fallback),
        fallbackNotice,
        purpose: data.purpose || p,
        budget: data.budget || budgetLabel,
        // Real catalog rows → enable an inline "Add to cart" on this build card.
        buildComponents:
          Array.isArray(data.build_components) && data.build_components.length
            ? data.build_components
            : null,
        totalPrice: data.total_price || null,
        // Deterministic rule-based verdict (compatible/score/checks/failures).
        compatibility: data.compatibility || null,
      });

      const hasEngineTable = /##\s*Recommended Components/i.test(markdown);
      if ((buildRequested || !data.conversational) && !hasEngineTable) {
        const builds = generateBuilds(
          p || purpose || 'Gaming',
          Number(b || budget) || 100000,
          c
        );
        setSuggestedBuilds(builds);
        setBuilds(builds);
        setShowSuggestedBuilds(true);
      } else {
        setSuggestedBuilds([]);
        setShowSuggestedBuilds(false);
      }
    } catch (error) {
      setAiRecommendationMarkdown(null);
      setGeminiPartsPayload(null);
      setBuildComponents(null);
      setAiCompatibility(null);

      if (pureGreeting && !buildRequested) {
        const guide = buildGuideGreetingResponse();
        await waitForChatReply(replyStartedAt);
        addBotMessage('', {
          type: 'ai_recommendation',
          markdown: guide.recommendation_markdown,
          source: AI_SOURCE.GUIDE,
          sourceLabel: `${getAiSourceBadge(AI_SOURCE.GUIDE).icon} ${getAiSourceBadge(AI_SOURCE.GUIDE).label}`,
          geminiActive: false,
          isFallback: false,
        });
        setSuggestedBuilds([]);
        setShowSuggestedBuilds(false);
        return;
      }

      const isTimeout =
        /timed out|timeout|econnaborted/i.test(String(error?.message || ''));
      const isUnreachable =
        /not reachable|failed to fetch|connection refused|network error/i.test(
          String(error?.message || '')
        );

      if (buildRequested && (isTimeout || isUnreachable)) {
        setSuggestedBuilds([]);
        setShowSuggestedBuilds(false);
        await waitForChatReply(replyStartedAt);
        addBotMessage(formatDetectionError(error.message));
      } else if (buildRequested) {
        const builds = generateBuilds(
          p || purpose || 'Gaming',
          Number(b || budget) || 100000,
          c
        );
        setSuggestedBuilds(builds);
        setBuilds(builds);
        setShowSuggestedBuilds(true);
        await waitForChatReply(replyStartedAt);
        addBotMessage(
          `${formatDetectionError(error.message)} Showing template builds below.`,
          { type: 'builds_ready' }
        );
      } else {
        setSuggestedBuilds([]);
        setShowSuggestedBuilds(false);
        await waitForChatReply(replyStartedAt);
        addBotMessage(formatDetectionError(error.message));
      }
    }
  };

  const handleAddToCart = async (componentsArg) => {
    // Preferred path: the DB-driven recommend-build already resolved every slot to
    // a real catalog row, so add those component IDs straight to the cart — no
    // name re-resolution. Uses /add-to-cart (vendor auto-assigned by the backend).
    // componentsArg lets each chat build card add its OWN build (falls back to state).
    const comps = Array.isArray(componentsArg) ? componentsArg : buildComponents;
    if (Array.isArray(comps) && comps.length) {
      setErpSaving(true);
      let added = 0;
      try {
        const failedLabels = [];
        const seen = new Set();
        for (const comp of comps) {
          const id = comp?.component_id ?? comp?.id;
          if (!id || seen.has(id)) continue;
          seen.add(id);
          const ok = await addToCart({ id, item_type: 'component', vendor_id: null }, 1, { silent: true });
          if (ok) added += 1;
          else failedLabels.push(comp.label || comp.name || `#${id}`);
        }
        if (added > 0) {
          setErpBanner({
            type: 'success',
            message: failedLabels.length
              ? `Added ${added} part(s) to cart. Could not add: ${failedLabels.join(', ')}.`
              : `Added ${added} part(s) to cart. Open the cart to review your total.`,
          });
        } else {
          setErpBanner({
            type: 'error',
            message: 'Could not add these parts — they may be out of stock right now. Try another budget.',
          });
        }
      } catch (error) {
        setErpBanner({ type: 'error', message: formatDetectionError(error.message) });
      } finally {
        setErpSaving(false);
      }
      return added;
    }

    let partsMap = null;

    if (aiRecommendationMarkdown || geminiPartsPayload) {
      const { parts, missing } = extractGeminiBuildSlots(
        aiRecommendationMarkdown,
        geminiPartsPayload
      );
      if (missing.length) {
        setErpBanner({
          type: 'error',
          message: `Missing parts in AI table: ${missing.join(', ')}. Pick a suggested build or adjust your budget.`,
        });
        return 0;
      }
      partsMap = parts;
    } else {
      const buildParts =
        previewBuild?.parts ||
        (suggestedBuilds.length ? suggestedBuilds[0]?.parts : null);
      if (buildParts?.length) {
        const labelToKey = Object.fromEntries(
          Object.entries(SLOT_LABELS).map(([k, label]) => [label, k])
        );
        partsMap = Object.fromEntries(
          buildParts
            .filter((p) => p.name && p.value && !/^integrated$/i.test(String(p.value)))
            .map((p) => [labelToKey[p.name] || String(p.name).toLowerCase(), p.value])
        );
      }
    }

    if (!partsMap || !Object.keys(partsMap).length) {
      setErpBanner({
        type: 'error',
        message: 'No AI build to add. Run Get recommendations first.',
      });
      return 0;
    }

    setErpSaving(true);
    let fallbackAdded = 0;
    try {
      const result = await addBuildPartsBulk(partsMap);
      if (result.cart) {
        applyCartFromServer(result.cart);
      }

      const addedCount = Number(result.added_count || 0);
      fallbackAdded = addedCount;
      const failed = Array.isArray(result.failed) ? result.failed : [];

      if (addedCount > 0) {
        const names = (result.added || [])
          .map((row) => row.catalog_name || row.label)
          .filter(Boolean)
          .slice(0, 4);
        const summary = names.length ? names.join(', ') : `${addedCount} components`;
        setErpBanner({
          type: 'success',
          message: `Added ${addedCount} part(s) to cart (${summary}${addedCount > 4 ? '…' : ''}). Open cart to review total.`,
        });
      }

      if (failed.length && addedCount === 0) {
        setErpBanner({
          type: 'error',
          message:
            'No parts matched the catalog. Add Montech/CPU/GPU names to the components table or use Components page.',
        });
        return 0;
      }

      if (failed.length && addedCount > 0) {
        setErpBanner({
          type: 'success',
          message: `Added ${addedCount} part(s). Could not match: ${failed.map((f) => f.slot).join(', ')}.`,
        });
      }
    } catch (error) {
      setErpBanner({
        type: 'error',
        message: formatDetectionError(error.message),
      });
    } finally {
      setErpSaving(false);
    }
    return fallbackAdded;
  };

  // Sidebar "Build preview" action: add the current build, then take the user to
  // the cart to review and check out. The in-card CTA adds inline (no navigation).
  const handleAddBuildAndReview = async () => {
    const added = await handleAddToCart();
    if (added > 0) navigate('/cart');
  };

  // Core send pipeline — shared by the input form and the quick-prompt chips.
  const submitMessage = (rawInput) => {
    const raw = String(rawInput || '').trim();
    if (!raw || isTyping) return;

    addUserMessage(raw);

    const { budget: parsedBudgetNum, purpose: parsedPurpose } = parseChatIntent(raw);

    // Multi-turn refinement: "make it cheaper" / "stronger" tweaks the LAST build's
    // budget (no new number given) instead of starting from scratch.
    const refine = parseRefinement(raw);
    const lastBudgetNum = Number(String(budget).replace(/\D/g, '')) || 0;
    if (refine && parsedBudgetNum == null && lastBudgetNum > 0) {
      const stepped = Math.round((lastBudgetNum * refine.factor) / 1000) * 1000;
      const newBudget = Math.max(40000, stepped);
      setBudget(String(newBudget));
      const dir = refine.kind === 'cheaper' ? 'a more affordable' : 'a higher-performance';
      addBotMessage(
        `Refining your ${(purpose || 'Gaming').toLowerCase()} build into ${dir} option — new target ~PKR ${newBudget.toLocaleString('en-PK')}.`
      );
      setTextInput('');
      setShowSuggestedBuilds(true);
      setIsTyping(true);
      fetchAiRecommendations({
        message: raw,
        purpose: purpose || undefined,
        budget: String(newBudget),
        city,
        build_requested: true,
      }).finally(() => setIsTyping(false));
      return;
    }

    const parsedBudget = parsedBudgetNum != null ? String(parsedBudgetNum) : '';
    if (parsedPurpose) setPurpose(parsedPurpose);
    if (parsedBudget) setBudget(parsedBudget);
    setTextInput('');

    const pureGreeting = isPureGreetingMessage(raw);
    const hasBuildIntent = !pureGreeting && hasBuildIntentFromChat(raw);
    setShowSuggestedBuilds(hasBuildIntent);

    setIsTyping(true);
    fetchAiRecommendations({
      message: raw,
      purpose: parsedPurpose || undefined,
      budget: parsedBudget || undefined,
      city,
      build_requested: hasBuildIntent,
    }).finally(() => {
      setIsTyping(false);
    });
  };

  const handleTextSubmit = (e) => {
    e.preventDefault();
    submitMessage(textInput);
  };

  /** Quick-prompt chip: either send a canned prompt or open image detection. */
  const handleQuickPrompt = (chip) => {
    if (isTyping) return;
    if (chip.image) {
      galleryInputRef.current?.click();
      return;
    }
    submitMessage(chip.text);
  };

  const handleGetRecommendations = () => {
    addUserMessage(`Purpose: ${purpose || 'Gaming'}, Budget: PKR ${budget || '100000'}, City: ${city || '—'}`);
    setShowSuggestedBuilds(true);
    setIsTyping(true);
    fetchAiRecommendations({ build_requested: true }).finally(() => setIsTyping(false));
  };

  const handleImageUpload = (e) => {
    const file = e.target?.files?.[0];
    if (!file) return;
    const url = URL.createObjectURL(file);
    analyzeImageFile(file, 'Uploaded component image', url, { confidence: UPLOAD_DETECT_CONF });
    e.target.value = '';
  };

  const handleCameraCapture = () => {
    const video = centerVideoRef.current;
    if (!video || !streamRef.current) return;

    const frame = captureFrameFromVideo(video);
    if (!frame) {
      addBotMessage('Could not prepare the camera frame. Please try again or upload a picture.');
      return;
    }
    const { canvas, width, height } = frame;

    canvas.toBlob((blob) => {
      if (!blob) {
        addBotMessage('Could not capture a camera frame. Please try again or upload a picture.');
        return;
      }

      const file = new File([blob], `camera-${Date.now()}.jpg`, { type: 'image/jpeg' });
      const url = URL.createObjectURL(file);
      analyzeImageFile(file, 'Captured from live camera', url, {
        confidence: UPLOAD_DETECT_CONF,
        cameraOverlay: { width, height },
      });
    }, 'image/jpeg', 0.92);
  };

  const handleSelectBuild = (build) => {
    setSelectedBuild(build);
    setPreviewBuild(build);
  };

  const handleProceed = async (build) => {
    setSelectedBuild(build);
    setPreviewBuild(build);
    setBuilds(suggestedBuilds.length ? suggestedBuilds : [build]);

    if (!build?.parts?.length) {
      navigate('/vendor-assignment');
      return;
    }

    // Same path as the prebuilt PCs: resolve each part name to a real in-stock
    // catalog component, then add by ID via /add-to-cart (vendor auto-assigned).
    // No /cart/add-build-parts (that route 404s on the Dashboard backend).
    setErpSaving(true);
    let added = 0;
    try {
      // Suggested builds carry parts as a 7-string array in slot order; prebuilt /
      // AI builds carry {name, value}. Normalise to {name, value} for the resolver.
      const SLOT_ORDER = ['CPU', 'GPU', 'Motherboard', 'RAM', 'Storage', 'PSU', 'Case'];
      const partsArray = build.parts.map((p, i) =>
        p && typeof p === 'object'
          ? p
          : { name: SLOT_ORDER[i] || `Part ${i + 1}`, value: String(p) }
      );
      const { slots } = await resolveBuildParts(partsArray);
      const result = await addResolvedBuildToCart(slots, addToCart, { silent: true });
      added = result.added;
      if (added > 0) {
        setErpBanner({
          type: 'success',
          message: result.failed.length
            ? `Added ${added} part(s) to cart. Could not match: ${result.failed.join(', ')}.`
            : `Added ${added} part(s) to cart — choose a vendor to continue.`,
        });
      } else {
        setErpBanner({
          type: 'error',
          message: 'Could not add this build — parts may be out of stock. Try another build or budget.',
        });
      }
    } catch (error) {
      setErpBanner({ type: 'error', message: formatDetectionError(error.message) });
    } finally {
      setErpSaving(false);
    }

    if (added > 0) navigate('/vendor-assignment');
  };

  const handleQuickPanelRecommend = () => {
    if (!purpose) setPurpose('Gaming');
    if (!budget) setBudget('100000');
    handleGetRecommendations();
  };

  const handleQuickChatExample = () => {
    setTextInput(QUICK_CHAT_EXAMPLE);
    chatInputRef.current?.focus();
  };

  const handleNewChat = () => {
    setMessages([]);
    setDetectedComponents([]);
    setSuggestedBuilds([]);
    setShowSuggestedBuilds(false);
    setPreviewBuild(null);
    setDetectedImageUrl(null);
    setCameraPreviewOverlay(null);
    setLiveDetectOn(false);
    setAiRecommendationMarkdown(null);
    setGeminiPartsPayload(null);
    setBuildComponents(null);
    setAiCompatibility(null);
    setErpBanner(null);
    if (detectedImageUrl) URL.revokeObjectURL(detectedImageUrl);
  };

  const displayBuild = previewBuild ?? suggestedBuilds[0] ?? null;

  // Newest chat recommendation that resolved to real catalog parts — the inline
  // card customizer renders under THIS message (wired to the live build state).
  let latestBuildMsgId = null;
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const p = messages[i]?.payload;
    if (p?.type === 'ai_recommendation' && Array.isArray(p.buildComponents) && p.buildComponents.length) {
      latestBuildMsgId = messages[i].id;
      break;
    }
  }

  return (
    <div className="chatbot-recommendation-page">
      {erpBanner && (
        <div
          className={`erp-toast erp-toast--${erpBanner.type}`}
          role="status"
          aria-live="polite"
        >
          <span className="erp-toast-message">{erpBanner.message}</span>
          <button
            type="button"
            className="erp-toast-dismiss"
            onClick={() => setErpBanner(null)}
            aria-label="Dismiss notification"
          >
            ×
          </button>
        </div>
      )}
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
              <div className="custom-select" ref={purposeRef}>
                <button
                  type="button"
                  className={`custom-select-trigger${purposeOpen ? ' is-open' : ''}${purpose ? '' : ' is-placeholder'}`}
                  onClick={() => setPurposeOpen((o) => !o)}
                  aria-haspopup="listbox"
                  aria-expanded={purposeOpen}
                  aria-label="Use case"
                >
                  <span className="custom-select-value">
                    {purpose ? PURPOSE_OPTIONS.find((o) => o.value === purpose)?.label : 'Select use case'}
                  </span>
                  <svg className="custom-select-caret" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </button>
                {purposeOpen && (
                  <ul className="custom-select-menu" role="listbox" aria-label="Use case options">
                    {PURPOSE_OPTIONS.map((opt) => (
                      <li
                        key={opt.value}
                        role="option"
                        aria-selected={purpose === opt.value}
                        className={`custom-select-option${purpose === opt.value ? ' is-selected' : ''}`}
                        onClick={() => {
                          setPurpose(opt.value);
                          setPurposeOpen(false);
                        }}
                      >
                        <span className="custom-select-option-icon" aria-hidden>{opt.icon}</span>
                        <span>{opt.label}</span>
                        {purpose === opt.value && (
                          <svg className="custom-select-check" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                            <polyline points="20 6 9 17 4 12" />
                          </svg>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
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
              Generate My Build
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
                  Define your use case and budget in the criteria panel or chat to receive up to three curated, compatible build configurations for comparison.
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

          <div
            className={`chat-output ${showOnboarding ? 'chat-output--onboarding' : ''}`}
            ref={chatOutputRef}
          >
            {showOnboarding && (
              <ChatOnboarding
                onPanelRecommend={handleQuickPanelRecommend}
                onChatExample={handleQuickChatExample}
                onUpload={() => galleryInputRef.current?.click()}
                onCamera={() => {
                  setCameraActive(true);
                  setLiveDetectOn(true);
                }}
              />
            )}
            {messages.map((msg) => (
              <div key={msg.id} className={`chat-message ${msg.type}`}>
                {msg.type === 'bot' ? (
                  <div className="message-avatar">AI</div>
                ) : (
                  <div className="message-avatar message-avatar--user">
                    <div className="user-avatar-icon" aria-hidden="true">
                      <User size={16} strokeWidth={2.5} />
                    </div>
                  </div>
                )}
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
                  {msg.payload?.type === 'detection' && msg.payload.components?.length > 0 ? (
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
                              {!row.isUnknown && row.info && (
                                <p
                                  className="component-chip-info"
                                  style={{ fontSize: '0.74rem', opacity: 0.8, margin: '0.45rem 0 0', lineHeight: 1.35 }}
                                >
                                  {row.info}
                                </p>
                              )}
                            </div>
                          );
                        })}
                      </div>
                      <p className="detection-scope-note" style={{ fontSize: '0.78rem', opacity: 0.72, margin: '0.4rem 0 0' }}>
                        This detector recognizes <strong>CPU, GPU, RAM, motherboard, PSU, cooler and storage</strong>.
                        Other objects may be labeled as the closest of these — confirm before adding to a build.
                      </p>
                      <p className="detection-next-step">
                        Component saved for your build. Set purpose and budget on the left, then click
                        {' '}
                        <strong>Get recommendations</strong>
                        {' '}
                        when you are ready for full PC options.
                      </p>
                    </div>
                  ) : msg.payload?.type === 'ai_recommendation' ? (
                    <div className="ai-recommendation-wrap">
                      {msg.payload.markdown ? (
                        <div className="ai-recommendation-markdown ai-recommendation-markdown--enhanced">
                          <BuildRecommendationCard
                            markdown={msg.payload.markdown}
                            purpose={msg.payload.purpose}
                            budget={msg.payload.budget}
                            buildComponents={msg.payload.buildComponents}
                            compatibility={msg.payload.compatibility}
                            onAddToCart={(comps) => handleAddToCart(comps)}
                            adding={erpSaving}
                            editable={msg.id === latestBuildMsgId &&
                              Array.isArray(buildComponents) && buildComponents.length > 0}
                          />
                          {msg.id === latestBuildMsgId &&
                          Array.isArray(buildComponents) && buildComponents.length ? (
                            <BuildCustomizer
                              buildComponents={buildComponents}
                              purpose={purpose}
                              budget={budget ? Number(budget) : null}
                              onApply={(rows) => setBuildComponents(rows)}
                              onAddToCart={(comps) => handleAddToCart(comps)}
                              adding={erpSaving}
                            />
                          ) : null}
                        </div>
                      ) : null}
                      {msg.payload.fallbackNotice ? (
                        <p className="ai-fallback-notice" role="status">
                          {msg.payload.fallbackNotice}
                        </p>
                      ) : null}
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

            {showSuggestedBuilds && suggestedBuilds.length > 0 && (
              <div className="suggested-builds">
                <h3>Suggested builds</h3>
                <div className="build-cards">
                  {suggestedBuilds.map((build) => (
                    <article
                      key={build.id}
                      className={`build-card${previewBuild?.id === build.id ? ' build-card--selected' : ''}`}
                      role="button"
                      tabIndex={0}
                      onClick={() => handleSelectBuild(build)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          handleSelectBuild(build);
                        }
                      }}
                    >
                      <div className="build-card-top">
                        <span className="build-type">{build.type}</span>
                        <div className="build-price">
                          <span className="build-price-label">PKR</span>
                          {build.price.toLocaleString()}
                        </div>
                      </div>
                      <ul className="build-parts-list">
                        {build.parts.slice(0, 4).map((p, i) => (
                          <li key={i}>
                            <span className="build-part-key">{p.name}</span>
                            <span className="build-part-val">{p.value}</span>
                          </li>
                        ))}
                      </ul>
                      <div className="build-actions">
                        <button
                          type="button"
                          className="btn btn-primary build-card-proceed"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleProceed(build);
                          }}
                        >
                          Proceed
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="chat-quick-prompts" role="group" aria-label="Quick prompts">
            {QUICK_PROMPTS.map((chip) => (
              <button
                key={chip.label}
                type="button"
                className={`chat-quick-chip ${chip.image ? 'chat-quick-chip--accent' : ''}`}
                onClick={() => handleQuickPrompt(chip)}
                disabled={isTyping}
              >
                {chip.label}
              </button>
            ))}
          </div>

          <form className="chat-input-form" onSubmit={handleTextSubmit}>
            <div className="chat-input-wrap chat-input-bar">
              <div className="chat-input-plus-wrap" ref={plusMenuRef}>
                <button
                  type="button"
                  className="chat-input-plus-btn"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    setPlusMenuOpen((v) => !v);
                  }}
                  aria-expanded={plusMenuOpen}
                  aria-haspopup="menu"
                  aria-label="Add image, camera, or text recommendation"
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
                    <button
                      type="button"
                      role="menuitem"
                      className="chat-plus-option"
                      onClick={() => {
                        setCameraActive(true);
                        setLiveDetectOn(true);
                        setPlusMenuOpen(false);
                      }}
                    >
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
                placeholder="Ask for a build — e.g. “Gaming PC under 120K Karachi” — or “what is a GPU?”"
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
            <span className="footer-tip">Detect CPU, GPU, RAM, motherboard, PSU, cooler or storage from an image or camera.</span>
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
          {aiRecommendationMarkdown ? (
            <div className="preview-ai-build">
              <div className="preview-ai-build-scroll ai-recommendation-markdown ai-recommendation-markdown--enhanced">
                <BuildRecommendationCard markdown={aiRecommendationMarkdown} purpose={purpose} budget={budget ? `PKR ${Number(budget).toLocaleString()}` : ''} compatibility={aiCompatibility} editable />
              </div>
              <div className="preview-cart-action">
                <button
                  type="button"
                  className="preview-cart-btn"
                  onClick={handleAddBuildAndReview}
                  disabled={erpSaving || isTyping || !aiRecommendationMarkdown}
                  aria-label="Add this build to cart and go to the cart to review"
                >
                  {erpSaving ? (
                    <>
                      <span className="preview-cart-btn-spinner" aria-hidden />
                      <span className="preview-cart-btn-label">Adding to cart…</span>
                    </>
                  ) : (
                    <>
                      <svg
                        className="preview-cart-btn-icon"
                        width="18"
                        height="18"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        aria-hidden
                      >
                        <circle cx="9" cy="21" r="1" />
                        <circle cx="20" cy="21" r="1" />
                        <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" />
                      </svg>
                      <span className="preview-cart-btn-label">Add to Cart &amp; Review</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          ) : displayBuild ? (
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
