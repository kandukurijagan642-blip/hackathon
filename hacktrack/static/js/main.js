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
                    alert('Error toggling setting.');
                    this.checked = !this.checked;
                }
            })
            .catch(err => {
                this.disabled = false;
                alert('Connection error occurred.');
                this.checked = !this.checked;
            });
        });
    });
});

function setupEvaluationCalculators() {
    // Round 1 inputs
    const r1Inputs = [
        document.getElementById('innovation'),
        document.getElementById('problem_statement'),
        document.getElementById('feasibility'),
        document.getElementById('presentation'),
        document.getElementById('confidence')
    ];
    
    // Round 2 inputs
    const r2Inputs = [
        document.getElementById('prototype'),
        document.getElementById('technical_implementation'),
        document.getElementById('uiux'),
        document.getElementById('question_answer')
    ];
    
    // Round 3 inputs
    const r3Inputs = [
        document.getElementById('working_demo'),
        document.getElementById('business_model'),
        document.getElementById('scalability'),
        document.getElementById('presentation_r3') // name presentation is common in r1, so r3 has presentation_r3
    ];
    
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
    
    // Check which round we are currently evaluating and attach listeners
    if (r1Inputs.some(el => el !== null)) {
        r1Inputs.forEach(input => {
            if (input) {
                input.addEventListener('input', () => {
                    const total = calculateSum(r1Inputs);
                    updateDisplay(total);
                });
            }
        });
    } else if (r2Inputs.some(el => el !== null)) {
        r2Inputs.forEach(input => {
            if (input) {
                input.addEventListener('input', () => {
                    const total = calculateSum(r2Inputs);
                    updateDisplay(total);
                });
            }
        });
    } else if (r3Inputs.some(el => el !== null)) {
        r3Inputs.forEach(input => {
            if (input) {
                input.addEventListener('input', () => {
                    // Quick patch: in Round 3 form we have working_demo, business_model, scalability, presentation_r3
                    // Let's also check if standard presentation name is reused
                    const r3_p = document.getElementById('presentation');
                    const activeR3Inputs = [...r3Inputs];
                    if (r3_p && !activeR3Inputs.includes(r3_p)) {
                        activeR3Inputs.push(r3_p);
                    }
                    const total = calculateSum(activeR3Inputs);
                    updateDisplay(total);
                });
            }
        });
    }
}
