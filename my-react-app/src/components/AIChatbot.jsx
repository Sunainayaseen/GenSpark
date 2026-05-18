import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import './AIChatbot.css';

const GENSPARK_WIDGET_LOGO = '/genspark-gs-circuit-logo.png';

const AIChatbot = () => {
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(true);
  const [messages, setMessages] = useState([
    {
      type: 'bot',
      text: "Hello! 👋 I'm your AI Build Assistant at GenSpark Builds. I can help you find the perfect PC build based on your needs, budget, and preferences. Whether you're looking for gaming, content creation, or office work, I'm here to guide you!",
      timestamp: new Date(),
      id: Date.now(),
    }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [suggestedResponses, setSuggestedResponses] = useState([]);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const cameraInputRef = useRef(null);
  const galleryInputRef = useRef(null);
  const [cameraOpen, setCameraOpen] = useState(false);
  const cameraVideoRef = useRef(null);
  const cameraStreamRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const getAIResponse = (userMessage) => {
    const lowerMessage = userMessage.toLowerCase();
    let response = '';
    let suggestions = [];
    
    if (lowerMessage.includes('gaming') || lowerMessage.includes('game')) {
      response = "For gaming, I'd recommend focusing on a powerful GPU and CPU. What's your budget range? I can suggest builds from PKR 60K for entry-level gaming to PKR 2L+ for high-end setups.";
      suggestions = ['Budget: PKR 60K-1L', 'Mid-range: PKR 1L-1.5L', 'High-end: PKR 1.5L+', 'Show Gaming Builds'];
    } else if (lowerMessage.includes('budget') || lowerMessage.includes('cheap') || lowerMessage.includes('affordable')) {
      response = "Great! For budget builds, we can create excellent systems starting from PKR 30K. These typically include Ryzen 5 or Intel i5 processors, 16GB RAM, and entry-level GPUs. Would you like to see specific build options?";
      suggestions = ['PKR 30K-50K', 'PKR 50K-80K', 'Show Budget Builds'];
    } else if (lowerMessage.includes('content') || lowerMessage.includes('video') || lowerMessage.includes('editing')) {
      response = "Content creation requires strong CPU performance and plenty of RAM. I'd suggest builds with Ryzen 7/9 or Intel i7/i9, 32GB+ RAM, and professional GPUs. What type of content will you be creating?";
      suggestions = ['Video Editing', '3D Rendering', 'Streaming Setup', 'Show Content Builds'];
    } else if (lowerMessage.includes('build') || lowerMessage.includes('start') || lowerMessage.includes('create')) {
      response = "Perfect! I'll guide you through our build process. We'll need to know: 1) Your primary use case, 2) Budget range in PKR, 3) Your city in Pakistan for vendor selection, and 4) Any brand preferences. Ready to start?";
      suggestions = ['Start Build Process', 'View predefined PCs', 'Check Compatibility'];
    } else if (lowerMessage.includes('compatibility') || lowerMessage.includes('compatible')) {
      response = "Our AI engine automatically checks compatibility between all components - CPU socket with motherboard, RAM compatibility, PSU wattage, case dimensions, and more. Every build suggestion is fully compatible!";
      suggestions = ['View Compatible Builds', 'Check My Build'];
    } else if (lowerMessage.includes('vendor') || lowerMessage.includes('assembly') || lowerMessage.includes('assemble')) {
      response = "We partner with verified local vendors across major cities in Pakistan (Karachi, Lahore, Islamabad, Faisalabad, Multan). They handle professional assembly, testing, and can provide local support. Assembly typically takes 2-5 days depending on complexity.";
      suggestions = ['View Vendors', 'Check Assembly Cost', 'Track Order'];
    } else if (lowerMessage.includes('price') || lowerMessage.includes('cost') || lowerMessage.includes('pkr') || lowerMessage.includes('rupee')) {
      response = "Our builds range from PKR 30K for basic office PCs to PKR 3L+ for high-end workstations. The price includes all parts, assembly service, and shipping within Pakistan. Would you like to see builds in a specific price range?";
      suggestions = ['PKR 30K-60K', 'PKR 60K-1L', 'PKR 1L-2L', 'PKR 2L+'];
    } else if (lowerMessage.includes('hello') || lowerMessage.includes('hi') || lowerMessage.includes('hey')) {
      response = "Hello! 👋 Welcome to GenSpark Builds! I'm here to help you find the perfect PC build. What are you looking for today?";
      suggestions = ['Gaming PC', 'Budget (PKR)', 'Content Creation', 'Start Build'];
    } else if (lowerMessage.includes('help') || lowerMessage.includes('support')) {
      response = "I'm here to help! I can assist with: finding the right PC build, checking compatibility, comparing builds, vendor selection, and order tracking. What do you need help with?";
      suggestions = ['Predefined PCs', 'Compatibility Check', 'Vendor Info', 'Contact Support'];
    } else {
      const defaultResponses = [
        "I understand! Let me help you with that. Could you tell me more about what you're looking for?",
        "That's a great question! Our AI can generate multiple build options based on your requirements. Would you like to start the build process?",
        "I can help you with that! We offer builds for gaming, content creation, office work, and more. What's your primary use case?",
        "Excellent! I'd be happy to assist. Our platform ensures all parts are compatible and we have local vendors for assembly. Ready to build your PC?",
      ];
      response = defaultResponses[Math.floor(Math.random() * defaultResponses.length)];
      suggestions = ['Gaming PC', 'Budget (PKR)', 'Start Build', 'View Builds'];
    }
    
    setSuggestedResponses(suggestions);
    return response;
  };

  const handleSend = (e) => {
    e.preventDefault();
    if (!inputValue.trim() || isTyping) return;

    const userMessage = {
      type: 'user',
      text: inputValue,
      timestamp: new Date(),
      id: Date.now(),
    };

    setMessages(prev => [...prev, userMessage]);
    const messageText = inputValue;
    setInputValue('');
    setIsTyping(true);
    setSuggestedResponses([]);

    // Simulate AI thinking
    setTimeout(() => {
      const aiResponse = {
        type: 'bot',
        text: getAIResponse(messageText),
        timestamp: new Date(),
        id: Date.now() + 1,
      };
      setIsTyping(false);
      setMessages(prev => [...prev, aiResponse]);
    }, 1000 + Math.random() * 1000);
  };

  const handleSuggestedResponse = (suggestion) => {
    if (suggestion === 'Start Build Process' || suggestion === 'Start Build') {
      navigate('/chatbot');
      return;
    }
    if (suggestion.includes('Show') || suggestion.includes('View')) {
      navigate('/builds');
      return;
    }
    setInputValue(suggestion);
    setTimeout(() => {
      handleSend({ preventDefault: () => {} });
    }, 100);
  };

  const copyMessage = (text) => {
    navigator.clipboard.writeText(text);
    // You could add a toast notification here
  };

  const clearChat = () => {
    setMessages([
      {
        type: 'bot',
        text: "Chat cleared! How can I help you today?",
        timestamp: new Date(),
        id: Date.now(),
      }
    ]);
    setSuggestedResponses([]);
  };

  const quickActions = [
    {
      text: "Gaming PC",
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="4" y="8" width="16" height="10" rx="2"/>
          <path d="M8 8V6a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2"/>
          <line x1="8" y1="12" x2="8.01" y2="12"/><line x1="16" y1="12" x2="16.01" y2="12"/>
          <circle cx="12" cy="14" r="1.5" fill="currentColor"/>
        </svg>
      ),
      action: () => handleSuggestedResponse("Gaming PC"),
    },
    {
      text: "Budget (PKR)",
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          {/* Wallet icon — PKR is in the button label, not a US-currency glyph */}
          <path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1" />
          <path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4" />
        </svg>
      ),
      action: () => handleSuggestedResponse("Budget (PKR)"),
    },
    {
      text: "Content Creation",
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="2" y="4" width="20" height="16" rx="2"/><path d="M10 9l5 3-5 3V9z"/><path d="M2 12h4"/><path d="M18 12h4"/>
        </svg>
      ),
      action: () => handleSuggestedResponse("Content Creation"),
    },
    {
      text: "Start Build",
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
        </svg>
      ),
      action: () => navigate('/chatbot'),
    },
  ];

  const formatTime = (date) => {
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  };

  const handleImageMessage = (file, source) => {
    if (!file || isTyping) return;

    const imageUrl = URL.createObjectURL(file);
    const userMessage = {
      type: 'user',
      text: source === 'camera' ? 'Shared a photo from camera' : 'Uploaded a PC image',
      timestamp: new Date(),
      id: Date.now(),
      imageUrl,
    };

    setMessages(prev => [...prev, userMessage]);
    setIsTyping(true);
    setSuggestedResponses([]);

    setTimeout(() => {
      const aiResponse = {
        type: 'bot',
        text: "Got your image 📷. I’ll use it as a reference for your build (case style, RGB, and form factor). Tell me how you’ll use this PC and your budget so I can recommend parts.",
        timestamp: new Date(),
        id: Date.now() + 1,
      };
      setIsTyping(false);
      setMessages(prev => [...prev, aiResponse]);
    }, 1200);
  };

  const handleCameraChange = (event) => {
    const file = event.target.files?.[0];
    if (file) handleImageMessage(file, 'camera');
    event.target.value = '';
  };

  const openCamera = () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      cameraInputRef.current?.click();
      return;
    }
    navigator.mediaDevices.getUserMedia({ video: true })
      .then((stream) => {
        cameraStreamRef.current = stream;
        setCameraOpen(true);
      })
      .catch(() => {
        cameraInputRef.current?.click();
      });
  };

  const closeCamera = () => {
    if (cameraStreamRef.current) {
      cameraStreamRef.current.getTracks().forEach((t) => t.stop());
      cameraStreamRef.current = null;
    }
    setCameraOpen(false);
  };

  useEffect(() => {
    if (cameraOpen && cameraStreamRef.current && cameraVideoRef.current) {
      cameraVideoRef.current.srcObject = cameraStreamRef.current;
    }
  }, [cameraOpen]);

  useEffect(() => {
    return () => {
      if (cameraStreamRef.current) {
        cameraStreamRef.current.getTracks().forEach((t) => t.stop());
      }
    };
  }, []);

  const captureFromCamera = () => {
    const video = cameraVideoRef.current;
    const stream = cameraStreamRef.current;
    if (!video || !stream || !video.videoWidth) return;
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0);
    canvas.toBlob((blob) => {
      if (!blob) return;
      const file = new File([blob], `camera-${Date.now()}.jpg`, { type: 'image/jpeg' });
      handleImageMessage(file, 'camera');
      closeCamera();
    }, 'image/jpeg', 0.9);
  };

  const handleGalleryChange = (event) => {
    const file = event.target.files?.[0];
    handleImageMessage(file, 'gallery');
    event.target.value = '';
  };

  return (
    <>
      {cameraOpen && (
        <div className="widget-camera-overlay" role="dialog" aria-label="Camera">
          <div className="widget-camera-modal">
            <div className="widget-camera-header">
              <span>Take a photo</span>
              <button type="button" className="widget-camera-close" onClick={closeCamera} aria-label="Close camera">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
              </button>
            </div>
            <div className="widget-camera-video-wrap">
              <video ref={cameraVideoRef} autoPlay playsInline muted className="widget-camera-video" />
            </div>
            <div className="widget-camera-actions">
              <button type="button" className="widget-camera-cancel btn btn-secondary" onClick={closeCamera}>Cancel</button>
              <button type="button" className="widget-camera-capture btn btn-primary" onClick={captureFromCamera}>Capture</button>
            </div>
          </div>
        </div>
      )}
      {isMinimized && (
        <button
          className="chatbot-minimized"
          onClick={() => {
            setIsMinimized(false);
            setIsOpen(true);
          }}
          aria-label="Open AI Assistant"
        >
          <div className="minimized-icon">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M20 2H4C2.9 2 2 2.9 2 4V22L6 18H20C21.1 18 22 17.1 22 16V4C22 2.9 21.1 2 20 2ZM20 16H6L4 18V4H20V16Z" fill="currentColor"/>
              <path d="M7 9H17V11H7V9ZM7 12H15V14H7V12Z" fill="currentColor"/>
            </svg>
          </div>
          <span className="minimized-badge">{messages.length}</span>
          <div className="minimized-pulse"></div>
        </button>
      )}

      {!isMinimized && (
        <div className={`ai-chatbot-widget ${isOpen ? 'open' : ''}`}>
          <div className="chatbot-widget-header">
            <div className="widget-header-left">
              <div className="widget-avatar">
                <img
                  src={GENSPARK_WIDGET_LOGO}
                  alt="GenSpark Builds"
                  className="widget-avatar-logo"
                  width={41}
                  height={41}
                />
              </div>
              <div className="widget-header-info">
                <h3>AI Build Assistant</h3>
                <p className="widget-status">
                  <span className="status-dot"></span>
                  Online
                </p>
              </div>
            </div>
            <div className="widget-header-actions">
              <button
                className="widget-action-btn"
                onClick={clearChat}
                title="Clear Chat"
              >
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M2 4H14M5 4V2C5 1.44772 5.44772 1 6 1H10C10.5523 1 11 1.44772 11 2V4M13 4V14C13 14.5523 12.5523 15 12 15H4C3.44772 15 3 14.5523 3 14V4H13Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                </svg>
              </button>
              <button
                className="widget-minimize-btn"
                onClick={() => setIsMinimized(true)}
                title="Minimize"
              >
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M4 8H12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                </svg>
              </button>
              <button
                className="widget-close-btn"
                onClick={() => setIsOpen(false)}
                title="Close"
              >
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M12 4L4 12M4 4L12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                </svg>
              </button>
            </div>
          </div>

          <div className="chatbot-widget-body">
            <div className="widget-messages">
              {messages.map((msg) => (
                <div key={msg.id} className={`widget-message ${msg.type}`}>
                  <div className="widget-message-avatar">
                    {msg.type === 'bot' ? (
                      <div className="bot-avatar">
                        <span className="bot-avatar-text">AI</span>
                      </div>
                    ) : (
                      <div className="user-avatar">U</div>
                    )}
                  </div>
                  <div className="widget-message-content">
                    {msg.imageUrl && (
                      <div className="message-image-wrapper">
                        <img src={msg.imageUrl} alt="Shared content" className="message-image" />
                      </div>
                    )}
                    <p>{msg.text}</p>
                    <div className="message-footer">
                      <span className="message-time">{formatTime(msg.timestamp)}</span>
                      {msg.type === 'bot' && (
                        <button 
                          className="message-copy-btn"
                          onClick={() => copyMessage(msg.text)}
                          title="Copy message"
                        >
                          <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                            <path d="M6 2C5.44772 2 5 2.44772 5 3V11C5 11.5523 5.44772 12 6 12H12C12.5523 12 13 11.5523 13 11V3C13 2.44772 12.5523 2 12 2H6Z" stroke="currentColor" strokeWidth="1.5"/>
                            <path d="M3 5H2C1.44772 5 1 5.44772 1 6V14C1 14.5523 1.44772 15 2 15H10C10.5523 15 11 14.5523 11 14V13" stroke="currentColor" strokeWidth="1.5"/>
                          </svg>
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
              
              {isTyping && (
                <div className="widget-message bot typing">
                  <div className="widget-message-avatar">
                    <div className="bot-avatar">
                      <span className="bot-avatar-text">AI</span>
                    </div>
                  </div>
                  <div className="widget-message-content typing-indicator">
                    <div className="typing-dots">
                      <span></span>
                      <span></span>
                      <span></span>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {suggestedResponses.length > 0 && (
              <div className="widget-suggested-responses">
                <p className="suggested-label">Suggested responses:</p>
                <div className="suggested-buttons">
                  {suggestedResponses.map((suggestion, idx) => (
                    <button
                      key={idx}
                      className="suggested-btn"
                      onClick={() => handleSuggestedResponse(suggestion)}
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="widget-quick-actions">
              {quickActions.map((action, idx) => (
                <button
                  key={idx}
                  className="quick-action-btn"
                  onClick={action.action}
                >
                  <span className="action-icon" aria-hidden>{action.icon}</span>
                  <span>{action.text}</span>
                </button>
              ))}
            </div>

            <form className="widget-input-form" onSubmit={handleSend}>
              <input
                ref={cameraInputRef}
                type="file"
                accept="image/*"
                capture="environment"
                style={{ display: 'none' }}
                onChange={handleCameraChange}
              />
              <input
                ref={galleryInputRef}
                type="file"
                accept="image/*"
                style={{ display: 'none' }}
                onChange={handleGalleryChange}
              />
              <button
                type="button"
                className="widget-icon-btn"
                onClick={openCamera}
                title="Open camera"
                aria-label="Open camera"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                  <path d="M4 7H7L9 4H15L17 7H20C21.1 7 22 7.9 22 9V19C22 20.1 21.1 21 20 21H4C2.9 21 2 20.1 2 19V9C2 7.9 2.9 7 4 7Z" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
                  <circle cx="12" cy="14" r="4" stroke="currentColor" strokeWidth="1.6"/>
                </svg>
              </button>
              <button
                type="button"
                className="widget-icon-btn"
                onClick={() => galleryInputRef.current?.click()}
                title="Upload from gallery"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                  <rect x="3" y="5" width="18" height="14" rx="2" stroke="currentColor" strokeWidth="1.6"/>
                  <path d="M7 15L10 11L13 14L16 10L19 15" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
                  <circle cx="8" cy="9" r="1.2" fill="currentColor"/>
                </svg>
              </button>
              <input
                ref={inputRef}
                type="text"
                className="widget-input"
                placeholder="Type your message..."
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                disabled={isTyping}
                autoFocus={!isMinimized}
              />
              <button
                type="submit"
                className="widget-send-btn"
                disabled={!inputValue.trim() || isTyping}
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                  <path d="M2 21L23 12L2 3V10L17 12L2 14V21Z" fill="currentColor"/>
                </svg>
              </button>
            </form>
          </div>
        </div>
      )}
    </>
  );
};

export default AIChatbot;







