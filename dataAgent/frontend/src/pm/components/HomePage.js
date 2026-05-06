//const response = await fetch("https://pm-portal-2.onrender.com/api/process-multi-files", {
import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import * as XLSX from 'xlsx';
import axios from 'axios';
import './HomePage.css';
import GoogleDrivePicker from '../../qa/GoogleDrivePicker';
/* global gapi:readonly, google:readonly */ 
// gapi and google are external globals loaded by index.html scripts.

// --- NEW GLOBAL CODE FOR GOOGLE DRIVE INTEGRATION ---

const GOOGLE_CLIENT_ID = process.env.REACT_APP_GOOGLE_CLIENT_ID;
// 🚨 CRITICAL: Ensure you have REACT_APP_GOOGLE_DEVELOPER_API_KEY in your .env
const DEVELOPER_API_KEY = process.env.REACT_APP_GOOGLE_API_KEY; 
const DRIVE_SCOPES = 'https://www.googleapis.com/auth/drive.readonly'; 
const FASTAPI_DRIVE_UPLOAD_URL = process.env.REACT_APP_API_URL + '/api/upload-from-drive'; 

//let accessToken = ''; // Global variable to h
// old the OAuth token
let pickerApiLoaded = false;
//let chatDriveAccessToken = ''; // <--- NEW: Dedicated token for Chat Drive Picker
// ... (rest of the global functions are fine)

// 1. Initialization and Loading Check
// This function must be in the global scope to be called by the script tags.
// GLOBAL CODE (NO CHANGES NEEDED HERE, just confirmation)
// --------------------------------------------------------
// function gapiLoaded() {
//     if (typeof gapi !== 'undefined' && typeof gapi.load === 'function') {
//         gapi.load('picker', () => {
//             pickerApiLoaded = true; // <-- This flag is essential
//             console.log("Google Picker API ready.");
//         });
//     }
// }
// --------------------------------------------------------

// // Initial GAPI load check (assumes script tags load soon)
// if (typeof gapi !== 'undefined' && typeof gapi.load === 'function') {
//     gapi.load('client', gapiLoaded);
// }




const HomePage = () => {
  const [showProfilePopup, setShowProfilePopup] = useState(false);
  const [loading, setLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [toastVisible, setToastVisible] = useState(false);
  const [isPickerReady, setIsPickerReady] = useState(false); // New
  const [toastMessage, setToastMessage] = useState('');
  const isChatFullscreen = true;
  const [accessToken, setAccessToken] = useState('');
  const accessTokenRef = useRef('');
  const [chatDriveAccessToken, setChatDriveAccessToken] = useState('');
  const chatTokenRef = useRef('');
  const chatPickerRef = useRef(null);
  const templatePickerRef = useRef(null);



  // Chat drag/position state
  const [isDraggingChat, setIsDraggingChat] = useState(false);
  const [chatUseCustomPosition, setChatUseCustomPosition] = useState(false);
  const [chatPosition, setChatPosition] = useState({ x: 0, y: 0 });
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const [isChatDockedTopLeft, setIsChatDockedTopLeft] = useState(false);
  // Resize state
  const defaultChatSize = { width: 380, height: 500 };
  const [chatSize, setChatSize] = useState(defaultChatSize);
  const [isResizingChat, setIsResizingChat] = useState(false);
  const [resizeDirection, setResizeDirection] = useState(null); // 'br' | 'bl' | 'tr' | 'tl'
  const [resizeStart, setResizeStart] = useState({ mouseX: 0, mouseY: 0, width: defaultChatSize.width, height: defaultChatSize.height, left: 0, top: 0 });
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState([]);
  const [showAttachMenu, setShowAttachMenu] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [selectedFiles, setSelectedFiles] = useState([]); // For multiple file selection
  
  // Dummy function to use setSelectedFile (prevents unused variable warning)
  const handleSelectedFileChange = useCallback((file) => {
    setSelectedFile(file);
  }, []);
  const [uploadedFileId, setUploadedFileId] = useState(null);
  const [uploadedFileIds, setUploadedFileIds] = useState([]); // Track multiple uploaded file IDs
  const [isUploadingFile, setIsUploadingFile] = useState(false);
  const [playbookFileIds, setPlaybookFileIds] = useState(() => {
    // Load playbook file IDs from localStorage on component mount
    try {
      const saved = localStorage.getItem('playbookFileIds');
      return saved ? JSON.parse(saved) : [];
    } catch (error) {
      console.error('Error loading playbookFileIds from localStorage:', error);
      return [];
    }
  }); // Track playbook file IDs from Start a Project
  const [showMandatoryFilesDropdown, setShowMandatoryFilesDropdown] = useState(false);
  const [mandatoryFiles, setMandatoryFiles] = useState([]);
  const [mandatoryFilesSearch, setMandatoryFilesSearch] = useState('');
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadingFile, setUploadingFile] = useState(false);
  
  // Dummy function to use showUploadModal and setShowUploadModal (prevents unused variable warning)
  const toggleUploadModal = useCallback(() => {
    setShowUploadModal(prev => !prev);
    return showUploadModal;
  }, [showUploadModal]);
  const [filesMarkedForProject, setFilesMarkedForProject] = useState(new Set()); // Track which files are marked for project use
  const [openModuleDropdown, setOpenModuleDropdown] = useState(null); // Track which file's module dropdown is open (fileId or null)
  const [fileModules, setFileModules] = useState(new Map()); // Track selected module for each file: Map<fileId, moduleName>
  const [isChatHistoryCollapsed, setIsChatHistoryCollapsed] = useState(false); // Track sidebar collapse state
  const [showProjectsView, setShowProjectsView] = useState(false); // Track if projects view is shown
  const [projects, setProjects] = useState([]); // Store projects with nested conversations
  const [showCreateProjectModal, setShowCreateProjectModal] = useState(false); // Show create project modal
  const [showFileSourceModal, setShowFileSourceModal] = useState(false); // Show file source selection modal (Local/GDrive)
  const [projectName, setProjectName] = useState(''); // Project name input
  const [isCreatingProject, setIsCreatingProject] = useState(false); // Loading state for creating project
  const [expandedProjects, setExpandedProjects] = useState(new Set()); // Track which projects are expanded
  const [activeProjectId, setActiveProjectId] = useState(null); // Active project ID
  const [activeConversationId, setActiveConversationId] = useState(null); // Active conversation ID
  const [currentProject, setCurrentProject] = useState(null); // Current project info for header
  
  // useEffect(() => {
  //       if (typeof window !== 'undefined') {
  //           // Expose the state setter to the global gapiLoaded function in index.html
  //           window.setPickerApiLoaded = (status) => {
  //               setIsPickerReady(status);
  //               // Also update the local pickerApiLoaded let variable for createPicker
  //               pickerApiLoaded = status; 
  //           };
  //       }
  //       return () => {
  //           if (typeof window !== 'undefined') {
  //               delete window.setPickerApiLoaded;
  //           }
  //       };
  //   }, [setIsPickerReady]);

  // NEW DEFINITIVE INITIALIZATION EFFECT (Around Line 80)
useEffect(() => {
    const checkAndLoadPicker = () => {
        const isGisLoaded = typeof window.google?.accounts?.oauth2?.initTokenClient === 'function';
        const isGapiLoaded = typeof window.gapi?.load === 'function';

        if (isGapiLoaded && isGisLoaded) {
            // GIS is ready, now load the specific GAPI 'picker' module
            window.gapi.load('picker', () => {
                // All necessary global APIs are confirmed loaded and initialized.
                setIsPickerReady(true);
                // Update global flag for the createPicker function
                pickerApiLoaded = true;
                console.log("✅ Google Services (GIS + Picker) are fully ready.");
            });
        } else {
            // Not ready yet, poll briefly
            const timeout = setTimeout(checkAndLoadPicker, 250);
            return () => clearTimeout(timeout);
        }
    };

    checkAndLoadPicker();
    // No cleanup necessary for this polling, as it stops once ready (setIsPickerReady(true))
    // or when the component unmounts.
}, []); // Run only once on mount.

  // Compute active project from projects array
  const activeProject = useMemo(() => {
    if (!activeProjectId) return null;
    return projects.find(p => p.id === activeProjectId) || currentProject;
  }, [activeProjectId, projects, currentProject]);
  
  const createChatId = useCallback(() => {
    if (typeof window !== 'undefined' && window.crypto?.randomUUID) {
      return window.crypto.randomUUID();
    }
    return `chat-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
  }, []);
  
  const [chatId, setChatId] = useState(() => createChatId());
  const [activeChatId, setActiveChatId] = useState(() => chatId);
  const [chatSessions, setChatSessions] = useState([]);
  const [isLoadingChatHistory, setIsLoadingChatHistory] = useState(false);
  const [isBotTyping, setIsBotTyping] = useState(false); // Show typing indicator when waiting for bot response
  const [activeChatPreview, setActiveChatPreview] = useState('');
  const [activeChatUpdatedAt, setActiveChatUpdatedAt] = useState(null);
  
  // Dummy function to use activeChatUpdatedAt (prevents unused variable warning)
  const getActiveChatUpdatedAt = useCallback(() => {
    return activeChatUpdatedAt;
  }, [activeChatUpdatedAt]);
  
  const { user, logout, isAuthenticated, loading: authLoading } = useAuth();
  const navigate = useNavigate();

  const ensureChatId = () => {
    let currentId = chatId;
    if (!currentId) {
      currentId = createChatId();
      setChatId(currentId);
    }
    if (!activeChatId || activeChatId !== currentId) {
      setActiveChatId(currentId);
    }
    return currentId;
  };

  const fetchChatSessions = useCallback(async () => {
    if (!user?.email) return;
    try {
      const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/chat/sessions?user_email=${encodeURIComponent(user.email)}`, {
        method: 'GET',
        cache: 'no-cache'
      });
      if (!response.ok) {
        throw new Error(`Failed to load chat sessions: ${response.status}`);
      }
      const data = await response.json();
      if (data.success && Array.isArray(data.chats)) {
        // Sort by updated_at DESC (most recent first) as a fallback
        const sortedChats = [...data.chats].sort((a, b) => {
          const dateA = a.updated_at || a.last_message_at || '';
          const dateB = b.updated_at || b.last_message_at || '';
          return new Date(dateB).getTime() - new Date(dateA).getTime();
        });
        setChatSessions(sortedChats);
        const activeMatch = sortedChats.find((session) => session.chat_id === activeChatId);
        if (activeMatch) {
          if (!activeChatPreview && activeMatch.first_message_preview) {
            setActiveChatPreview(activeMatch.first_message_preview);
          }
          if (activeMatch.last_message_at || activeMatch.updated_at) {
            setActiveChatUpdatedAt(new Date(activeMatch.updated_at || activeMatch.last_message_at));
          }
        }
      }
    } catch (error) {
      console.error('Error fetching chat sessions:', error);
    }
  }, [user?.email, activeChatId, activeChatPreview]);

  const loadChatHistory = useCallback(async (targetChatId) => {
    if (!targetChatId || !user?.email) return;
    setIsLoadingChatHistory(true);
    try {
      const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
      const params = new URLSearchParams({
        chat_id: targetChatId,
        user_email: user.email
      });
      const response = await fetch(`${apiUrl}/api/chat/messages?${params.toString()}`, {
        method: 'GET',
        cache: 'no-cache'
      });
      if (!response.ok) {
        throw new Error(`Failed to load chat messages: ${response.status}`);
      }
      const data = await response.json();
      if (data.success && Array.isArray(data.messages)) {
        const formattedMessages = data.messages.map((msg) => {
          let messageText = msg.message || '';
          // Apply same formatting as new responses for consistency
          if (msg.role === 'assistant' && messageText.includes('```')) {
            messageText = messageText.replace(/```[a-zA-Z]*\s*\n?/g, '').replace(/```\s*\n?/g, '').trim();
          }
          return {
            text: messageText,
            type: msg.role === 'assistant' ? 'bot' : 'user',
            time: msg.created_at ? new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''
          };
        });
        setChatMessages(formattedMessages);
        setChatId(targetChatId);
        setActiveChatId(targetChatId);
        
        // Set current project if this conversation belongs to a project
        if (data.project) {
          setCurrentProject(data.project);
          setActiveProjectId(data.project.id);
        } else {
          setCurrentProject(null);
          setActiveProjectId(null);
        }
        
        fetchChatSessions();
        if (data.messages.length > 0) {
          // Find first user message for preview
          const firstUserMsg = data.messages.find(msg => msg.role === 'user');
          const previewText = firstUserMsg?.message || data.messages[0]?.message || '';
          const last = data.messages[data.messages.length - 1];
          setActiveChatPreview(previewText);
          setActiveChatUpdatedAt(last?.created_at ? new Date(last.created_at) : new Date());
          // Update saved label ref
          savedCurrentChatLabelRef.current = previewText || 'New chat';

          // Also update the preview for any matching project conversation in local state
          setProjects(prevProjects =>
            prevProjects.map(project => {
              if (!project.conversations) return project;
              const updatedConversations = project.conversations.map(conversation =>
                conversation.chat_id === targetChatId
                  ? {
                      ...conversation,
                      first_message_preview: previewText,
                    }
                  : conversation
              );
              return { ...project, conversations: updatedConversations };
            })
          );
        } else {
          setActiveChatPreview('');
          setActiveChatUpdatedAt(new Date());
          savedCurrentChatLabelRef.current = 'New chat';
        }
      }
    } catch (error) {
      console.error('Error loading chat history:', error);
    } finally {
      setIsLoadingChatHistory(false);
    }
  }, [user?.email, fetchChatSessions]);

  const formatChatPreview = useCallback(
    (previewText, emptyLabel = 'New conversation') => {
      const trimmed = (previewText || '').trim();
      if (!trimmed) {
        return emptyLabel;
      }
      const maxLength = 25;
      return trimmed.length > maxLength
        ? `${trimmed.slice(0, maxLength)}…`
        : trimmed;
    },
    []
  );

  const savedCurrentChatLabelRef = useRef('New chat');

  const currentChatTileLabel = useMemo(() => {
    const firstUserMessage = chatMessages.find((msg) => msg.type === 'user' && (msg.text || '').trim());
    const source = firstUserMessage?.text || activeChatPreview || '';
    const formatted = formatChatPreview(source, 'New chat');
    savedCurrentChatLabelRef.current = formatted;
    return formatted;
  }, [chatMessages, activeChatPreview, formatChatPreview]);

  // Real-time message saving helper
  const saveMessageToBackend = useCallback(async (chatId, role, message, userEmail) => {
    if (!chatId || !role || !message) return;
    
    try {
      const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
      const formData = new FormData();
      formData.append('chat_id', chatId);
      formData.append('role', role);
      formData.append('message', message);
      if (userEmail) {
        formData.append('user_email', userEmail);
      }
      
      const response = await fetch(`${apiUrl}/api/chat/save-message`, {
        method: 'POST',
        body: formData
      });
      
      if (!response.ok) {
        throw new Error(`Failed to save message: ${response.status}`);
      }
    } catch (error) {
      console.error('Error saving message to backend:', error);
    }
  }, []);

  // Save full conversation as JSON
  const saveConversationAsJSON = useCallback(async (chatId, messages, userEmail) => {
    if (!chatId || !messages || messages.length === 0) return;
    
    try {
      const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
      
      // Format messages as pairs: user and assistant together
      const formattedMessages = [];
      let messageId = 1;
      let currentPair = { message_id: messageId, user: "", assistant: "" };
      
      messages.forEach((msg) => {
        if (msg.type === 'user') {
          // If we have an incomplete pair, save it and start new one
          if (currentPair.user || currentPair.assistant) {
            formattedMessages.push({ ...currentPair });
            messageId++;
            currentPair = { message_id: messageId, user: "", assistant: "" };
          }
          currentPair.user = msg.text || "";
        } else if (msg.type === 'bot' || msg.type === 'assistant') {
          currentPair.assistant = msg.text || "";
          // After assistant message, save the pair
          formattedMessages.push({ ...currentPair });
          messageId++;
          currentPair = { message_id: messageId, user: "", assistant: "" };
        }
      });


      
      // If there's an incomplete pair (user without assistant), save it
      if (currentPair.user || currentPair.assistant) {
        formattedMessages.push(currentPair);
      }
      
      const conversationJSON = JSON.stringify({
        conversation_id: 1, // Will be updated by backend to actual id
        messages: formattedMessages
      });
      
      const formData = new FormData();
      formData.append('chat_id', chatId);
      formData.append('conversation_json', conversationJSON);
      if (userEmail) {
        formData.append('user_email', userEmail);
      }
      
      const response = await fetch(`${apiUrl}/api/chat/save-conversation`, {
        method: 'POST',
        body: formData
      });
      
      if (!response.ok) {
        throw new Error(`Failed to save conversation: ${response.status}`);
      }
    } catch (error) {
      console.error('Error saving conversation JSON:', error);
    }
  }, []);


   // Fetch mandatory files from backend
 // ✅ CORRECTED CODE BLOCK FOR fetchMandatoryFiles
// Fetch mandatory files from backend
const fetchMandatoryFiles = useCallback(async () => { // <--- ADDED useCallback
    try {
        const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
        const response = await fetch(`${apiUrl}/api/mandatory-files`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Defensive check - ensure data is valid
        if (data && data.success && Array.isArray(data.files)) {
            // Use functional update to prevent stale closures
            setMandatoryFiles(data.files);
        } else {
            console.error('Error fetching mandatory files:', data?.error || 'Invalid response');
            // Ensure we always have an array
            setMandatoryFiles([]);
        }
    } catch (error) {
        console.error('Error fetching mandatory files:', error);
        // Always set to empty array on error to prevent crashes
        setMandatoryFiles([]);
    }
}, []); // <--- ADDED EMPTY DEPENDENCY ARRAY to make the function stable

  // --- NEW CODE INSIDE const HomePage = () => { ... } (Insert starting around Line 321) ---

// // 1. OAuth Handler for the Drive Button Click (REPLACED FOR SILENT REFRESH)
// const initiateDriveUpload = useCallback((userEmail) => {
//     // ... (Initial checks remain unchanged)
//     if (!pickerApiLoaded || typeof window.google === 'undefined' || typeof window.google.accounts === 'undefined') {
//         alert("Google services are not ready yet. Please wait a moment.");
//         return;
//     }
    
//     if (!GOOGLE_CLIENT_ID || !DEVELOPER_API_KEY) { 
//         alert("Configuration Error: Google Client ID or API Key missing from environment variables.");
//         return;
//     }

//     // 1. Initialize the Token Client with the specific DRIVE_SCOPES
//     const tokenClient = window.google.accounts.oauth2.initTokenClient({
//         client_id: GOOGLE_CLIENT_ID,
//         scope: DRIVE_SCOPES, // Ensure this scope is requested!
//         callback: (tokenResponse) => {
//             if (tokenResponse && tokenResponse.access_token) {
//                 // SUCCESS: Token retrieved or silently refreshed.
//                 accessToken = tokenResponse.access_token;
//                 console.log("Token retrieved successfully. Launching Picker.");
//                 createPicker(userEmail); 
//             } else {
//                 // FAILURE: The token could not be retrieved silently.
//                 console.error("Token retrieval failed. Token response:", tokenResponse);
//                 alert("Authorization required. Please approve access to Google Drive in the new window.");
                
//                 // OPTIONAL: If the prompt: 'none' flow fails, we can try the interactive 
//                 // prompt again, but if the user is already signed in, this usually fixes it.
//                 // If this is still too aggressive, you could skip this step:
//                 // tokenClient.requestAccessToken({ prompt: 'consent' }); 
//             }
//         },
//     });

//     // 2. Attempt Silent Access Token Request
//     // We request the token silently first (prompt: 'none') to avoid the sign-in form.
//     // If successful, the callback fires and launches the picker without user prompt.
//     window.setTimeout(() => {
//         try {
//             tokenClient.requestAccessToken({ prompt: 'none' });
//             console.log("Attempting silent token refresh for Drive scope...");
//         } catch (e) {
//             console.error("Error during token request initiation:", e);
//             alert("Could not start silent token request.");
//         }
//     }, 100); 
// 1. OAuth Handler for the Drive Button Click (FINAL ROBUST VERSION)




// 4. UPDATED: Direct Handler to fix COOP/Popup blocking issues
const openChatDrivePicker = useCallback((e) => {
    if (e) e.stopPropagation();

    // 1. Mandatory Readiness Check
    if (!user?.email || !isPickerReady) {
        alert("Google Drive services are still loading. Please wait a moment.");
        return;
    }

    if (!GOOGLE_CLIENT_ID || !DEVELOPER_API_KEY) {
        alert("Configuration Error: Google Client ID or API Key missing.");
        return;
    }
    
    // --- SCENARIO A: Token is already in memory ---
    if (chatDriveAccessToken) {
        console.log("Chat Token available. Launching Picker.");
        chatPickerRef.current?.open(chatDriveAccessToken);
        return;
    }

    // --- SCENARIO B: Request Token directly (Fixes the COOP/Silent loop error) ---
    console.log("Initiating Google Login for Chat Drive...");

    const client = window.google.accounts.oauth2.initTokenClient({
        client_id: GOOGLE_CLIENT_ID,
        scope: DRIVE_SCOPES,
        callback: (tokenResponse) => {
            if (tokenResponse && tokenResponse.access_token) {
                chatTokenRef.current = tokenResponse.access_token;
                setChatDriveAccessToken(tokenResponse.access_token);
                console.log("✅ Token received. Launching Picker.");
                chatPickerRef.current?.open(tokenResponse.access_token);
            } else if (tokenResponse.error) {
                console.error("Token error:", tokenResponse.error);
            }
        },
    });

    // This opens the popup directly, which is more reliable for local development
    client.requestAccessToken(); 

}, [isPickerReady, user?.email]);


// Callback function triggered once files are selected (Sends to /api/process-multi-files)
const uploadChatDriveFiles = async (files, passedToken) => {
    if (!files.length) return;

    // Display file names in chat immediately for better UX
    files.forEach(file => {
      const fileMessage = {
        text: `📎 ${file.name} (from Drive)`,
        type: 'user',
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        isFile: true
      };
      setChatMessages(prev => [...prev, fileMessage]);
    });

    try {
      // NOTE: This assumes your backend has the /api/process-multi-files endpoint ready 
      // to handle {source: "google_drive"} and the access token (we will verify this in the backend step).
      const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/process-multi-files`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          // Pass the token to the backend for file download
          Authorization: `Bearer ${passedToken}` 
        },
        body: JSON.stringify({
          source: "google_drive", // CRITICAL: Identify source for backend
          files: files.map(f => ({
            drive_file_id: f.id, // Backend needs the drive ID
            name: f.name,
            mime_type: f.mimeType
          })),
          user_email: user.email // Pass user email
        })
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.error || "Drive upload failed");
      }

      // Display success/failure messages in the chat
      if (result.success && result.uploadedFileIds) {
        // Update state to track these files (they will override playbook for subsequent questions)
        setUploadedFileIds(prev => [
          ...prev,
          ...result.uploadedFileIds
        ]);
        setUploadedFileId(result.uploadedFileIds[result.uploadedFileIds.length - 1] || null);
        
        const successCount = result.uploadedFileIds.length;
        let summaryText = ""; 
        if (result.status === "reused") { 
            summaryText = "✅ File already exists. You can now ask questions directly.";
         } 
         else if (result.status === "mixed") { 
          summaryText = "✅ Some files already existed. You can now ask questions directly."; 
        } else { 
          summaryText = `✅ ${successCount}/${files.length} file(s) from Drive processed successfully! You can now ask questions about these documents.`; 
        }
        
        const summaryMessage = {
            text: summaryText,
            type: 'bot',
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setChatMessages(prev => [...prev, summaryMessage]);

        // Crucial: Clear playbook when files are uploaded to chat
        setPlaybookFileIds([]); 
        localStorage.removeItem('playbookFileIds'); 
      } else {
        const errorMessage = {
            text: result.error ? `❌ Drive processing error: ${result.error}` : "❌ Drive processing failed: Invalid response from server.",
            type: 'bot',
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setChatMessages(prev => [...prev, errorMessage]);
      }

    } catch (err) {
      console.error("Chat Drive upload error:", err);
      const errorMessage = {
          text: `❌ Error communicating with server: ${err.message}. Please check console.`,
          type: 'bot',
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setChatMessages(prev => [...prev, errorMessage]);
    }
}

const initiateDriveUpload = useCallback((userEmail) => {

    // 1. Mandatory Readiness Check: If false, the button SHOULD NOT even be clicked,
    // but if it is, this handles the user feedback.
    if (!userEmail || !isPickerReady) {
        console.error("GIS/Picker not ready or user unauthenticated.");
        alert("Google Drive services are still loading. Please wait a moment.");
        return; 
    }

    // ... (rest of configuration checks are fine)
    if (!GOOGLE_CLIENT_ID || !DEVELOPER_API_KEY) { 
        alert("Configuration Error: Google Client ID or API Key missing from environment variables.");
        return;
    }

    // --- SCENARIO A: Token is already in memory ('accessToken'). ---
    if (accessToken) {
        console.log("Token available in memory. Launching Picker directly.");
        templatePickerRef.current?.open(accessToken);
        setShowFileSourceModal(false);
        return;
    }

    // --- SCENARIO B: Token is missing. Start GIS flow. ---

    // Define the central callback function for both attempts
const handleTokenResponse = (tokenResponse) => {
    if (tokenResponse && tokenResponse.access_token) {
        // 1. Update React state and ref for subsequent uses
        accessTokenRef.current = tokenResponse.access_token;
        setAccessToken(tokenResponse.access_token);

        console.log("Token retrieved successfully. Launching Picker.");

        // 2. Close the selection modal
        setShowFileSourceModal(false);
        
        // 3. Open the templates picker with the fresh token
        templatePickerRef.current?.open(tokenResponse.access_token);
    } else if (tokenResponse.error === 'popup_closed_by_user') {
        console.warn("Authentication popup closed by user.");
    } else {
        // Trigger interactive login if silent fails
        const interactiveClient = window.google.accounts.oauth2.initTokenClient({
            client_id: GOOGLE_CLIENT_ID,
            scope: DRIVE_SCOPES,
            callback: handleTokenResponse, 
        });
        interactiveClient.requestAccessToken({ prompt: 'consent' });
    }
};

    // 2. Attempt SILENT Token Request (Synchronous)
    try {
        const tokenClient = window.google.accounts.oauth2.initTokenClient({
            client_id: GOOGLE_CLIENT_ID,
            scope: DRIVE_SCOPES,
            callback: handleTokenResponse,
        });

        console.log("Attempting silent token refresh/access (prompt: none).");

        // This is the critical synchronous call tied to the user gesture.
        tokenClient.requestAccessToken({ 
            prompt: 'none' // Try silently first to avoid re-login prompt
        }); 

    } catch (e) {
        console.error("Error during synchronous GIS initiation:", e);
        alert("Critical failure during Google service initiation. Check console.");
    }

    // Close the file source modal immediately *if* we failed to launch silently, 
    // to make way for the interactive pop-up (if launched inside the callback).
    // It's safer to let the handler manage closure (as above) to avoid the flicker.
    // We will rely on setShowFileSourceModal(false) inside the success path of the callback.

}, [isPickerReady, user?.email, accessToken]);
// Note: setShowFileSourceModal is not included in dependency array as it's a stable setter function.
// The explicit call to setShowFileSourceModal is moved inside the success path of handleTokenResponse.
// 2. Picker Callback Function Definition (defined as a standard const using useCallback)
const pickerCallback = useCallback((data, userEmail) => {
    if (data.action !== window.google.picker.Action.PICKED) return;

    const files = data.docs.map(file => ({
        id: file.id,
        name: file.name,
        mimeType: file.mimeType
    }));

    fetch(FASTAPI_DRIVE_UPLOAD_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            files,
            access_token: accessTokenRef.current,
            user_email: userEmail
        })
    })
    .then(res => res.json())
    .then(result => {
        console.log("DRIVE UPLOAD RESPONSE:", result);

        // --- FIX: your backend returns file_name, file_id, file_type ---
        const successfulFiles = result.files
            .filter(f => f.success)
            .map(f => ({
                id: f.file_id,
                name: f.file_name,
                mimeType: f.file_type,
                url: f.file_url || null
            }));

        if (successfulFiles.length === 0) return;

        // Update UI immediately
        setMandatoryFiles(prev => [...successfulFiles, ...prev]);

        // Refresh list from DB
        fetchMandatoryFiles();

        const ids = successfulFiles.map(f => f.id);
        setUploadedFileIds(prev => [...prev, ...ids]);
        setUploadedFileId(ids[ids.length - 1]);
    })
    .catch(err => {
        console.error("Drive Upload Error:", err);
    });

}, [fetchMandatoryFiles, setMandatoryFiles, setUploadedFileIds, setUploadedFileId]);

// --- END of Corrected Picker Callback Definition ---


// --- END NEW CODE INSIDE const HomePage = () => { ... } ---

  // Create chat record when new chat starts
  const createChatRecord = useCallback(async (chatId, userEmail) => {
    if (!chatId) return;
    
    try {
      const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
      const formData = new FormData();
      formData.append('chat_id', chatId);
      if (userEmail) {
        formData.append('user_email', userEmail);
      }
      
      const response = await fetch(`${apiUrl}/api/chat/create`, {
        method: 'POST',
        body: formData
      });
      
      if (!response.ok) {
        throw new Error(`Failed to create chat record: ${response.status}`);
      }
    } catch (error) {
      console.error('Error creating chat record:', error);
    }
  }, []);

  // --- DELETE FUNCTION (Stand-alone) ---
  const handleDeleteChat = async (e, chatIdToDelete) => {
    e.stopPropagation();
    if (!window.confirm("Are you sure you want to delete this chat history?")) return;
    try {
      const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/chat/${chatIdToDelete}`, { method: 'DELETE' });
      if (response.ok) {
        setChatSessions(prev => prev.filter(s => s.chat_id !== chatIdToDelete));
        if (activeChatId === chatIdToDelete) {
          setChatMessages([]);
          setActiveChatPreview('');
          setChatId(createChatId());
        }
        setToastMessage("Chat deleted");
        setToastVisible(true);
        setTimeout(() => setToastVisible(false), 2000);
      }
    } catch (error) { console.error("Error:", error); }
  };

  const handleNewChat = useCallback(async () => {
    // Reset projects view
    setShowProjectsView(false);
    // Clear project info for new chat
    setCurrentProject(null);
    setActiveProjectId(null);
    setActiveConversationId(null);
    // Save current conversation before creating new chat
    if (activeChatId && chatMessages.length > 0 && user?.email) {
      try {
        // Save the current conversation to database
        await saveConversationAsJSON(activeChatId, chatMessages, user.email);
      } catch (error) {
        console.error('Error saving conversation before new chat:', error);
      }
    }

    // Create new chat
    const newId = createChatId();
    setChatMessages([]);
    setChatId(newId);
    setActiveChatId(newId);
    setActiveChatPreview('');
    setActiveChatUpdatedAt(new Date());
    savedCurrentChatLabelRef.current = 'New chat';
    
    // Create chat record for new chat
    if (user?.email) {
      createChatRecord(newId, user.email);
    }
    
    // Refresh chat sessions to show updated list
    fetchChatSessions();
  }, [activeChatId, chatMessages, createChatId, fetchChatSessions, createChatRecord, saveConversationAsJSON, user?.email]);

  // Ensure mandatoryFiles is always an array
  useEffect(() => {
    if (!Array.isArray(mandatoryFiles)) {
      setMandatoryFiles([]);
    }
  }, [mandatoryFiles]);

  useEffect(() => {
    if (isAuthenticated && user?.email) {
      fetchChatSessions();
      // Create chat record for initial chat session
      if (chatId && user.email) {
        createChatRecord(chatId, user.email);
      }
    }
  }, [isAuthenticated, user?.email, fetchChatSessions, chatId, createChatRecord]);

  // SIMPLIFIED: Removed complex link handling - HTML links with target="_blank" work automatically

  // Fetch saved project knowledge base files from database on mount
  useEffect(() => {
    const fetchSavedKnowledgeBase = async () => {
      if (!user?.email) return;
      
      try {
        const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
        const response = await fetch(`${apiUrl}/api/project-knowledge-base?user_email=${encodeURIComponent(user.email)}`);
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.success && Array.isArray(data.file_ids)) {
          setFilesMarkedForProject(new Set(data.file_ids));
          console.log('📚 Loaded saved knowledge base files:', data.file_ids);
        }
      } catch (error) {
        console.error('Error fetching saved knowledge base:', error);
        // Fallback to localStorage if database fetch fails
        try {
          const saved = localStorage.getItem('filesMarkedForProject');
          if (saved) {
            const parsed = JSON.parse(saved);
            if (Array.isArray(parsed)) {
              setFilesMarkedForProject(new Set(parsed));
            }
          }
        } catch (localError) {
          console.error('Error loading from localStorage:', localError);
        }
      }
    };
    
    if (isAuthenticated && user) {
      fetchSavedKnowledgeBase();
    }
  }, [isAuthenticated, user]);

  // Save to localStorage as backup (not primary storage anymore)
  useEffect(() => {
    try {
      localStorage.setItem('filesMarkedForProject', JSON.stringify(Array.from(filesMarkedForProject)));
    } catch (error) {
      console.error('Error saving marked files to localStorage:', error);
    }
  }, [filesMarkedForProject]);


  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/');
    }
  }, [isAuthenticated, navigate]);


  // Auto-scroll chat to bottom when new messages are added
  useEffect(() => {
    if (chatMessages.length > 0) {
      const chatContent = document.querySelector('.chat-expanded-content');
      if (chatContent) {
        // Use setTimeout to ensure DOM is updated
        setTimeout(() => {
          chatContent.scrollTop = chatContent.scrollHeight;
        }, 100);
      }
    }
  }, [chatMessages]);

  // Handle chat drag events (mouse)
  useEffect(() => {
    if (!isDraggingChat) return;

    const onMouseMove = (e) => {
      const nextX = Math.max(8, e.clientX - dragOffset.x);
      const nextY = Math.max(8, e.clientY - dragOffset.y);

      // Constrain to viewport bounds so it doesn't go off-screen
      const maxX = window.innerWidth - 8;
      const maxY = window.innerHeight - 8;
      const clampedX = Math.min(nextX, maxX);
      const clampedY = Math.min(nextY, maxY);

      setChatUseCustomPosition(true);
      setChatPosition({ x: clampedX, y: clampedY });

      // Edge detection for top-left dock and enlarge
      const dockThreshold = 30;
      const shouldDock = clampedX <= dockThreshold && clampedY <= dockThreshold;
      setIsChatDockedTopLeft(shouldDock);
    };

    const onMouseUp = () => {
      setIsDraggingChat(false);
    };

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };
  }, [isDraggingChat, dragOffset]);

  // Handle chat resize events (mouse)
  useEffect(() => {
    if (!isResizingChat) return;

    const onMouseMove = (e) => {
      const minW = 300;
      const minH = 320;
      const maxW = Math.min(window.innerWidth - 32, 900);
      const maxH = Math.min(window.innerHeight - 32, 900);

      let nextLeft = resizeStart.left;
      let nextTop = resizeStart.top;
      let nextW = resizeStart.width;
      let nextH = resizeStart.height;
      const dx = e.clientX - resizeStart.mouseX;
      const dy = e.clientY - resizeStart.mouseY;

      if (resizeDirection === 'br') {
        nextW = resizeStart.width + dx;
        nextH = resizeStart.height + dy;
      } else if (resizeDirection === 'bl') {
        nextW = resizeStart.width - dx;
        nextLeft = resizeStart.left + dx;
        nextH = resizeStart.height + dy;
      } else if (resizeDirection === 'tr') {
        nextW = resizeStart.width + dx;
        nextH = resizeStart.height - dy;
        nextTop = resizeStart.top + dy;
      } else if (resizeDirection === 'tl') {
        nextW = resizeStart.width - dx;
        nextLeft = resizeStart.left + dx;
        nextH = resizeStart.height - dy;
        nextTop = resizeStart.top + dy;
      }

      nextW = Math.min(Math.max(nextW, minW), maxW);
      nextH = Math.min(Math.max(nextH, minH), maxH);

      // Constrain left/top within viewport when shrinking from left/top
      nextLeft = Math.max(8, Math.min(nextLeft, window.innerWidth - 8));
      nextTop = Math.max(8, Math.min(nextTop, window.innerHeight - 8));

      setChatUseCustomPosition(true);
      setChatPosition({ x: nextLeft, y: nextTop });
      setChatSize({ width: nextW, height: nextH });
    };

    const onMouseUp = () => setIsResizingChat(false);

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };
  }, [isResizingChat, resizeStart, resizeDirection]);
  
 


  // No-op effect to mark file-upload flags and dummy functions as used (silences no-unused-vars)
  useEffect(() => {
    void selectedFile;
    void isUploadingFile;
    // Reference dummy functions to prevent unused warnings
    void handleSelectedFileChange;
    void toggleUploadModal;
    void getActiveChatUpdatedAt;
  }, [selectedFile, isUploadingFile, handleSelectedFileChange, toggleUploadModal, getActiveChatUpdatedAt]);

  // Bot response function with predefined logic
  const getBotResponse = (userMessage) => {
    const message = userMessage.toLowerCase().trim();
    
    // Greeting responses
    if (message === 'hi' || message === 'hello' || message === 'hey' || message === 'hii') {
      return "Hello! How can I help you today?";
    }
    
    // Identity questions
    if (message.includes('who are you') || message.includes('what are you')) {
      return "I'm your PM Portal assistant 🤖.";
    }
    
    // Help requests
    if (message.includes('help') || message.includes('support')) {
      return "I'm here to help! You can ask me questions about the PM Portal features, or I can assist with sprint planning and risk assessments.";
    }
    
    // Default response for unrecognized messages
    return "I didn't quite get that. Can you rephrase?";
  };

  // Sanitize/format bot text: remove markdown code fences like ```html, convert newlines, and make links clickable
  const formatBotResponse = (rawText) => {
    const original = typeof rawText === 'string' ? rawText : '';
    
    // Debug logging
    if (original.includes('```')) {
      console.log('📝 [FORMAT] Detected markdown code blocks in response');
      console.log('📝 [FORMAT] Original (first 500 chars):', original.substring(0, 500));
    }
    
    let formatted = original
      // Remove opening code fences with optional language (handle multiline)
      .replace(/```[a-zA-Z]*\s*\n?/g, '')
      // Remove closing code fences (handle multiline)
      .replace(/```\s*\n?/g, '')
      // Trim any leading/trailing whitespace
      .trim();
    
    // Debug logging after formatting
    if (original.includes('```')) {
      console.log('📝 [FORMAT] After removing code blocks (first 500 chars):', formatted.substring(0, 500));
    }
    
    // Convert markdown-style links [text](url) to HTML links
    formatted = formatted.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, text, url) => {
      // Escape HTML in the link text
      const escapedText = text.replace(/</g, '&lt;').replace(/>/g, '&gt;');
      // Ensure URL is properly encoded and has protocol if needed
      let cleanUrl = url.trim();
      if (!cleanUrl.startsWith('http://') && !cleanUrl.startsWith('https://') && !cleanUrl.startsWith('mailto:')) {
        cleanUrl = 'https://' + cleanUrl;
      }
      return `<a href="${cleanUrl}" target="_blank" rel="noopener noreferrer" class="external-link" style="color: #3b82f6; text-decoration: underline; cursor: pointer;">${escapedText}</a>`;
    });
    
    // Convert plain URLs to clickable links
    // Match common URL patterns: http://, https://, www., or domain.com patterns
    // Process in order: full URLs first, then www., then domain patterns
    const urlPatterns = [
      // Full URLs with protocol (process first)
      { pattern: /(https?:\/\/[^\s<>"{}|\\^`[\]()]+)/g, priority: 1 },
      // www. URLs (process second)
      { pattern: /(www\.[^\s<>"{}|\\^`[\]()]+)/g, priority: 2 },
      // Domain patterns (process last, most generic)
      { pattern: /([a-zA-Z0-9][a-zA-Z0-9-]{0,61}[a-zA-Z0-9]?\.[a-zA-Z]{2,}(?::[0-9]{1,5})?(?:\/[^\s<>"{}|\\^`[\]()]*)?)/g, priority: 3 }
    ];
    
    // Process each URL pattern in priority order
    urlPatterns.forEach(({ pattern }) => {
      const urlMatches = [];
      let match;
      let searchStart = 0;
      
      // Find all matches, avoiding already-processed areas
      while ((match = pattern.exec(formatted)) !== null) {
        // Skip if match is before our search start (already processed)
        if (match.index < searchStart) {
          continue;
        }
        
        urlMatches.push({
          url: match[0],
          index: match.index
        });
      }
      
      // Process matches in reverse order to maintain indices
      for (let i = urlMatches.length - 1; i >= 0; i--) {
        const { url, index } = urlMatches[i];
        
        // Skip if URL is already inside an HTML tag
        const beforeUrl = formatted.substring(0, index);
        const lastOpenTag = beforeUrl.lastIndexOf('<a');
        const lastCloseTag = beforeUrl.lastIndexOf('</a>');
        
        if (lastOpenTag > lastCloseTag) {
          continue; // Already inside a link tag, skip
        }
        
        // Skip if URL is inside HTML attributes
        const beforeContext = beforeUrl.substring(Math.max(0, beforeUrl.length - 100));
        if (beforeContext.includes('href="') || beforeContext.includes("href='") || 
            beforeContext.includes('src="') || beforeContext.includes("src='") ||
            beforeContext.includes('url(') || beforeContext.includes('url("')) {
          continue; // Inside an HTML attribute, skip
        }
        
        // Remove trailing punctuation from URL (periods, commas, etc. that are not part of the URL)
        let cleanUrl = url;
        const trailingPunctuation = /[.,;:!?)]+$/;
        const trailingMatch = cleanUrl.match(trailingPunctuation);
        let trailingPunct = '';
        // Check if URL ends with a common TLD (these shouldn't have trailing punctuation removed)
        const commonTlds = /\.(com|org|net|io|edu|gov|co|uk|us|au|ca|de|fr|it|es|nl|be|ch|at|se|no|dk|fi|pl|cz|ie|pt|gr|ru|jp|cn|kr|in|br|mx|ar|za|nz|sg|hk|tw|my|th|ph|id|vn|tr|ae|sa|il|eg|ma|ng|ke|gh|tz|ug|et|zw|bw|na|mu|sc|mg|rw|bi|dj|er|so|sd|ly|tn|dz|mr|ml|ne|td|cm|cf|cg|cd|ga|gq|st|ao|gw|gn|sl|lr|ci|bf|bj|tg|gm|gu|link|info|xyz|online|site|website|tech|app|dev|ai|cloud|digital|online|store|shop|blog|news|media|tv|live|space|email|email|name|pro|biz|mobi|tel|asia|jobs|travel|xxx|xxx|xxx|xxx)$/i;
        if (trailingMatch && !commonTlds.test(cleanUrl)) {
          trailingPunct = trailingMatch[0];
          cleanUrl = cleanUrl.replace(trailingPunctuation, '');
        }
        
        // Ensure URL has protocol
        let href = cleanUrl;
        if (!cleanUrl.startsWith('http://') && !cleanUrl.startsWith('https://')) {
          href = 'https://' + cleanUrl;
        }
        
        // Escape HTML in the URL for display
        const displayUrl = cleanUrl.replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
        
        const linkHtml = `<a href="${href}" target="_blank" rel="noopener noreferrer" class="external-link" style="color: #3b82f6; text-decoration: underline; word-break: break-all; cursor: pointer;">${displayUrl}</a>${trailingPunct}`;
        
        formatted = formatted.substring(0, index) + linkHtml + formatted.substring(index + url.length);
      }
    });
    
    // Convert newlines to <br/> (do this last to preserve line breaks)
    formatted = formatted.replace(/\n/g, '<br/>');
    
    return formatted;
  };

  // Helper function to add user message and bot response
  const addMessageWithBotResponse = async (userText) => {
    const trimmedQuestion = userText.trim();
    const userMessage = {
      text: trimmedQuestion,
      type: 'user',
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    
    // Add user message
    setChatMessages(prev => [...prev, userMessage]);
    setIsBotTyping(true); // Show typing indicator
    const messageTimestamp = new Date();
    setActiveChatPreview((prev) => prev || trimmedQuestion);
    setActiveChatUpdatedAt(messageTimestamp);

    // If this chat belongs to a project conversation and doesn't yet have a preview,
    // update the in-memory projects state so the sidebar shows the first message.
    setProjects(prevProjects =>
      prevProjects.map(project => {
        if (!project.conversations) return project;
        const updatedConversations = project.conversations.map(conversation =>
          conversation.chat_id === activeChatId && !conversation.first_message_preview
            ? {
                ...conversation,
                first_message_preview: trimmedQuestion,
              }
            : conversation
        );
        return { ...project, conversations: updatedConversations };
      })
    );
    
    // Debug: Log current state
    console.log('🔍 [FRONTEND] Question asked:', trimmedQuestion);
    console.log('🔍 [FRONTEND] Current state - uploadedFileId:', uploadedFileId, 'uploadedFileIds:', uploadedFileIds, 'playbookFileIds:', playbookFileIds);
    
    const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
    const activeChatSessionId = ensureChatId();
    setActiveChatId(activeChatSessionId);
    
    // Save user message in real-time
    if (user?.email) {
      saveMessageToBackend(activeChatSessionId, 'user', trimmedQuestion, user.email);
    }
    
    // Priority: 1. Uploaded file, 2. Playbook from Start a Project (default), 3. Predefined responses
    if (uploadedFileId || uploadedFileIds.length > 0) {
      console.log('📁 [FRONTEND] Using uploaded file(s)');
      // Use uploaded file(s) - highest priority
      const fileIdToUse = uploadedFileId || uploadedFileIds[uploadedFileIds.length - 1];
      // Use uploaded file (highest priority)
      try {
        const formData = new FormData();
        formData.append('question', trimmedQuestion);
        formData.append('file_id', fileIdToUse);
        formData.append('chat_id', activeChatSessionId);
        if (user?.email) {
          formData.append('user_email', user.email);
        }
        
        const response = await fetch(`${apiUrl}/api/ask-question`, {
          method: 'POST',
          body: formData
        });
        
        const data = await response.json();
        if (data.chat_id && data.chat_id !== chatId) {
          setChatId(data.chat_id);
          setActiveChatId(data.chat_id);
        }
        
        if (data.success && data.response) {
          // Use formatBotResponse for consistent formatting (same as normal chats)
          let responseText = formatBotResponse(data.response);
          
          const botResponse = {
            text: responseText,
            type: 'bot',
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          };
          
          setChatMessages(prev => {
            const updated = [...prev, botResponse];
            // Save bot message in real-time and update conversation JSON
            if (user?.email) {
              saveMessageToBackend(activeChatSessionId, 'assistant', responseText, user.email);
              saveConversationAsJSON(activeChatSessionId, updated, user.email);
            }
            return updated;
          });
          setActiveChatUpdatedAt(new Date());
        } else {
          const botResponse = {
            text: data.error || 'Sorry, I encountered an error. Please try again.',
            type: 'bot',
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          };
          setChatMessages(prev => {
            const updated = [...prev, botResponse];
            // Save error message in real-time
            if (user?.email) {
              saveMessageToBackend(activeChatSessionId, 'assistant', data.error || 'Sorry, I encountered an error. Please try again.', user.email);
            }
            return updated;
          });
          setActiveChatUpdatedAt(new Date());
        }
      } catch (error) {
        const botResponse = {
          text: `Sorry, there was an error: ${error.message}. Please try again.`,
          type: 'bot',
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setChatMessages(prev => {
          const updated = [...prev, botResponse];
          // Save error message in real-time
          if (user?.email) {
            saveMessageToBackend(activeChatSessionId, 'assistant', `Sorry, there was an error: ${error.message}. Please try again.`, user.email);
          }
          return updated;
        });
        setActiveChatUpdatedAt(new Date());
      } finally {
        setIsBotTyping(false); // Hide typing indicator
        fetchChatSessions();
      }
    } else if (playbookFileIds.length > 0) {
      // Use playbook from Start a Project
      console.log('📚 [FRONTEND] Using playbook files:', playbookFileIds);
      try {
        // Fetch playbook files with their extracted text
        console.log('📚 [FRONTEND] Fetching playbook files from API...');
        const filesResponse = await fetch(`${apiUrl}/api/mandatory-files?include_content=true`, {
          method: 'GET',
          cache: 'no-cache'
        });
        
        if (!filesResponse.ok) {
          throw new Error(`Failed to fetch files: ${filesResponse.status}`);
        }
        
        const filesData = await filesResponse.json();
        console.log('📚 [FRONTEND] Received files data:', filesData.success ? `${filesData.files?.length || 0} files` : 'Failed');
        
        if (!filesData.success || !Array.isArray(filesData.files)) {
          throw new Error('Invalid response from files API');
        }
        
        // Filter and combine extracted text from playbook files
        const playbookFiles = filesData.files.filter(file => 
          file.id && playbookFileIds.includes(file.id) && file.extracted_text
        );
        
        console.log('📚 [FRONTEND] Filtered playbook files:', playbookFiles.length, 'files with content');
        
        if (playbookFiles.length === 0) {
          throw new Error('Playbook files not found or have no content');
        }
        
        // Combine extracted text from all playbook files
        const combinedContext = playbookFiles.map((file, index) => {
          const fileHeader = `\n\n=== DOCUMENT ${index + 1}: ${file.file_name} ===\n`;
          return fileHeader + (file.extracted_text || '');
        }).join('\n\n');
        
        console.log('📚 [FRONTEND] Combined context length:', combinedContext.length, 'characters');
        console.log('📚 [FRONTEND] Sending question to backend with playbook context...');
        
        // Send question with playbook context
        const questionFormData = new FormData();
        questionFormData.append('question', trimmedQuestion);
        // questionFormData.append('file_context', combinedContext);
        questionFormData.append('mandatory_file_ids', JSON.stringify(playbookFileIds));
        questionFormData.append('chat_id', activeChatSessionId);
        if (user?.email) {
          questionFormData.append('user_email', user.email);
        }
        
        const response = await fetch(`${apiUrl}/api/ask-question`, {
          method: 'POST',
          body: questionFormData
        });
        
        const data = await response.json();
        if (data.chat_id && data.chat_id !== chatId) {
          setChatId(data.chat_id);
          setActiveChatId(data.chat_id);
        }
        
        if (data.success && data.response) {
          // Use formatBotResponse for consistent formatting (same as normal chats)
          let responseText = formatBotResponse(data.response);
          
          const botResponse = {
            text: responseText,
            type: 'bot',
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          };
          
          setChatMessages(prev => {
            const updated = [...prev, botResponse];
            // Save bot message in real-time and update conversation JSON
            if (user?.email) {
              saveMessageToBackend(activeChatSessionId, 'assistant', responseText, user.email);
              saveConversationAsJSON(activeChatSessionId, updated, user.email);
            }
            return updated;
          });
          setActiveChatUpdatedAt(new Date());
        } else {
          const botResponse = {
            text: data.error || 'Sorry, I encountered an error. Please try again.',
            type: 'bot',
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          };
          setChatMessages(prev => {
            const updated = [...prev, botResponse];
            // Save error message in real-time
            if (user?.email) {
              saveMessageToBackend(activeChatSessionId, 'assistant', data.error || 'Sorry, I encountered an error. Please try again.', user.email);
            }
            return updated;
          });
          setActiveChatUpdatedAt(new Date());
        }
      } catch (error) {
        const botResponse = {
          text: `Sorry, there was an error: ${error.message}. Please try again.`,
          type: 'bot',
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setChatMessages(prev => {
          const updated = [...prev, botResponse];
          // Save error message in real-time
          if (user?.email) {
            saveMessageToBackend(activeChatSessionId, 'assistant', `Sorry, there was an error: ${error.message}. Please try again.`, user.email);
          }
          return updated;
        });
        setActiveChatUpdatedAt(new Date());
      } finally {
        setIsBotTyping(false); // Hide typing indicator
        fetchChatSessions();
      }
    } else {
      // No file uploaded and no playbook, rely on backend knowledge base/router
      console.log('⚠️ [FRONTEND] No files or playbook available, sending question to backend');
      try {
        const fallbackFormData = new FormData();
        fallbackFormData.append('question', trimmedQuestion);
        fallbackFormData.append('chat_id', activeChatSessionId);
        if (user?.email) {
          fallbackFormData.append('user_email', user.email);
        }

        const response = await fetch(`${apiUrl}/api/ask-question`, {
          method: 'POST',
          body: fallbackFormData
        });

        const data = await response.json();
        if (data.chat_id && data.chat_id !== chatId) {
          setChatId(data.chat_id);
          setActiveChatId(data.chat_id);
        }

        if (data.success && data.response) {
          // Use formatBotResponse for consistent formatting (same as normal chats)
          let responseText = formatBotResponse(data.response);
          const botResponse = {
            text: responseText,
            type: 'bot',
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          };
          setChatMessages(prev => {
            const updated = [...prev, botResponse];
            // Save bot message in real-time and update conversation JSON
            if (user?.email) {
              saveMessageToBackend(activeChatSessionId, 'assistant', responseText, user.email);
              saveConversationAsJSON(activeChatSessionId, updated, user.email);
            }
            return updated;
          });
          setActiveChatUpdatedAt(new Date());
        } else {
          const fallbackText = formatBotResponse(data.error || getBotResponse(trimmedQuestion));
          const botResponse = {
            text: fallbackText,
            type: 'bot',
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          };
          setChatMessages(prev => {
            const updated = [...prev, botResponse];
            // Save bot message in real-time and update conversation JSON
            if (user?.email) {
              saveMessageToBackend(activeChatSessionId, 'assistant', fallbackText, user.email);
              saveConversationAsJSON(activeChatSessionId, updated, user.email);
            }
            return updated;
          });
          setActiveChatUpdatedAt(new Date());
        }
      } catch (error) {
        const fallbackText = `Sorry, there was an error: ${error.message}. Please try again.`;
        const botResponse = {
          text: fallbackText,
          type: 'bot',
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setChatMessages(prev => {
          const updated = [...prev, botResponse];
          // Save error message in real-time
          if (user?.email) {
            saveMessageToBackend(activeChatSessionId, 'assistant', fallbackText, user.email);
          }
          return updated;
        });
        setActiveChatUpdatedAt(new Date());
      } finally {
        setIsBotTyping(false); // Hide typing indicator
        fetchChatSessions();
      }
    }
  };

  // Handle file selection (stores files, doesn't upload immediately)
  const handleFileSelect = (event) => {
    const newFiles = Array.from(event.target.files || []);
    if (!newFiles || newFiles.length === 0) return;
    
    // Combine with existing selected files
    const combinedFiles = [...selectedFiles, ...newFiles];
    
    // Limit to 5 files total
    if (combinedFiles.length > 5) {
      const botResponse = {
        text: `❌ Maximum 5 files allowed. You already have ${selectedFiles.length} file(s) selected. Please select up to ${5 - selectedFiles.length} more file(s).`,
        type: 'bot',
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setChatMessages(prev => [...prev, botResponse]);
      event.target.value = '';
      return;
    }
    
    // Add new files to selected files
    setSelectedFiles(combinedFiles);
    setShowAttachMenu(false);
    
    // Reset file input to allow selecting more files
    event.target.value = '';
  };

  // Remove a file from selected files
  const handleRemoveSelectedFile = (indexToRemove) => {
    setSelectedFiles(prev => prev.filter((_, index) => index !== indexToRemove));
  };

  // Upload selected files
  const handleUploadSelectedFiles = async () => {
    if (selectedFiles.length === 0) return;
    
    setIsUploadingFile(true);
    const uploadedIds = [];
    const failedFiles = [];
    
    // Display file names in chat
    selectedFiles.forEach(file => {
      const fileMessage = {
        text: `📎 ${file.name}`,
        type: 'user',
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        isFile: true
      };
      setChatMessages(prev => [...prev, fileMessage]);
    });
    
    try {
      // Upload all files in a single request
      const formData = new FormData();
      selectedFiles.forEach(file => {
        formData.append('files', file);
      });
      if (user?.email) {
        formData.append('uploaded_by', user.email);
      }
      
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/upload-file`, {
        method: 'POST',
        body: formData
      });
      
      const data = await response.json();
      
      if (data.success && data.files) {
        // Process each file result
        data.files.forEach((fileResult, index) => {
          const fileName =
            fileResult.file_name || selectedFiles[index]?.name || 'Unknown file';
          if (fileResult.success) {
            uploadedIds.push(fileResult.file_id);
            let messageText;

            if (fileResult.status === "reused") {
                messageText = `ℹ️ File "${fileName}" already exists. You can directly ask questions about it.`;
          } else {
                messageText = `✅ File "${fileName}" uploaded successfully!`;
          }
            //const fileName = fileResult.file_name || selectedFiles[index]?.name || 'Unknown file';
            const botResponse = {
              text: messageText,
              type: 'bot',
              time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            };
            setChatMessages(prev => [...prev, botResponse]);
          } else {
            //const fileName = fileResult.file_name || selectedFiles[index]?.name || 'Unknown file';
            failedFiles.push(fileName);
            const botResponse = {
              text: `❌ Failed to upload "${fileName}": ${fileResult.error || 'Unknown error'}`,
              type: 'bot',
              time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            };
            setChatMessages(prev => [...prev, botResponse]);
          }
        });
        
        // Update state with uploaded file IDs
        if (uploadedIds.length > 0) {
          setUploadedFileIds(prev => [...prev, ...uploadedIds]);
          // Also set the last uploaded file ID for backward compatibility
          setUploadedFileId(uploadedIds[uploadedIds.length - 1]);
          // Note: Keep playbookFileIds - uploaded files take priority, but playbook remains as fallback
          // Playbook will be used automatically if uploaded files are removed
        }
        
        // Show summary message
        if (data.successful_uploads === selectedFiles.length) {
          const summaryMessage = {
            text: `✅ All ${data.successful_uploads} file(s) uploaded successfully! You can now ask questions about these documents.`,
            type: 'bot',
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          };
          setChatMessages(prev => [...prev, summaryMessage]);
        } else if (data.successful_uploads > 0) {
          const summaryMessage = {
            text: `✅ ${data.successful_uploads} file(s) uploaded successfully. ${data.failed_uploads} file(s) failed.`,
            type: 'bot',
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          };
          setChatMessages(prev => [...prev, summaryMessage]);
        }
      } else {
        // Overall request failed
        const errorMessage = {
          text: `❌ Upload failed: ${data.error || 'Unknown error'}`,
          type: 'bot',
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setChatMessages(prev => [...prev, errorMessage]);
      }
    } catch (error) {
      // Network or other errors
      const errorMessage = {
        text: `❌ Error uploading files: ${error.message}`,
        type: 'bot',
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setChatMessages(prev => [...prev, errorMessage]);
    }
    
    setIsUploadingFile(false);
    setSelectedFiles([]);
  };

  // Handle Start a Project button click
  const handleStartProject = async (e, moduleName = null) => {
    e.stopPropagation();
    
    // Add loading message with unique identifier
    const loadingMessageId = `loading-${Date.now()}`;
    const loadingMessage = {
      id: loadingMessageId,
      text: moduleName === 'PM Template' ? 'Loading ...' : 'Starting project analysis...',
      type: 'bot',
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    setChatMessages(prev => [...prev, loadingMessage]);
    
    try {
      const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
      // const question = "As a PM of new project, what steps you recommend ?";
      const question =
      moduleName === 'PM Template'
        ? 'As a PM of new project, what steps you recommend ?'
        : `I am a new Project Manager.Based on the Project Management Playbook, explain how to start and run a project.Cover project phases, PM responsibilities, and key deliverables concisely.`;
      
      // Step 1: Get all marked files for project use, or use all mandatory files as default
      let markedFileIds = Array.from(filesMarkedForProject);
      
      // If PM Template is clicked, filter files by selected module
      if (moduleName === 'PM Template') {
        // Get files that have "PM Template" selected as their module
        const pmTemplateFileIds = Array.from(fileModules.entries())
          .filter(([fileId, module]) => module === 'PM Template')
          .map(([fileId]) => fileId);
        
        // Only use files that are both marked for project AND have PM Template selected
        markedFileIds = markedFileIds.filter(fileId => pmTemplateFileIds.includes(fileId));
        
        console.log('📋 PM Template: Filtering files by module. Found', markedFileIds.length, 'file(s) with PM Template selected');
        
        // If no files found with PM Template, show error
        if (markedFileIds.length === 0) {
          setChatMessages(prev => prev.filter(msg => msg.id !== loadingMessageId));
          const errorMessage = {
            text: formatBotResponse('⚠️ No files found with "PM Template" module selected. Please select "PM Template" for files in the Mandatory Files section.'),
            type: 'bot',
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          };
          setChatMessages(prev => [...prev, errorMessage]);
          return;
        }
      } else {
        // For "Start a Project", use existing logic unchanged
        // If no files marked, automatically use all mandatory files as default playbook
        if (markedFileIds.length === 0) {
          const filesResponse = await fetch(`${apiUrl}/api/mandatory-files`, {
            method: 'GET',
            cache: 'no-cache'
          });
          
          if (filesResponse.ok) {
            const filesData = await filesResponse.json();
            if (filesData.success && Array.isArray(filesData.files) && filesData.files.length > 0) {
              // Use all active mandatory files as default playbook
              const pmPlaybookFile = filesData.files.find(
                file =>
                  file.file_name?.toLowerCase().includes(
                    'project management playbook'
                  )
                );

                  if (!pmPlaybookFile) {
                    throw new Error(
                      'Project Management Playbook not found or not processed'
                    );
                  }
                markedFileIds = [pmPlaybookFile.id];  
              // markedFileIds = filesData.files
              //   .filter(file => file.id && file.is_active !== false)
              //   .map(file => file.id);
              
              console.log('📚 Using default playbook with', markedFileIds.length, 'file(s)');
            }
          }
          
          // If still no files found, show error
          if (markedFileIds.length === 0) {
            setChatMessages(prev => prev.filter(msg => msg.id !== loadingMessageId));
            const errorMessage = {
              text: formatBotResponse('⚠️ No mandatory files available. Please upload at least one file in the Mandatory Files section.'),
              type: 'bot',
              time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            };
            setChatMessages(prev => [...prev, errorMessage]);
            return;
          }
        }
      }
      
      // Step 2: Fetch all marked files with their extracted text
      console.log('📁 Fetching marked files for project:', markedFileIds);
      const filesResponse = await fetch(`${apiUrl}/api/mandatory-files?include_content=true`, {
        method: 'GET',
        cache: 'no-cache'
      });
      
      if (!filesResponse.ok) {
        throw new Error(`Failed to fetch files: ${filesResponse.status}`);
      }
      
      const filesData = await filesResponse.json();
      
      if (!filesData.success || !Array.isArray(filesData.files)) {
        throw new Error('Invalid response from files API');
      }
      
      // Step 3: Filter and combine extracted text from marked files
      const markedFiles = filesData.files.filter(file => 
        file.id && markedFileIds.includes(file.id) && file.extracted_text
      );
      
      // Log file details for debugging
      markedFiles.forEach(file => {
        console.log(`📄 File: ${file.file_name} (ID: ${file.id})`);
        console.log(`   Content length: ${file.extracted_text ? file.extracted_text.length : 0} characters`);
        console.log(`   Has content: ${!!file.extracted_text}`);
      });
      
      if (markedFiles.length === 0) {
        setChatMessages(prev => prev.filter(msg => msg.id !== loadingMessageId));
        const errorMessage = {
          text: formatBotResponse('⚠️ No valid file content found in marked files. Please ensure files have been processed and contain extracted text.'),
          type: 'bot',
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setChatMessages(prev => [...prev, errorMessage]);
        return;
      }
      
      // Combine extracted text from all marked files
      const combinedContext = markedFiles.map((file, index) => {
        const fileHeader = `\n\n=== DOCUMENT ${index + 1}: ${file.file_name} ===\n`;
        const fileContent = file.extracted_text || '';
        console.log(`📝 File ${index + 1} (${file.file_name}): ${fileContent.length} characters`);
        
        // Warn if content seems incomplete (very short for a file)
        if (fileContent.length < 100 && file.file_size > 10000) {
          console.warn(`⚠️ File ${file.file_name} has very short extracted text (${fileContent.length} chars) but large file size (${file.file_size} bytes). Extraction might be incomplete.`);
        }
        
        return fileHeader + fileContent;
      }).join('\n\n');
      
      console.log(`📝 Combined context from ${markedFiles.length} file(s), total length: ${combinedContext.length} characters`);
      console.log(`📝 First 500 chars of combined context: ${combinedContext.substring(0, 500)}...`);
      console.log(`📝 Last 500 chars of combined context: ...${combinedContext.substring(Math.max(0, combinedContext.length - 500))}`);
      
      // Verify we have substantial content
      if (combinedContext.length < 100) {
        setChatMessages(prev => prev.filter(msg => msg.id !== loadingMessageId));
        const errorMessage = {
          text: formatBotResponse('⚠️ The selected files have very little extracted content. Please ensure files have been properly processed. You may need to re-upload the files.'),
          type: 'bot',
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setChatMessages(prev => [...prev, errorMessage]);
        return;
      }
      
      // Step 4: Send question with combined context to backend
      const currentChatId = ensureChatId();
      const questionFormData = new FormData();
      questionFormData.append('question', question);
      // questionFormData.append('file_context', combinedContext);
      questionFormData.append('mandatory_file_ids', JSON.stringify(markedFileIds));
      questionFormData.append('chat_id', currentChatId);
      if (user?.email) {
        questionFormData.append('user_email', user.email);
      }
      
      const questionResponse = await fetch(`${apiUrl}/api/ask-question`, {
        method: 'POST',
        body: questionFormData
      });
      
      const questionData = await questionResponse.json();
      
      // Remove loading message
      setChatMessages(prev => prev.filter(msg => msg.id !== loadingMessageId));
      
      // Step 5: Display user message (the question) - Skip for PM Template
      if (moduleName !== 'PM Template') {
        const userMessage = {
          text: question,
          type: 'user',
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setChatMessages(prev => [...prev, userMessage]);
      }
      
      // Step 6: Display bot response
      if (questionData.success) {
        // Store playbook file IDs for subsequent questions (persists across sessions)
        setPlaybookFileIds(markedFileIds);
        localStorage.setItem('playbookFileIds', JSON.stringify(markedFileIds));
        // Clear uploadedFileId so questions use playbook
        setUploadedFileId(null);
        setUploadedFileIds([]);
        
        // Ensure we're using the response field, not the file context
        const responseText = questionData.response || questionData.message || 'No response received';
        
        // Remove markdown code blocks if present
        let cleanedResponse = responseText;
        if (cleanedResponse.includes('```')) {
          cleanedResponse = cleanedResponse.replace(/```[a-zA-Z]*\s*\n?/g, '').replace(/```\s*\n?/g, '').trim();
        }
        
        const botResponse = {
          text: cleanedResponse,
          type: 'bot',
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setChatMessages(prev => [...prev, botResponse]);
      } else {
        const botResponse = {
          text: `I'm sorry, I encountered an error: ${questionData.error || 'Unknown error'}`,
          type: 'bot',
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setChatMessages(prev => [...prev, botResponse]);
      }
    } catch (error) {
      // Remove loading message
      setChatMessages(prev => prev.filter(msg => msg.id !== loadingMessageId));
      
      const errorMessage = {
        text: formatBotResponse(`Error starting project: ${error.message}. Please try again.`),
        type: 'bot',
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setChatMessages(prev => [...prev, errorMessage]);
    }
  };


  // Load mandatory files on component mount
  useEffect(() => {
    fetchMandatoryFiles();
  }, []);

  // Initialize default playbook on component mount if not already set
  useEffect(() => {
    const initializeDefaultPlaybook = async () => {
      // Only initialize if no playbook is set and no file is uploaded
      if (playbookFileIds.length === 0 && !uploadedFileId && uploadedFileIds.length === 0) {
        try {
          const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
          const response = await fetch(`${apiUrl}/api/mandatory-files`);
          
          if (response.ok) {
            const data = await response.json();
            if (data && data.success && Array.isArray(data.files) && data.files.length > 0) {
              // Use all mandatory files as default playbook
              const allMandatoryFileIds = data.files
                .filter(file => file.id && file.is_active !== false)
                .map(file => file.id);
              
              if (allMandatoryFileIds.length > 0) {
                setPlaybookFileIds(allMandatoryFileIds);
                localStorage.setItem('playbookFileIds', JSON.stringify(allMandatoryFileIds));
                console.log('📚 Default playbook initialized with', allMandatoryFileIds.length, 'file(s):', allMandatoryFileIds);
              } else {
                console.log('⚠️ No active mandatory files found for default playbook');
              }
            }
          }
        } catch (error) {
          console.error('Error initializing default playbook:', error);
        }
      }
    };

    initializeDefaultPlaybook();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Run only once on mount - intentionally excluding dependencies

  // Persist playbookFileIds to localStorage whenever it changes
  useEffect(() => {
    try {
      if (playbookFileIds.length > 0) {
        localStorage.setItem('playbookFileIds', JSON.stringify(playbookFileIds));
      } else {
        localStorage.removeItem('playbookFileIds');
      }
    } catch (error) {
      console.error('Error saving playbookFileIds to localStorage:', error);
    }
  }, [playbookFileIds]);

  // Handle mandatory file upload
  const handleUploadMandatoryFile = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setUploadingFile(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      if (user?.email) {
        formData.append('uploaded_by', user.email);
      }

      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/mandatory-files/upload`, {
        method: 'POST',
        body: formData
      });

      const data = await response.json();

      if (data.success) {
        setToastMessage(`File "${data.file_name}" uploaded successfully!`);
        setToastVisible(true);
        setTimeout(() => setToastVisible(false), 3000);
        fetchMandatoryFiles(); // Refresh the list
        setShowUploadModal(false);
      } else {
        setToastMessage(`Error: ${data.error || 'Failed to upload file'}`);
        setToastVisible(true);
        setTimeout(() => setToastVisible(false), 3000);
      }
    } catch (error) {
      setToastMessage(`Error uploading file: ${error.message}`);
      setToastVisible(true);
      setTimeout(() => setToastVisible(false), 3000);
    } finally {
      setUploadingFile(false);
      event.target.value = ''; // Reset file input
    }
  };

  // Delete file immediately without confirmation
  const handleDeleteMandatoryFile = async (fileId, fileName) => {
    if (!fileId) return;
    
    // Ensure dropdown stays open
    setShowMandatoryFilesDropdown(true);
    
    try {
      const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/mandatory-files/${fileId}`, {
        method: 'DELETE'
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      if (data.success) {
        // Show success message
        setToastMessage(`File "${fileName || 'file'}" deleted successfully!`);
        setToastVisible(true);
        setTimeout(() => setToastVisible(false), 3000);
        
        // Immediately remove the file from local state for instant UI update
        setMandatoryFiles(prev => {
          if (!Array.isArray(prev)) return [];
          return prev.filter(file => file && file.id !== fileId);
        });
        
        // Also remove from project knowledge base if it was marked
        setFilesMarkedForProject(prev => {
          const newSet = new Set(prev);
          newSet.delete(fileId);
          return newSet;
        });
      } else {
        setToastMessage(`Error: ${data.error || 'Failed to delete file'}`);
        setToastVisible(true);
        setTimeout(() => setToastVisible(false), 3000);
      }
    } catch (error) {
      console.error('Error deleting file:', error);
      setToastMessage(`Error: ${error.message || 'Failed to delete file'}`);
      setToastVisible(true);
      setTimeout(() => setToastVisible(false), 3000);
    }
    
    // Always ensure dropdown stays open
    setShowMandatoryFilesDropdown(true);
  };

  // Refresh mandatory files list
  const handleRefreshMandatoryFiles = async () => {
    try {
      await fetchMandatoryFiles();
      setToastMessage('Files refreshed successfully!');
      setToastVisible(true);
      setTimeout(() => setToastVisible(false), 2000);
    } catch (error) {
      console.error('Error refreshing files:', error);
      setToastMessage('Error refreshing files');
      setToastVisible(true);
      setTimeout(() => setToastVisible(false), 2000);
    }
  };

  // Handle mandatory file download
  const handleDownloadMandatoryFile = (fileId, fileName) => {
    try {
      if (!fileId || !fileName) {
        console.error('Invalid fileId or fileName for download');
        return;
      }
      const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
      const fileUrl = `${apiUrl}/api/mandatory-files/${fileId}/download`;
      
      const link = document.createElement('a');
      link.href = fileUrl;
      link.download = fileName;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (error) {
      console.error('Error downloading file:', error);
      setToastMessage(`Error downloading file: ${error.message}`);
      setToastVisible(true);
      setTimeout(() => setToastVisible(false), 3000);
    }
  };

  // Handle module selection for a file
  const handleSelectModule = (fileId, moduleName) => {
    setFileModules(prev => {
      const newMap = new Map(prev);
      newMap.set(fileId, moduleName);
      return newMap;
    });
    setOpenModuleDropdown(null); // Close dropdown after selection
  };

  // Toggle file marking for project use (save to database)
  const handleToggleFileForProject = async (fileId, fileName, driveFileId = null) => {
    if (!user?.email) {
      setToastMessage('Please log in to save project knowledge base selections');
      setToastVisible(true);
      setTimeout(() => setToastVisible(false), 3000);
      return;
    }

    try {
      const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
      const isCurrentlyMarked = filesMarkedForProject.has(fileId);

      let response;
      if (isCurrentlyMarked) {
        // Remove from knowledge base
        response = await fetch(`${apiUrl}/api/project-knowledge-base/remove?file_id=${fileId}&user_email=${encodeURIComponent(user.email)}`, {
          method: 'DELETE'
        });
      } else {
        const formData = new FormData();
        formData.append('file_id', fileId);
        formData.append('user_email', user.email);

        if (driveFileId && accessToken) {
          // Fetch fresh content from Google Drive, chunk and index
          formData.append('access_token', accessToken);
          response = await fetch(`${apiUrl}/api/project-knowledge-base/add-from-drive`, {
            method: 'POST',
            body: formData
          });
        } else {
          // Fallback: use already-stored extracted_text
          response = await fetch(`${apiUrl}/api/project-knowledge-base/add`, {
            method: 'POST',
            body: formData
          });
        }
      }
      
      const data = await response.json();
      
      if (data.success) {
        // Update local state
        setFilesMarkedForProject(prev => {
          const newSet = new Set(prev);
          if (isCurrentlyMarked) {
            newSet.delete(fileId);
            setToastMessage(`"${fileName}" removed from project knowledge base`);
          } else {
            newSet.add(fileId);
            setToastMessage(`"${fileName}" added to project knowledge base`);
          }
          setToastVisible(true);
          setTimeout(() => setToastVisible(false), 3000);
          return newSet;
        });
      } else {
        throw new Error(data.error || 'Failed to update knowledge base');
      }
    } catch (error) {
      console.error('Error toggling file for project:', error);
      setToastMessage(`Error: ${error.message || 'Failed to update knowledge base'}`);
      setToastVisible(true);
      setTimeout(() => setToastVisible(false), 3000);
    }
  };

  const handleCreateProject = async () => {
    if (!projectName.trim() || !user?.email || isCreatingProject) return;

    setIsCreatingProject(true);
    try {
      const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
      const formData = new FormData();
      formData.append('name', projectName.trim());
      formData.append('user_email', user.email);

      const response = await fetch(`${apiUrl}/api/projects`, {
        method: 'POST',
        body: formData
      });

      const data = await response.json();
      console.log('Create project response:', data);

      if (data.success && data.project && data.conversation) {
        // Add the new project to the list immediately
        const newProject = {
          ...data.project,
          conversations: [data.conversation]
        };
        setProjects(prev => [newProject, ...prev]);
        
        // Expand the project and set as active
        setExpandedProjects(prev => new Set([...prev, data.project.id]));
        setActiveProjectId(data.project.id);
        setActiveConversationId(data.conversation.id);
        
        // Load the conversation
        if (data.conversation.chat_id) {
          loadChatHistory(data.conversation.chat_id);
        }
        
        setProjectName('');
        setShowProjectsView(false);
      } else {
        console.error('Error creating project:', data.message);
        alert('Error creating project: ' + (data.message || 'Unknown error'));
      }
    } catch (error) {
      console.error('Error creating project:', error);
      alert('Error creating project: ' + error.message);
    } finally {
      setIsCreatingProject(false);
    }
  };

  const fetchProjects = useCallback(async () => {
    if (!user?.email) return;
    
    try {
      const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/projects?user_email=${encodeURIComponent(user.email)}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      const data = await response.json();

      if (data.success) {
        console.log('Projects fetched:', data.projects);
        const projectsList = data.projects || [];
        console.log('Setting projects state with:', projectsList.length, 'projects');
        setProjects(projectsList);
        
        // Auto-expand first project with conversations if none are expanded
        const projectsWithConversations = projectsList.filter(p => p.conversations && p.conversations.length > 0);
        if (projectsWithConversations.length > 0) {
          setExpandedProjects(prev => {
            if (prev.size === 0) {
              return new Set([projectsWithConversations[0].id]);
            }
            return prev;
          });
        }
      } else {
        console.error('Error fetching projects:', data.message);
      }
    } catch (error) {
      console.error('Error fetching projects:', error);
    }
  }, [user?.email]);

  useEffect(() => {
    const script = document.createElement("script");
    script.src = "https://apis.google.com/js/api.js";
    script.onload = () => {
        window.gapi.load("picker", () => console.log("Picker loaded"));
    };
    document.body.appendChild(script);
}, []);


  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  const handleDeleteProject = async (projectId, projectName, e) => {
    if (e) {
      e.stopPropagation(); // Prevent triggering project click
    }

    try {
      const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
      const response = await fetch(
        `${apiUrl}/api/projects/${projectId}?user_email=${encodeURIComponent(
          user?.email || ''
        )}`,
        {
          method: 'DELETE',
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      const data = await response.json();

      if (data.success) {
        // If the deleted project is currently active, clear related state
        if (activeProjectId === projectId) {
          setActiveProjectId(null);
          setActiveConversationId(null);
          setCurrentProject(null);
          setShowProjectsView(false);
        }

        // Refresh projects list
        await fetchProjects();
      } else {
        console.error('Error deleting project:', data.message);
        alert('Error deleting project: ' + (data.message || 'Unknown error'));
      }
    } catch (error) {
      console.error('Error deleting project:', error);
      alert('Error deleting project: ' + error.message);
    }
  };

  const handleLogout = async () => {
  // Clear sessionStorage for chatbot
  sessionStorage.removeItem('hasShownFullscreenChat');
  sessionStorage.removeItem('lastShownFullscreenChatUserId');

  await logout();

  // Go to landing page (same as Data Agent style)
  window.location.href = `${process.env.REACT_APP_BASE_FRONTEND_URL}?action=logout`;

  setShowProfilePopup(false);
  };

  const handleAddAccount = async () => {
    // Close the popup first
    setShowProfilePopup(false);
    
    try {
      // Get Google OAuth URL from backend with account selection prompt
      const response = await axios.get(`${process.env.REACT_APP_API_URL}/api/auth/google/url?prompt=select_account`);
      const { auth_url, error } = response.data;
      
      if (error || !auth_url) {
        console.error('Google OAuth configuration error:', error);
        alert('Unable to add account. Please try again later.');
        return;
      }
      
      // Open in a new popup window for account selection
      const popup = window.open(
        auth_url,
        'google-add-account',
        'width=500,height=600,scrollbars=yes,resizable=yes,top=100,left=100'
      );
      
      // Listen for the popup to close and check for successful authentication
      const checkClosed = setInterval(() => {
        if (popup.closed) {
          clearInterval(checkClosed);
          // Check if a new user was added by checking localStorage
          const currentUser = localStorage.getItem('user');
          if (currentUser) {
            // Refresh the page to show updated user info
            window.location.reload();
          }
        }
      }, 1000);
      
    } catch (error) {
      console.error('Add account error:', error);
      alert('Failed to add account. Please try again.');
    }
  };


  // Helper function to map sheet data to form fields
  const mapSheetData = (sheetName, jsonData) => {
    console.log(`Mapping sheet: ${sheetName}`, jsonData);
    if (!jsonData || jsonData.length < 2) {
      console.log(`Sheet ${sheetName} has insufficient data`);
      return {};
    }

    const headers = jsonData[0];
    const dataRow = jsonData[1]; // Assuming first data row contains the values
    console.log(`Headers for ${sheetName}:`, headers);
    console.log(`Data row for ${sheetName}:`, dataRow);

    switch (sheetName) {
      case 'Sprint Overview':
        return {
          sprintNumber: dataRow[0] || 'N/A',
          sprintDates: dataRow[1] || 'N/A',
          sprintDuration: dataRow[2] || 'N/A',
          teamName: dataRow[3] || 'N/A',
          sprintGoal: dataRow[4] || 'N/A'
        };

      case 'Team Capacity':
        const teamMembers = [];
        // Start from row 4 (index 3) where team member data begins
        for (let i = 3; i < jsonData.length; i++) {
          if (jsonData[i][0] && jsonData[i][0] !== 'Role') {
            teamMembers.push({
              role: jsonData[i][0] || 'N/A',
              workingHours: jsonData[i][1] || 'N/A'
            });
          }
        }
        // If no team members found, add a default one
        if (teamMembers.length === 0) {
          teamMembers.push({
            role: 'N/A',
            workingHours: 'N/A'
          });
        }
        return {
          totalHoursPerPerson: dataRow[0] || 'N/A',
          historicalStoryPoints: dataRow[1] || 'N/A',
          teamMembers: teamMembers
        };

      case 'Product Backlog':
        const userStories = [];
        // Start from row 2 (index 1) where user stories begin
        for (let i = 1; i < jsonData.length; i++) {
          if (jsonData[i][0] && jsonData[i][0] !== 'UserStorySummary') {
            userStories.push({
              userStorySummary: jsonData[i][0] || 'N/A',
              acceptanceCriteria: jsonData[i][1] || 'N/A',
              priority: jsonData[i][2] || 'Low',
              effortEstimate: parseInt(jsonData[i][3]) || 0
            });
          }
        }
        // If no user stories found, add a default one
        if (userStories.length === 0) {
          userStories.push({
            userStorySummary: 'N/A',
            acceptanceCriteria: 'N/A',
            priority: 'Low',
            effortEstimate: 0
          });
        }
        return { userStories };

      case 'Definition of Done':
        const criteria = dataRow[0] || '';
        const criteriaArray = criteria.split(';').map(c => c.trim()).filter(c => c);
        return {
          definitionOfDone: criteriaArray.length > 0 ? criteriaArray : ['N/A']
        };

      case 'Risks & Impediments':
        const risks = dataRow[0] || '';
        const risksArray = risks.split(',').map(r => r.trim()).filter(r => r);
        return {
          risksImpediments: risksArray.length > 0 ? risksArray : ['N/A']
        };

      case 'Additional Comments':
        return {
          additionalComments: dataRow[0] || 'N/A'
        };

      default:
        return {};
    }
  };

  // Helper function to map risk assessment sheet data to form fields
  // eslint-disable-next-line no-unused-vars
  const mapRiskSheetData = (sheetName, jsonData) => { void mapRiskSheetData;
    if (!jsonData || jsonData.length < 2) return {};

    const headers = jsonData[0];
    void headers;
    const dataRow = jsonData[1]; // Assuming first data row contains the values

    switch (sheetName) {
      case 'Risk ID':
        return {
          riskIDValue: dataRow[0] || ''
        };

      case 'Risk Description':
        return {
          primarySource: dataRow[0] || '',
          secondarySource: dataRow[1] || ''
        };

      case 'Severity':
        return {
          source: dataRow[0] || '',
          alternativeSource: dataRow[1] || '',
          severityValue: dataRow[2] || 'Medium'
        };

      case 'Status':
        return {
          statusValue: dataRow[0] || 'Open'
        };

      case 'Risk Owner':
        return {
          primarySource: dataRow[0] || '',
          secondarySource: dataRow[1] || ''
        };

      case 'Date Identified':
        return {
          dateIdentifiedValue: dataRow[0] || ''
        };

      case 'Mitigation Plan':
        return {
          primarySource: dataRow[0] || '',
          secondarySource: dataRow[1] || ''
        };

      case 'Relevant NotesContext':
        return {
          relevantNotesValue: dataRow[0] || ''
        };

      default:
        return {};
    }
  };

  // Function to download sprint planning template

  // Profile popup component
  const ProfilePopup = () => (
    <div className="profile-popup-overlay" onClick={() => setShowProfilePopup(false)}>
      <div className="profile-popup simple-theme" onClick={(e) => e.stopPropagation()}>
        <div className="profile-popup-header">
          <div className="profile-info">
            <div className="profile-picture-container">
              <img 
                src={user?.picture || user?.photoURL || ''} 
                alt="Profile" 
                className="profile-picture"
                onError={(e) => {
                  e.target.style.display = 'none';
                }}
              />
              {!user?.picture && !user?.photoURL && (
                <div className="profile-picture-fallback">
                  {(user?.name || user?.displayName || user?.email || 'U').charAt(0).toUpperCase()}
                </div>
              )}
            </div>
            <div className="profile-details">
              <h3>{user?.name || user?.displayName || user?.email?.split('@')[0] || 'User'}</h3>
              <p className="user-email">{user?.email}</p>
            </div>
          </div>
        </div>
        
        <div className="profile-popup-actions">
          <button className="add-account-btn" onClick={handleAddAccount}>
            Add Account
          </button>
          <button className="signout-btn" onClick={handleLogout}>
            Sign out
          </button>
        </div>
      </div>
    </div>
  );

  // Safeguard: Ensure component always renders something, even if auth check fails
  // Wait for auth to finish loading before checking authentication
  if (authLoading) {
    // Show loading state while AuthContext initializes (checks session cookie)
    return (
      <div className="pm-scope home-page" style={{ padding: '20px', textAlign: 'center' }}>
        <p>Loading...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    // Return a minimal loading/redirect message instead of null to prevent blank pages
    return (
      <div className="pm-scope home-page" style={{ padding: '20px', textAlign: 'center' }}>
        <p>Redirecting to login...</p>
      </div>
    );
  }

  // Main return statement
  return (
    <div className={`pm-scope home-page ${isChatFullscreen ? 'chat-fullscreen-active' : ''}`}>
      {/* Chat Google Drive Picker — renders null, opened imperatively via chatPickerRef */}
      <GoogleDrivePicker
        ref={chatPickerRef}
        accessToken={chatDriveAccessToken}
        multiSelect={true}
        onFileSelected={(files) => uploadChatDriveFiles(files, chatTokenRef.current)}
      />
      {/* Templates / Mandatory Files Google Drive Picker */}
      <GoogleDrivePicker
        ref={templatePickerRef}
        accessToken={accessToken}
        multiSelect={true}
        onFileSelected={(docs) => pickerCallback({ action: window.google.picker.Action.PICKED, docs }, user?.email)}
      />
      {/* Loading Overlay */}
      {loading && (
        <div className="loading-overlay">
          <div className="loading-content">
            <div className="loading-ring-large"></div>
            <div className="loading-text">Processing Your Document</div>
            <div className="loading-subtext">This may take a few moments...</div>
            <div className="upload-progress-container">
              <div className="upload-progress-bar">
                <div className="progress-bar-fill" style={{ width: `${uploadProgress}%` }}></div>
              </div>
              <div className="upload-progress-text">{Math.round(uploadProgress)}%</div>
            </div>
            <div className="upload-status-text">Parsing document content...</div>
          </div>
        </div>
      )}
      {toastVisible && (
        <div className="toast success-toast">{toastMessage}</div>
      )}
      
      {showProfilePopup && <ProfilePopup />}

      {/* Top Right Back and Logout Buttons */}
      <div className="header-buttons-container">
        <button 
          className="header-back-btn"
          onClick={() => {
          window.location.href = `${process.env.REACT_APP_BASE_FRONTEND_URL}`;
        }}
          title="Go Back"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M19 12H5M12 19l-7-7 7-7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <span>HOME</span>
        </button>
        <button 
          className="header-logout-btn"
          onClick={handleLogout}
          title="Logout"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            <polyline points="16,17 21,12 16,7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            <line x1="21" y1="12" x2="9" y2="12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <span>Logout</span>
        </button>
      </div>

      {/* Floating Chat Icon and Expanded Chat UI */}
      <div className="chat-panel-container">
        {/* Expanded Chat Box */}
          <div className={`chat-expanded-box ${isChatDockedTopLeft ? 'enlarged' : ''} ${isChatFullscreen ? 'chat-fullscreen' : ''} ${isChatHistoryCollapsed ? 'sidebar-collapsed' : ''}`}
            style={{
              ...(isChatFullscreen ? {} : (chatUseCustomPosition ? { position: 'fixed', top: isChatDockedTopLeft ? 16 : chatPosition.y, left: isChatDockedTopLeft ? 16 : chatPosition.x } : {})),
              ...(isChatFullscreen ? {} : { width: `${chatSize.width}px`, height: `${chatSize.height}px` })
            }}
            onClick={(e) => {
            e.stopPropagation();
            // Close attach menu if clicking outside of it
            if (showAttachMenu) {
              const attachWrapper = e.target.closest('.chat-attach-wrapper');
              if (!attachWrapper) {
                setShowAttachMenu(false);
              }
            }
            // Close mandatory files dropdown if clicking outside of it
            if (showMandatoryFilesDropdown) {
              const mandatoryFilesSection = e.target.closest('.chat-mandatory-files-wrapper');
              if (!mandatoryFilesSection) {
                setShowMandatoryFilesDropdown(false);
              }
            }
            // Close module dropdown if clicking outside of it
            if (openModuleDropdown !== null) {
              const moduleWrapper = e.target.closest('.mandatory-file-module-wrapper');
              if (!moduleWrapper) {
                setOpenModuleDropdown(null);
              }
            }
          }}>
            <div className="chat-expanded-header"
              onMouseDown={(e) => {
                // Don't allow dragging in fullscreen mode
                if (!isChatFullscreen) {
                  setIsDraggingChat(true);
                  const rect = e.currentTarget.parentElement.getBoundingClientRect();
                  setDragOffset({ x: e.clientX - rect.left, y: e.clientY - rect.top });
                }
              }}
            >
              <h3 className="chat-expanded-title">Hi there! What can I do for you today?</h3>
              <div style={{ display: 'flex', gap: '8px' }} />
            </div>
            {/* Mandatory Files Section */}
            <div style={{ padding: '12px 16px', display: 'flex', justifyContent: 'flex-end' }}>
              <div className="chat-right-buttons-wrapper">
                <div className="chat-mandatory-files-wrapper">
                  <button 
                    className="chat-mandatory-files-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      setShowMandatoryFilesDropdown(!showMandatoryFilesDropdown);
                    }}
                    aria-label="Mandatory Files"
                    title="Mandatory Files"
                  >
                    <span>Templates</span>
                  </button>
                  {showMandatoryFilesDropdown && (() => {
                    // Check if user is admin - check role and email
                    const userRole = user?.role || localStorage.getItem("role");
                    const ADMIN_EMAILS = [
                       "vandana.dandge@forsysinc.com",
                       "archana.chandel@forsysinc.com",
                       "nihal.yemula@forsysinc.com",

                      // Add more admin emails here as needed
                    ];
                    const isAdmin = userRole === "admin" || (user?.email && ADMIN_EMAILS.includes(user.email));
                    
                    return (
                      <div className="mandatory-files-dropdown">
                        {/* Add File and Refresh Buttons - Admin Only */}
                        {isAdmin && (
                          <div className="mandatory-file-upload-section">
                        <input
                          type="file"
                          id="mandatory-file-upload"
                          style={{ display: 'none' }}
                          accept=".pdf,.docx,.doc,.txt,.xlsx,.xls,.pptx,.ppt"
                          onChange={handleUploadMandatoryFile}
                        />
                        <button
                          className="mandatory-file-add-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            setShowFileSourceModal(true);
                          }}
                          disabled={uploadingFile}
                        >
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <line x1="12" y1="5" x2="12" y2="19" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                            <line x1="5" y1="12" x2="19" y2="12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                          </svg>
                          <span>{uploadingFile ? 'Uploading...' : 'Add File'}</span>
                        </button>
                        <button
                          className="mandatory-file-refresh-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleRefreshMandatoryFiles();
                          }}
                          title="Refresh files list"
                        >
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                            <path d="M21 3v5h-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                            <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                            <path d="M3 21v-5h5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                          </svg>
                          <span>Refresh</span>
                        </button>
                          </div>
                        )}
                      
                        {/* Search Bar */}
                        <div className="mandatory-files-search-wrapper">
                          <input
                            type="text"
                            className="mandatory-files-search-input"
                            placeholder="Search files…"
                            value={mandatoryFilesSearch}
                            onChange={(e) => setMandatoryFilesSearch(e.target.value)}
                            onClick={(e) => e.stopPropagation()}
                          />
                        </div>

                        {/* Files List */}
                      {(() => {
                        try {
                          if (!mandatoryFiles || !Array.isArray(mandatoryFiles) || mandatoryFiles.length === 0) {
                            return <div className="mandatory-file-empty">No files available</div>;
                          }
                          
                          // Safely map files with error handling and search filtering
                          const safeFiles = mandatoryFiles.filter(file => {
                            if (!file || !file.id) return false;
                            // Apply search filter
                            if (mandatoryFilesSearch.trim()) {
                              const searchTerm = mandatoryFilesSearch.toLowerCase().trim();
                              const fileName = (file.file_name || '').toLowerCase();
                              return fileName.includes(searchTerm);
                            }
                            return true;
                          });
                          
                          if (safeFiles.length === 0) {
                            if (mandatoryFilesSearch.trim()) {
                              return <div className="mandatory-file-empty">No files match "{mandatoryFilesSearch}"</div>;
                            }
                            return <div className="mandatory-file-empty">No files available</div>;
                          }
                          
                          return safeFiles.map((file) => {
                            try {
                              if (!file || !file.id) {
                                return null;
                              }
                              return (
                                <div key={file.id} className="mandatory-file-item-wrapper">
                                  <div className="mandatory-file-item">
                                    <span 
                                      onClick={(e) => {
                                        try {
                                          e.stopPropagation();
                                          if (file.id && file.file_name) {
                                            handleDownloadMandatoryFile(file.id, file.file_name);
                                          }
                                        } catch (err) {
                                          console.error('Error downloading file:', err);
                                        }
                                      }}
                                      style={{ cursor: 'pointer', flex: 1 }}
                                    >
                                      {file.file_name || 'Unknown file'}
                                    </span>
                                    <div className="mandatory-file-actions">
                                      {/* Admin-only actions: Module dropdown, Use for Project checkbox, Delete button */}
                                      {isAdmin && (
                                        <>
                                          {/* Select Module Button */}
                                          <div className="mandatory-file-module-wrapper" style={{ position: 'relative' }}>
                                            <button
                                              className="mandatory-file-select-module-btn"
                                              onClick={(e) => {
                                                try {
                                                  e.preventDefault();
                                                  e.stopPropagation();
                                                  setOpenModuleDropdown(openModuleDropdown === file.id ? null : file.id);
                                                } catch (err) {
                                                  console.error('Error toggling module dropdown:', err);
                                                }
                                              }}
                                              title="Select Module"
                                              type="button"
                                            >
                                              <span className="select-module-text">
                                                {fileModules.get(file.id) || 'Select Module'}
                                              </span>
                                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                                <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                              </svg>
                                            </button>
                                            {openModuleDropdown === file.id && (
                                              <div className="mandatory-file-module-dropdown">
                                                <div
                                                  className="mandatory-file-module-option"
                                                  onClick={(e) => {
                                                    e.preventDefault();
                                                    e.stopPropagation();
                                                    handleSelectModule(file.id, 'PM Template');
                                                  }}
                                                >
                                                  PM Template
                                                </div>
                                              </div>
                                            )}
                                          </div>
                                          <button
                                            className={`mandatory-file-use-for-project-btn ${filesMarkedForProject.has(file.id) ? 'active' : ''}`}
                                            onClick={(e) => {
                                              try {
                                                e.preventDefault();
                                                e.stopPropagation();
                                                if (file.id && file.file_name) {
                                                  handleToggleFileForProject(file.id, file.file_name, file.drive_file_id);
                                                }
                                              } catch (err) {
                                                console.error('Error toggling file for project:', err);
                                              }
                                            }}
                                            title={filesMarkedForProject.has(file.id) ? "Remove from project knowledge base" : "Add to project knowledge base"}
                                            type="button"
                                          >
                                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                              <path d="M9 11l3 3L22 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                              <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                            </svg>
                                            <span className="use-for-project-text">Use for Project</span>
                                          </button>
                                        </>
                                      )}
                                      {/* Download button - Always visible */}
                                      <button
                                        className="mandatory-file-download-btn"
                                        onClick={(e) => {
                                          try {
                                            e.preventDefault();
                                            e.stopPropagation();
                                            if (file.id && file.file_name) {
                                              handleDownloadMandatoryFile(file.id, file.file_name);
                                            }
                                          } catch (err) {
                                            console.error('Error downloading file:', err);
                                          }
                                        }}
                                        title="Download file"
                                        type="button"
                                        style={{ background: 'none', border: 'none', padding: '4px', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
                                      >
                                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className="download-icon">
                                          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                          <polyline points="7 10 12 15 17 10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                          <line x1="12" y1="15" x2="12" y2="3" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                                        </svg>
                                      </button>
                                      {/* Delete button - Admin only */}
                                      {isAdmin && (
                                        <button
                                          className="mandatory-file-delete-btn"
                                          onClick={(e) => {
                                            try {
                                              e.preventDefault();
                                              e.stopPropagation();
                                              if (file.id && file.file_name) {
                                                handleDeleteMandatoryFile(file.id, file.file_name);
                                              }
                                            } catch (err) {
                                              console.error('Error deleting file:', err);
                                            }
                                          }}
                                          title="Delete file"
                                          type="button"
                                        >
                                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                            <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                          </svg>
                                        </button>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              );
                            } catch (err) {
                              console.error('Error rendering file item:', err);
                              return null;
                            }
                          });
                        } catch (err) {
                          console.error('Error rendering files list:', err);
                          return <div className="mandatory-file-empty">Error loading files</div>;
                        }
                      })()}
                      </div>
                    );
                  })()}
                </div>
              </div>
            </div>
            
            {/* Chat body with sidebar and content */}
            <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
              {/* ChatGPT-Style History Sidebar */}
              <div className={`chat-history-sidebar ${isChatHistoryCollapsed ? 'collapsed' : ''}`}>
                {/* Collapse Button */}
                <button 
                  className="chat-history-collapse-btn"
                  onClick={() => setIsChatHistoryCollapsed(!isChatHistoryCollapsed)}
                  title={isChatHistoryCollapsed ? "Expand sidebar" : "Collapse sidebar"}
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path 
                      d={isChatHistoryCollapsed ? "M9 18l6-6-6-6" : "M15 18l-6-6 6-6"} 
                      stroke="currentColor" 
                      strokeWidth="2" 
                      strokeLinecap="round" 
                      strokeLinejoin="round"
                    />
                  </svg>
                </button>
                
                {/* Action Buttons Section */}
                <div className="chat-history-actions">
                  <button 
                    className="chat-action-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleNewChat();
                    }}
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                    </svg>
                    <span>New chat</span>
                  </button>
                  
                  
                  <button 
                    className="chat-action-btn"
                    onClick={() => {
                      setShowProjectsView(true);
                    }}
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" stroke="currentColor" strokeWidth="2"/>
                      <path d="M12 11v6M9 14h6" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                    </svg>
                    <span>Projects</span>
                  </button>
                </div>
                
                {/* Projects List Section */}
                {projects.length > 0 ? (
                  <div className="projects-sidebar-section">
                    <div className="projects-sidebar-list">
                      {projects.map((project) => {
                        const isExpanded = expandedProjects.has(project.id);
                        const hasConversations = project.conversations && project.conversations.length > 0;
                        
                        return (
                          <div key={project.id} className="project-sidebar-wrapper">
                            <div 
                              className={`project-sidebar-item ${activeProjectId === project.id ? 'active' : ''}`}
                              onClick={(e) => {
                                if (e.target.closest('.project-delete-btn') || e.target.closest('.project-expand-btn')) {
                                  return;
                                }
                                // Toggle expansion
                                setExpandedProjects(prev => {
                                  const newSet = new Set(prev);
                                  if (newSet.has(project.id)) {
                                    newSet.delete(project.id);
                                  } else {
                                    newSet.add(project.id);
                                  }
                                  return newSet;
                                });
                                setActiveProjectId(project.id);
                              }}
                            >
                              {hasConversations && (
                                <button
                                  className="project-expand-btn"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setExpandedProjects(prev => {
                                      const newSet = new Set(prev);
                                      if (newSet.has(project.id)) {
                                        newSet.delete(project.id);
                                      } else {
                                        newSet.add(project.id);
                                      }
                                      return newSet;
                                    });
                                  }}
                                  title={isExpanded ? "Collapse" : "Expand"}
                                >
                                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                    <path 
                                      d={isExpanded ? "M6 9l6 6 6-6" : "M9 18l6-6-6-6"} 
                                      stroke="currentColor" 
                                      strokeWidth="2" 
                                      strokeLinecap="round" 
                                      strokeLinejoin="round"
                                    />
                                  </svg>
                                </button>
                              )}
                              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className="project-sidebar-icon">
                                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" stroke="currentColor" strokeWidth="2"/>
                              </svg>
                              <span className="project-sidebar-name">{project.name}</span>
                              <button
                                className="project-delete-btn"
                                onClick={(e) => handleDeleteProject(project.id, project.name, e)}
                                title="Delete project"
                              >
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                  <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                </svg>
                              </button>
                            </div>
                            {isExpanded && hasConversations && (
                              <div className="conversations-nested-list">
                                {project.conversations.map((conversation) => {
                                  const matchingSession = chatSessions.find(
                                    (session) => session.chat_id === conversation.chat_id
                                  );
                                  const previewSource =
                                    matchingSession?.first_message_preview ||
                                    conversation.first_message_preview ||
                                    (conversation.title && conversation.title !== 'Default chat'
                                      ? conversation.title
                                      : '');
                                  const truncatedPreview = formatChatPreview(
                                    previewSource,
                                    'New chat'
                                  );

                                  return (
                                    <div
                                      key={conversation.id}
                                      className={`conversation-sidebar-item ${activeConversationId === conversation.id ? 'active' : ''}`}
                                      onClick={() => {
                                        setActiveConversationId(conversation.id);
                                        setActiveProjectId(project.id);
                                        if (conversation.chat_id) {
                                          loadChatHistory(conversation.chat_id);
                                        }
                                      }}
                                    >
                                      <svg
                                        width="14"
                                        height="14"
                                        viewBox="0 0 24 24"
                                        fill="none"
                                        xmlns="http://www.w3.org/2000/svg"
                                        className="conversation-icon"
                                      >
                                        <path
                                          d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"
                                          stroke="currentColor"
                                          strokeWidth="2"
                                        />
                                      </svg>
                                      <span className="conversation-sidebar-name">
                                        {truncatedPreview}
                                      </span>
                                    </div>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ) : null}
                
                {/* Chats List Section */}
          {/* Chats List Section */}
            <div className="chat-history-middle-section">
              <div className="chat-history-header">
                <h3>Chats</h3>
              </div>
              <div className="chat-history-list">
                {isLoadingChatHistory && (
                  <div className="chat-history-loading">
                    <span>Loading…</span>
                  </div>
                )}
                {chatSessions.length === 0 ? (
                  <div className="chat-history-empty">
                    <span>No previous chats</span>
                  </div>
                ) : (
                  chatSessions.map((session) => {
                    const truncatedPreview = formatChatPreview(session.first_message_preview);
                    let formattedDate = '';
                    const dateToUse = session.updated_at || session.last_message_at;
                    if (dateToUse) {
                      const parsed = new Date(dateToUse);
                      if (!Number.isNaN(parsed.getTime())) {
                        formattedDate = parsed.toLocaleString([], {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit'
                        });
                      }
                    }

                    return (
                      <div
                        key={session.chat_id}
                        className={`chat-history-item ${activeChatId === session.chat_id ? 'active' : ''}`}
                        onClick={() => {
                          if (session.chat_id === activeChatId && session.isLocal) return;
                          setCurrentProject(null);
                          setActiveProjectId(null);
                          setActiveConversationId(null);
                          loadChatHistory(session.chat_id);
                        }}
                        style={{ 
                            display: 'flex', 
                            justifyContent: 'space-between', 
                            alignItems: 'center', 
                            width: '100%',
                            paddingRight: '10px' 
                        }}
                      >
                        <div className="chat-history-item-content" style={{ flex: 1, overflow: 'hidden' }}>
                          <div className="chat-history-item-title">
                            <span>{truncatedPreview}</span>
                          </div>
                          {formattedDate && (
                            <div className="chat-history-item-date">
                              <span>{formattedDate}</span>
                            </div>
                          )}
                        </div>

                        <button 
                            className="chat-item-delete-btn" 
                            onClick={(e) => handleDeleteChat(e, session.chat_id)}
                            title="Delete history"
                            style={{
                              background: 'none',
                              border: 'none',
                              color: '#ff4d4d',
                              cursor: 'pointer',
                              padding: '4px',
                              display: 'flex',
                              alignItems: 'center',
                              opacity: 0.9,
                              zIndex: 10
                            }}
                          >
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                              <path d="M3 6h18" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                              <rect x="5" y="6" width="14" height="14" rx="2" stroke="currentColor" strokeWidth="2"/>
                              <path d="M9 10v6" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                              <path d="M15 10v6" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                              <rect x="9" y="2" width="6" height="4" rx="1" stroke="currentColor" strokeWidth="2"/>
                            </svg>
                        </button>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </div> {/* This closing div was missing and caused the Render error */}
              {/* Chat Content Area */}
              <div className="chat-expanded-content" style={{ flex: 1 }}>
                {/* Project Header - Show only when project is active and no messages yet */}
                {activeProject && !showProjectsView && chatMessages.length === 0 && (
                  <div className="project-conversation-header">
                    <div className="project-conversation-header-content">
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className="project-header-icon">
                        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" stroke="currentColor" strokeWidth="2"/>
                      </svg>
                      <span className="project-header-name">{activeProject.name}</span>
                    </div>
                  </div>
                )}
                {showProjectsView ? (
                  <>
                    <div className="projects-backdrop" onClick={() => setShowProjectsView(false)}></div>
                    <div className="projects-view-container">
                      <div className="project-create-window">
                        <div className="project-create-header">
                          <h2>Project name</h2>
                          <button 
                            className="project-window-close-btn"
                            onClick={() => setShowProjectsView(false)}
                            title="Close"
                          >
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                              <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                            </svg>
                          </button>
                        </div>
                        <div className="project-create-body">
                          <div className="project-name-input-wrapper">
                            
                            <input
                              type="text"
                              className="project-name-input"
                              placeholder="Project name"
                              value={projectName}
                              onChange={(e) => setProjectName(e.target.value)}
                              onKeyPress={(e) => {
                                if (e.key === 'Enter' && projectName.trim()) {
                                  handleCreateProject();
                                }
                              }}
                              autoFocus
                            />
                          </div>

                          <div className="modal-info">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className="info-icon">
                              <path d="M9 21h6M12 3a6 6 0 00-6 6c0 2.5 1 4.5 2.5 5.5v1.5a1.5 1.5 0 003 0V14.5c1.5-1 2.5-3 2.5-5.5a6 6 0 00-6-6z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                            </svg>
                            <p>Projects keep chats, files, and custom instructions in one place. Use them for ongoing work, or just to keep things tidy.</p>
                          </div>
                        </div>
                        <div className="project-create-footer">
                          <button
                            className="create-btn"
                            onClick={handleCreateProject}
                            disabled={!projectName.trim() || isCreatingProject}
                          >
                            {isCreatingProject ? 'Creating...' : 'Create project'}
                          </button>
                        </div>
                      </div>
                    </div>
                  </>
                ) : chatMessages.length === 0 ? (
                  <div className="chat-empty-state">
                    <p className="chat-empty-text">Start a conversation...</p>
                  </div>
                ) : (
                  <div className="chat-messages-list">
                    {chatMessages.map((message, index) => (
                      <div key={index} className={`chat-message ${message.type}`}>
                        <div className="chat-message-content">
                          {message.type === 'bot' ? (
                            <div dangerouslySetInnerHTML={{ __html: message.text || '' }} />
                          ) : (
                            <p>{message.text}</p>
                          )}
                          <span className="chat-message-time">{message.time}</span>
                        </div>
                      </div>
                    ))}
                    {/* Typing Indicator */}
                    {isBotTyping && (
                      <div className="chat-message bot typing-indicator-message">
                        <div className="chat-message-content">
                          <div className="typing-indicator">
                            <span className="typing-dot"></span>
                            <span className="typing-dot"></span>
                            <span className="typing-dot"></span>
                            <span className="typing-text">Getting your response</span>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
            <div className="chat-expanded-input-container" onClick={(e) => e.stopPropagation()}>
              {/* Hidden file input */}
              <input
                type="file"
                id="chat-file-input"
                style={{ display: 'none' }}
                accept=".pdf,.docx,.doc,.txt,.xlsx"
                multiple
                onChange={handleFileSelect}
              />
              {/* Selected files preview */}
              {selectedFiles.length > 0 && (
                <div className="selected-files-preview" onClick={(e) => e.stopPropagation()}>
                  {selectedFiles.map((file, index) => (
                    <div key={index} className="selected-file-chip">
                      <span className="selected-file-name" title={file.name}>
                        📎 {file.name.length > 20 ? file.name.substring(0, 20) + '...' : file.name}
                      </span>
                      <button
                        className="selected-file-remove"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleRemoveSelectedFile(index);
                        }}
                        title="Remove file"
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                          <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                        </svg>
                      </button>
                    </div>
                  ))}
                  {selectedFiles.length > 0 && (
                    <button
                      className="upload-files-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleUploadSelectedFiles();
                      }}
                      disabled={isUploadingFile}
                      title="Upload selected files"
                    >
                      {isUploadingFile ? 'Uploading...' : 'Upload'}
                    </button>
                  )}
                </div>
              )}
              {/* Modern ChatGPT-style floating input wrapper */}
              <div className="chat-input-wrapper">
              {/* Start a Project and PM Template buttons inside prompt box, above plus icon */}
              <div className="chat-start-project-wrapper">
                <button
                  className="chat-start-project-btn"
                  onClick={(e) => handleStartProject(e, null)}
                  aria-label="Start a Project"
                  title="Start a Project"
                >
                  <span>PM Guide- Start project</span>
                </button>
               {/* <button
                  className="chat-start-project-btn"
                  onClick={(e) => handleStartProject(e, 'PM Template')}
                  aria-label="PM Template"
                  title="PM Template"
                >
                  <span>PM Template</span>
                </button> */}
                <button
                  className="chat-start-project-btn"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    window.open('https://helpdesk.forsysinc.com/', '_blank', 'noopener,noreferrer');
                    
                  }}
                  aria-label="Help Desk"
                  title="Help Desk"
                >
                  <span>Help Desk</span>               
                </button>

                <button
                  className="chat-start-project-btn"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    window.open('https://weekly-tracker-frontend.onrender.com', '_blank', 'noopener,noreferrer');
                    
                  }}

                  aria-label="Generate weekly status report"
                  title="Generate weekly status report"
                >
                 <span>Generate weekly status report</span> 
                </button>
              </div>
              <div className="chat-input-row">
                <div className="chat-attach-wrapper" onClick={(e) => e.stopPropagation()}>
                  <button 
                    className={`chat-attach-btn ${showAttachMenu ? 'active' : ''}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      e.preventDefault();
                      setShowAttachMenu(!showAttachMenu);
                    }}
                    aria-label="Add attachment"
                    title="Add"
                  >
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <line x1="12" y1="5" x2="12" y2="19" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
                      <line x1="5" y1="12" x2="19" y2="12" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
                    </svg>
                  </button>
                  
                  {/* Attach Menu Dropdown */}
                  {showAttachMenu && (
                    <div className="chat-attach-menu" onClick={(e) => e.stopPropagation()}>
                      <button 
                        className="chat-attach-menu-item"
                        onClick={(e) => {
                          e.stopPropagation();
                          e.preventDefault();
                          document.getElementById('chat-file-input').click();
                          setShowAttachMenu(false);
                        }}
                      >
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                          <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                        </svg>
                        <span>Add photos & files</span>
                      </button>
                      <button
  className="chat-attach-menu-item"
  onClick={(e) => {
    e.stopPropagation();
    e.preventDefault();
    //console.log("Chat Google Drive clicked");
    //setShowAttachMenu(false);
    setShowAttachMenu(false);
    // CRITICAL CHANGE: Call the new, dedicated function
    openChatDrivePicker(e);
  }}
>
  <svg
    width="20"
    height="20"
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    <path
      d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
  <span>Add from Google Drive</span>
</button>


                    </div>
                  )}
                </div>
                <input
                  type="text"
                  className="chat-expanded-input"
                  placeholder="Ask anything"
                  value={chatInput}
                  onChange={(e) => {
                    e.stopPropagation();
                    setChatInput(e.target.value);
                  }}
                  onClick={(e) => e.stopPropagation()}
                  onFocus={(e) => e.stopPropagation()}
                  onKeyPress={(e) => {
                    e.stopPropagation();
                    if (e.key === 'Enter' && chatInput.trim()) {
                      const inputText = chatInput.trim();
                      addMessageWithBotResponse(inputText);
                      console.log('Send message:', inputText);
                      setChatInput('');
                    }
                  }}
                  autoFocus
                />
                <div className="chat-action-buttons">
                  <button 
                    className="chat-send-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      e.preventDefault();
                      if (chatInput.trim()) {
                        const inputText = chatInput.trim();
                        addMessageWithBotResponse(inputText);
                        console.log('Send message:', inputText);
                        setChatInput('');
                      }
                    }}
                    aria-label="Send message"
                    title="Send"
                    disabled={!chatInput.trim()}
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M12 19V5M5 12L12 5L19 12" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </button>
                </div>
              </div>
              </div>
            </div>
            {/* Invisible corner resize handles - hide in fullscreen */}
            {!isChatFullscreen && (
              <>
            <div className="chat-resize-handle tl" onMouseDown={(e) => {
              e.stopPropagation();
              const rect = e.currentTarget.parentElement.getBoundingClientRect();
              setResizeStart({ mouseX: e.clientX, mouseY: e.clientY, width: rect.width, height: rect.height, left: rect.left, top: rect.top });
              setResizeDirection('tl');
              setChatUseCustomPosition(true);
              setChatPosition({ x: rect.left, y: rect.top });
              setIsResizingChat(true);
            }} />
            <div className="chat-resize-handle tr" onMouseDown={(e) => {
              e.stopPropagation();
              const rect = e.currentTarget.parentElement.getBoundingClientRect();
              setResizeStart({ mouseX: e.clientX, mouseY: e.clientY, width: rect.width, height: rect.height, left: rect.left, top: rect.top });
              setResizeDirection('tr');
              setChatUseCustomPosition(true);
              setChatPosition({ x: rect.left, y: rect.top });
              setIsResizingChat(true);
            }} />
            <div className="chat-resize-handle bl" onMouseDown={(e) => {
              e.stopPropagation();
              const rect = e.currentTarget.parentElement.getBoundingClientRect();
              setResizeStart({ mouseX: e.clientX, mouseY: e.clientY, width: rect.width, height: rect.height, left: rect.left, top: rect.top });
              setResizeDirection('bl');
              setChatUseCustomPosition(true);
              setChatPosition({ x: rect.left, y: rect.top });
              setIsResizingChat(true);
            }} />
            <div className="chat-resize-handle br" onMouseDown={(e) => {
              e.stopPropagation();
              const rect = e.currentTarget.parentElement.getBoundingClientRect();
              setResizeStart({ mouseX: e.clientX, mouseY: e.clientY, width: rect.width, height: rect.height, left: rect.left, top: rect.top });
              setResizeDirection('br');
              setChatUseCustomPosition(true);
              setChatPosition({ x: rect.left, y: rect.top });
              setIsResizingChat(true);
            }} />
            </>
            )}
          </div>
      </div>

      {/* Create Project Modal */}
      {showCreateProjectModal && (
        <div className="modal-overlay" onClick={() => setShowCreateProjectModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Project name</h2>
              <div className="modal-header-actions">
                <button className="modal-settings-btn" title="Settings">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 15a3 3 0 100-6 3 3 0 000 6z" stroke="currentColor" strokeWidth="2"/>
                    <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z" stroke="currentColor" strokeWidth="2"/>
                  </svg>
                </button>
                <button 
                  className="modal-close-btn"
                  onClick={() => setShowCreateProjectModal(false)}
                  title="Close"
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                  </svg>
                </button>
              </div>
            </div>
            <div className="modal-body">
              <div className="project-name-input-wrapper">
                <span className="input-icon">😊</span>
                <input
                  type="text"
                  className="project-name-input"
                  placeholder="Copenhagen Trip"
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  onKeyPress={(e) => {
                    if (e.key === 'Enter' && projectName.trim()) {
                      handleCreateProject();
                    }
                  }}
                  autoFocus
                />
              </div>
              

              <div className="modal-info">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className="info-icon">
                  <path d="M9 21h6M12 3a6 6 0 00-6 6c0 2.5 1 4.5 2.5 5.5v1.5a1.5 1.5 0 003 0V14.5c1.5-1 2.5-3 2.5-5.5a6 6 0 00-6-6z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                <p>Projects keep chats, files, and custom instructions in one place. Use them for ongoing work, or just to keep things tidy.</p>
              </div>
            </div>
            <div className="modal-footer">
              <button
                className="create-btn"
                onClick={handleCreateProject}
                disabled={!projectName.trim()}
              >
                Create project
              </button>
            </div>
          </div>
        </div>
      )}

      {/* File Source Selection Modal */}
      {showFileSourceModal && (
        <div className="file-source-modal-overlay" onClick={() => setShowFileSourceModal(false)}>
          <div className="file-source-modal" onClick={(e) => e.stopPropagation()}>
            <h2 className="file-source-modal-title">Select the file on which you want me to work on!</h2>
            <div className="file-source-options">
               <button
                 className="file-source-option"
                   onClick={(e) => {
                   // Check readiness and authentication directly before running main logic
                     const isReady = isPickerReady && window.google?.accounts?.oauth2;

                     if (user?.email && isReady) {
                         initiateDriveUpload(user.email);
                    } else {
                      alert(isReady ? 
                          'Please log in to upload from Google Drive.' : 
                         'Google Drive services are still loading. Please try again in a moment.'
                    );
                   }
                  }}
                     // Remove disabled attribute entirely to stop unexpected blocking
                  >
                <div className="file-source-icon gdrive-icon">
                  <svg width="28" height="28" viewBox="0 0 87.3 78" xmlns="http://www.w3.org/2000/svg">
                    <path d="M6.6 66.85L29.2 27.95l22.6 38.9z" fill="#0066da"/>
                    <path d="M58.2 66.85L80.7 28.05l-22.6-.1z" fill="#00ac47"/>
                    <path d="M29.2 27.95L51.8 66.85h28.9L58.1 28.05z" fill="#ea4335"/>
                    <path d="M29.2 27.95h22.6L80.7 28l-22.5-27.9z" fill="#00832d"/>
                    <path d="M6.6 66.85L29.2 27.95 6.7 28.05z" fill="#2684fc"/>
                    <path d="M51.8 66.85L29.2 27.95h-22.5L29.2 0.1z" fill="#ffba00"/>
                  </svg>
                </div>
                <span className="file-source-name">Google Drive</span>
                <span className="file-source-desc">Access from Drive</span>
              </button>
              <button 
                className="file-source-option active"
                onClick={() => {
                  setShowFileSourceModal(false);
                  document.getElementById('mandatory-file-upload').click();
                }}
              >
                <div className="file-source-icon local-icon">
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" stroke="#3b6eb5" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    <polyline points="17,8 12,3 7,8" stroke="#3b6eb5" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    <line x1="12" y1="3" x2="12" y2="15" stroke="#3b6eb5" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </div>
                <span className="file-source-name">Local Upload</span>
                <span className="file-source-desc">Upload from computer</span>
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};

export default HomePage;
