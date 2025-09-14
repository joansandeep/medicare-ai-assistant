class ChatBot {
  constructor() {
    this.initializeElements();
    this.initializeEventListeners();
    this.messages = [
      { role: "system", content: "You are MediCare AI Assistant. Help users navigate the portal and provide general guidance. Do not provide medical diagnosis." }
    ];
    this.startNewChat();
  }

  initializeElements() {
    this.messageInput = document.querySelector('.input-field');
    this.sendButton = document.querySelector('.send-btn');
    this.fileButton = document.querySelector('.file-btn');
    this.fileInput = document.querySelector('.file-upload');
    this.messagesContainer = document.querySelector('.chat-messages');
    this.newChatButton = document.querySelector('.new-chat-btn');
  }

  initializeEventListeners() {
    this.sendButton.addEventListener('click', () => this.sendMessage());
    this.messageInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.sendMessage(); }
    });
    this.fileButton.addEventListener('click', () => this.fileInput.click());
    this.fileInput.addEventListener('change', (e) => this.handleFileUpload(e));
    this.newChatButton.addEventListener('click', () => this.startNewChat());
  }

  startNewChat() {
    this.messages = this.messages.filter(m => m.role === 'system');
    this.messagesContainer.innerHTML = '';
    this.addMessage('How can I help you today?', 'bot');
  }

  async sendMessage() {
    const message = this.messageInput.value.trim();
    if (!message) return;
    this.addMessage(message, 'user');
    this.messageInput.value = '';

    this.messages.push({ role: 'user', content: message });

    this.showTypingIndicator();
    try {
      const resp = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: this.messages })
      });
      const data = await resp.json();
      this.hideTypingIndicator();
      if (data && data.content) {
        this.messages.push({ role: 'assistant', content: data.content });
        this.addMessage(data.content, 'bot');
      } else {
        this.addMessage('Sorry, I could not process that.', 'bot');
      }
    } catch {
      this.hideTypingIndicator();
      this.addMessage('Network error. Please try again.', 'bot');
    }
  }

  addMessage(content, who) {
    const div = document.createElement('div');
    div.className = `message ${who === 'bot' ? 'ai-message' : 'user-message'}`;
    const timestamp = new Date().toLocaleTimeString();
    div.innerHTML = `
      <div class="message-content">
        <div class="message-text">${this.escapeHTML(content).replace(/\n/g, '<br>')}</div>
        <div class="message-time">${timestamp}</div>
      </div>
    `;
    this.messagesContainer.appendChild(div);
    this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
  }

  showTypingIndicator() {
    const typing = document.createElement('div');
    typing.className = 'message ai-message typing';
    typing.innerHTML = `
      <div class="message-content">
        <div class="typing-indicator"><span></span><span></span><span></span></div>
      </div>
    `;
    this.messagesContainer.appendChild(typing);
    this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
  }

  hideTypingIndicator() {
    const t = this.messagesContainer.querySelector('.typing');
    if (t) t.remove();
  }

  handleFileUpload(event) {
    const file = event.target.files[0];
    if (file) {
      this.addMessage(`File uploaded: ${file.name}`, 'user');
    }
  }

  escapeHTML(s) {
    return s.replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  }
}

document.addEventListener('DOMContentLoaded', () => new ChatBot());