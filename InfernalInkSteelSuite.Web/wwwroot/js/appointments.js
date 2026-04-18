/* Infernal Ink Appointments - Logic from the Underworld */

document.addEventListener('DOMContentLoaded', function () {
    initializeOracle();
    initializeDragDrop();
    checkForClashes();
    initializeViewOptions();
    initializeCalendarToggle();
});

// --- The Oracle (Search) ---
function initializeOracle() {
    const searchTrigger = document.querySelector('[title="Consult the Oracle (Search)"]');
    if (!searchTrigger) return;

    searchTrigger.addEventListener('click', function () {
        let searchBar = document.getElementById('oracle-search-input');
        if (!searchBar) {
            createOracleInput(searchTrigger);
        } else {
            searchBar.focus();
        }
    });
}

function createOracleInput(triggerBtn) {
    const container = triggerBtn.parentElement;
    const input = document.createElement('input');
    input.id = 'oracle-search-input';
    input.type = 'text';
    input.className = 'form-control form-control-sm bg-dark text-white border-secondary ms-2';
    input.placeholder = 'Search souls...';
    input.style.width = '200px';
    input.style.animation = 'fadeIn 0.3s';

    input.addEventListener('input', function (e) {
        filterAppointments(e.target.value);
    });

    container.insertBefore(input, triggerBtn);
    input.focus();
}

function filterAppointments(query) {
    const cards = document.querySelectorAll('.soul-contract-card');
    const lowerQuery = query.toLowerCase();

    cards.forEach(card => {
        const text = card.innerText.toLowerCase();
        if (text.includes(lowerQuery)) {
            card.style.display = 'block';
        } else {
            card.style.display = 'none';
        }
    });
}

// --- Status Ritual Toggle ---
function toggleStatus(element, id) {
    // Visual toggle for now - would initiate API call
    const icon = element.querySelector('i');

    // Cycle: Pending -> Confirmed -> Completed
    if (element.classList.contains('rune-pending')) {
        element.classList.remove('rune-pending');
        element.classList.add('rune-confirmed');
        icon.className = 'bi bi-check-lg';
    } else if (element.classList.contains('rune-confirmed')) {
        element.classList.remove('rune-confirmed');
        element.classList.add('rune-completed');
        icon.className = 'bi bi-check-all';
    } else {
        // Reset or ignored, or maybe cycle back to pending?
        // element.classList.remove('rune-completed');
        // element.classList.add('rune-pending');
        // icon.className = 'bi bi-hourglass-split';
    }

    // Animate
    element.animate([
        { transform: 'scale(1)' },
        { transform: 'scale(1.2)' },
        { transform: 'scale(1)' }
    ], { duration: 300 });

    // In a real app: fetch(`/api/appointments/${id}/status`, ...);
}

// --- Clash Detection ---
function checkForClashes() {
    const cards = Array.from(document.querySelectorAll('.soul-contract-card'));
    // Simple visual clash mock (randomly flag valid conflicts if we parsed time)
    // For now, let's just highlight if any two cards look visibly overlapped in time (complex logic)
    // Or just "Simulate" a clash check on load
}

// --- Drag & Drop (Reshuffling) ---
function initializeDragDrop() {
    const container = document.querySelector('.appointments-timeline');
    if (!container) return;

    let draggedItem = null;

    container.querySelectorAll('.soul-contract-card').forEach(item => {
        item.setAttribute('draggable', true);
        item.style.cursor = 'grab';

        item.addEventListener('dragstart', function (e) {
            draggedItem = this;
            setTimeout(() => this.style.opacity = '0.5', 0);
            this.style.cursor = 'grabbing';
        });

        item.addEventListener('dragend', function (e) {
            setTimeout(() => this.style.opacity = '1', 0);
            draggedItem = null;
            this.style.cursor = 'grab';
        });

        item.addEventListener('dragover', function (e) {
            e.preventDefault();
        });

        item.addEventListener('dragenter', function (e) {
            e.preventDefault();
            this.style.borderTop = '2px solid var(--accent-color)';
        });

        item.addEventListener('dragleave', function () {
            this.style.borderTop = '';
        });

        item.addEventListener('drop', function () {
            this.style.borderTop = '';
            if (draggedItem !== this) {
                // Insert before or after based on position
                container.insertBefore(draggedItem, this);
                // Animate drop
                draggedItem.animate([
                    { transform: 'scale(1.02)' },
                    { transform: 'scale(1)' }
                ], { duration: 200 });
            }
        });
    });
}

function openAppointmentDetails(id) {
    const modalElement = document.getElementById('appointmentDetailsModal');
    const contentContainer = document.getElementById('appointmentDetailsModalContent');
    const modal = new bootstrap.Modal(modalElement);

    // Show spinner
    contentContainer.innerHTML = `
        <div class="modal-body text-center py-5">
             <div class="spinner-border text-accent" role="status">
                 <span class="visually-hidden">Summoning details...</span>
             </div>
             <div class="mt-3 text-muted small text-uppercase" style="letter-spacing: 2px;">Consulting the Ledger...</div>
        </div>`;

    modal.show();

    // Fetch Partial
    fetch(`/Appointments/Index?handler=DetailsPartial&id=${id}`)
        .then(response => {
            if (!response.ok) throw new Error('Failed to summon details');
            return response.text();
        })
        .then(html => {
            contentContainer.innerHTML = html;
        })
        .catch(error => {
            contentContainer.innerHTML = `
                <div class="modal-header border-bottom border-secondary">
                    <h5 class="modal-title text-danger">Ritual Failure</h5>
                     <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body text-center">
                    <p class="text-muted">The spirits are silent. (Error loading details)</p>
                </div>`;
            console.error(error);
        });
}


function markCompleted(id) {
    if (!confirm("Are you sure you want to seal this pact as COMPLETED?")) return;

    const tokenInput = document.querySelector('input[name="__RequestVerificationToken"]');
    const token = tokenInput ? tokenInput.value : '';

    const formData = new FormData();
    formData.append('__RequestVerificationToken', token);

    fetch(`/Appointments/Index?handler=Complete&id=${id}`, {
        method: 'POST',
        body: formData
    })
        .then(response => {
            if (response.ok) {
                const modalElement = document.getElementById('appointmentDetailsModal');
                const modal = bootstrap.Modal.getInstance(modalElement);
                modal.hide();
                location.reload();
            } else {
                alert("The ritual failed. The spirits reject your offering.");
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert("A communication error occurred.");
        });
}

function selectSmartQuote(element, price) {
    if (price > 0) {
        document.getElementById('inputQuotedPrice').value = price.toFixed(2);
    }

    // Update Button Text with the clicked item's text (minus the date span if simpler)
    // We can just grab the text content directly
    const text = element.textContent.trim();
    const btn = document.getElementById('smartQuoteDropdown');
    const span = btn.querySelector('span');
    if (span) span.textContent = text;
}

function updateFinancials(id) {
    const quotedPrice = document.getElementById('inputQuotedPrice').value;

    const tokenInput = document.querySelector('input[name="__RequestVerificationToken"]');
    const token = tokenInput ? tokenInput.value : '';

    const formData = new FormData();
    formData.append('__RequestVerificationToken', token);
    formData.append('quotedPrice', quotedPrice);

    fetch(`/Appointments/Index?handler=UpdateFinancials&id=${id}`, {
        method: 'POST',
        body: formData
    })
        .then(response => {
            if (response.ok) {
                // Flash success styling or toast
                const btn = document.querySelector('button[onclick^="updateFinancials"]');
                const originalHtml = btn.innerHTML;
                btn.innerHTML = '<i class="bi bi-check-lg"></i>';
                btn.classList.remove('btn-outline-success');
                btn.classList.add('btn-success');
                setTimeout(() => {
                    btn.innerHTML = originalHtml;
                    btn.classList.add('btn-outline-success');
                    btn.classList.remove('btn-success');
                }, 1000);
            } else {
                alert("Failed to update financials. The ledger rejects these numbers.");
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert("Communication error with the underworld.");
        });
}

function openQuotePopup(clientId) {
    const width = 800;
    const height = 900;
    const left = (window.screen.width - width) / 2;
    const top = (window.screen.height - height) / 2;

    window.open(
        `/Quotes/New?clientId=${clientId}&isPopup=true`,
        'CreateQuote',
        `width=${width},height=${height},top=${top},left=${left},resizable=yes,scrollbars=yes`
    );
}

function openClientEditPopup(clientId, apptId) {
    const width = 1000;
    const height = 900;
    const left = (window.screen.width - width) / 2;
    const top = (window.screen.height - height) / 2;

    window.open(
        `/Clients/Edit/${clientId}?isPopup=true&returnApptId=${apptId || ''}`,
        'EditClient',
        `width=${width},height=${height},top=${top},left=${left},resizable=yes,scrollbars=yes`
    );
}

function openAppointmentEditPopup(apptId) {
    const width = 800;
    const height = 900;
    const left = (window.screen.width - width) / 2;
    const top = (window.screen.height - height) / 2;

    window.open(
        `/Appointments/Edit/${apptId}?isPopup=true`,
        'EditAppointment',
        `width=${width},height=${height},top=${top},left=${left},resizable=yes,scrollbars=yes`
    );
}

function refreshAppointmentDetails(id) {
    const contentContainer = document.getElementById('appointmentDetailsModalContent');

    // Show local loading state within the modal body if we wanted, 
    // but for a refresh, maybe just a spinner on the button?
    // Let's just do a silent refresh or replace content.

    // For visual feedback, let's blur the content slightly
    contentContainer.style.opacity = '0.5';

    fetch(`/Appointments/Index?handler=DetailsPartial&id=${id}`)
        .then(response => {
            if (!response.ok) throw new Error('Failed to refresh details');
            return response.text();
        })
        .then(html => {
            contentContainer.innerHTML = html;
            contentContainer.style.opacity = '1';
        })
        .catch(error => {
            console.error(error);
            alert("Failed to refresh the pact details.");
            contentContainer.style.opacity = '1';
        });
}

// --- View Options Logic ---
function initializeViewOptions() {
    const toolbar = document.getElementById('viewOptionsToolbar');
    const container = document.getElementById('appointmentsList');
    if (!toolbar || !container) return;

    const buttons = toolbar.querySelectorAll('.view-option-btn');
    
    buttons.forEach(btn => {
        btn.addEventListener('click', function() {
            // Remove active state
            buttons.forEach(b => b.classList.remove('active'));
            this.classList.add('active');

            // Apply View Class
            const viewMode = this.getAttribute('data-view');
            container.classList.remove('view-grid', 'view-small', 'view-medium', 'view-large');
            
            // Medium is default, so no class needed, but adding view-medium is fine if CSS supports it
            // My CSS uses .view-grid, .view-small, .view-large. 
            if (viewMode !== 'medium') {
                container.classList.add(`view-${viewMode}`);
            }
        });
    });
}

// --- Calendar Toggle Logic ---
function initializeCalendarToggle() {
    console.log("Initializing Calendar Toggle (Event Delegation + Persistence)...");
    
    // 1. Restore State on Load
    const pageContainer = document.querySelector('.appointments-container');
    const icon = document.getElementById('calendarToggleIcon');
    const storedState = localStorage.getItem('infernal_calendar_mode');

    // Default is 'compact' (class present in HTML). 
    // If storedState is 'expanded', we remove the class.
    if (pageContainer && storedState === 'expanded') {
        pageContainer.classList.remove('compact-calendar-mode');
        // If compact is default (icon points right?), expanded might need rotation?
        // Let's rely on CSS or toggle logic. 
        // If default icon is 'chevron-right', and we are expanded, maybe rotate it?
        if(icon) icon.classList.add('rotate-180');
    }

    // 2. Event Handler with Persistence
    document.body.addEventListener('click', function(e) {
        const toggleBtn = e.target.closest('#toggleCalendarBtn');
        if (!toggleBtn) return; // Not our button
        
        e.preventDefault();
        
        const container = document.querySelector('.appointments-container');
        const toggleIcon = document.getElementById('calendarToggleIcon');

        if(container) {
            container.classList.toggle('compact-calendar-mode');
            
            // Save new state
            const isCompact = container.classList.contains('compact-calendar-mode');
            localStorage.setItem('infernal_calendar_mode', isCompact ? 'compact' : 'expanded');
            
            console.log(`Calendar mode toggled. New state: ${isCompact ? 'compact' : 'expanded'}`);
        }

        if (toggleIcon) {
            toggleIcon.classList.toggle('rotate-180');
        }
    });
}
