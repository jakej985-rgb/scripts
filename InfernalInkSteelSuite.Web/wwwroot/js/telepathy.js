/* --- Teletpathy (Simulated SignalR) --- */
// In a production environment, this would connect to an actual SignalR hub.

const TELEPATHY_EVENTS = [
    { title: "New Appointment Request", msg: "A soul seeks an audience.", type: "info" },
    { title: "Inventory Critical", msg: "Black Ink levels are running low.", type: "warning" },
    { title: "Ritual Complete", msg: "Damien has finished the 'Void Stare' session.", type: "success" },
    { title: "Message from the Void", msg: "Client 'Lilith' says: 'Running 5 mins late.'", type: "info" }
];

function initTelepathy() {
    console.log("Establish telepathic link...");

    // Simulate incoming messages unpredictably
    setInterval(() => {
        // 10% chance every 10 seconds to receive a message
        if (Math.random() > 0.9) {
            triggerPsychicEvent();
        }
    }, 10000);
}

function triggerPsychicEvent() {
    const event = TELEPATHY_EVENTS[Math.floor(Math.random() * TELEPATHY_EVENTS.length)];

    // Play subtle sound if enabled
    if (typeof playSound === 'function') {
        playSound('hover'); // utilizing existing sound for now
    }

    // Visual Pulse on the view
    document.body.classList.add('psychic-pulse');
    setTimeout(() => document.body.classList.remove('psychic-pulse'), 500);

    // Show Omen
    if (typeof showOmen === 'function') {
        showOmen(event.msg, event.type);
    }
}

// Auto-initialize if not locally prevented
if (localStorage.getItem('telepathy-enabled') !== 'false') {
    document.addEventListener('DOMContentLoaded', initTelepathy);
}
