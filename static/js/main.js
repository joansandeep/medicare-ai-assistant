// Enhanced helpers for the base layout
(function(){
    // Menu toggle for mobile
    document.querySelector('.menu-toggle')?.addEventListener('click', ()=>{
        document.body.classList.toggle('sidebar-collapsed');
    });

    // Live clock update
    function tick(){
        const el = document.getElementById('current-time');
        if(!el) return;
        const now = new Date();
        el.textContent = now.toLocaleString(undefined, {
            year:'numeric', month:'2-digit', day:'2-digit',
            hour:'2-digit', minute:'2-digit', second:'2-digit'
        });
    }
    tick(); 
    setInterval(tick, 1000);

    // Emergency button
    window.handleEmergency = function() {
        if(confirm('🚨 This will dial emergency services. Continue?')) {
            // In a real app, this would actually call emergency services
            alert('Emergency services contacted. Help is on the way!');
            // You could also redirect to a dedicated emergency page
        }
    };

    // Floating chatbot button animation
    const floatingBtn = document.querySelector('.floating-chat-btn');
    if(floatingBtn) {
        // Add pulse animation periodically
        setInterval(() => {
            floatingBtn.classList.add('pulse');
            setTimeout(() => floatingBtn.classList.remove('pulse'), 1000);
        }, 8000); // Pulse every 8 seconds
    }

    // Auto-hide alerts after 5 seconds
    document.querySelectorAll('.alert').forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });

    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    console.log('🏥 MediCare Portal loaded successfully!');
})();
