// Infernal Ink & Steel Suite - Main Script

document.addEventListener('DOMContentLoaded', () => {
    initEmberCursor();
    initBloodInk();
    initSoulBinding();
    initRitualLoader();
    initOracle();
    initSoundscapes();
    initSummonFAB();
    initContextMenus();
    initGestures();
});

// Hellfire Init Check
if (localStorage.getItem('hellfire-mode') === 'true') {
    document.body.classList.add('hellfire-mode');
}

/* --- 1. Ember Cursor Trail --- */
function initEmberCursor() {
    const container = document.createElement('div');
    container.id = 'ember-container';
    document.body.appendChild(container);

    let throttle = false;
    document.addEventListener('mousemove', (e) => {
        if (throttle) return;
        throttle = true;
        setTimeout(() => throttle = false, 20); // Limit particle creation rate

        createEmber(e.clientX, e.clientY);
    });
}

function createEmber(x, y) {
    const ember = document.createElement('div');
    ember.classList.add('ember-particle');

    // Randomize size and drift
    const size = Math.random() * 4 + 2; // 2px to 6px
    const driftX = (Math.random() - 0.5) * 30;
    const driftY = (Math.random() - 0.5) * 30 - 20; // Tend upwards (-y is up)

    ember.style.width = `${size}px`;
    ember.style.height = `${size}px`;
    ember.style.left = `${x}px`;
    ember.style.top = `${y}px`;

    // Random color variant (Yellow -> Orange -> Red)
    const colors = ['#ffcc00', '#ff6600', '#ff3300', '#cc0000'];
    ember.style.background = colors[Math.floor(Math.random() * colors.length)];

    document.getElementById('ember-container').appendChild(ember);

    // Animate
    const animation = ember.animate([
        { transform: 'translate(0, 0) scale(1)', opacity: 1 },
        { transform: `translate(${driftX}px, ${driftY}px) scale(0)`, opacity: 0 }
    ], {
        duration: 800 + Math.random() * 400,
        easing: 'cubic-bezier(0, .9, .57, 1)',
        fill: 'forwards'
    });

    animation.onfinish = () => ember.remove();
}

/* --- 2. Blood Ink Inputs --- */
function initBloodInk() {
    // Select all text inputs and textareas
    const inputs = document.querySelectorAll('input[type="text"], textarea');

    inputs.forEach(input => {
        input.classList.add('blood-ink-input');

        // Typing effect
        input.addEventListener('input', () => {
            input.style.color = '#ff3333'; // Fresh blood
            input.style.textShadow = '0 0 5px rgba(255, 51, 51, 0.5)';

            // "Dry" the ink after a delay
            clearTimeout(input.dryTimer);
            input.dryTimer = setTimeout(() => {
                input.style.color = '#8a0000'; // Dried blood
                input.style.textShadow = 'none';
                input.style.transition = 'color 3s ease, text-shadow 3s ease';
            }, 2000);
        });
    });
}

/* --- 3. Omen Toasts (Notifications) --- */
window.showOmen = function (message, type = 'info') {
    let container = document.getElementById('omen-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'omen-container';
        document.body.appendChild(container);
    }

    const omen = document.createElement('div');
    omen.classList.add('omen-toast', `omen-${type}`);

    let icon = 'bi-info-circle';
    if (type === 'success') icon = 'bi-check-circle';
    if (type === 'error') icon = 'bi-exclamation-triangle';
    if (type === 'warning') icon = 'bi-exclamation-circle';

    omen.innerHTML = `
        <div class="omen-icon"><i class="bi ${icon}"></i></div>
        <div class="omen-body">${message}</div>
        <div class="omen-close"><i class="bi bi-x"></i></div>
    `;

    container.appendChild(omen);

    // Animation In
    requestAnimationFrame(() => omen.classList.add('show'));

    // Dismiss Logic
    const closeBtn = omen.querySelector('.omen-close');
    closeBtn.addEventListener('click', () => dismissOmen(omen));

    // Auto Dismiss after 5s
    setTimeout(() => dismissOmen(omen), 5000);
};

function dismissOmen(element) {
    if (!element) return;
    element.classList.remove('show');
    // Wait for CSS transition
    setTimeout(() => {
        if (element.parentNode) element.parentNode.removeChild(element);
    }, 400); // match CSS transition time
}

/* --- 4. Soul Binding (Persisted Settings) --- */
function initSoulBinding() {
    const savedSoul = localStorage.getItem('soul-color');
    if (savedSoul) {
        bindSoul(savedSoul, false); // Don't notify on init
    }
}

window.bindSoul = function (color, notify = true) {
    document.documentElement.style.setProperty('--accent-color', color);
    document.documentElement.style.setProperty('--primary-color', color);
    localStorage.setItem('soul-color', color);

    if (notify) showOmen('Soul bound successfully.', 'success');
}

/* --- 5. Ritual Spinner (Simple Loader) --- */
function initRitualLoader() {
    const spinner = document.getElementById('ritual-spinner');
    if (!spinner) return;

    // Show on form submit
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', () => {
            if (form.checkValidity()) {
                spinner.classList.remove('d-none');
            }
        });
    });

    // Show on internal navigation
    document.querySelectorAll('a').forEach(link => {
        link.addEventListener('click', (e) => {
            const href = link.getAttribute('href');
            // Only show for internal pages, not hashes or new tabs
            if (href && href.startsWith('/') && !href.startsWith('#') && !link.hasAttribute('data-bs-toggle') && link.target !== '_blank') {
                spinner.classList.remove('d-none');
            }
        });
    });

    // Hide on back button (pageshow event)
    window.addEventListener('pageshow', (e) => {
        spinner.classList.add('d-none');
    });
}

/* --- 6. The Oracle (Command Palette) --- */
function initOracle() {
    const overlay = document.getElementById('oracle-overlay');
    const input = document.getElementById('oracle-input');
    const resultsContainer = document.getElementById('oracle-results');

    if (!overlay || !input) return;

    // Actions Dictionary
    const actions = [
        { label: 'Dashboard', icon: 'bi-speedometer2', url: '/Dashboard/Index', meta: 'Page' },
        { label: 'Appointments: All', icon: 'bi-calendar-event', url: '/Appointments', meta: 'List' },
        { label: 'Appointments: Create New', icon: 'bi-plus-circle', url: '/Appointments/Create', meta: 'Action' },
        { label: 'Clients: All', icon: 'bi-people', url: '/Clients', meta: 'List' },
        { label: 'Clients: Create New', icon: 'bi-person-plus', url: '/Clients/Create', meta: 'Action' },
        { label: 'Settings', icon: 'bi-gear', url: '/Settings/Index', meta: 'System' },
        { label: 'Log Out', icon: 'bi-box-arrow-right', url: '/Account/Logout', meta: 'System' },
        // Aesthetic Toggles
        { label: 'Toggle Sound', icon: 'bi-volume-up', click: toggleSound, meta: 'Setting' },
        { label: 'Toggle Hellfire', icon: 'bi-fire', click: toggleHellfire, meta: 'Setting' },
        { label: 'Toggle Trance', icon: 'bi-eye-slash', click: toggleTrance, meta: 'Setting' },
        { label: 'Force 404 (Limbo)', icon: 'bi-question-diamond', url: '/Force404', meta: 'Debug' },
        { label: 'Force 500 (Ritual Fail)', icon: 'bi-exclamation-triangle', url: '/Force500', meta: 'Debug' }
    ];

    let isOpen = false;
    let filteredActions = [];
    let selectedIndex = 0;

    // Toggle Visibility
    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            toggleOracle();
        }
        if (e.key === 'Escape' && isOpen) {
            toggleOracle();
        }
    });

    function toggleOracle() {
        isOpen = !isOpen;
        if (isOpen) {
            overlay.classList.remove('d-none');
            input.value = '';
            input.focus();
            renderResults(actions);
        } else {
            overlay.classList.add('d-none');
        }
    }

    // Input Handling
    input.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase();
        filteredActions = actions.filter(action =>
            action.label.toLowerCase().includes(query) ||
            action.meta.toLowerCase().includes(query)
        );
        selectedIndex = 0;
        renderResults(filteredActions);
    });

    // Keyboard Navigation
    input.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            selectedIndex = (selectedIndex + 1) % filteredActions.length;
            updateSelection();
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            selectedIndex = (selectedIndex - 1 + filteredActions.length) % filteredActions.length;
            updateSelection();
        } else if (e.key === 'Enter') {
            e.preventDefault();
            executeAction(filteredActions[selectedIndex]);
        }
    });

    function renderResults(list) {
        filteredActions = list;
        resultsContainer.innerHTML = '';
        list.forEach((action, index) => {
            const div = document.createElement('div');
            div.className = `oracle-item ${index === 0 ? 'active' : ''}`;
            div.innerHTML = `<i class="bi ${action.icon}"></i> <span>${action.label}</span> <span class="meta">${action.meta}</span>`;
            div.addEventListener('click', () => executeAction(action));
            div.addEventListener('mouseenter', () => {
                selectedIndex = index;
                updateSelection();
            });
            resultsContainer.appendChild(div);
        });
    }

    function updateSelection() {
        const items = resultsContainer.querySelectorAll('.oracle-item');
        items.forEach((item, index) => {
            if (index === selectedIndex) {
                item.classList.add('active');
                item.scrollIntoView({ block: 'nearest' });
            } else {
                item.classList.remove('active');
            }
        });
    }

    function executeAction(action) {
        if (!action) return;
        playSound('click'); // Feedback
        if (action.click) {
            action.click();
            toggleOracle();
        } else if (action.url) {
            window.location.href = action.url;
        }
    }

    // Close on overlay click
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) toggleOracle();
    });
}

/* --- 7. Soundscapes (Web Audio API) --- */
let audioCtx;
let soundsEnabled = false;

function initSoundscapes() {
    // Check preference
    if (localStorage.getItem('portal-sounds') === 'true') {
        soundsEnabled = true;
    }

    // Interactive Elements
    document.querySelectorAll('a, button, .btn').forEach(el => {
        el.addEventListener('mouseenter', () => playSound('hover'));
        el.addEventListener('click', () => playSound('click'));
    });

    // Inputs
    document.querySelectorAll('input, textarea').forEach(el => {
        el.addEventListener('focus', () => playSound('hover'));
        el.addEventListener('input', () => {
            // Very subtle typing click? maybe too annoying.
        });
    });
}

function toggleSound() {
    soundsEnabled = !soundsEnabled;
    localStorage.setItem('portal-sounds', soundsEnabled);
    showOmen(`Soundscapes ${soundsEnabled ? 'Enabled' : 'Disabled'}`, 'info');
    if (soundsEnabled) playSound('click');
}

function playSound(type) {
    if (!soundsEnabled) return;

    // Init context on first gesture if needed
    if (!audioCtx) {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        audioCtx = new AudioContext();
    }

    const osc = audioCtx.createOscillator();
    const gainNode = audioCtx.createGain();

    osc.connect(gainNode);
    gainNode.connect(audioCtx.destination);

    const now = audioCtx.currentTime;

    if (type === 'hover') {
        // Subtle low thrum
        osc.type = 'sine';
        osc.frequency.setValueAtTime(80, now);
        osc.frequency.exponentialRampToValueAtTime(120, now + 0.1);

        gainNode.gain.setValueAtTime(0.01, now); // Very quiet
        gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.1);

        osc.start(now);
        osc.stop(now + 0.1);
    } else if (type === 'click') {
        // Sharp metallic click
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(800, now);
        osc.frequency.exponentialRampToValueAtTime(100, now + 0.1);

        gainNode.gain.setValueAtTime(0.05, now);
        gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.15);

        osc.start(now);
        osc.stop(now + 0.15);
    }

    /* --- 10. Hellfire Mode & Trance Mode --- */
    function toggleHellfire() {
        document.body.classList.toggle('hellfire-mode');
        const isHell = document.body.classList.contains('hellfire-mode');
        localStorage.setItem('hellfire-mode', isHell);
        showOmen(isHell ? 'Hellfire Ignited!' : 'Flames Extinguished.', 'warning');
    }

    function toggleTrance() {
        document.body.classList.toggle('trance-mode');
        const isTrance = document.body.classList.contains('trance-mode');
        showOmen(isTrance ? 'Trance Focus: ON' : 'Trance Focus: OFF', 'info');
    }

    /* --- 11. Predictive Incantations --- */
    function initPredictiveIncantations() {
        const commonSpells = ['Tattoo Consultation', 'Touch-up', 'Full Sleeve', 'Cover-up', 'Piercing Check', 'Aftercare'];

        document.querySelectorAll('.predictive-input').forEach(input => {
            // Create suggestion box
            const wrapper = document.createElement('div');
            wrapper.className = 'predictive-wrapper';
            if (input.parentNode) {
                input.parentNode.insertBefore(wrapper, input);
                wrapper.appendChild(input);
            }

            const box = document.createElement('div');
            box.className = 'predictive-suggestions';
            wrapper.appendChild(box);

            input.addEventListener('input', () => {
                const val = input.value.toLowerCase();
                if (val.length < 2) {
                    box.style.display = 'none';
                    return;
                }

                const matches = commonSpells.filter(s => s.toLowerCase().includes(val));
                if (matches.length > 0) {
                    box.innerHTML = matches.map(s => `<div class="predictive-suggestion">${s}</div>`).join('');
                    box.style.display = 'block';

                    box.querySelectorAll('.predictive-suggestion').forEach(div => {
                        div.addEventListener('click', () => {
                            input.value = div.innerText;
                            box.style.display = 'none';
                        });
                    });
                } else {
                    box.style.display = 'none';
                }
            });

            // Hide on click outside
            document.addEventListener('click', (e) => {
                if (!wrapper.contains(e.target)) box.style.display = 'none';
            });
        });
    }


    /* --- 12. Gestural Actions (Swipe) --- */
    function initGestures() {
        let touchStartX = 0;

        document.querySelectorAll('.kanban-card, .list-group-item').forEach(el => {
            el.addEventListener('touchstart', e => {
                touchStartX = e.changedTouches[0].screenX;
            }, { passive: true });

            el.addEventListener('touchend', e => {
                const touchEndX = e.changedTouches[0].screenX;
                if (touchStartX - touchEndX > 100) {
                    // Swipe Left
                    showOmen('Swipe Action Triggered (Archive)', 'info');
                }
            }, { passive: true });
        });
    }

    /* --- 13. Soul Contract Signature Pad --- */
    let signaturePadContext;
    let isDrawing = false;

    function initSignaturePad() {
        const canvas = document.getElementById('signature-pad');
        if (!canvas) return;

        // Set resolution
        canvas.width = canvas.offsetWidth;
        canvas.height = canvas.offsetHeight;

        signaturePadContext = canvas.getContext('2d');
        signaturePadContext.strokeStyle = '#8a0000'; // Blood Red
        signaturePadContext.lineWidth = 3;
        signaturePadContext.lineCap = 'round';

        // Mouse Events
        canvas.addEventListener('mousedown', startDrawing);
        canvas.addEventListener('mousemove', draw);
        canvas.addEventListener('mouseup', stopDrawing);
        canvas.addEventListener('mouseout', stopDrawing);

        // Touch Events
        canvas.addEventListener('touchstart', (e) => {
            e.preventDefault();
            startDrawing(e.touches[0]);
        });
        canvas.addEventListener('touchmove', (e) => {
            e.preventDefault();
            draw(e.touches[0]);
        });
        canvas.addEventListener('touchend', stopDrawing);
    }

    function startDrawing(e) {
        isDrawing = true;
        draw(e); // Draw dot
    }

    function draw(e) {
        if (!isDrawing) return;

        // Get correct coordinates
        const canvas = document.getElementById('signature-pad');
        const rect = canvas.getBoundingClientRect();
        const x = (e.clientX || e.pageX) - rect.left;
        const y = (e.clientY || e.pageY) - rect.top;

        signaturePadContext.lineTo(x, y);
        signaturePadContext.stroke();
        signaturePadContext.beginPath();
        signaturePadContext.moveTo(x, y);
    }

    function stopDrawing() {
        isDrawing = false;
        if (signaturePadContext) signaturePadContext.beginPath();
    }

    function clearSignature() {
        const canvas = document.getElementById('signature-pad');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
    }

    window.sealContract = function () {
        showOmen("Contract Sealed. Your soul is bound.", "success");
        // In real app, convert canvas.toDataURL() and POST it
        setTimeout(() => {
            window.location.href = '/Appointments/Index';
        }, 2000);
    }

    /* --- 19. The Shadow Realm (Service Worker) --- */
    if ('serviceWorker' in navigator) {
        window.addEventListener('load', () => {
            navigator.serviceWorker.register('/sw.js')
                .then(registration => {
                    console.log('Shadow Realm registered:', registration.scope);
                })
                .catch(error => {
                    console.log('Shadow Realm connection failed:', error);
                });
        });
    }

    /* --- 20. Lazy Loading (Performance) --- */
    document.addEventListener("DOMContentLoaded", function () {
        const lazyImages = [].slice.call(document.querySelectorAll("img.lazy-load"));

        if ("IntersectionObserver" in window) {
            let lazyImageObserver = new IntersectionObserver(function (entries, observer) {
                entries.forEach(function (entry) {
                    if (entry.isIntersecting) {
                        let lazyImage = entry.target;
                        lazyImage.src = lazyImage.dataset.src;
                        lazyImage.classList.remove("lazy-load");
                        lazyImage.classList.add("fade-in");
                        lazyImageObserver.unobserve(lazyImage);
                    }
                });
            });

            lazyImages.forEach(function (lazyImage) {
                lazyImageObserver.observe(lazyImage);
            });
        }
    });
