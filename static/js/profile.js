// Profile page functionality
document.addEventListener('DOMContentLoaded', function() {
    // Initialize modals
    const modal = document.getElementById('editModal');
    const closeBtn = modal.querySelector('.close-btn');
    
    // Initialize form
    const profileForm = document.getElementById('profileForm');
    const editBtns = document.querySelectorAll('.edit-btn');

    // Form field templates
    const formTemplates = {
        personal: `
            <div class="form-group">
                <label>Full Name</label>
                <input type="text" name="fullName" class="form-input" required>
            </div>
            <div class="form-group">
                <label>Date of Birth</label>
                <input type="date" name="dob" class="form-input">
            </div>
            <div class="form-group">
                <label>Gender</label>
                <select name="gender" class="form-input">
                    <option value="">Select Gender</option>
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                    <option value="other">Other</option>
                </select>
            </div>
            <div class="form-group">
                <label>Email</label>
                <input type="email" name="email" class="form-input" required>
            </div>
            <div class="form-group">
                <label>Phone</label>
                <input type="tel" name="phone" class="form-input">
            </div>
            <div class="form-group">
                <label>Address</label>
                <textarea name="address" class="form-input" rows="3"></textarea>
            </div>
            <div class="form-actions">
                <button type="button" class="btn cancel" onclick="closeModal()">Cancel</button>
                <button type="submit" class="btn save">Save Changes</button>
            </div>
        `,
        medical: `
            <div class="form-group">
                <label>Blood Type</label>
                <select name="bloodGroup" class="form-input">
                    <option value="">Select Blood Type</option>
                    <option value="A+">A+</option>
                    <option value="A-">A-</option>
                    <option value="B+">B+</option>
                    <option value="B-">B-</option>
                    <option value="O+">O+</option>
                    <option value="O-">O-</option>
                    <option value="AB+">AB+</option>
                    <option value="AB-">AB-</option>
                </select>
            </div>
            <div class="form-group">
                <label>Height (cm)</label>
                <input type="number" name="height" class="form-input">
            </div>
            <div class="form-group">
                <label>Weight (kg)</label>
                <input type="number" name="weight" class="form-input">
            </div>
            <div class="form-group">
                <label>Medical Conditions</label>
                <textarea name="medicalConditions" class="form-input" rows="3"></textarea>
            </div>
            <div class="form-group">
                <label>Allergies</label>
                <textarea name="allergies" class="form-input" rows="3"></textarea>
            </div>
            <div class="form-group">
                <label>Current Medications</label>
                <textarea name="medications" class="form-input" rows="3"></textarea>
            </div>
            <div class="form-actions">
                <button type="button" class="btn cancel" onclick="closeModal()">Cancel</button>
                <button type="submit" class="btn save">Save Changes</button>
            </div>
        `
    };

    // Event Listeners
    editBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const section = btn.getAttribute('data-section');
            openEditModal(section);
        });
    });

    closeBtn.addEventListener('click', closeModal);

    profileForm.addEventListener('submit', handleFormSubmit);

    // Functions
    function openEditModal(section) {
        const form = document.getElementById('profileForm');
        form.innerHTML = formTemplates[section];
        modal.style.display = 'block';
        
        // Populate form with existing data
        populateForm(section);
    }

    function closeModal() {
        modal.style.display = 'none';
    }

    async function handleFormSubmit(e) {
        e.preventDefault();
        const formData = new FormData(e.target);
        const data = Object.fromEntries(formData);

        try {
            const response = await fetch('/update_profile', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            });

            const result = await response.json();
            if (result.status === 'success') {
                showNotification('Profile updated successfully', 'success');
                closeModal();
                location.reload();
            } else {
                showNotification(result.message || 'Failed to update profile', 'error');
            }
        } catch (error) {
            showNotification('An error occurred', 'error');
        }
    }

    function populateForm(section) {
        // Get current user data from the page
        const formInputs = document.querySelectorAll(`#profileForm .form-input`);
        formInputs.forEach(input => {
            const fieldName = input.name;
            const currentValue = getCurrentValue(fieldName);
            if (currentValue) {
                input.value = currentValue;
            }
        });
    }

    function getCurrentValue(fieldName) {
        const element = document.querySelector(`[data-field="${fieldName}"]`);
        return element ? element.textContent.trim() : '';
    }

    function showNotification(message, type) {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }
});