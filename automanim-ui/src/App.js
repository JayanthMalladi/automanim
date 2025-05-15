import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import Prism from 'prismjs';
import 'prismjs/themes/prism-tomorrow.css';
import 'prismjs/components/prism-python';
import './App.css';

// API endpoints with fallbacks
const API_ENDPOINTS = {
  primary: 'https://automanim-1.onrender.com',
  fallback: 'https://automanim-1.onrender.com', // Same for now, could be changed to another backup server
};

const CodeBlock = ({ code }) => {
  useEffect(() => {
    Prism.highlightAll();
  }, [code]);

  return (
    <pre className="code-block">
      <code className="language-python">{code}</code>
    </pre>
  );
};

function App() {
  const [messages, setMessages] = useState([]);
  const [prompt, setPrompt] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [isImproving, setIsImproving] = useState(false);
  const [gettingInstructions, setGettingInstructions] = useState(false);
  const [runInstructions, setRunInstructions] = useState(null);
  const [lastCodeMessage, setLastCodeMessage] = useState(null);
  const [autoExpand, setAutoExpand] = useState(false);
  const [improvedPrompt, setImprovedPrompt] = useState(null);
  const [showPreview, setShowPreview] = useState(false);
  const [currentApiEndpoint, setCurrentApiEndpoint] = useState(API_ENDPOINTS.primary);
  const messagesEndRef = useRef(null);
  const contentAreaRef = useRef(null);
  const textareaRef = useRef(null);

  // Example prompts that users can select from
  const examplePrompts = [
    "Animate a bouncing ball animation with physics",
    "Animate a circle morphing into a square over 2 seconds",
    "Animate the quadratic formula with step-by-step explanation",
    "Animate a 3D rotating cube that changes colors"
  ];

  // Documentation links and resources
  const docResources = [
    {
      title: "Getting Started",
      items: [
        { text: "Installation Guide", icon: "📥", link: "https://docs.manim.community/en/stable/installation.html" },
        { text: "Basic Tutorial", icon: "🚀", link: "https://docs.manim.community/en/stable/tutorials/quickstart.html" },
        { text: "Configuration", icon: "⚙️", link: "https://docs.manim.community/en/stable/guides/configuration.html" }
      ]
    },
    {
      title: "Core Concepts",
      items: [
        { text: "Animations", icon: "🎬", link: "https://docs.manim.community/en/stable/reference/manim.animation.html" },
        { text: "Mobjects", icon: "🔷", link: "https://docs.manim.community/en/stable/reference/manim.mobject.html" },
        { text: "Scenes", icon: "🎭", link: "https://docs.manim.community/en/stable/reference/manim.scene.html" }
      ]
    },
    {
      title: "Examples",
      items: [
        { text: "Animation Gallery", icon: "🖼️", link: "https://docs.manim.community/en/stable/examples.html" },
        { text: "Example Projects", icon: "📁", link: "https://github.com/ManimCommunity/manim/tree/main/example_scenes" }
      ]
    }
  ];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isGenerating]);

  useEffect(() => {
    if (textareaRef.current && autoExpand) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [prompt, autoExpand]);

  const handlePromptSelect = (selectedPrompt) => {
    setPrompt(selectedPrompt);
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  };

  // Function to try API call with fallback
  const fetchWithFallback = async (endpoint, options) => {
    try {
      console.log(`Attempting to fetch from: ${currentApiEndpoint}${endpoint}`);
      const response = await fetch(`${currentApiEndpoint}${endpoint}`, options);
      
      console.log("Response status:", response.status);
      console.log("Response headers:", [...response.headers.entries()].map(e => `${e[0]}: ${e[1]}`).join(', '));
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error("Error response:", errorText);
        throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
      }
      
      return response;
    } catch (error) {
      console.error(`Error fetching from ${currentApiEndpoint}${endpoint}:`, error);
      
      // If we're already using the fallback, just throw the error
      if (currentApiEndpoint === API_ENDPOINTS.fallback) {
        throw error;
      }
      
      // Switch to fallback endpoint and retry
      console.log("Switching to fallback API endpoint");
      setCurrentApiEndpoint(API_ENDPOINTS.fallback);
      const fallbackResponse = await fetch(`${API_ENDPOINTS.fallback}${endpoint}`, options);
      
      if (!fallbackResponse.ok) {
        const errorText = await fallbackResponse.text();
        throw new Error(`HTTP error from fallback! status: ${fallbackResponse.status}, message: ${errorText}`);
      }
      
      return fallbackResponse;
    }
  };

  const handleGenerate = async () => {
    if (!prompt.trim()) return;
    
    // Add user message
    setMessages(prev => [...prev, { type: 'user', content: prompt }]);
    setPrompt('');
    setIsGenerating(true);

    try {
      console.log("Fetching from backend...");
      const response = await fetchWithFallback('/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt }),
        mode: 'cors',
        credentials: 'omit'
      });
      
      const data = await response.json();
      console.log("Received data:", data);
      
      // Add assistant message immediately
      setMessages(prev => [...prev, { type: 'assistant', content: data.code }]);
      setIsGenerating(false);
    } catch (error) {
      console.error("Error generating code:", error);
      // More detailed error message for user
      let errorMessage = "// Error: Could not connect to the server. Please make sure the backend is running.";
      if (error.message) {
        errorMessage += `\n// Details: ${error.message}`;
      }
      setMessages(prev => [...prev, { 
        type: 'assistant', 
        content: errorMessage
      }]);
      setIsGenerating(false);
    }
  };

  const handleImprovePrompt = async () => {
    if (!prompt.trim()) return;
    console.log("Starting prompt improvement...");
    setIsImproving(true);
    
    try {
      console.log("Sending prompt to backend:", prompt);
      const response = await fetchWithFallback('/improve_prompt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt }),
        mode: 'cors',
        credentials: 'omit'
      });
      
      const data = await response.json();
      console.log("Received response data:", data);
      
      if (data.improved_prompt) {
        console.log("Setting improved prompt:", data.improved_prompt);
        setPrompt(data.improved_prompt);
        
        // Add slight delay to ensure state is updated before adjusting height
        setTimeout(() => {
          if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
            textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight + 10, 300)}px`;
          }
        }, 10);
      } else {
        console.log("No improved prompt in response");
      }
    } catch (error) {
      console.error("Error improving prompt:", error);
      alert("Failed to improve prompt: " + error.message);
    } finally {
      setIsImproving(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleGenerate();
    }
  };

  const handleTextareaChange = (e) => {
    setPrompt(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const newHeight = Math.min(textareaRef.current.scrollHeight + 10, 300);
      textareaRef.current.style.height = `${newHeight}px`;
    }
    if (!autoExpand) setAutoExpand(true);
  };

  const startNewChat = () => {
    setMessages([]);
    setRunInstructions(null);
  };

  const cancelImprovement = () => {
    setShowPreview(false);
    setImprovedPrompt(null);
  };

  const applyImprovedPrompt = () => {
    if (improvedPrompt) {
      setPrompt(improvedPrompt);
      setShowPreview(false);
      setImprovedPrompt(null);
    }
  };

  // Function to provide standard run instructions instead of calling LLM
  const handleGetRunInstructions = (code) => {
    setGettingInstructions(true);
    
    // Extract the class name from the code to use in the instructions
    let className = "YourAnimation";
    const classMatch = code.match(/class\s+(\w+)\s*\(\s*Scene\s*\)/);
    if (classMatch && classMatch[1]) {
      className = classMatch[1];
    }
    
    // Extract the file name (if any) from the code comments
    let fileName = `${className.toLowerCase()}.py`;
    const fileNameMatch = code.match(/# Filename: ([\w\.]+)/i);
    if (fileNameMatch && fileNameMatch[1]) {
      fileName = fileNameMatch[1];
    }
    
    // Standard instructions for running Manim code
    const standardInstructions = `
# How to Run This Manim Animation

## Step 1: Install Manim and Dependencies

1. **Prerequisites**: Ensure you have Python 3.8 or higher installed.
   \`\`\`bash
   python --version
   \`\`\`

2. **Install Manim**: Install the Manim Community Edition.
   \`\`\`bash
   pip install manim
   \`\`\`

3. **Additional Dependencies**: For 3D animations, you may need to install these packages.
   \`\`\`bash
   pip install moderngl moderngl-window
   \`\`\`

## Step 2: Save the Code

1. Save the provided code to a file named \`${fileName}\`.

## Step 3: Run the Animation

1. **Basic render** (low quality but fast):
   \`\`\`bash
   manim -pql ${fileName} ${className}
   \`\`\`

2. **Medium quality**:
   \`\`\`bash
   manim -pqm ${fileName} ${className}
   \`\`\`

3. **High quality** (slower but better for final output):
   \`\`\`bash
   manim -pqh ${fileName} ${className}
   \`\`\`

## Troubleshooting Tips

- **Missing Dependencies**: If you encounter errors about missing modules, install them with \`pip install [module_name]\`.
- **LaTeX Issues**: Ensure you have a LaTeX distribution installed if the animation uses mathematical symbols.
- **Rendering Problems**: Try updating Manim with \`pip install --upgrade manim\`.
- **Media Folder**: The rendered video will be saved in the \`./media/videos/\` directory.
`;

    // Set the instructions and turn off loading
    setTimeout(() => {
      setRunInstructions(standardInstructions);
      setGettingInstructions(false);
    }, 300); // Short timeout to show loading indicator briefly
  };

  // Update to track the last code message
  useEffect(() => {
    // Find the last assistant message containing code
    const lastCode = [...messages].reverse().find(msg => msg.type === 'assistant');
    if (lastCode) {
      setLastCodeMessage(lastCode.content);
    } else {
      setLastCodeMessage(null);
    }
  }, [messages]);

  const renderMessage = (message) => {
    return (
      <div className={`message ${message.type}-message`}>
        <div className={`avatar ${message.type}-avatar`}>
          {message.type === 'user' ? (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M20 21V19C20 16.7909 18.2091 15 16 15H8C5.79086 15 4 16.7909 4 19V21M16 7C16 9.20914 14.2091 11 12 11C9.79086 11 8 9.20914 8 7C8 4.79086 9.79086 3 12 3C14.2091 3 16 4.79086 16 7Z" 
                stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          ) : (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M9.25 7L14.75 7M9.25 11H14.75M9.25 15H14.75M7.75 19H16.25C17.3546 19 18.25 18.1046 18.25 17V7C18.25 5.89543 17.3546 5 16.25 5H7.75C6.64543 5 5.75 5.89543 5.75 7V17C5.75 18.1046 6.64543 19 7.75 19Z" 
                stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          )}
        </div>
        <div className="message-content">
          {message.type === 'assistant' ? (
            <CodeBlock code={message.content} />
          ) : (
            <p className="message-text">{message.content}</p>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="app-container">
      <div className="sidebar">
        <div className="sidebar-header">
          <h1>
            <span className="logo-icon">▲</span>
            AutoManim
          </h1>
        </div>
        <div className="sidebar-actions">
          <button 
            className="new-chat-button"
            onClick={startNewChat}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            New Chat
          </button>
        </div>
        <div className="sidebar-section">
          <h2>Documentation</h2>
          {docResources.map((section, idx) => (
            <div key={idx} className="doc-section">
              <h3>{section.title}</h3>
              <div className="doc-links">
                {section.items.map((item, i) => (
                  <a 
                    key={i} 
                    href={item.link} 
                    target="_blank" 
                    rel="noopener noreferrer" 
                    className="doc-link"
                  >
                    <span className="doc-icon">{item.icon}</span>
                    {item.text}
                  </a>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="sidebar-section">
          <h2>Quick Tips</h2>
          <div className="tips-container">
            <div className="tip-item">
              <span className="tip-icon">💡</span>
              <p>Use <code>self.play()</code> for smooth animations</p>
            </div>
            <div className="tip-item">
              <span className="tip-icon">⚡</span>
              <p>Press <code>Ctrl+Enter</code> to generate quickly</p>
            </div>
            <div className="tip-item">
              <span className="tip-icon">🎨</span>
              <p>Customize colors with built-in constants like <code>BLUE</code>, <code>RED</code></p>
            </div>
          </div>
        </div>
      </div>
      
      <div className="main-content">
        <div className="header">
          <h1>
            <span className="logo-icon">▲</span>
            AutoManim <span className="subtitle">| AI-Powered Manim Generator</span>
          </h1>
        </div>
        <div className="content-area" ref={contentAreaRef}>
          {messages.length === 0 ? (
            <div className="welcome-screen">
              <div className="welcome-icon">▲ ● ■</div>
              <h2>Welcome to AutoManim</h2>
              <p className="welcome-description">
                Describe the animation you want to create with Manim, and I'll generate the code for you.
              </p>
              <div className="prompt-examples">
                {examplePrompts.map((examplePrompt, index) => (
                  <div 
                    key={index} 
                    className="prompt-example"
                    onClick={() => handlePromptSelect(examplePrompt)}
                  >
                    <div className="prompt-example-icon">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M12 4V20M4 12H20" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                      </svg>
                    </div>
                    {examplePrompt}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages.map((message, index) => (
                <div key={index}>
                  {renderMessage(message)}
                </div>
              ))}
              
              {isGenerating && (
                <div className="message assistant-message">
                  <div className="avatar assistant-avatar">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M9.25 7L14.75 7M9.25 11H14.75M9.25 15H14.75M7.75 19H16.25C17.3546 19 18.25 18.1046 18.25 17V7C18.25 5.89543 17.3546 5 16.25 5H7.75C6.64543 5 5.75 5.89543 5.75 7V17C5.75 18.1046 6.64543 19 7.75 19Z" 
                        stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                    </svg>
                  </div>
                  <div className="typing-indicator">
                    <div className="typing-dot"></div>
                    <div className="typing-dot"></div>
                    <div className="typing-dot"></div>
                  </div>
                </div>
              )}
              
              <div style={{
                display: "flex", 
                justifyContent: "flex-end", 
                width: "100%",
                marginTop: "16px", 
                marginBottom: "16px"
              }}>
                {lastCodeMessage && !runInstructions && (
                  <button 
                    className="how-to-run-button"
                    onClick={() => handleGetRunInstructions(lastCodeMessage)}
                    disabled={gettingInstructions}
                  >
                    {gettingInstructions ? (
                      <>
                        <div className="button-loading">
                          <div className="loading-dot"></div>
                          <div className="loading-dot"></div>
                          <div className="loading-dot"></div>
                        </div>
                        Getting instructions...
                      </>
                    ) : (
                      <>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                          <path d="M5 5V19M19 12L5 12M19 12L13 6M19 12L13 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                        </svg>
                        How to run this code
                      </>
                    )}
                  </button>
                )}
              </div>
              
              {runInstructions && (
                <div className="run-instructions">
                  <button
                    className="instructions-close-icon"
                    onClick={() => setRunInstructions(null)}
                    aria-label="Close instructions"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M6 18L18 6M6 6L18 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </button>
                  <h3>How to Run This Code</h3>
                  <div className="markdown-content">
                    <ReactMarkdown>{runInstructions}</ReactMarkdown>
                  </div>
                </div>
              )}
              
              <div ref={messagesEndRef} />
            </>
          )}
        </div>
        
        <div className="input-container">
          <div className="input-area">
            {isImproving ? (
              <div className="loading-prompt">
                <div className="typing-indicator">
                  <div className="typing-dot"></div>
                  <div className="typing-dot"></div>
                  <div className="typing-dot"></div>
                </div>
                <p>Improving prompt...</p>
              </div>
            ) : (
              <textarea
                ref={textareaRef}
                value={prompt}
                onChange={handleTextareaChange}
                onKeyDown={handleKeyDown}
                placeholder="How can AutoManim help you today?"
                disabled={isGenerating || isImproving}
                className="markdown-input"
              />
            )}
            <div className="input-icons-vertical">
              <button
                className="input-icon-sparkle"
                onClick={handleImprovePrompt}
                disabled={!prompt || isGenerating || isImproving}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" 
                    stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>
              <button
                className="input-icon-right"
                onClick={handleGenerate}
                disabled={!prompt || isGenerating || isImproving}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M5 12H19M19 12L12 5M19 12L12 19" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;