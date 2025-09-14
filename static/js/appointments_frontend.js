(function(){
  const LS_KEY = 'mc_appointments_v1';
  const tbody = document.getElementById('appointmentsBody');
  const scheduleBtn = document.querySelector('.schedule-btn');
  const modal = document.getElementById('apptModal');
  const modalTitle = document.getElementById('apptModalTitle');
  const closeBtn = document.getElementById('apptModalClose');
  const cancelBtn = document.getElementById('apptCancelBtn');
  const form = document.getElementById('apptForm');

  // Wait for Bootstrap to be ready
  document.addEventListener('DOMContentLoaded', function() {
    console.log('[appointments] Starting initialization...');
    initialize();
  });

  function initialize() {
    // SAFETY: if dashboard CSS didn't load or is overridden, inject minimal modal CSS so it overlays
    (function ensureModalCss(){
      try {
        if (modal) {
          const pos = getComputedStyle(modal).position;
          if (pos !== 'fixed') {
            const style = document.createElement('style');
            style.textContent = `
              .hc-modal{position:fixed;inset:0;background:rgba(0,0,0,.5);display:flex;align-items:center;justify-content:center;z-index:1000;}
              .hc-modal__dialog{width:92%;max-width:560px;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 10px 30px rgba(0,0,0,0.2);}
              .hc-modal__header{display:flex;align-items:center;justify-content:space-between;padding:12px 14px;border-bottom:1px solid #edf1f7;}
              .hc-modal__body{padding:14px;}
              .hc-modal__close{border:none;background:transparent;font-size:24px;cursor:pointer;}
              .hc-modal__footer{display:flex;gap:10px;justify-content:flex-end;margin-top:10px;}
              .form-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;}
              .form-grid label{font-size:.9rem;color:#475569;display:flex;flex-direction:column;gap:6px;}
              .form-grid input,.form-grid select{padding:8px 10px;border:1px solid #dbe2ea;border-radius:8px;}
              @media (max-width:640px){ .form-grid { grid-template-columns:1fr; } }
            `;
            document.head.appendChild(style);
            console.warn('[appointments] Injected safety CSS (hc-modal) because computed position was', pos);
          }
        }
      } catch(e) {
        console.warn('[appointments] Could not verify modal CSS:', e);
      }
    })();

    const fld = {
      id: document.getElementById('apptId'),
      dt: document.getElementById('apptDateTime'),
      title: document.getElementById('apptTitle'),
      desc: document.getElementById('apptDesc'),
      doctor: document.getElementById('apptDoctor'),
      dept: document.getElementById('apptDept'),
      type: document.getElementById('apptType'),
      duration: document.getElementById('apptDuration')
    };

    let appointments = load();
    if(!appointments.length){ seed(); save(); }
    render();

    // Event listeners
    scheduleBtn?.addEventListener('click', ()=> openModal());
    closeBtn?.addEventListener('click', closeModal);
    cancelBtn?.addEventListener('click', closeModal);
    modal?.addEventListener('click', e => { if(e.target === modal) closeModal(); });

    form?.addEventListener('submit', e => {
      e.preventDefault();
      const appt = collect();
      if(appt.id){
        const i = appointments.findIndex(a => a.id === appt.id);
        if(i > -1) appointments[i] = appt;
      }else{
        appt.id = (crypto && crypto.randomUUID) ? crypto.randomUUID() : String(Date.now()) + Math.random().toString(16).slice(2);
        appointments.push(appt);
      }
      sort(); save(); render(); closeModal();
    });

    function seed(){
      const now = new Date();
      appointments = [
        mk(now, 1, 'General Checkup', 'Routine health examination', 'Dr. Sarah Johnson', 'Internal Medicine', 'routine', 45),
        mk(now, 5, 'Lab Results Review', 'Review recent test results', 'Dr. Michael Chen', 'Laboratory Medicine', 'follow-up', 30),
        mk(now, 12, 'Cardiology Consultation', 'Heart health evaluation', 'Dr. Lisa Williams', 'Cardiology', 'specialist', 60),
      ];
    }

    function mk(base, offsetDays, title, desc, doctor, dept, type, duration){
      const d = new Date(base.getTime() + offsetDays*86400000);
      d.setHours(10 + offsetDays, 30, 0, 0);
      return { id: (crypto && crypto.randomUUID) ? crypto.randomUUID() : String(Date.now()) + Math.random().toString(16).slice(2), start: d.toISOString(), title, desc, doctor, dept, type, duration };
    }

    function load(){ try { return JSON.parse(localStorage.getItem(LS_KEY)) || []; } catch { return []; } }
    function save(){ localStorage.setItem(LS_KEY, JSON.stringify(appointments)); }
    function sort(){ appointments.sort((a,b)=> new Date(a.start) - new Date(b.start)); }

    function render(){
      console.log('[appointments] Rendering appointments...', appointments.length);
      sort();
      if (!tbody) {
        console.error('[appointments] appointmentsBody element not found!');
        return;
      }
      
      tbody.innerHTML = '';
      if(!appointments.length){
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#666;padding:12px;">No appointments</td></tr>';
        return;
      }
      
      appointments.forEach(a=>{
        const { date, time } = fmt(a.start);
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>
            <div class="date-info">
              <div class="date-main">${date}</div>
              <div class="time-main">${time}</div>
              <div class="duration">${a.duration} min</div>
            </div>
          </td>
          <td>
            <div class="appointment-info">
              <div class="appointment-title">${esc(a.title)}</div>
              <div class="appointment-desc">${esc(a.desc || '')}</div>
            </div>
          </td>
          <td>
            <div class="doctor-info">
              <div class="doctor-name">${esc(a.doctor)}</div>
              <div class="department">${esc(a.dept)}</div>
            </div>
          </td>
          <td><span class="type-badge ${a.type}">${label(a.type)}</span></td>
          <td>
            <div class="custom-dropdown">
              <button class="btn btn-sm btn-primary dropdown-toggle" type="button" onclick="toggleDropdown('${a.id}')">
                Actions <i class="fas fa-chevron-down"></i>
              </button>
              <div class="dropdown-menu" id="dropdown-${a.id}">
                <a class="dropdown-item join" href="#" data-id="${a.id}">
                  <i class="fas fa-video"></i> Join Call
                </a>
                <a class="dropdown-item details" href="#" data-id="${a.id}">
                  <i class="fas fa-info-circle"></i> Details
                </a>
                <a class="dropdown-item" href="#" data-action="edit" data-id="${a.id}">
                  <i class="fas fa-edit"></i> Edit
                </a>
                <a class="dropdown-item call" href="#" data-id="${a.id}">
                  <i class="fas fa-phone"></i> Call Doctor
                </a>
                <hr class="dropdown-divider">
                <a class="dropdown-item delete text-danger" href="#" data-id="${a.id}">
                  <i class="fas fa-times"></i> Cancel
                </a>
              </div>
            </div>
          </td>
        `;
        tbody.appendChild(tr);
      });

      // Bind events after rendering
      setTimeout(() => {
        tbody.querySelectorAll('.dropdown-item').forEach(b=> b.addEventListener('click', onAction));
      }, 100);
      
      console.log('[appointments] Rendered', appointments.length, 'appointments');
    }

    // CUSTOM DROPDOWN TOGGLE FUNCTION - NEW
    window.toggleDropdown = function(id) {
      // Close all other dropdowns first
      document.querySelectorAll('.dropdown-menu.show').forEach(menu => {
        menu.classList.remove('show');
      });
      
      // Toggle the clicked dropdown
      const dropdown = document.getElementById(`dropdown-${id}`);
      if (dropdown) {
        dropdown.classList.toggle('show');
      }
    };

    // Close dropdowns when clicking outside - NEW
    document.addEventListener('click', function(event) {
      if (!event.target.closest('.custom-dropdown')) {
        document.querySelectorAll('.dropdown-menu.show').forEach(menu => {
          menu.classList.remove('show');
        });
      }
    });

    function onAction(e){
      e.preventDefault();
      const id = e.currentTarget.dataset.id;
      const a = appointments.find(x => x.id === id);
      if(!a) return;
      
      // Close the dropdown
      document.querySelectorAll('.dropdown-menu.show').forEach(menu => {
        menu.classList.remove('show');
      });
      
      if(e.currentTarget.classList.contains('join')) alert(`Joining "${a.title}" (demo)`);
      else if(e.currentTarget.classList.contains('visit')) alert(`Open map for "${a.title}" (demo)`);
      else if(e.currentTarget.classList.contains('call')) alert(`Calling clinic for "${a.title}" (demo)`);
      else if(e.currentTarget.classList.contains('details')) showDetails(a);
      else if(e.currentTarget.getAttribute('data-action') === 'edit') openModal(a);
      else if(e.currentTarget.classList.contains('delete')){
        if(confirm('Cancel this appointment?')){
          appointments = appointments.filter(x => x.id !== id);
          save(); render();
        }
      }
    }

    function showDetails(a){
      alert(
`Appointment Details:
Title: ${a.title}
Doctor: ${a.doctor} (${a.dept})
When: ${new Date(a.start).toLocaleString()}
Type: ${label(a.type)}
Duration: ${a.duration} min
Notes: ${a.desc || '(none)'}`
      );
    }

    function openModal(a){
      if (!modal) return;
      modal.style.display = 'block';
      document.body.style.overflow = 'hidden';
      document.body.classList.add('modal-open');
      if(a){
        modalTitle.textContent = 'Edit Appointment';
        setForm(a);
      } else {
        modalTitle.textContent = 'Schedule Appointment';
        form.reset();
        fld.id.value = '';
        const d = new Date(); d.setMinutes(d.getMinutes()+30,0,0);
        fld.dt.value = toLocal(d.toISOString());
      }
    }

    function setForm(a){
      fld.id.value = a.id;
      fld.dt.value = toLocal(a.start);
      fld.title.value = a.title;
      fld.desc.value = a.desc || '';
      fld.doctor.value = a.doctor;
      fld.dept.value = a.dept;
      fld.type.value = a.type;
      fld.duration.value = a.duration;
    }

    function closeModal(){
      if (!modal) return;
      modal.style.display = 'none';
      document.body.style.overflow = '';
      document.body.classList.remove('modal-open');
    }

    function collect(){
      return {
        id: fld.id.value || null,
        start: new Date(fld.dt.value).toISOString(),
        title: fld.title.value.trim(),
        desc: fld.desc.value.trim(),
        doctor: fld.doctor.value.trim(),
        dept: fld.dept.value.trim(),
        type: fld.type.value,
        duration: parseInt(fld.duration.value,10)||30
      };
    }

    function fmt(iso){
      const d = new Date(iso);
      return {
        date: d.toLocaleDateString(undefined, { day:'2-digit', month:'short' }).toUpperCase(),
        time: d.toLocaleTimeString(undefined, { hour:'2-digit', minute:'2-digit' })
      };
    }

    function toLocal(iso){
      const d = new Date(iso);
      const pad = n => String(n).padStart(2,'0');
      return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
    }

    function label(t){ return t==='follow-up' ? 'FOLLOW-UP' : t==='specialist' ? 'SPECIALIST' : 'ROUTINE'; }
    function esc(s){ return (s||'').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
  }
})();
