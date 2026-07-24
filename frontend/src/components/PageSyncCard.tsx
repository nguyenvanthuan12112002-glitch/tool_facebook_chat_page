"use client";

import React, { useState, useEffect, useRef, useMemo } from "react";
import styles from "./PageSyncCard.module.css";

interface PageData {
  id: number;
  page_id: string;
  page_name: string;
  facebook_user_id: string;
  avatar_url: string | null;
  status: string;
}

interface MessageData {
  id: number;
  facebook_message_id: string;
  page_id: string;
  sender_id: string;
  text: string;
  timestamp: number | null;
  direction: string;
  reactions?: string | null;
  reply_to_message_id?: string | null;
  created_at: string;
}

interface ConversationData {
  page_id: string;
  page_name: string;
  avatar_url: string | null;
  sender_id: string;
  last_message: string;
  timestamp: number | null;
  direction: string;
  is_read: boolean;
  is_replied: boolean;
  created_at: string;
}

interface NotificationData {
  id: string;
  facebook_notification_id: string;
  page_id: string;
  page_name: string;
  title: string;
  link: string | null;
  created_time: string;
  unread: boolean;
  is_replied: boolean;
}

interface ToastState {
  show: boolean;
  message: string;
  type: "success" | "error";
}

export default function PageSyncCard() {
  const API_BASE_URL = "http://localhost:8000/api/facebook";
  const WS_BASE_URL = "ws://localhost:8000/api/facebook/ws";

  // Config & Session
  const [facebookUserId, setFacebookUserId] = useState<string>("");
  const [customAccessToken, setCustomAccessToken] = useState<string>("");
  
  // ERROR CATCHING STATE
  const [crashError, setCrashError] = useState<string | null>(null);

  useEffect(() => {
    const handleErr = (msg: any, url: any, lineNo: any, columnNo: any, error: any) => {
      setCrashError(`${msg} @ ${lineNo}:${columnNo} \n ${error?.stack}`);
      return false;
    };
    window.onerror = handleErr;
    window.addEventListener("unhandledrejection", (e) => {
      setCrashError(`Unhandled Rejection: ${e.reason?.message || e.reason} \n ${e.reason?.stack}`);
    });
  }, []);
  
  // Data States
  const [dbPages, setDbPages] = useState<PageData[]>([]);
  const [conversations, setConversations] = useState<ConversationData[]>([]);
  const [messages, setMessages] = useState<MessageData[]>([]);
  const [notifications, setNotifications] = useState<NotificationData[]>([]);
  
  // Filter States
  const [chatFilter, setChatFilter] = useState<"all" | "unread" | "unreplied">("all");
  const [notificationFilter, setNotificationFilter] = useState<"all" | "unread" | "unreplied">("all");
  
  // Selection States
  const [activeThread, setActiveThread] = useState<{
    page_id: string;
    sender_id: string;
    type?: "chat" | "comment";
    comment_id?: string;
    title?: string;
    page_name?: string;
  } | null>(null);

  // Unified Omnichannel Inbox: Messenger Chats (Comments are only in Notifications Tab)
  const allThreads = useMemo(() => {
    let filteredConversations = conversations;
    if (chatFilter === "unread") {
      filteredConversations = filteredConversations.filter(c => !c.is_read);
    } else if (chatFilter === "unreplied") {
      filteredConversations = filteredConversations.filter(c => !c.is_replied);
    }

    const chatItems = filteredConversations.map((conv) => ({
      key: `chat-${conv.page_id}-${conv.sender_id}`,
      type: "chat" as const,
      page_id: conv.page_id,
      sender_id: conv.sender_id,
      created_at: conv.created_at,
      page_name: conv.page_name,
      preview: getPreviewText(conv),
      is_read: conv.is_read,
      is_replied: conv.is_replied
    }));

    chatItems.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    return chatItems;
  }, [conversations, chatFilter]);
  
  const filteredNotifications = useMemo(() => {
    let filtered = notifications;
    if (notificationFilter === "unread") {
      filtered = filtered.filter(n => n.unread);
    } else if (notificationFilter === "unreplied") {
      filtered = filtered.filter(n => !n.is_replied);
    }
    return filtered;
  }, [notifications, notificationFilter]);

  // Tab Switchers
  const [activeRightTab, setActiveRightTab] = useState<"config" | "notifications">("config");

  // Input states
  const [replyText, setReplyText] = useState<string>("");
  
  // Interactive UI states
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isResetting, setIsResetting] = useState<boolean>(false);
  const [isSending, setIsSending] = useState<boolean>(false);
  const [isSimulating, setIsSimulating] = useState<boolean>(false);
  const [toast, setToast] = useState<ToastState>({ show: false, message: "", type: "success" });
  const [commentReplies, setCommentReplies] = useState<Record<string, string>>({});
  const [customerProfiles, setCustomerProfiles] = useState<Record<string, { name: string; avatar?: string }>>({});
  const [activeCommentPicker, setActiveCommentPicker] = useState<{ notifId: string; type: "emoji" | "gif" | "sticker" | "role" } | null>(null);

  // Auto-resolve customer real names & avatars via Facebook Graph API
  useEffect(() => {
    conversations.forEach((conv) => {
      const psid = conv.sender_id;
      const pageId = conv.page_id;
      if (psid && pageId && !customerProfiles[psid]) {
        fetch(`${API_BASE_URL}/customer_profile/${psid}?page_id=${pageId}`)
          .then((res) => (res.ok ? res.json() : null))
          .then((data) => {
            if (data && data.name) {
              setCustomerProfiles((prev) => ({
                ...prev,
                [psid]: { name: data.name, avatar: data.avatar_url }
              }));
            }
          })
          .catch(() => {});
      }
    });
  }, [conversations]);
  
  // Refs
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const toastTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const wsPingRef = useRef<NodeJS.Timeout | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Additional Picker UI states
  const [showEmojiPicker, setShowEmojiPicker] = useState<boolean>(false);
  const [showStickerPicker, setShowStickerPicker] = useState<boolean>(false);
  const [showGifPicker, setShowGifPicker] = useState<boolean>(false);
  const [emojiActiveTab, setEmojiActiveTab] = useState<string>("smileys");

  // Message interaction states
  const [replyingTo, setReplyingTo] = useState<MessageData | null>(null);
  const [hoveredMessageId, setHoveredMessageId] = useState<string | null>(null);
  const [activeReactionMenuId, setActiveReactionMenuId] = useState<string | null>(null);
  const [activeActionMenuId, setActiveActionMenuId] = useState<string | null>(null);
  const [showForwardModal, setShowForwardModal] = useState<boolean>(false);
  const [messageToForward, setMessageToForward] = useState<MessageData | null>(null);

  // Voice recording states & refs
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [recordingTime, setRecordingTime] = useState<number>(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const recordingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Helper to parse dates in local timezone
  function parseDate(dateStr: string | number | null): Date {
    if (!dateStr) return new Date();
    if (typeof dateStr === "number") return new Date(dateStr);
    
    // If it's a string from FastAPI and doesn't contain timezone info, append 'Z' to treat it as UTC
    if (typeof dateStr === "string" && !dateStr.endsWith("Z") && !dateStr.includes("+")) {
      return new Date(dateStr + "Z");
    }
    return new Date(dateStr);
  };

  // Helper to render message content with attachments (image/file/audio)
  function renderMessageContent(text: string | null) {
    if (!text) return null;
    if (text.startsWith("[image] ")) {
      const url = text.substring(8);
      return <img src={url} alt="Attachment" className={styles.attachmentImage} onClick={() => window.open(url, "_blank")} />;
    }
    if (text.startsWith("[audio] ")) {
      const url = text.substring(8);
      return (
        <div style={{ marginTop: "4px", minWidth: "240px", maxWidth: "100%" }}>
          <audio src={url} controls style={{ width: "100%", height: "40px", borderRadius: "20px" }} />
        </div>
      );
    }
    if (text.startsWith("[file] ")) {
      const url = text.substring(7);
      const isVideo = /\.(mp4|webm|ogg|mov)$/i.test(url);
      if (isVideo) {
        return (
          <div style={{ marginTop: "4px", minWidth: "240px", maxWidth: "100%" }}>
            <video src={url} controls style={{ width: "100%", maxHeight: "300px", borderRadius: "8px" }} />
          </div>
        );
      }
      let fileName = url.substring(url.lastIndexOf("/") + 1);
      if (url.includes("/uploads/")) {
        fileName = fileName.substring(11); // Skip 10-digit epoch timestamp + 1 underscore
      }
      return (
        <a href={url} target="_blank" rel="noreferrer" className={styles.attachmentFile}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ flexShrink: 0 }}>
            <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
          </svg>
          <span style={{ wordBreak: "break-all" }}>{fileName || "Tải xuống tập tin"}</span>
        </a>
      );
    }
    return <div>{text}</div>;
  };

  // Helper to get thread list preview text
  function getPreviewText(thread: ConversationData) {
    if (!thread.last_message) return "Đính kèm";
    if (thread.last_message.startsWith("[image] ")) {
      return "📷 [Hình ảnh]";
    }
    if (thread.last_message.startsWith("[audio] ")) {
      return "🎙️ [Tin nhắn thoại]";
    }
    if (thread.last_message.startsWith("[file] ")) {
      const url = thread.last_message.substring(7);
      if (/\.(mp4|webm|ogg|mov)$/i.test(url)) return "🎥 [Video]";
      return "📎 [Tập tin]";
    }
    return (thread.direction === "outbound" ? "Bạn: " : "") + thread.last_message;
  };

  // Trigger floating toast alerts
  const triggerToast = (message: string, type: "success" | "error") => {
    if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
    setToast({ show: true, message, type });
    toastTimeoutRef.current = setTimeout(() => {
      setToast((prev) => ({ ...prev, show: false }));
    }, 5000);
  };

  const closeToast = () => {
    if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
    setToast((prev) => ({ ...prev, show: false }));
  };

  // Fetch local pages from DB
  const loadPagesFromDb = async (userId: string) => {
    if (!userId) return;
    try {
      const res = await fetch(`${API_BASE_URL}/pages?facebook_user_id=${userId}`);
      if (res.ok) {
        const data = await res.json();
        setDbPages(data || []);
      }
    } catch (err) {
      console.error("Failed to load local DB pages:", err);
    }
  };

  // Fetch active conversations list
  const loadConversations = async (userId: string) => {
    if (!userId) return;
    try {
      const res = await fetch(`${API_BASE_URL}/conversations?facebook_user_id=${userId}`);
      if (res.ok) {
        const data = await res.json();
        setConversations(data || []);
      }
    } catch (err) {
      console.error("Error loading conversations:", err);
    }
  };

  // Fetch live notifications
  const loadNotifications = async (userId: string) => {
    if (!userId) return;
    try {
      const res = await fetch(`${API_BASE_URL}/notifications?facebook_user_id=${userId}`);
      if (res.ok) {
        const data = await res.json();
        setNotifications(data || []);
      }
    } catch (err) {
      console.error("Error loading notifications:", err);
    }
  };

  // Fetch messages history for active chat thread
  const loadActiveThreadMessages = async (pageId: string, senderId: string) => {
    if (!facebookUserId) return;
    try {
      const res = await fetch(
        `${API_BASE_URL}/messages?facebook_user_id=${facebookUserId}&page_id=${pageId}&sender_id=${senderId}`
      );
      if (res.ok) {
        const data = await res.json();
        setMessages(data || []);
      }
    } catch (err) {
      console.error("Error loading messages:", err);
    }
  };

  // Initialization
  useEffect(() => {
    const savedUserId = localStorage.getItem("saved_fb_user_id");
    if (savedUserId) {
      setFacebookUserId(savedUserId);
      loadPagesFromDb(savedUserId);
      loadConversations(savedUserId);
      loadNotifications(savedUserId);
    }
    return () => {
      if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  // Poll conversations & notifications in background
  useEffect(() => {
    if (!facebookUserId) return;

    const intervalConversations = setInterval(() => loadConversations(facebookUserId), 4000);
    const intervalNotifications = setInterval(() => loadNotifications(facebookUserId), 5000);

    return () => {
      clearInterval(intervalConversations);
      clearInterval(intervalNotifications);
    };
  }, [facebookUserId]);

  // Load chat messages when active thread is updated
  useEffect(() => {
    if (activeThread) {
      loadActiveThreadMessages(activeThread.page_id, activeThread.sender_id);
    } else {
      setMessages([]);
    }
  }, [activeThread]);

  // Auto scroll chat body to the bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Track activeThread state in a Ref to prevent WebSocket reconnect loops when switching chats
  const activeThreadRef = useRef(activeThread);
  useEffect(() => {
    activeThreadRef.current = activeThread;
  }, [activeThread]);

  // Connect WebSocket for real-time pushes
  useEffect(() => {
    if (!facebookUserId) {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      return;
    }

    const connectWebSocket = () => {
      if (wsRef.current) wsRef.current.close();
      if (wsPingRef.current) clearInterval(wsPingRef.current);

      const socket = new WebSocket(`${WS_BASE_URL}/${facebookUserId}`);
      wsRef.current = socket;

      socket.onopen = () => {
        print(`[WebSocket] Connected to FastAPI backend client for User: ${facebookUserId}`);
        // Send ping every 25 seconds to keep connection alive
        wsPingRef.current = setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: "ping" }));
          }
        }, 25000);
      };

      socket.onmessage = (event) => {
        try {
          const packet = JSON.parse(event.data);
          if (packet.type === "pong") return; // ignore server pong
          
          if (packet.type === "message") {
            const newMsg: MessageData = packet.data;
            const currentThread = activeThreadRef.current;
            // 1. If incoming message belongs to current active thread, append it
            if (currentThread && currentThread.page_id === newMsg.page_id && currentThread.sender_id === newMsg.sender_id) {
              setMessages((prev) => {
                // Prevent duplicate inserts
                if (prev.some((m) => m.facebook_message_id === newMsg.facebook_message_id)) return prev;
                return [...prev, newMsg];
              });
            }
            // 2. Immediately update sidebar conversation preview
            loadConversations(facebookUserId);
          } 
          
          else if (packet.type === "reaction") {
            const reactionData = packet.data;
            setMessages((prev) =>
              prev.map((msg) =>
                msg.facebook_message_id === reactionData.facebook_message_id
                  ? { ...msg, reactions: reactionData.reactions }
                  : msg
              )
            );
          }

          else if (packet.type === "delete_message") {
            const deleteData = packet.data;
            setMessages((prev) =>
              prev.filter((msg) => msg.facebook_message_id !== deleteData.facebook_message_id)
            );
            loadConversations(facebookUserId);
          }

          else if (packet.type === "notification") {
            const newNotif: NotificationData = packet.data;
            setNotifications((prev) => {
              if (prev.some((n) => n.facebook_notification_id === newNotif.facebook_notification_id)) return prev;
              return [newNotif, ...prev];
            });
            // Trigger UI popup toast
            triggerToast(newNotif.title, "success");
          }
        } catch (err) {
          console.error("Error parsing WebSocket packet:", err);
        }
      };

      socket.onclose = () => {
        if (wsPingRef.current) clearInterval(wsPingRef.current);
        if (wsRef.current === socket) {
          print("[WebSocket] Disconnected. Reconnecting in 5 seconds...");
          setTimeout(() => {
            if (facebookUserId) connectWebSocket();
          }, 5000);
        }
      };
    };

    connectWebSocket();

    return () => {
      if (wsPingRef.current) clearInterval(wsPingRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [facebookUserId]);

  // Handle Token Syncing
  const handleSyncPages = async () => {
    if (!customAccessToken) {
      triggerToast("Vui lòng dán Facebook Access Token trước khi đồng bộ!", "error");
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/sync-by-token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ access_token: customAccessToken }),
      });
      const data = await response.json();

      if (response.ok) {
        setDbPages(data.pages || []);
        setFacebookUserId(data.facebook_user_id);
        localStorage.setItem("saved_fb_user_id", data.facebook_user_id);
        
        loadConversations(data.facebook_user_id);
        loadNotifications(data.facebook_user_id);
        
        triggerToast(data.message, "success");
        setCustomAccessToken(""); // clear input
      } else {
        const errorMsg = data.detail || "Có lỗi xảy ra khi đồng bộ.";
        // Catch auth/OAuth failures and trigger standard error toast
        if (response.status === 401) {
          triggerToast("Tài khoản bị mất kết nối, vui lòng xác thực lại.", "error");
        } else {
          triggerToast(errorMsg, "error");
        }
      }
    } catch (err) {
      triggerToast("Không thể kết nối đến API backend. Vui lòng kiểm tra server python.", "error");
    } finally {
      setIsLoading(false);
    }
  };

  const markChatRead = async (pageId: string, senderId: string) => {
    setConversations(prev => prev.map(c => (c.page_id === pageId && c.sender_id === senderId) ? { ...c, is_read: true } : c));
    try { await fetch(`${API_BASE_URL}/conversations/${pageId}/${senderId}/read`, { method: "PUT" }); } catch (e) {}
  };

  const markChatReplied = async (pageId: string, senderId: string) => {
    setConversations(prev => prev.map(c => (c.page_id === pageId && c.sender_id === senderId) ? { ...c, is_replied: true } : c));
    try { await fetch(`${API_BASE_URL}/conversations/${pageId}/${senderId}/replied`, { method: "PUT" }); } catch (e) {}
  };

  const markNotificationRead = async (notifId: string) => {
    setNotifications(prev => prev.map(n => n.facebook_notification_id === notifId ? { ...n, unread: false } : n));
    try { await fetch(`${API_BASE_URL}/notifications/${notifId}/read`, { method: "PUT" }); } catch (e) {}
  };

  const markNotificationReplied = async (notifId: string) => {
    setNotifications(prev => prev.map(n => n.facebook_notification_id === notifId ? { ...n, is_replied: true } : n));
    try { await fetch(`${API_BASE_URL}/notifications/${notifId}/replied`, { method: "PUT" }); } catch (e) {}
  };

  // Send Reply via Facebook Send API
  const handleSendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!activeThread || !replyText.trim() || isSending) return;

    const textToSend = replyText;
    setReplyText(""); // Clear input immediately for responsive UX
    setIsSending(true);
    try {
      const response = await fetch(`${API_BASE_URL}/send-reply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          page_id: activeThread.page_id,
          recipient_id: activeThread.sender_id,
          text: textToSend,
          reply_to_message_id: replyingTo?.facebook_message_id || null,
        }),
      });
      const data = await response.json();

      if (response.ok) {
        setReplyingTo(null);
        await markChatReplied(activeThread.page_id, activeThread.sender_id);
        // Reload messages from DB to show sent message accurately
        await loadActiveThreadMessages(activeThread.page_id, activeThread.sender_id);
        loadConversations(facebookUserId); // update sidebar snippet
      } else {
        setReplyText(textToSend); // Restore text if failed
        const errorMsg = data.detail || "Gửi tin nhắn thất bại.";
        if (response.status === 401) {
          triggerToast("Tài khoản bị mất kết nối, vui lòng xác thực lại.", "error");
        } else {
          triggerToast(errorMsg, "error");
        }
      }
    } catch (err) {
      setReplyText(textToSend); // Restore text if network error
      triggerToast("Không thể gửi tin nhắn. Lỗi kết nối server.", "error");
    } finally {
      setIsSending(false);
    }
  };

  // Send attachment (Image or File)
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !activeThread) return;

    const formData = new FormData();
    formData.append("page_id", activeThread.page_id);
    formData.append("recipient_id", activeThread.sender_id);
    formData.append("attachment_type", file.type.startsWith("image/") ? "image" : "file");
    formData.append("file", file);

    setIsSending(true);
    try {
      const response = await fetch(`${API_BASE_URL}/send-attachment`, {
        method: "POST",
        body: formData,
      });
      const data = await response.json();

      if (response.ok) {
        await markChatReplied(activeThread.page_id, activeThread.sender_id);
        await loadActiveThreadMessages(activeThread.page_id, activeThread.sender_id);
        loadConversations(facebookUserId); // update sidebar snippet
      } else {
        const errorMsg = data.detail || "Gửi tệp đính kèm thất bại.";
        triggerToast(errorMsg, "error");
      }
    } catch (err) {
      triggerToast("Không thể gửi tệp đính kèm. Lỗi kết nối server.", "error");
    } finally {
      setIsSending(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  // Send attachment using URL (Stickers / GIFs)
  const handleSendAttachmentUrl = async (url: string, type: "image" | "file") => {
    if (!activeThread) return;
    setIsSending(true);
    try {
      const response = await fetch(`${API_BASE_URL}/send-attachment-url`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          page_id: activeThread.page_id,
          recipient_id: activeThread.sender_id,
          attachment_type: type,
          url: url,
        }),
      });
      const data = await response.json();
      if (response.ok) {
        await markChatReplied(activeThread.page_id, activeThread.sender_id);
        await loadActiveThreadMessages(activeThread.page_id, activeThread.sender_id);
        loadConversations(facebookUserId); // update sidebar snippet
      } else {
        const errorMsg = data.detail || "Gửi tệp đính kèm thất bại.";
        triggerToast(errorMsg, "error");
      }
    } catch (err) {
      triggerToast("Không thể gửi tệp đính kèm. Lỗi kết nối server.", "error");
    } finally {
      setIsSending(false);
      setShowStickerPicker(false);
      setShowGifPicker(false);
    }
  };

  // Start recording voice note
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksRef.current = [];
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        const audioFile = new File([audioBlob], `voice_${Date.now()}.webm`, { type: "audio/webm" });
        
        if (!activeThread) return;
        const formData = new FormData();
        formData.append("page_id", activeThread.page_id);
        formData.append("recipient_id", activeThread.sender_id);
        formData.append("attachment_type", "audio");
        formData.append("file", audioFile);

        setIsSending(true);
        try {
          const response = await fetch(`${API_BASE_URL}/send-attachment`, {
            method: "POST",
            body: formData,
          });
          if (response.ok) {
            await markChatReplied(activeThread.page_id, activeThread.sender_id);
            await loadActiveThreadMessages(activeThread.page_id, activeThread.sender_id);
            loadConversations(facebookUserId);
          } else {
            triggerToast("Không thể gửi tin nhắn thoại.", "error");
          }
        } catch (err) {
          triggerToast("Lỗi gửi tin nhắn thoại.", "error");
        } finally {
          setIsSending(false);
        }

        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.start();
      setIsRecording(true);
      setRecordingTime(0);
      recordingIntervalRef.current = setInterval(() => {
        setRecordingTime((prev) => prev + 1);
      }, 1000);
    } catch (err) {
      triggerToast("Không thể truy cập Micro. Vui lòng cấp quyền ghi âm.", "error");
    }
  };

  // Stop recording and send
  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (recordingIntervalRef.current) clearInterval(recordingIntervalRef.current);
    }
  };

  // Cancel recording and discard
  const cancelRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      // Temporarily override onstop to discard recording
      mediaRecorderRef.current.onstop = () => {
        if (mediaRecorderRef.current) {
          const stream = mediaRecorderRef.current.stream;
          stream.getTracks().forEach((track) => track.stop());
        }
      };
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (recordingIntervalRef.current) clearInterval(recordingIntervalRef.current);
      triggerToast("Đã hủy ghi âm.", "success");
    }
  };

  // React to a message
  const handleReactToMessage = async (facebookMessageId: string, emoji: string | null) => {
    if (!activeThread) return;
    try {
      const response = await fetch(`${API_BASE_URL}/messages/${facebookMessageId}/react`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          page_id: activeThread.page_id,
          recipient_id: activeThread.sender_id,
          reaction: emoji,
        }),
      });
      if (response.ok) {
        setMessages((prev) =>
          prev.map((msg) =>
            msg.facebook_message_id === facebookMessageId ? { ...msg, reactions: emoji } : msg
          )
        );
      }
    } catch (err) {
      console.error("Error reacting to message:", err);
    } finally {
      setActiveReactionMenuId(null);
    }
  };

  // Unsend a message
  const handleUnsendMessage = async (facebookMessageId: string) => {
    if (!activeThread) return;
    if (!window.confirm("Bạn có chắc chắn muốn gỡ tin nhắn này không?")) return;
    try {
      const response = await fetch(`${API_BASE_URL}/messages/${facebookMessageId}?page_id=${activeThread.page_id}`, {
        method: "DELETE",
      });
      if (response.ok) {
        setMessages((prev) => prev.filter((m) => m.facebook_message_id !== facebookMessageId));
        loadConversations(facebookUserId); // update sidebar preview text
        triggerToast("Tin nhắn đã được gỡ bỏ.", "success");
      } else {
        triggerToast("Không thể gỡ tin nhắn.", "error");
      }
    } catch (err) {
      triggerToast("Lỗi kết nối khi gỡ tin nhắn.", "error");
    } finally {
      setActiveActionMenuId(null);
    }
  };

  // Forward a message to another thread
  const handleForwardMessage = async (targetPageId: string, targetSenderId: string) => {
    if (!messageToForward) return;
    
    let content = messageToForward.text || "";
    setIsSending(true);
    try {
      let response;
      if (content.startsWith("[image] ") || content.startsWith("[file] ") || content.startsWith("[audio] ")) {
        const prefix = content.split(" ")[0];
        const attType = prefix === "[image]" ? "image" : "file";
        const url = content.substring(prefix.length + 1);
        
        response = await fetch(`${API_BASE_URL}/send-attachment-url`, {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: new URLSearchParams({
            page_id: targetPageId,
            recipient_id: targetSenderId,
            attachment_type: attType,
            url: url,
          }),
        });
      } else {
        response = await fetch(`${API_BASE_URL}/send-reply`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            page_id: targetPageId,
            recipient_id: targetSenderId,
            text: content,
          }),
        });
      }

      if (response.ok) {
        triggerToast("Đã chuyển tiếp tin nhắn thành công.", "success");
        if (activeThread && activeThread.page_id === targetPageId && activeThread.sender_id === targetSenderId) {
          await loadActiveThreadMessages(targetPageId, targetSenderId);
        }
      } else {
        triggerToast("Chuyển tiếp thất bại.", "error");
      }
    } catch (err) {
      triggerToast("Lỗi kết nối khi chuyển tiếp.", "error");
    } finally {
      setIsSending(false);
      setShowForwardModal(false);
      setMessageToForward(null);
      setActiveActionMenuId(null);
    }
  };

  // Report message mock
  const handleReportMessage = (facebookMessageId: string) => {
    triggerToast("Đã gửi báo cáo tin nhắn vi phạm tới Facebook.", "success");
    setActiveActionMenuId(null);
  };

  // Reset database
  const handleResetDatabase = async () => {
    if (window.confirm("Bạn có chắc chắn muốn xóa toàn bộ dữ liệu tài khoản, tin nhắn và trang không?")) {
      setIsResetting(true);
      try {
        const response = await fetch(`${API_BASE_URL}/reset`, { method: "POST" });
        const data = await response.json();

        if (response.ok) {
          setDbPages([]);
          setConversations([]);
          setMessages([]);
          setNotifications([]);
          setFacebookUserId("");
          setCustomAccessToken("");
          setActiveThread(null);
          localStorage.removeItem("saved_fb_user_id");
          triggerToast(data.message || "Đã xóa toàn bộ dữ liệu thành công.", "success");
        } else {
          triggerToast(data.detail || "Không thể reset dữ liệu.", "error");
        }
      } catch (err) {
        triggerToast("Không thể kết nối đến API backend.", "error");
      } finally {
        setIsResetting(false);
      }
    }
  };

  // Reply to comment directly from notification
  const handleReplyToComment = async (commentId: string, pageId: string) => {
    const text = commentReplies[commentId];
    if (!text || !text.trim()) return;

    try {
      const response = await fetch(`${API_BASE_URL}/comments/${commentId}/reply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ page_id: pageId, text }),
      });
      if (response.ok) {
        triggerToast("Đã phản hồi bình luận thành công!", "success");
        setCommentReplies((prev) => ({ ...prev, [commentId]: "" }));
        await markNotificationReplied(commentId);
      } else {
        const data = await response.json();
        triggerToast(data.detail || "Không thể phản hồi bình luận.", "error");
      }
    } catch (err) {
      triggerToast("Lỗi kết nối khi gửi phản hồi bình luận.", "error");
    }
  };

  // React/Like comment directly from notification
  const handleReactToComment = async (commentId: string, pageId: string, emojiName: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/comments/${commentId}/react`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ page_id: pageId, reaction: emojiName }),
      });
      if (response.ok) {
        triggerToast("Thả cảm xúc bình luận thành công!", "success");
      } else {
        const data = await response.json();
        triggerToast(data.detail || "Không thể thả cảm xúc bình luận.", "error");
      }
    } catch (err) {
      triggerToast("Lỗi kết nối khi thả cảm xúc bình luận.", "error");
    }
  };

  // Webhook Event Simulation
  const handleSimulateWebhookMessage = async (simulateType: "message" | "comment" | "like") => {
    if (dbPages.length === 0) {
      triggerToast("Vui lòng đồng bộ fanpage trước khi giả lập sự kiện!", "error");
      return;
    }

    setIsSimulating(true);
    try {
      const targetPage = dbPages[Math.floor(Math.random() * dbPages.length)];
      const randomSenderId = "psid_" + Math.floor(Math.random() * 1000000000);
      const randomMsgId = "mid.mock_" + Math.random().toString(36).substring(2, 15);
      const timestamp = Date.now();
      
      let payload: any = { object: "page", entry: [] };

      if (simulateType === "message") {
        const sampleTexts = [
          "Xin chào shop, sản phẩm này còn hàng không?",
          "Bên mình có ship COD vào TP.HCM không ạ?",
          "Shop tư vấn giúp mình mẫu này với!",
          "Cho mình xin bảng giá sỉ sản phẩm này nhé.",
          "Đơn hàng của mình đã gửi đi chưa shop ơi?"
        ];
        const randomText = sampleTexts[Math.floor(Math.random() * sampleTexts.length)];
        payload.entry.push({
          id: targetPage.page_id,
          time: Math.floor(timestamp / 1000),
          messaging: [{
            sender: { id: randomSenderId },
            recipient: { id: targetPage.page_id },
            timestamp: timestamp,
            message: { mid: randomMsgId, text: randomText }
          }]
        });
      } 
      
      else {
        // Feed events (Comments/Likes)
        const mockChange: any = {
          field: "feed",
          value: {
            item: simulateType,
            verb: "add",
            sender_name: ["Quốc Anh", "Minh Thư", "Hoàng Nam", "Bích Phương"][Math.floor(Math.random() * 4)],
            sender_id: randomSenderId,
            post_id: "post_11223344"
          }
        };

        if (simulateType === "comment") {
          mockChange.value.comment_id = "comment_" + Math.random().toString(36).substring(2, 10);
          mockChange.value.message = "Mẫu này đẹp quá, inbox báo giá giúp em nha page!";
        }

        payload.entry.push({
          id: targetPage.page_id,
          time: Math.floor(timestamp / 1000),
          changes: [mockChange]
        });
      }

      const response = await fetch(`${API_BASE_URL}/webhook`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (response.ok) {
        triggerToast("Đã đẩy gói tin giả lập webhook thành công!", "success");
      } else {
        triggerToast("Gửi webhook giả lập thất bại.", "error");
      }
    } catch (err) {
      triggerToast("Lỗi kết nối khi gửi giả lập webhook.", "error");
    } finally {
      setIsSimulating(false);
    }
  };

  // Helper log utility
  function print(msg: string) {
    console.log(msg);
  }

  // 24-Hour Policy Checker:
  // Find the last message sent by the customer (direction == "inbound")
  // Calculate if the duration since that message has exceeded 24 hours.
  let is24hBlocked = false;
  let timeRemainingText = "";
  if (activeThread && messages.length > 0) {
    const inboundMessages = messages.filter((m) => m.direction === "inbound");
    if (inboundMessages.length > 0) {
      const lastCustomerMsg = inboundMessages[inboundMessages.length - 1];
      const lastMsgTime = parseDate(lastCustomerMsg.created_at).getTime();
      const timeDiffMs = Date.now() - lastMsgTime;
      const hoursDiff = timeDiffMs / (1000 * 60 * 60);
      
      if (hoursDiff >= 24) {
        is24hBlocked = true;
      } else {
        const minsLeft = Math.round((24 - hoursDiff) * 60);
        timeRemainingText = `Còn ${Math.floor(minsLeft / 60)}h ${minsLeft % 60}m để phản hồi`;
      }
    }
  }

  const unreadNotifsCount = notifications.filter((n) => n.unread).length;

  return (
    <div className={styles.container}>
      {crashError && (
        <div style={{ position: 'fixed', top: 0, left: 0, width: '100%', background: 'red', color: 'white', padding: '20px', zIndex: 99999, overflow: 'auto', maxHeight: '100vh', wordBreak: 'break-all' }}>
          <h2>🚨 Xảy ra lỗi trên giao diện (Client-side Crash):</h2>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: '14px' }}>{crashError}</pre>
          <button onClick={() => setCrashError(null)} style={{ background: 'black', color: 'white', padding: '8px 16px', border: 'none', cursor: 'pointer', marginTop: '10px' }}>Đóng / Bỏ qua lỗi</button>
        </div>
      )}
      {/* Toast popup */}
      {toast.show && (
        <div className={`${styles.toast} ${toast.type === "success" ? styles.toastSuccess : styles.toastError}`}>
          {toast.type === "success" ? (
            <svg className={styles.toastIcon} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          ) : (
            <svg className={styles.toastIcon} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          )}
          <span className={styles.toastMessage}>{toast.message}</span>
          <button className={styles.toastCloseBtn} onClick={closeToast}>×</button>
        </div>
      )}

      {/* Title */}
      <div className={styles.header}>
        <div>
          <h1 className={styles.headerTitle}>Hội thoại Đa kênh (Omnichannel Dashboard)</h1>
          <p className={styles.headerDesc}>Quản lý chat tập trung, đồng bộ các Fanpage và nhận thông báo thời gian thực.</p>
        </div>
      </div>

      {/* Main Omnichannel Dashboard Layout */}
      <div className={styles.dashboardLayout}>
        
        {/* COLUMN 1: Conversations list */}
        <div className={styles.leftPanel}>
          <div className={styles.panelHeader}>
            <span>Hội thoại</span>
            <span style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "none" }}>
              ({allThreads.length} Active)
            </span>
          </div>
          
          <div className={styles.filterTabs}>
            <button className={`${styles.filterTab} ${chatFilter === "all" ? styles.filterTabActive : ""}`} onClick={() => setChatFilter("all")}>Tất cả</button>
            <button className={`${styles.filterTab} ${chatFilter === "unread" ? styles.filterTabActive : ""}`} onClick={() => setChatFilter("unread")}>Chưa xem</button>
            <button className={`${styles.filterTab} ${chatFilter === "unreplied" ? styles.filterTabActive : ""}`} onClick={() => setChatFilter("unreplied")}>Chưa trả lời</button>
          </div>
          
          <div className={styles.threadList}>
            {allThreads.length === 0 ? (
              <div style={{ padding: "20px", color: "var(--text-muted)", fontSize: "12px", textAlign: "center" }}>
                Chưa có hội thoại nào. Đồng bộ trang và nhắn thử tin nhắn hoặc bình luận để test.
              </div>
            ) : (
              allThreads.map((thread) => {
                const isActive = activeThread?.type !== "comment" && activeThread?.page_id === thread.page_id && activeThread?.sender_id === thread.sender_id;
                const customerName = customerProfiles[thread.sender_id]?.name || `KH: ${thread.sender_id?.substring(0, 8) || "Unknown"}...`;

                return (
                  <div
                    key={thread.key}
                    className={`${styles.threadItem} ${isActive ? styles.threadItemActive : ""}`}
                    onClick={() => {
                      setActiveThread({ type: "chat", page_id: thread.page_id, sender_id: thread.sender_id });
                      markChatRead(thread.page_id, thread.sender_id);
                    }}
                  >
                    <div className={styles.threadMeta}>
                      <span className={styles.threadSender} style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                        <span style={{ fontSize: "9px", padding: "1px 5px", borderRadius: "4px", background: "rgba(59, 130, 246, 0.2)", color: "#60a5fa", fontWeight: 700 }}>
                          💬 Chat
                        </span>
                        <span>{customerName}</span>
                      </span>
                      <span className={styles.threadTime}>
                        {parseDate(thread.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                    <div className={styles.threadPreview}>
                      <span style={{ fontWeight: thread.is_read ? "normal" : "bold", color: thread.is_read ? "inherit" : "#fff" }}>
                        {thread.preview}
                      </span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "6px" }}>
                      <div className={styles.threadPageBadge}>
                        {thread.page_name}
                      </div>
                      <div style={{ display: "flex", gap: "6px", fontSize: "10px" }}>
                        {!thread.is_read && <span style={{ display: "flex", alignItems: "center", gap: "3px", color: "#60a5fa" }}>🔵 Chưa xem</span>}
                        {thread.is_replied && <span style={{ display: "flex", alignItems: "center", gap: "3px", color: "#34d399" }}>✔ Đã trả lời</span>}
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* COLUMN 2: Center Chat Workspace */}
        <div className={styles.centerPanel}>
          {activeThread ? (
            activeThread.type === "comment" ? (
              <>
                  {/* Chat Header for Comment Thread */}
                  <div className={styles.chatHeader}>
                    <div className={styles.avatarWrapper} style={{ width: "38px", height: "38px", background: "#8b5cf6" }}>
                      <span style={{ fontSize: "14px", fontWeight: 700, color: "#ffffff" }}>
                        {(activeThread.title || "K").charAt(0).toUpperCase()}
                      </span>
                    </div>
                    <div>
                      <div className={styles.chatHeaderTitle} style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                        <span>{activeThread.title?.split("đã bình luận")[0]?.trim() || "Khách hàng"}</span>
                        <span style={{ fontSize: "10px", background: "rgba(168, 85, 247, 0.2)", color: "#c084fc", padding: "2px 6px", borderRadius: "4px", fontWeight: 700 }}>
                          Bình luận bài viết
                        </span>
                      </div>
                      <div className={styles.chatHeaderSubtitle}>
                        Trang nhận: {activeThread.page_name}
                      </div>
                    </div>
                  </div>

                  {/* Chat Body for Comment Thread */}
                  <div className={styles.chatBody}>
                    <div className={styles.messageRow} style={{ justifyContent: "flex-start", marginBottom: "16px" }}>
                      <div className={styles.bubble} style={{ background: "rgba(139, 92, 246, 0.12)", border: "1px solid rgba(139, 92, 246, 0.3)", maxWidth: "85%", borderRadius: "16px", padding: "12px 16px" }}>
                        <div style={{ fontSize: "13px", fontWeight: 600, color: "#e9d5ff", marginBottom: "6px" }}>
                          {activeThread.title}
                        </div>
                        <div className={styles.commentReactionContainer} style={{ marginTop: "8px" }}>
                          {[
                            { emoji: "👍", name: "LIKE" },
                            { emoji: "❤️", name: "LOVE" },
                            { emoji: "😂", name: "HAHA" },
                            { emoji: "😮", name: "WOW" },
                            { emoji: "😢", name: "SAD" },
                            { emoji: "😡", name: "ANGRY" }
                          ].map((item) => (
                            <span
                              key={item.name}
                              className={styles.commentReactionEmoji}
                              onClick={() => handleReactToComment(activeThread.comment_id!, activeThread.page_id, item.name)}
                              title={`Thả cảm xúc ${item.emoji}`}
                            >
                              {item.emoji}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Center Panel Bottom Bar: Facebook-Style Comment Reply Input Bar */}
                  <div className={styles.messengerInputBar} style={{ padding: "12px" }}>
                    {(() => {
                      const notifId = activeThread.comment_id!;
                      const targetPage = dbPages.find((p) => p.page_id === activeThread.page_id);
                      const pageAvatar = targetPage?.avatar_url;
                      return (
                        <div className={styles.fbCommentWrapper}>
                          <div className={styles.fbCommentAvatarBadge} title={`Bình luận với tư cách ${activeThread.page_name}`}>
                            <div className={styles.fbAvatarCircle}>
                              {pageAvatar ? (
                                <img src={pageAvatar} alt="" />
                              ) : (
                                <span>{(activeThread.page_name || "P").charAt(0).toUpperCase()}</span>
                              )}
                            </div>
                            <div className={styles.fbAvatarBadgeArrow}>▼</div>
                          </div>

                          <div className={styles.fbCommentInputContainer}>
                            {/* Interactive Popups */}
                            {activeCommentPicker?.notifId === notifId && (
                              <div className={styles.commentPickerPopup} onClick={(e) => e.stopPropagation()}>
                                {activeCommentPicker.type === "emoji" && (
                                  <>
                                    <div className={styles.commentPickerTitle}>Biểu tượng cảm xúc</div>
                                    <div className={styles.commentPickerGrid}>
                                      {["😊", "👍", "❤️", "🔥", "🎉", "🙏", "😍", "🥰", "😂", "😮", "😢", "😡", "✨", "💯"].map((em) => (
                                        <span
                                          key={em}
                                          className={styles.commentPickerItem}
                                          onClick={() => {
                                            setCommentReplies((prev) => ({
                                              ...prev,
                                              [notifId]: (prev[notifId] || "") + em
                                            }));
                                            setActiveCommentPicker(null);
                                          }}
                                        >
                                          {em}
                                        </span>
                                      ))}
                                    </div>
                                  </>
                                )}
                                {activeCommentPicker.type === "gif" && (
                                  <>
                                    <div className={styles.commentPickerTitle}>Ảnh động GIF</div>
                                    <div className={styles.commentPickerGrid}>
                                      {["[GIF Cảm ơn]", "[GIF Xin chào]", "[GIF Thả tim]", "[GIF Chúc mừng]"].map((gifText) => (
                                        <span
                                          key={gifText}
                                          className={styles.commentPickerBadgeItem}
                                          onClick={() => {
                                            setCommentReplies((prev) => ({
                                              ...prev,
                                              [notifId]: (prev[notifId] || "") + " " + gifText
                                            }));
                                            setActiveCommentPicker(null);
                                          }}
                                        >
                                          {gifText}
                                        </span>
                                      ))}
                                    </div>
                                  </>
                                )}
                                {activeCommentPicker.type === "sticker" && (
                                  <>
                                    <div className={styles.commentPickerTitle}>Nhãn dán Sticker</div>
                                    <div className={styles.commentPickerGrid}>
                                      {["👍 Like", "❤️ Love", "🎉 Party", "🔥 Hot", "⭐ Star", "🐱 Cute Cat"].map((stk) => (
                                        <span
                                          key={stk}
                                          className={styles.commentPickerBadgeItem}
                                          onClick={() => {
                                            setCommentReplies((prev) => ({
                                              ...prev,
                                              [notifId]: (prev[notifId] || "") + " " + stk
                                            }));
                                            setActiveCommentPicker(null);
                                          }}
                                        >
                                          {stk}
                                        </span>
                                      ))}
                                    </div>
                                  </>
                                )}
                                {activeCommentPicker.type === "role" && (
                                  <>
                                    <div className={styles.commentPickerTitle}>Bình luận với tư cách Trang:</div>
                                    {dbPages.map((pg) => (
                                      <div
                                        key={pg.page_id}
                                        className={styles.commentPickerRoleItem}
                                        onClick={() => {
                                          triggerToast(`Đã chuyển vai trò bình luận sang ${pg.page_name}`, "success");
                                          setActiveCommentPicker(null);
                                        }}
                                      >
                                        <span>📄</span>
                                        <strong>{pg.page_name}</strong>
                                      </div>
                                    ))}
                                  </>
                                )}
                              </div>
                            )}

                            <input
                              type="text"
                              className={styles.fbCommentTextInput}
                              placeholder={`Trả lời bình luận với tư cách ${activeThread.page_name}...`}
                              value={commentReplies[notifId] || ""}
                              onChange={(e) => setCommentReplies((prev) => ({
                                ...prev,
                                [notifId]: e.target.value
                              }))}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") {
                                  e.preventDefault();
                                  handleReplyToComment(notifId, activeThread.page_id);
                                }
                              }}
                            />
                            <div className={styles.fbCommentToolbar}>
                              <div className={styles.fbToolbarLeftIcons}>
                                <button type="button" className={styles.fbToolbarIconBtn} title="Chọn vai trò bình luận" onClick={(e) => { e.stopPropagation(); setActiveCommentPicker(activeCommentPicker?.notifId === notifId && activeCommentPicker.type === "role" ? null : { notifId, type: "role" }); }}>
                                  <svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 3c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zm0 14.2c-2.5 0-4.71-1.28-6-3.22.03-1.99 4-3.08 6-3.08 1.99 0 5.97 1.09 6 3.08-1.29 1.94-3.5 3.22-6 3.22z"/></svg>
                                </button>
                                <button type="button" className={styles.fbToolbarIconBtn} title="Chèn biểu tượng cảm xúc" onClick={(e) => { e.stopPropagation(); setActiveCommentPicker(activeCommentPicker?.notifId === notifId && activeCommentPicker.type === "emoji" ? null : { notifId, type: "emoji" }); }}>
                                  <svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor"><path d="M12 2C6.47 2 2 6.47 2 12s4.47 10 10 10 10-4.47 10-10S17.53 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm3.5-9c.83 0 1.5-.67 1.5-1.5S16.33 8 15.5 8 14 8.67 14 9.5s.67 1.5 1.5 1.5zm-7 0c.83 0 1.5-.67 1.5-1.5S9.33 8 8.5 8 7 8.67 7 9.5 7.67 11 8.5 11zm3.5 6.5c2.33 0 4.31-1.46 5.11-3.5H6.89c.8 2.04 2.78 3.5 5.11 3.5z"/></svg>
                                </button>
                                <button type="button" className={styles.fbToolbarIconBtn} title="Đính kèm ảnh hoặc video" onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click(); }}>
                                  <svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor"><path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"/><path d="M9 2L7.17 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2h-3.17L15 2H9zm3 15c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5z"/></svg>
                                </button>
                                <button type="button" className={styles.fbToolbarIconBtn} title="Đính kèm file GIF" onClick={(e) => { e.stopPropagation(); setActiveCommentPicker(activeCommentPicker?.notifId === notifId && activeCommentPicker.type === "gif" ? null : { notifId, type: "gif" }); }}>
                                  <span style={{ fontSize: "9px", fontWeight: 800, border: "1.2px solid currentColor", borderRadius: "3px", padding: "0 2px" }}>GIF</span>
                                </button>
                                <button type="button" className={styles.fbToolbarIconBtn} title="Đính kèm nhãn dán" onClick={(e) => { e.stopPropagation(); setActiveCommentPicker(activeCommentPicker?.notifId === notifId && activeCommentPicker.type === "sticker" ? null : { notifId, type: "sticker" }); }}>
                                  <svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor"><path d="M12 2A10 10 0 0 0 2 12a10 10 0 0 0 10 10 10 10 0 0 0 10-10A10 10 0 0 0 12 2zm1 17.93V15a1 1 0 0 1 1-1h4.93A8.001 8.001 0 0 1 13 19.93zM19.93 13H15a3 3 0 0 0-3 3v4.93A8.006 8.006 0 0 1 4 12C4 7.58 7.58 4 12 4s8 3.58 8 8c0 .34-.02.67-.07 1z"/></svg>
                                </button>
                              </div>
                              <button
                                type="button"
                                className={`${styles.fbSendBtn} ${(commentReplies[notifId] || "").trim() ? styles.fbSendBtnActive : ""}`}
                                onClick={() => handleReplyToComment(notifId, activeThread.page_id)}
                                disabled={!(commentReplies[notifId] || "").trim()}
                                title="Gửi bình luận"
                              >
                                <svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
                              </button>
                            </div>
                          </div>
                        </div>
                      );
                    })()}
                  </div>
                </>
              ) : (
                <>
                  {/* Chat Header */}
                  <div className={styles.chatHeader}>
                    <div className={styles.avatarWrapper} style={{ width: "38px", height: "38px" }}>
                      {customerProfiles[activeThread.sender_id]?.avatar ? (
                        <img src={customerProfiles[activeThread.sender_id].avatar} alt="" className={styles.avatar} />
                      ) : (
                        <span style={{ fontSize: "14px", fontWeight: 700, color: "#3b82f6" }}>
                          {(customerProfiles[activeThread.sender_id]?.name || "KH").charAt(0).toUpperCase()}
                        </span>
                      )}
                    </div>
                    <div>
                      <div className={styles.chatHeaderTitle}>
                        {customerProfiles[activeThread.sender_id]?.name || `Khách hàng (${activeThread.sender_id.substring(0, 8)}...)`}
                      </div>
                      <div className={styles.chatHeaderSubtitle}>
                        PSID: {activeThread.sender_id} • Kênh nhận: {conversations.find((c) => c.page_id === activeThread.page_id)?.page_name || activeThread.page_id}
                      </div>
                    </div>
                  </div>

                  {/* Chat Messages */}
                  <div className={styles.chatBody}>
                    {messages.map((msg) => {
                      const isOut = msg.direction === "outbound";
                      const showActions = hoveredMessageId === msg.facebook_message_id;
                      const reactionsMenuOpen = activeReactionMenuId === msg.facebook_message_id;
                      const actionMenuOpen = activeActionMenuId === msg.facebook_message_id;

                      return (
                    <div
                      key={msg.id}
                      className={`${styles.messageRow} ${isOut ? styles.messageRowOutbound : styles.messageRowInbound}`}
                      onMouseEnter={() => setHoveredMessageId(msg.facebook_message_id)}
                      onMouseLeave={() => {
                        setHoveredMessageId(null);
                        setActiveReactionMenuId(null);
                        setActiveActionMenuId(null);
                      }}
                      style={{ position: "relative" }}
                    >
                      {/* Outbound hover utility buttons on the left */}
                      {isOut && showActions && (
                        <div className={styles.bubbleActionsLeft}>
                          <button type="button" className={styles.bubbleActionBtn} onClick={() => setActiveReactionMenuId(reactionsMenuOpen ? null : msg.facebook_message_id)} title="Thả cảm xúc">😃</button>
                          <button type="button" className={styles.bubbleActionBtn} onClick={() => setReplyingTo(msg)} title="Trả lời">↩️</button>
                          <button type="button" className={styles.bubbleActionBtn} onClick={() => setActiveActionMenuId(actionMenuOpen ? null : msg.facebook_message_id)} title="Khác">⋮</button>
                        </div>
                      )}

                      <div className={`${styles.bubble} ${isOut ? styles.bubbleOutbound : styles.bubbleInbound}`}>
                        {/* Quoted Reply Quote Container */}
                        {msg.reply_to_message_id && (
                          <div className={styles.quotedQuoteContainer}>
                            {(() => {
                              const quotedMsg = messages.find(m => m.facebook_message_id === msg.reply_to_message_id);
                              const textToRender = quotedMsg ? (
                                quotedMsg.text?.startsWith("[image] ") ? "📷 [Hình ảnh]" : 
                                quotedMsg.text?.startsWith("[file] ") && /\.(mp4|webm|ogg|mov)$/i.test(quotedMsg.text.substring(7)) ? "🎥 [Video]" :
                                quotedMsg.text?.startsWith("[file] ") ? "📎 [Tập tin]" : 
                                quotedMsg.text?.startsWith("[audio] ") ? "🎙️ [Tin nhắn thoại]" : 
                                quotedMsg.text
                              ) : "Tin nhắn đã bị gỡ";
                              return (
                                <div className={styles.quotedQuoteText}>
                                  {textToRender}
                                </div>
                              );
                            })()}
                          </div>
                        )}

                        {renderMessageContent(msg.text)}

                        {/* Reaction emoji badge */}
                        {msg.reactions && (
                          <div className={`${styles.reactionBadge} ${isOut ? styles.reactionBadgeOut : styles.reactionBadgeIn}`}>
                            {msg.reactions}
                          </div>
                        )}

                        <div style={{ 
                          fontSize: "9px", 
                          opacity: 0.6, 
                          textAlign: isOut ? "right" : "left", 
                          marginTop: "4px" 
                        }}>
                          {parseDate(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </div>
                      </div>

                      {/* Inbound hover utility buttons on the right */}
                      {!isOut && showActions && (
                        <div className={styles.bubbleActionsRight}>
                          <button type="button" className={styles.bubbleActionBtn} onClick={() => setActiveReactionMenuId(reactionsMenuOpen ? null : msg.facebook_message_id)} title="Thả cảm xúc">😃</button>
                          <button type="button" className={styles.bubbleActionBtn} onClick={() => setReplyingTo(msg)} title="Trả lời">↩️</button>
                          <button type="button" className={styles.bubbleActionBtn} onClick={() => setActiveActionMenuId(actionMenuOpen ? null : msg.facebook_message_id)} title="Khác">⋮</button>
                        </div>
                      )}

                      {/* Tooltip Quick Reaction Picker */}
                      {reactionsMenuOpen && (
                        <div className={`${styles.reactionTooltip} ${isOut ? styles.reactionTooltipOut : styles.reactionTooltipIn}`}>
                          {["👍", "❤️", "😂", "😮", "😢", "😡"].map((emoji) => (
                            <span
                              key={emoji}
                              className={styles.reactionTooltipEmoji}
                              onClick={() => handleReactToMessage(msg.facebook_message_id, msg.reactions === emoji ? null : emoji)}
                            >
                              {emoji}
                            </span>
                          ))}
                        </div>
                      )}

                      {/* More Popover Context Menu (Gỡ, Chuyển tiếp, Báo cáo) */}
                      {actionMenuOpen && (
                        <div className={`${styles.actionContextMenu} ${isOut ? styles.actionContextMenuOut : styles.actionContextMenuIn}`}>
                          <button type="button" className={styles.contextMenuItem} onClick={() => handleUnsendMessage(msg.facebook_message_id)}>Gỡ bỏ</button>
                          <button type="button" className={styles.contextMenuItem} onClick={() => {
                            setMessageToForward(msg);
                            setShowForwardModal(true);
                            setActiveActionMenuId(null);
                          }}>Chuyển tiếp</button>
                          <button type="button" className={styles.contextMenuItem} onClick={() => handleReportMessage(msg.facebook_message_id)}>Báo cáo</button>
                        </div>
                      )}
                    </div>
                  );
                    })}
                    <div ref={chatEndRef} />
                  </div>

                  {/* Chat Footer / Input controls */}
                  <div className={styles.chatFooter}>
                {is24hBlocked ? (
                  <div className={styles.warning24h}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                      <line x1="12" y1="9" x2="12" y2="13" />
                      <line x1="12" y1="17" x2="12.01" y2="17" />
                    </svg>
                    Vượt quá chính sách 24h của Facebook, không thể gửi tin nhắn phản hồi mới.
                  </div>
                ) : timeRemainingText ? (
                  <div style={{ fontSize: "11px", color: "#f59e0b", marginBottom: "8px", fontWeight: 600 }}>
                    ⚠️ {timeRemainingText}
                  </div>
                ) : null}

                {/* Reply Quote Preview Banner */}
                {replyingTo && (
                  <div style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    background: "rgba(255, 255, 255, 0.05)",
                    borderLeft: "4px solid #0084ff",
                    padding: "8px 12px",
                    borderRadius: "4px",
                    marginBottom: "8px",
                    fontSize: "12px",
                    color: "var(--text-secondary)"
                  }}>
                    <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      Đang trả lời: <strong>{
                        replyingTo.text?.startsWith("[image] ") ? "📷 [Hình ảnh]" : 
                        replyingTo.text?.startsWith("[file] ") && /\.(mp4|webm|ogg|mov)$/i.test(replyingTo.text.substring(7)) ? "🎥 [Video]" :
                        replyingTo.text?.startsWith("[file] ") ? "📎 [Tập tin]" : 
                        replyingTo.text?.startsWith("[audio] ") ? "🎙️ [Tin nhắn thoại]" : 
                        replyingTo.text
                      }</strong>
                    </div>
                    <button
                      type="button"
                      onClick={() => setReplyingTo(null)}
                      style={{ background: "none", border: "none", color: "#f87171", cursor: "pointer", fontWeight: 700 }}
                    >
                      Hủy
                    </button>
                  </div>
                )}

                {isRecording ? (
                  <div style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    background: "rgba(239, 68, 68, 0.08)",
                    border: "1px solid rgba(239, 68, 68, 0.2)",
                    borderRadius: "20px",
                    padding: "8px 16px",
                    width: "100%",
                    animation: "pulse-glow 2s infinite"
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <span style={{
                        width: "8px",
                        height: "8px",
                        borderRadius: "50%",
                        backgroundColor: "#ef4444",
                        display: "inline-block",
                        animation: "spin 1.5s linear infinite"
                      }} />
                      <span style={{ fontSize: "13px", fontWeight: 600, color: "#fca5a5" }}>
                        Đang ghi âm: {Math.floor(recordingTime / 60).toString().padStart(2, '0')}:{(recordingTime % 60).toString().padStart(2, '0')}
                      </span>
                    </div>
                    <div style={{ display: "flex", gap: "12px" }}>
                      <button
                        type="button"
                        className={`${styles.btn} ${styles.btnSecondary}`}
                        onClick={cancelRecording}
                        style={{ padding: "6px 12px", fontSize: "11px", borderColor: "rgba(239, 68, 68, 0.3)", color: "#ef4444" }}
                      >
                        Hủy
                      </button>
                      <button
                        type="button"
                        className={`${styles.btn} ${styles.btnPrimary}`}
                        onClick={stopRecording}
                        style={{ padding: "6px 12px", fontSize: "11px", backgroundColor: "#ef4444" }}
                      >
                        Gửi ghi âm 🎙️
                      </button>
                    </div>
                  </div>
                ) : (
                  <form onSubmit={handleSendMessage} className={styles.messengerInputBar}>
                    {/* Hidden File Input */}
                    <input
                      type="file"
                      ref={fileInputRef}
                      style={{ display: "none" }}
                      onChange={handleFileChange}
                      accept="image/*,video/*,audio/*,application/*"
                    />

                    {/* 1. Microphone icon */}
                    <button
                      type="button"
                      className={`${styles.iconButton} ${is24hBlocked ? styles.iconButtonDisabled : ""}`}
                      disabled={is24hBlocked}
                      onClick={startRecording}
                      title="Gửi tin nhắn thoại"
                    >
                      <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
                        <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3zm5.5 10a5.5 5.5 0 0 1-11 0v-1a.75.75 0 0 0-1.5 0v1a7 7 0 0 0 6.25 6.91v2.34H9a.75.75 0 0 0 0 1.5h6a.75.75 0 0 0 0-1.5h-2.25v-2.34A7 7 0 0 0 19.5 11v-1a.75.75 0 0 0-1.5 0v1z"/>
                      </svg>
                    </button>

                    {/* 2. Image icon (File Upload) */}
                    <button
                      type="button"
                      className={`${styles.iconButton} ${is24hBlocked ? styles.iconButtonDisabled : ""}`}
                      disabled={is24hBlocked}
                      onClick={() => fileInputRef.current?.click()}
                      title="Đính kèm ảnh hoặc tệp tin"
                    >
                      <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
                        <path d="M19 3H5a3 3 0 0 0-3 3v12a3 3 0 0 0 3 3h14a3 3 0 0 0 3-3V6a3 3 0 0 0-3-3zM5 4.5h14a1.5 1.5 0 0 1 1.5 1.5v7.44l-3.32-3.14a2.25 2.25 0 0 0-3.08 0l-3.9 3.7-2.18-1.92a2.25 2.25 0 0 0-3.04.05L3.5 13.91V6A1.5 1.5 0 0 1 5 4.5zM8.25 10.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z"/>
                      </svg>
                    </button>

                    {/* 3. Sticker icon */}
                    <button
                      type="button"
                      className={`${styles.iconButton} ${is24hBlocked ? styles.iconButtonDisabled : ""}`}
                      disabled={is24hBlocked}
                      onClick={() => {
                        setShowStickerPicker(!showStickerPicker);
                        setShowGifPicker(false);
                        setShowEmojiPicker(false);
                      }}
                      title="Gửi nhãn dán Stickers"
                    >
                      <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
                        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm5.5 14.25c-.2.2-.45.3-.75.3a1.05 1.05 0 0 1-.75-.3L13 13.2l-3 3.05c-.2.2-.45.3-.75.3a1.05 1.05 0 0 1-.75-.3 1.05 1.05 0 0 1 0-1.5L11.5 11.7 8.5 8.65a1.05 1.05 0 0 1 0-1.5 1.05 1.05 0 0 1 1.5 0l3 3.05 3-3.05a1.05 1.05 0 0 1 1.5 0 1.05 1.05 0 0 1 0 1.5l-3 3.05 3 3.05c.4.4.4 1 .1 1.4z"/>
                      </svg>
                    </button>

                    {/* Sticker Popover */}
                    {showStickerPicker && (
                      <div className={styles.emojiPopover} style={{ gridTemplateColumns: "repeat(4, 1fr)", width: "300px", bottom: "58px", right: "80px" }}>
                        {[
                          "https://i.giphy.com/media/v1.Y2lkPTc5MGI3NjExM2Qwb2x5czV3YXR0Y21kMW92M2oxbmltM2V4cmU5bDB5b253b216ZCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9cw/l3q2zVr6cu95nF6O4/giphy.gif",
                          "https://i.giphy.com/media/v1.Y2lkPTc5MGI3NjExM3Qwb2x5czV3YXR0Y21kMW92M2oxbmltM2V4cmU5bDB5b253b216ZCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9cw/3oz8xALRf1LTCX4YPS/giphy.gif",
                          "https://i.giphy.com/media/v1.Y2lkPTc5MGI3NjExM3Qwb2x5czV3YXR0Y21kMW92M2oxbmltM2V4cmU5bDB5b253b216ZCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9cw/l0G18bM1hvitv68hy/giphy.gif",
                          "https://i.giphy.com/media/v1.Y2lkPTc5MGI3NjExM3Qwb2x5czV3YXR0Y21kMW92M2oxbmltM2V4cmU5bDB5b253b216ZCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9cw/3o7TKSjRrfIPjei16M/giphy.gif",
                          "https://i.giphy.com/media/v1.Y2lkPTc5MGI3NjExM3Qwb2x5czV3YXR0Y21kMW92M2oxbmltM2V4cmU5bDB5b253b216ZCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9cw/l0HlOBIP8K9U8V5qU/giphy.gif",
                          "https://i.giphy.com/media/v1.Y2lkPTc5MGI3NjExM3Qwb2x5czV3YXR0Y21kMW92M2oxbmltM2V4cmU5bDB5b253b216ZCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9cw/3o7qDQ4kcSD1PLM3BK/giphy.gif",
                          "https://i.giphy.com/media/v1.Y2lkPTc5MGI3NjExM3Qwb2x5czV3YXR0Y21kMW92M2oxbmltM2V4cmU5bDB5b253b216ZCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9cw/l3q2t2b2b1156820g/giphy.gif",
                          "https://i.giphy.com/media/v1.Y2lkPTc5MGI3NjExM3Qwb2x5czV3YXR0Y21kMW92M2oxbmltM2V4cmU5bDB5b253b216ZCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9cw/3o7qE0gCO5JyA57iJG/giphy.gif"
                        ].map((url, index) => (
                          <img
                            key={index}
                            src={url}
                            alt={`Sticker ${index}`}
                            style={{ width: "60px", height: "60px", cursor: "pointer", objectFit: "contain" }}
                            onClick={() => handleSendAttachmentUrl(url, "image")}
                          />
                        ))}
                      </div>
                    )}

                    {/* 4. GIF icon */}
                    <button
                      type="button"
                      className={`${styles.iconButton} ${is24hBlocked ? styles.iconButtonDisabled : ""}`}
                      disabled={is24hBlocked}
                      onClick={() => {
                        setShowGifPicker(!showGifPicker);
                        setShowStickerPicker(false);
                        setShowEmojiPicker(false);
                      }}
                      title="Gửi file GIF động"
                    >
                      <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
                        <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-8 8.5h-1.5V13h1.5v1.5H9.5c-.83 0-1.5-.67-1.5-1.5v-3c0-.83.67-1.5 1.5-1.5h1.5v1.5zm3 3H12.5v-6H14v6zm4-4.5h-2v1h1.5V11H16v3.5h-1.5v-6h3.5V11z"/>
                      </svg>
                    </button>

                    {/* GIF Popover */}
                    {showGifPicker && (
                      <div className={styles.emojiPopover} style={{ gridTemplateColumns: "repeat(2, 1fr)", width: "320px", bottom: "58px", right: "50px" }}>
                        {[
                          "https://media.giphy.com/media/l3q2XhfQ8oCkm1K7m/giphy.gif",
                          "https://media.giphy.com/media/xT0xezQGU5xCDJuCPe/giphy.gif",
                          "https://media.giphy.com/media/dpK9kWc3YQH28/giphy.gif",
                          "https://media.giphy.com/media/3o7qE1YN7aBOFPRw8E/giphy.gif",
                          "https://media.giphy.com/media/26ufdipQqU2lhNA4g/giphy.gif",
                          "https://media.giphy.com/media/c8UN4zmmuqmWc/giphy.gif",
                          "https://media.giphy.com/media/12XMGIWtrHBl5e/giphy.gif",
                          "https://media.giphy.com/media/kb9LpghG6iENa/giphy.gif"
                        ].map((url, index) => (
                          <img
                            key={index}
                            src={url}
                            alt={`GIF ${index}`}
                            style={{ width: "135px", height: "95px", cursor: "pointer", objectFit: "cover", borderRadius: "8px" }}
                            onClick={() => handleSendAttachmentUrl(url, "image")}
                          />
                        ))}
                      </div>
                    )}

                    {/* 5. Input container with rounded background & emoji picker trigger */}
                    <div className={styles.inputContainer}>
                      <input
                        type="text"
                        className={styles.messengerInput}
                        placeholder={is24hBlocked ? "Phản hồi bị khóa (Quá hạn 24h)" : "Aa"}
                        value={replyText}
                        onChange={(e) => setReplyText(e.target.value)}
                        disabled={is24hBlocked || isSending}
                      />

                      {/* Emoji Button inside Input */}
                      <button
                        type="button"
                        className={styles.emojiButton}
                        disabled={is24hBlocked}
                        onClick={() => {
                          setShowEmojiPicker(!showEmojiPicker);
                          setShowStickerPicker(false);
                          setShowGifPicker(false);
                        }}
                        title="Chọn biểu tượng cảm xúc (Emoji)"
                      >
                        <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
                          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm-3.5-9c.83 0 1.5-.67 1.5-1.5S9.33 8 8.5 8 7 8.67 7 9.5s.67 1.5 1.5 1.5zm7 0c.83 0 1.5-.67 1.5-1.5S16.33 8 15.5 8 14 8.67 14 9.5s.67 1.5 1.5 1.5zm-3.5 5.5c2.33 0 4.31-1.46 5.11-3.5H6.89c.8 2.04 2.78 3.5 5.11 3.5z"/>
                        </svg>
                      </button>

                      {/* Tabbed Emoji Picker Popover */}
                      {showEmojiPicker && (
                        <div className={styles.emojiPopover} style={{ display: "flex", flexDirection: "column", width: "320px", maxHeight: "250px" }}>
                          {/* Tabs */}
                          <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid rgba(255,255,255,0.08)", paddingBottom: "6px", marginBottom: "8px" }}>
                            {[
                              { key: "smileys", label: "😃" },
                              { key: "hearts", label: "❤️" },
                              { key: "animals", label: "🐱" },
                              { key: "food", label: "🍔" },
                              { key: "objects", label: "⚽" }
                            ].map((tab) => (
                              <button
                                key={tab.key}
                                type="button"
                                style={{
                                  background: "none",
                                  border: "none",
                                  fontSize: "18px",
                                  cursor: "pointer",
                                  padding: "4px 8px",
                                  borderRadius: "6px",
                                  backgroundColor: emojiActiveTab === tab.key ? "rgba(255,255,255,0.12)" : "transparent"
                                }}
                                onClick={() => setEmojiActiveTab(tab.key)}
                              >
                                {tab.label}
                              </button>
                            ))}
                          </div>
                          {/* Grid */}
                          <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: "6px", overflowY: "auto", maxHeight: "180px", paddingRight: "4px" }}>
                            {
                              {
                                smileys: ["😀", "😃", "😄", "😁", "😆", "😅", "😂", "🤣", "😊", "😇", "🙂", "🙃", "😉", "😌", "😍", "🥰", "😘", "😗", "😙", "😚", "😋", "😛", "😝", "😜", "🤪", "🤨", "🧐", "🤓", "😎", "🥸", "🤩", "🥳", "😏", "😒", "😞", "😔", "😟", "😕", "🙁", "☹️"],
                                hearts: ["👍", "👎", "👊", "✊", "🤛", "🤜", "🤞", "✌️", "🤟", "🤘", "👌", "🤌", "🤏", "👈", "👉", "👆", "👇", "☝️", "✋", "🤚", "🖐️", "🖖", "👋", "✍️", "👏", "🙌", "👐", "🤲", "🙏", "❤️", "🧡", "💛", "💚", "💙", "💜", "🖤", "🤍", "🤎", "💔", "❣️"],
                                animals: ["🐶", "🐱", "🐭", "🐹", "🐰", "🦊", "🐻", "🐼", "🐨", "🐯", "🦁", "🐮", "🐷", "🐸", "🐵", "🐔", "🐧", "🐦", "🐤", "🦆", "🦅", "🦉", "🦇", "🐺", "🐗", "🦄", "🐝", "🐛", "🦋", "🐌", "🐞", "🐜", "🕷️", "🐢", "🐍", "🦎", "🐙", "🦑", "🐬", "🐠"],
                                food: ["🍎", "🍊", "🍋", "🍌", "🍉", "🍇", "🍓", "🍒", "🍑", "🍍", "🥥", "🥝", "🍅", "🍆", "🥑", "🥦", "🥬", "🥒", "🌶️", "🌽", "🥕", "🍞", "🥐", "🥖", "🥞", "🧇", "🧀", "🍖", "🍗", "🥩", " Bacon", "🍔", "🍟", "🍕", "🌭", "🥪", "🌮", "🌯", "☕", "🍺"],
                                objects: ["⚽", "🏀", "🏈", "⚾", "🥎", "🎾", "🎱", "🏓", "🥊", "🛹", "🚲", "🚗", "✈️", "🚀", "🛸", "⌚", "📱", "💻", "⌨️", "🖥️", "🖨️", "🖱️", "📷", "📸", "📹", "🎙️", "📻", "🎸", "🎹", "🥁", "🎨", "🎭", "🎮", "🎲", "🧩", "🎯", "🎳", "💡", "🔑", "🚩"]
                              }[emojiActiveTab].map((emoji) => (
                                <span
                                  key={emoji}
                                  className={styles.emojiItem}
                                  onClick={() => setReplyText((prev) => prev + emoji)}
                                >
                                  {emoji}
                                </span>
                              ))
                            }
                          </div>
                        </div>
                      )}
                    </div>

                    {/* 6. Send button (Paper airplane) */}
                    <button
                      type="submit"
                      className={styles.btnSend}
                      disabled={is24hBlocked || !replyText.trim() || isSending}
                      title="Gửi tin nhắn"
                    >
                      <svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor">
                        <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
                      </svg>
                    </button>
                  </form>
                )}
                </div>
              </>
            )
          ) : (
            <div style={{ display: "flex", flex: 1, alignItems: "center", justifyContent: "center", color: "var(--text-secondary)", fontSize: "13px", padding: "20px" }}>
              Vui lòng chọn một cuộc hội thoại từ danh sách bên trái để bắt đầu chat.
            </div>
          )}
        </div>

        {/* COLUMN 3: Right configuration & notifications panel */}
        <div className={styles.rightPanel}>
          <div className={styles.tabsContainer}>
            <button
              className={`${styles.tabButton} ${activeRightTab === "config" ? styles.tabButtonActive : ""}`}
              onClick={() => setActiveRightTab("config")}
            >
              Cấu hình
            </button>
            <button
              className={`${styles.tabButton} ${activeRightTab === "notifications" ? styles.tabButtonActive : ""}`}
              onClick={() => setActiveRightTab("notifications")}
            >
              Thông báo {unreadNotifsCount > 0 && `(${unreadNotifsCount})`}
            </button>
          </div>

          <div className={styles.rightPanelBody}>
            {/* CONFIG TAB */}
            {activeRightTab === "config" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "16px", flexGrow: 1 }}>
                
                {/* Access Token Manager */}
                <div className={styles.configSection}>
                  <div className={styles.formGroup}>
                    <label className={styles.label}>Facebook User Token (Short/Long-lived)</label>
                    <input
                      type="password"
                      className={styles.input}
                      value={customAccessToken}
                      onChange={(e) => setCustomAccessToken(e.target.value)}
                      placeholder="Dán mã EAA... tại đây"
                    />
                  </div>
                  
                  <div style={{ display: "flex", gap: "8px", marginTop: "12px" }}>
                    <button
                      className={`${styles.btn} ${styles.btnPrimary}`}
                      onClick={handleSyncPages}
                      disabled={isLoading || isResetting}
                      style={{ flex: 1 }}
                    >
                      {isLoading ? "Đang đồng bộ..." : "Đồng bộ Trang"}
                    </button>
                  </div>
                </div>

                {/* Exchanged profile status */}
                {facebookUserId && (
                  <div style={{
                    fontSize: "12px",
                    background: "rgba(16, 185, 129, 0.08)",
                    border: "1px solid rgba(16, 185, 129, 0.2)",
                    padding: "10px",
                    borderRadius: "8px",
                    color: "#a7f3d0",
                    display: "flex",
                    alignItems: "center",
                    gap: "6px"
                  }}>
                    <span className={`${styles.statusIndicator} ${styles.statusIndicatorActive}`} />
                    <span>User ID: <strong>{facebookUserId}</strong> (Exchanged)</span>
                  </div>
                )}



                {/* Database wipes */}
                {(facebookUserId || dbPages.length > 0) && (
                  <button
                    className={`${styles.btn} ${styles.btnSecondary}`}
                    onClick={handleResetDatabase}
                    disabled={isLoading || isResetting}
                    style={{
                      marginTop: "auto",
                      borderColor: "rgba(239, 68, 68, 0.2)",
                      color: "#fca5a5",
                      background: "rgba(239, 68, 68, 0.04)"
                    }}
                  >
                    {isResetting ? "Đang xóa..." : "Reset Dữ Liệu"}
                  </button>
                )}
                
                {/* Synced pages list count */}
                <div className={styles.pageCountSummary}>
                  <span className={styles.countLabel}>Số Fanpage đã liên kết</span>
                  <span className={styles.countBadge}>{dbPages.length} Pages</span>
                </div>

                {/* DB Pages Scroll list */}
                <div className={styles.listContainer} style={{ maxHeight: "150px", overflowY: "auto" }}>
                  {dbPages.map((page) => (
                    <div key={page.id} className={styles.pageCard}>
                      <div className={styles.pageLeft}>
                        <div className={styles.avatarWrapper} style={{ width: "24px", height: "24px" }}>
                          {page.avatar_url ? (
                            <img src={page.avatar_url} alt="" className={styles.avatar} />
                          ) : (
                            <span style={{ fontSize: "10px", fontWeight: 700, color: "#3b82f6" }}>
                              {page.page_name.charAt(0)}
                            </span>
                          )}
                        </div>
                        <span className={styles.pageName}>{page.page_name}</span>
                      </div>
                      <div className={`${styles.statusIndicator} ${styles.statusIndicatorActive}`} />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* NOTIFICATIONS TAB */}
            {activeRightTab === "notifications" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                <div className={styles.filterTabs}>
                  <button className={`${styles.filterTab} ${notificationFilter === "all" ? styles.filterTabActive : ""}`} onClick={() => setNotificationFilter("all")}>Tất cả</button>
                  <button className={`${styles.filterTab} ${notificationFilter === "unread" ? styles.filterTabActive : ""}`} onClick={() => setNotificationFilter("unread")}>Chưa xem</button>
                  <button className={`${styles.filterTab} ${notificationFilter === "unreplied" ? styles.filterTabActive : ""}`} onClick={() => setNotificationFilter("unreplied")}>Chưa trả lời</button>
                </div>
                {filteredNotifications.length === 0 ? (
                  <div className={styles.emptyState}>
                    <svg className={styles.emptyIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a9.049 9.049 0 01-5.116-2.28 9 9 0 000-11.602 9.049 9.049 0 015.116-2.28m0 16.162a9 9 0 01-5.116 2.28m5.116-18.442a9 9 0 015.116 2.28m-5.116 2.28a9 9 0 000 11.602" />
                    </svg>
                    <span>Không có thông báo nào thỏa mãn bộ lọc.</span>
                  </div>
                ) : (
                  filteredNotifications.map((notif) => {
                    const isComment = notif.title.includes("bình luận:");
                    return (
                      <div
                        key={notif.id}
                        className={styles.notifCard}
                        onClick={() => {
                          markNotificationRead(notif.facebook_notification_id);
                          if (isComment) {
                            setActiveThread({
                              type: "comment",
                              page_id: notif.page_id,
                              sender_id: notif.facebook_notification_id,
                              comment_id: notif.facebook_notification_id,
                              title: notif.title,
                              page_name: notif.page_name
                            });
                          } else if (notif.link) {
                            window.open(notif.link, "_blank");
                          }
                        }}
                        title="Nhấp chuột để mở bài viết trên Facebook"
                      >
                        <div className={styles.notifContent}>
                          <div className={styles.notifTitle}>{notif.title}</div>
                          <div className={styles.notifMeta}>
                            <span>Trang: <strong>{notif.page_name}</strong></span>
                            <span>{parseDate(notif.created_time).toLocaleString()}</span>
                          </div>
                          <div style={{ display: "flex", gap: "6px", fontSize: "10px", marginTop: "6px" }}>
                            {notif.unread && <span style={{ display: "flex", alignItems: "center", gap: "3px", color: "#60a5fa" }}>🔵 Chưa xem</span>}
                            {notif.is_replied && <span style={{ display: "flex", alignItems: "center", gap: "3px", color: "#34d399" }}>✔ Đã trả lời</span>}
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Forward Message Modal Dialog */}
    {showForwardModal && messageToForward && (
      <div style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: "rgba(0,0,0,0.6)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 9999,
        backdropFilter: "blur(4px)"
      }}>
        <div style={{
          backgroundColor: "var(--bg-secondary)",
          border: "1px solid var(--border-glass)",
          borderRadius: "16px",
          padding: "20px",
          width: "350px",
          boxShadow: "0 10px 25px rgba(0,0,0,0.5)"
        }}>
          <h4 style={{ margin: "0 0 12px 0", color: "var(--text-primary)" }}>Chuyển tiếp tin nhắn</h4>
          <div style={{
            fontSize: "12px",
            color: "var(--text-secondary)",
            background: "rgba(255,255,255,0.03)",
            padding: "8px 12px",
            borderRadius: "8px",
            marginBottom: "16px",
            maxHeight: "60px",
            overflowY: "auto"
          }}>
            {messageToForward.text?.startsWith("[image]") ? "📷 [Hình ảnh]" : messageToForward.text?.startsWith("[file]") ? "📎 [Tập tin]" : messageToForward.text?.startsWith("[audio]") ? "🎙️ [Tin nhắn thoại]" : messageToForward.text}
          </div>
          <p style={{ fontSize: "11px", color: "var(--text-muted)", marginBottom: "8px" }}>Chọn cuộc trò chuyện để gửi:</p>
          <div style={{ maxHeight: "180px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "6px", marginBottom: "16px" }}>
            {conversations.map((c) => (
              <button
                key={`${c.page_id}-${c.sender_id}`}
                type="button"
                onClick={() => handleForwardMessage(c.page_id, c.sender_id)}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "8px 12px",
                  background: "rgba(255,255,255,0.05)",
                  border: "1px solid var(--border-glass)",
                  borderRadius: "8px",
                  color: "var(--text-primary)",
                  textAlign: "left",
                  cursor: "pointer",
                  fontSize: "12px"
                }}
              >
                <span>KH: {c.sender_id.substring(5, 12)}... ({c.page_name})</span>
                <span style={{ color: "#3b82f6", fontWeight: 600 }}>Gửi</span>
              </button>
            ))}
          </div>
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button
              type="button"
              className={`${styles.btn} ${styles.btnSecondary}`}
              onClick={() => {
                setShowForwardModal(false);
                setMessageToForward(null);
              }}
              style={{ padding: "6px 12px", fontSize: "12px" }}
            >
              Hủy bỏ
            </button>
          </div>
        </div>
      </div>
    )}
    </div>
  );
}
