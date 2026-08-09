document.addEventListener('DOMContentLoaded', function () {
    // 1. Dark Mode Setup
    const themeToggleBtn = document.getElementById('theme-toggle');
    const themeIcon = themeToggleBtn ? themeToggleBtn.querySelector('i') : null;
    
    // Check local storage or system preference
    const isDarkMode = localStorage.getItem('theme') === 'dark' || 
                       (!localStorage.getItem('theme') && window.matchMedia('(prefers-color-scheme: dark)').matches);
                       
    if (isDarkMode) {
        document.body.classList.add('dark-mode');
        if (themeIcon) {
            themeIcon.classList.replace('bi-moon-stars-fill', 'bi-sun-fill');
        }
    } else {
        document.body.classList.remove('dark-mode');
        if (themeIcon) {
            themeIcon.classList.replace('bi-sun-fill', 'bi-moon-stars-fill');
        }
    }
    
    // Theme toggle click handler
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', function () {
            document.body.classList.toggle('dark-mode');
            const isDark = document.body.classList.contains('dark-mode');
            localStorage.setItem('theme', isDark ? 'dark' : 'light');
            
            if (themeIcon) {
                if (isDark) {
                    themeIcon.classList.replace('bi-moon-stars-fill', 'bi-sun-fill');
                } else {
                    themeIcon.classList.replace('bi-sun-fill', 'bi-moon-stars-fill');
                }
            }
        });
    }

    // 2. Mobile Sidebar Toggle
    const navToggle = document.getElementById('nav-toggle');
    const sidebar = document.querySelector('.sidebar');
    const overlay = document.getElementById('sidebar-overlay');

    function openSidebar() {
        sidebar.classList.add('active');
        if (overlay) overlay.classList.add('active');
        document.body.style.overflow = 'hidden'; // prevent body scroll when sidebar open
    }

    function closeSidebar() {
        sidebar.classList.remove('active');
        if (overlay) overlay.classList.remove('active');
        document.body.style.overflow = '';
    }

    if (navToggle && sidebar) {
        navToggle.addEventListener('click', function (e) {
            e.stopPropagation();
            if (sidebar.classList.contains('active')) {
                closeSidebar();
            } else {
                openSidebar();
            }
        });
    }

    // Close sidebar when overlay is tapped
    if (overlay) {
        overlay.addEventListener('click', closeSidebar);
    }

    // Close sidebar when a nav link is clicked on mobile
    if (sidebar) {
        sidebar.querySelectorAll('.sidebar-menu a').forEach(function(link) {
            link.addEventListener('click', function() {
                if (window.innerWidth < 992) {
                    closeSidebar();
                }
            });
        });
    }

    // 3. Real-time Score Calculator for Judge Evaluation
    setupEvaluationCalculators();

    // 4. AJAX Toggle Switches for System Settings (Fast/Advanced Controls)
    const ajaxSwitches = document.querySelectorAll('.ajax-toggle-switch');
    ajaxSwitches.forEach(sw => {
        sw.addEventListener('change', function() {
            const key = this.getAttribute('data-key');
            const url = `/organizer/toggle-setting/${key}`;
            this.disabled = true;
            
            fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(res => res.json())
            .then(data => {
                this.disabled = false;
                if (data.success) {
                    showToast('Setting updated successfully!', true);
                    // Flash visual confirmation card pulse
                    const container = this.closest('.bg-dark-card') || this.closest('.d-flex') || this.parentElement;
                    if (container) {
                        const originalBg = container.style.backgroundColor;
                        container.style.transition = 'all 0.3s ease';
                        container.style.backgroundColor = 'rgba(16, 185, 129, 0.15)';
                        setTimeout(() => {
                            container.style.backgroundColor = originalBg;
                        }, 500);
                    }
                } else {
                    showToast('Failed to update setting.', false);
                    this.checked = !this.checked;
                }
            })
            .catch(err => {
                this.disabled = false;
                showToast('Connection error occurred.', false);
                this.checked = !this.checked;
            });
        });
    });
    
    // Add Toast container placeholder to the body
    const toastContainer = document.createElement('div');
    toastContainer.id = 'custom-toast-container';
    toastContainer.style.cssText = 'position: fixed; bottom: 24px; right: 24px; z-index: 9999; display: flex; flex-direction: column; gap: 8px;';
    document.body.appendChild(toastContainer);
});

// 5. Custom Premium Toast Notification System
function showToast(message, isSuccess = true) {
    const container = document.getElementById('custom-toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = 'fade-in-up';
    
    // Sleek glassmorphism styles matching the dark/light premium dashboard
    const bg = isSuccess ? 'rgba(16, 185, 129, 0.95)' : 'rgba(239, 68, 68, 0.95)';
    const icon = isSuccess ? 'bi-check-circle-fill' : 'bi-exclamation-triangle-fill';
    
    toast.style.cssText = `
        background: ${bg};
        color: #ffffff;
        padding: 12px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        display: flex;
        align-items: center;
        gap: 10px;
        font-family: 'Inter', sans-serif;
        font-size: 14px;
        font-weight: 500;
        min-width: 250px;
        backdrop-filter: blur(4px);
        transition: all 0.3s ease;
        opacity: 0;
        transform: translateY(10px);
    `;

    toast.innerHTML = `<i class="bi ${icon}"></i> <span>${message}</span>`;
    container.appendChild(toast);

    // Trigger animate-in
    setTimeout(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'translateY(0)';
    }, 10);

    // Auto-destruct after 3.5s
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(-10px)';
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 3500);
}

function setupEvaluationCalculators() {
    // Round 1 inputs
    const r1Inputs = [
        document.getElementById('innovation'),
        document.getElementById('problem_statement'),
        document.getElementById('feasibility'),
        document.getElementById('presentation'),
        document.getElementById('confidence')
    ].filter(el => el !== null);
    
    // Round 2 inputs
    const r2Inputs = [
        document.getElementById('prototype'),
        document.getElementById('technical_implementation'),
        document.getElementById('uiux'),
        document.getElementById('question_answer')
    ].filter(el => el !== null);
    
    // Round 3 inputs
    const r3Inputs = [
        document.getElementById('working_demo'),
        document.getElementById('business_model'),
        document.getElementById('scalability'),
        document.getElementById('presentation_r3')
    ].filter(el => el !== null);
    
    const displayVal = document.getElementById('total-marks-display');
    const inputVal = document.getElementById('total-marks-input');
    
    function calculateSum(inputs) {
        let sum = 0;
        inputs.forEach(input => {
            if (input) {
                const val = parseInt(input.value) || 0;
                sum += val;
            }
        });
        return sum;
    }
    
    function updateDisplay(sum) {
        if (displayVal) displayVal.textContent = sum;
        if (inputVal) inputVal.value = sum;
    }
    
    // Set up listeners for each round independently (fully decoupled)
    if (r1Inputs.length > 0) {
        r1Inputs.forEach(input => {
            input.addEventListener('input', () => {
                updateDisplay(calculateSum(r1Inputs));
            });
        });
    }
    
    if (r2Inputs.length > 0) {
        r2Inputs.forEach(input => {
            input.addEventListener('input', () => {
                updateDisplay(calculateSum(r2Inputs));
            });
        });
    }
    
    if (r3Inputs.length > 0) {
        r3Inputs.forEach(input => {
            input.addEventListener('input', () => {
                updateDisplay(calculateSum(r3Inputs));
            });
        });
    }
}
