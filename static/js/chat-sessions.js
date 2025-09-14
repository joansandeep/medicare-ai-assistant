// Chat Session Management
class ChatSessionManager {
    constructor() {
        this.currentSessionId = null;
        this.chatSessions = [];
        this.initializeSessionManager();
    }

    async initializeSessionManager() {
        // Load existing sessions
        await this.loadChatSessions();
        this.setupEventListeners();
        this.renderSessionList();
    }

    async loadChatSessions() {
        try {
            const response = await fetch('/api/chat/history', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                this.chatSessions = data.sessions || [];
                
                // Set current session if available
                if (window.currentSessionId) {
                    this.currentSessionId = window.currentSessionId;
                } else if (this.chatSessions.length > 0) {
                    this.currentSessionId = this.chatSessions[0].session_id;
                }
            }
        } catch (error) {
            console.error('Error loading chat sessions:', error);
        }
    }

    setupEventListeners() {
        // New Chat button
        document.addEventListener('click', (e) => {
            if (e.target.matches('#new-chat-btn')) {
                this.createNewSession();
            }
            
            // Session click handler
            if (e.target.matches('.chat-session-item')) {
                const sessionId = e.target.dataset.sessionId;
                this.switchToSession(sessionId);
            }
            
            // Delete session handler
            if (e.target.matches('.delete-session-btn')) {
                e.stopPropagation();
                const sessionId = e.target.dataset.sessionId;
                this.deleteSession(sessionId);
            }
        });
    }

    async createNewSession() {
        try {
            const response = await fetch('/api/chat/new_session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                this.currentSessionId = data.session_id;
                
                // Clear current chat
                this.clearChatDisplay();
                
                // Reload sessions list
                await this.loadChatSessions();
                this.renderSessionList();
                
                // Update UI
                this.updateActiveSession();
                
                console.log('New chat session created:', data.session_id);
            }
        } catch (error) {
            console.error('Error creating new session:', error);
        }
    }

    async switchToSession(sessionId) {
        try {
            const response = await fetch('/api/chat/switch_session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ session_id: sessionId })
            });
            
            if (response.ok) {
                const data = await response.json();
                this.currentSessionId = data.session_id;
                
                // Load and display messages
                this.loadSessionMessages(data.messages);
                
                // Update UI
                this.updateActiveSession();
                
                console.log('Switched to session:', sessionId);
            }
        } catch (error) {
            console.error('Error switching session:', error);
        }
    }

    async deleteSession(sessionId) {
        if (!confirm('Are you sure you want to delete this chat session?')) {
            return;
        }
        
        try {
            const response = await fetch('/api/chat/delete_session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ session_id: sessionId })
            });
            
            if (response.ok) {
                // Reload sessions
                await this.loadChatSessions();
                this.renderSessionList();
                
                // If deleted session was current, clear chat
                if (sessionId === this.currentSessionId) {
                    this.clearChatDisplay();
                    await this.createNewSession();
                }
                
                console.log('Session deleted:', sessionId);
            }
        } catch (error) {
            console.error('Error deleting session:', error);
        }
    }

    loadSessionMessages(messages) {
        this.clearChatDisplay();
        
        messages.forEach(message => {
            this.displayMessage(message.message_content, message.message_type === 'user' ? 'user' : 'ai');
        });
    }

    clearChatDisplay() {
        const chatContainer = document.querySelector('#chat-container');
        if (chatContainer) {
            chatContainer.innerHTML = '';
        }
    }

    displayMessage(content, sender) {
        const chatContainer = document.querySelector('#chat-container');
        if (!chatContainer) return;

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message`;
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        messageContent.innerHTML = this.formatMessage(content);
        
        const timestamp = document.createElement('div');
        timestamp.className = 'message-timestamp';
        timestamp.textContent = new Date().toLocaleTimeString();
        
        messageDiv.appendChild(messageContent);
        messageDiv.appendChild(timestamp);
        chatContainer.appendChild(messageDiv);
        
        // Scroll to bottom
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    formatMessage(content) {
        // Basic markdown-like formatting
        return content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/\n/g, '<br>');
    }

    renderSessionList() {
        const sessionsList = document.querySelector('#chat-sessions-list');
        if (!sessionsList) return;

        sessionsList.innerHTML = '';
        
        this.chatSessions.forEach(session => {
            const sessionItem = document.createElement('div');
            sessionItem.className = `chat-session-item ${session.session_id === this.currentSessionId ? 'active' : ''}`;
            sessionItem.dataset.sessionId = session.session_id;
            
            const sessionTitle = session.first_user_message || 'New Chat';
            const sessionTime = new Date(session.last_message).toLocaleDateString();
            const messageCount = session.message_count;
            
            sessionItem.innerHTML = `
                <div class="session-info">
                    <div class="session-title">${sessionTitle}</div>
                    <div class="session-meta">${sessionTime} • ${messageCount} messages</div>
                </div>
                <button class="delete-session-btn" data-session-id="${session.session_id}">×</button>
            `;
            
            sessionsList.appendChild(sessionItem);
        });
    }

    updateActiveSession() {
        // Update active session in UI
        document.querySelectorAll('.chat-session-item').forEach(item => {
            item.classList.toggle('active', item.dataset.sessionId === this.currentSessionId);
        });
    }

    getCurrentSessionId() {
        return this.currentSessionId;
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.chatSessionManager = new ChatSessionManager();
});

// CSS Styles for Chat Sessions
const chatSessionStyles = `
<style>
#chat-sessions-sidebar {
    width: 300px;
    background: #f8f9fa;
    border-right: 1px solid #dee2e6;
    padding: 1rem;
    max-height: 100vh;
    overflow-y: auto;
}

#new-chat-btn {
    width: 100%;
    padding: 0.75rem;
    background: #007bff;
    color: white;
    border: none;
    border-radius: 0.375rem;
    cursor: pointer;
    margin-bottom: 1rem;
    font-weight: 500;
}

#new-chat-btn:hover {
    background: #0056b3;
}

.chat-session-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem;
    margin-bottom: 0.5rem;
    background: white;
    border: 1px solid #dee2e6;
    border-radius: 0.375rem;
    cursor: pointer;
    transition: all 0.2s;
}

.chat-session-item:hover {
    background: #e9ecef;
    border-color: #adb5bd;
}

.chat-session-item.active {
    background: #e7f3ff;
    border-color: #007bff;
}

.session-info {
    flex: 1;
    min-width: 0;
}

.session-title {
    font-weight: 500;
    color: #212529;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    margin-bottom: 0.25rem;
}

.session-meta {
    font-size: 0.875rem;
    color: #6c757d;
}

.delete-session-btn {
    background: none;
    border: none;
    color: #dc3545;
    cursor: pointer;
    padding: 0.25rem 0.5rem;
    border-radius: 0.25rem;
    opacity: 0;
    transition: opacity 0.2s;
}

.chat-session-item:hover .delete-session-btn {
    opacity: 1;
}

.delete-session-btn:hover {
    background: #f8d7da;
}

#chat-main-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 100vh;
}

#chat-container {
    flex: 1;
    padding: 1rem;
    overflow-y: auto;
    max-height: calc(100vh - 200px);
}

.message {
    margin-bottom: 1rem;
    max-width: 80%;
}

.user-message {
    margin-left: auto;
}

.user-message .message-content {
    background: #007bff;
    color: white;
    padding: 0.75rem;
    border-radius: 1rem 1rem 0.25rem 1rem;
}

.ai-message .message-content {
    background: #f8f9fa;
    color: #212529;
    padding: 0.75rem;
    border-radius: 1rem 1rem 1rem 0.25rem;
    border: 1px solid #dee2e6;
}

.message-timestamp {
    font-size: 0.75rem;
    color: #6c757d;
    margin-top: 0.25rem;
    text-align: right;
}

.user-message .message-timestamp {
    text-align: left;
}
</style>
`;

// Inject styles
document.head.insertAdjacentHTML('beforeend', chatSessionStyles);