/**
 * Trading Event Viewer - Simplified Client JavaScript
 * WebSocket connection and UI update only (no control logic)
 */

// State
let ws = null;
let reconnectAttempts = 0;
let maxReconnectAttempts = 10;
let autoScroll = true;

// Data stores
const orders = new Map();
const quotes = new Map();
const maxLogEntries = 500;
const maxQuotes = 20;
const maxOrders = 20;

// DOM Elements
const elements = {
    statusDot: null,
    statusText: null,
    ordersPanel: null,
    ordersCount: null,
    quotesPanel: null,
    quotesCount: null,
    logPanel: null,
    logCount: null,
    btnAutoScroll: null,
};

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
    initElements();
    connectWebSocket();
});

function initElements() {
    const connStatus = document.getElementById('connection-status');
    elements.statusDot = connStatus?.querySelector('.status-dot');
    elements.statusText = connStatus?.querySelector('.status-text');
    elements.ordersPanel = document.getElementById('orders-panel');
    elements.ordersCount = document.getElementById('orders-count');
    elements.quotesPanel = document.getElementById('quotes-panel');
    elements.quotesCount = document.getElementById('quotes-count');
    elements.logPanel = document.getElementById('log-panel');
    elements.logCount = document.getElementById('log-count');
    elements.btnAutoScroll = document.getElementById('btn-auto-scroll');
}

// WebSocket Connection
function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        updateConnectionStatus(true);
        reconnectAttempts = 0;
        addLog('Connected to server', 'success');
    };

    ws.onclose = () => {
        updateConnectionStatus(false);
        addLog('Disconnected from server', 'warning');
        scheduleReconnect();
    };

    ws.onerror = () => {
        addLog('Connection error', 'error');
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleMessage(data);
        } catch (e) {
            console.error('Failed to parse message:', e);
        }
    };
}

function scheduleReconnect() {
    if (reconnectAttempts < maxReconnectAttempts) {
        reconnectAttempts++;
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);
        addLog(`Reconnecting in ${delay / 1000}s...`, 'info');
        setTimeout(connectWebSocket, delay);
    }
}

function updateConnectionStatus(connected) {
    if (elements.statusDot) {
        elements.statusDot.className = `status-dot ${connected ? 'connected' : 'disconnected'}`;
    }
    if (elements.statusText) {
        elements.statusText.textContent = connected ? 'Connected' : 'Disconnected';
    }
}

// Message Handling
function handleMessage(data) {
    const { type, data: content, time } = data;

    switch (type) {
        case 'ODR':
            handleOrderMessage(content);
            break;
        case 'MKT':
            handleMarketMessage(content, time);
            break;
        case 'SYS':
            addLog(content, 'info', time);
            break;
        case 'ALT':
            handleAlertMessage(content, time);
            break;
        case 'CLR':
            handleClearMessage(content);
            break;
        default:
            addLog(content, 'info', time);
    }
}

function handleAlertMessage(content, time) {
    let level = 'info';
    if (content.includes('SUCCESS')) level = 'success';
    else if (content.includes('ERROR')) level = 'error';
    else if (content.includes('WARNING')) level = 'warning';
    addLog(content, level, time);
}

function handleOrderMessage(content) {
    const parts = content.split('|');

    if (parts[0]?.trim() === 'REMOVED') {
        const orderId = parts[1]?.trim();
        if (orderId) {
            orders.delete(orderId);
            updateOrdersPanel();
        }
        return;
    }

    if (parts.length >= 6) {
        const [name, ticker, side, qty, price, state, orderId] = parts.map(p => p.trim());
        const id = orderId || `${ticker}_${Date.now()}`;

        orders.set(id, {
            time: new Date().toLocaleTimeString('en-US', { hour12: false }),
            name, ticker, side, qty, price, state
        });

        while (orders.size > maxOrders) {
            const firstKey = orders.keys().next().value;
            orders.delete(firstKey);
        }

        updateOrdersPanel();
    }
}

function handleMarketMessage(content, time) {
    const parts = content.split('|');
    if (parts.length < 2) return;

    let ticker = parts[1]?.trim();
    if (!ticker) return;

    if (ticker.length > 6 && ['DNAS', 'DNYS', 'DAMS'].includes(ticker.substring(0, 4))) {
        ticker = ticker.substring(4);
    }

    quotes.set(ticker, {
        content,
        time: time || new Date().toLocaleTimeString('en-US', { hour12: false })
    });

    while (quotes.size > maxQuotes) {
        const firstKey = quotes.keys().next().value;
        quotes.delete(firstKey);
    }

    updateQuotesPanel();
    addLog(content, 'mkt', time);
}

function handleClearMessage(content) {
    if (content.trim() === 'ORDERS') {
        orders.clear();
        updateOrdersPanel();
    } else if (content.trim() === 'QUOTES') {
        quotes.clear();
        updateQuotesPanel();
    }
}

// UI Updates
function updateOrdersPanel() {
    if (!elements.ordersPanel) return;

    if (orders.size === 0) {
        elements.ordersPanel.innerHTML = '<div class="empty-state">No orders</div>';
    } else {
        const entries = Array.from(orders.entries()).reverse();
        elements.ordersPanel.innerHTML = entries.map(([id, order]) => {
            const sideClass = order.side.toUpperCase().includes('BUY') ? 'buy' : 'sell';
            return `
                <div class="order-entry ${sideClass}">
                    <span class="time">${order.time}</span>
                    <span style="width:150px;overflow:hidden;text-overflow:ellipsis">${order.name}</span>
                    <span style="width:60px">${order.ticker}</span>
                    <span style="width:60px;color:${sideClass === 'buy' ? 'var(--accent-success)' : 'var(--accent-danger)'}">${order.side}</span>
                    <span style="width:80px;text-align:right">${formatNumber(order.price)}</span>
                    <span style="width:50px;text-align:right">${order.qty}</span>
                    <span style="margin-left:auto;color:var(--text-dim)">${order.state}</span>
                </div>`;
        }).join('');
    }

    if (elements.ordersCount) {
        elements.ordersCount.textContent = orders.size;
    }
}

function updateQuotesPanel() {
    if (!elements.quotesPanel) return;

    if (quotes.size === 0) {
        elements.quotesPanel.innerHTML = '<div class="empty-state">Waiting for quotes...</div>';
    } else {
        const entries = Array.from(quotes.entries()).reverse();
        elements.quotesPanel.innerHTML = entries.map(([ticker, quote]) => {
            return `<div class="quote-entry">${colorizeQuote(quote.content)}</div>`;
        }).join('');
    }

    if (elements.quotesCount) {
        elements.quotesCount.textContent = quotes.size;
    }
}

function colorizeQuote(content) {
    let result = escapeHtml(content);
    result = result.replace(/Last:([^|]+)/g, 'Last:<span class="value-neutral">$1</span>');
    result = result.replace(/Diff:([^|]*-[^|]+)/g, 'Diff:<span class="value-down">$1</span>');
    result = result.replace(/Diff:([^|]+)/g, 'Diff:<span class="value-up">$1</span>');
    return result;
}

function addLog(message, level = 'info', time = null) {
    if (!elements.logPanel) return;

    const timestamp = time || new Date().toLocaleTimeString('en-US', { hour12: false });
    const entry = document.createElement('div');
    entry.className = `log-entry ${level}`;
    entry.innerHTML = `<span class="time">${timestamp}</span>${escapeHtml(message)}`;

    elements.logPanel.appendChild(entry);

    while (elements.logPanel.children.length > maxLogEntries) {
        elements.logPanel.removeChild(elements.logPanel.firstChild);
    }

    if (autoScroll) {
        elements.logPanel.scrollTop = elements.logPanel.scrollHeight;
    }

    if (elements.logCount) {
        elements.logCount.textContent = elements.logPanel.children.length;
    }
}

// UI Controls
function toggleAutoScroll() {
    autoScroll = !autoScroll;
    if (elements.btnAutoScroll) {
        elements.btnAutoScroll.textContent = `Auto-Scroll: ${autoScroll ? 'ON' : 'OFF'}`;
    }
}

function clearLogs() {
    if (elements.logPanel) {
        elements.logPanel.innerHTML = '';
        addLog('Logs cleared', 'info');
    }
}

// Utilities
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatNumber(value) {
    if (!value) return value;
    const num = parseFloat(value.replace(/,/g, ''));
    if (isNaN(num)) return value;
    return num.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 4 });
}
