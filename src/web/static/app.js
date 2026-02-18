/**
 * Trading Event Viewer - Simplified Client JavaScript
 * WebSocket connection and UI update only (no control logic)
 */

// State
let ws = null;
let reconnectAttempts = 0;
let maxReconnectAttempts = 10;
let autoScroll = true;
let showMktLogs = false;
let autoRefreshOrders = true;

// Data stores
const orders = new Map();
const quotes = new Map();
const maxLogEntries = 500;
const maxQuotes = 20;
const maxOrders = 20;

// Fixed Ticker Order Configuration
const tickerOrder = [
    // Leverage ETFs
    'SOXL', 'FAS', 'TQQQ', 'QLD',
    // ETFs
    'QQQM', 'VOO', 'SCHD', 'TLT',
    // Individual Stocks
    'GOOGL', 'TSM', 'NVDA', 'AVGO', 'QCOM', 'BLK'
]; // Tickers will layout in this order. Others will follow alphabetically.

// Cancel modal state
let pendingCancelOrderId = null;
let pendingCancelTicker = null;

// DOM Elements
const elements = {
    statusDot: null,
    statusText: null,
    ordersPanel: null,
    ordersCount: null,
    ordersAutoToggle: null,
    quotesPanel: null,
    quotesCount: null,
    logPanel: null,
    logCount: null,
    btnAutoScroll: null,
    mktToggle: null,
    memosPanel: null, // New
};

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
    initElements();
    initMktToggle();
    initOrdersAutoToggle();
    connectWebSocket();
    fetchMemos(); // New

    // Auto-refresh orders every 30 seconds
    setInterval(() => {
        if (autoRefreshOrders) {
            refreshOrders(true);
        }
    }, 30000);
});

function initElements() {
    const connStatus = document.getElementById('connection-status');
    elements.statusDot = connStatus?.querySelector('.status-dot');
    elements.statusText = connStatus?.querySelector('.status-text');
    elements.ordersPanel = document.getElementById('orders-panel');
    elements.ordersCount = document.getElementById('orders-count');
    elements.ordersAutoToggle = document.getElementById('orders-auto-toggle');
    elements.quotesPanel = document.getElementById('quotes-panel');
    elements.quotesCount = document.getElementById('quotes-count');
    elements.logPanel = document.getElementById('log-panel');
    elements.logCount = document.getElementById('log-count');
    elements.btnAutoScroll = document.getElementById('btn-auto-scroll');
    elements.mktToggle = document.getElementById('mkt-toggle');
    elements.memosPanel = document.getElementById('memos-panel'); // New
}

function initMktToggle() {
    if (elements.mktToggle) {
        elements.mktToggle.addEventListener('click', () => {
            showMktLogs = !showMktLogs;
            elements.mktToggle.classList.toggle('active', showMktLogs);
        });
    }
}

function initOrdersAutoToggle() {
    if (elements.ordersAutoToggle) {
        elements.ordersAutoToggle.addEventListener('click', () => {
            autoRefreshOrders = !autoRefreshOrders;
            elements.ordersAutoToggle.classList.toggle('active', autoRefreshOrders);
            addLog(`Orders auto-refresh: ${autoRefreshOrders ? 'ON' : 'OFF'}`, 'info');
        });
    }
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
        // Request existing orders on connection
        ws.send('sync_orders');
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
            handleOrderMessage(content, time);
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

function handleOrderMessage(content, time) {
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
            time: time || new Date().toLocaleTimeString('en-US', { hour12: false }),
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
            const cancelLink = order.state === 'PLACED'
                ? `<span class="cancel-link" onclick="showCancelConfirm('${id}', '${order.ticker}')">Cancel</span>`
                : '';
            return `
                <div class="order-entry ${sideClass}">
                    <span class="time" style="margin-right:8px">${order.time}</span>
                    <span style="width:220px;overflow:hidden;text-overflow:ellipsis;display:inline-block">${order.name}</span>
                    <span style="width:55px;display:inline-block" class="ticker-link" onclick="openTickerModal('${order.ticker}')">${order.ticker}</span>
                    <span style="width:70px;display:inline-block;color:${sideClass === 'buy' ? 'var(--accent-success)' : 'var(--accent-danger)'}">${order.side}</span>
                    <span style="width:70px;text-align:right;display:inline-block">${formatNumber(order.price)}</span>
                    <span style="width:40px;text-align:right;display:inline-block">${order.qty}</span>
                    <span style="margin-left:auto;color:var(--text-dim)">${order.state}${cancelLink}</span>
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
        const entries = Array.from(quotes.entries());

        // Sort based on tickerOrder
        entries.sort((a, b) => {
            const tickerA = a[0];
            const tickerB = b[0];
            const indexA = tickerOrder.indexOf(tickerA);
            const indexB = tickerOrder.indexOf(tickerB);

            // Both in list: Sort by index
            if (indexA !== -1 && indexB !== -1) {
                return indexA - indexB;
            }
            // Only A in list: A comes first
            if (indexA !== -1) return -1;
            // Only B in list: B comes first
            if (indexB !== -1) return 1;

            // Neither in list: Sort alphabetically
            return tickerA.localeCompare(tickerB);
        });

        elements.quotesPanel.innerHTML = entries.map(([ticker, quote]) => {
            return `<div class="quote-entry">${formatQuoteColumns(quote.content, quote.time)}</div>`;
        }).join('');
    }

    if (elements.quotesCount) {
        elements.quotesCount.textContent = quotes.size;
    }
}

function formatQuoteColumns(content, time) {
    // Parse quote format: "Name|Ticker|Bid|Last(Vol)|Diff(Rate%)|Ask"
    const parts = content.split('|');
    if (parts.length < 6) {
        return colorizeQuote(content);
    }

    const name = escapeHtml(parts[0]?.trim() || '');
    const ticker = escapeHtml(parts[1]?.trim() || '');
    const bid = parts[2]?.trim() || '';
    const last = parts[3]?.trim() || '';
    const diff = parts[4]?.trim() || '';
    const ask = parts[5]?.trim() || '';

    // Colorize diff
    let diffHtml = escapeHtml(diff);
    if (diff.includes('-')) {
        diffHtml = `<span class="value-down">${escapeHtml(diff)}</span>`;
    } else {
        diffHtml = `<span class="value-up">${escapeHtml(diff)}</span>`;
    }

    // Colorize last
    let lastHtml = `<span class="value-neutral">${escapeHtml(last)}</span>`;

    return `
        <span class="time" style="margin-right:8px">${time}</span>
        <span style="width:220px;overflow:hidden;text-overflow:ellipsis;display:inline-block">${name}</span>
        <span style="width:55px;display:inline-block" class="ticker-link" onclick="openTickerModal('${escapeHtml(ticker)}')">${escapeHtml(ticker)}</span>
        <span style="width:80px;display:inline-block">${escapeHtml(bid)}</span>
        <span style="width:140px;display:inline-block">${lastHtml}</span>
        <span style="width:140px;display:inline-block">${diffHtml}</span>
        <span style="display:inline-block">${escapeHtml(ask)}</span>
    `;
}

function colorizeQuote(content) {
    let result = escapeHtml(content);
    result = result.replace(/Last:([^|]+)/g, 'Last:<span class="value-neutral">$1</span>');
    result = result.replace(/Diff:([^|]*-[^|]+)/g, 'Diff:<span class="value-down">$1</span>');
    result = result.replace(/Diff:([^|]+)/g, 'Diff:<span class="value-up">$1</span>');
    return result;
}

function formatLogContent(message) {
    if (!message.includes('|')) return escapeHtml(message);

    const parts = message.split('|');
    // Common widths based on the column purpose:
    // [Name] | [Ticker] | [Bid] | [Last(Vol)] | [Diff(Rate)] | [Ask]
    return parts.map((part, index) => {
        let width = 'auto';
        let textAlign = 'left';

        if (parts.length >= 6) { // Market data format
            if (index === 0) width = '180px'; // Name
            else if (index === 1) width = '45px';  // Ticker
            else if (index === 2) { width = '85px'; textAlign = 'right'; } // Bid
            else if (index === 3) { width = '130px'; textAlign = 'right'; } // Last(Vol) (Further Increased)
            else if (index === 4) { width = '135px'; textAlign = 'right'; } // Diff(Rate) (Further Increased)
            else if (index === 5) { width = '85px'; textAlign = 'right'; } // Ask
        } else {
            // Generic pipe-delimited (Orders, Sync)
            if (index === 0) width = '100px';
            else if (index === 1) width = '60px';
            else if (index === 2) width = '150px';
            else width = '80px';
        }

        return `<span style="width:${width}; display:inline-block; text-align:${textAlign}; vertical-align:top; margin-right:8px">${escapeHtml(part.trim())}</span>`;
    }).join(''); // Space-based separation for cleaner look
}

function addLog(message, level = 'info', time = null) {
    if (!elements.logPanel) return;

    // Filter MKT logs if toggle is off
    if (level === 'mkt' && !showMktLogs) return;

    const timestamp = time || new Date().toLocaleTimeString('en-US', { hour12: false });
    const entry = document.createElement('div');
    entry.className = `log-entry ${level}`;

    // Apply special formatting only for market data logs
    const formattedContent = (level === 'mkt')
        ? formatLogContent(message)
        : escapeHtml(message);

    entry.innerHTML = `<span class="time">${timestamp}</span>${formattedContent}`;

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

function refreshOrders(isAuto = false) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        orders.clear();
        updateOrdersPanel();
        ws.send('sync_orders');
        if (!isAuto) {
            addLog('Refreshing orders...', 'info');
        }
    } else {
        if (!isAuto) {
            addLog('Cannot refresh: WebSocket not connected', 'warning');
        }
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


// --- Modal & TradingView Logic ---

function openTickerModal(ticker) {
    if (!ticker) return;

    const modal = document.getElementById('ticker-modal');
    if (modal) {
        modal.classList.remove('hidden');
        document.getElementById('modal-title').textContent = ticker;

        loadTradingViewChart(ticker);
        loadHoldingsData(ticker);
    }
}

function closeTickerModal() {
    const modal = document.getElementById('ticker-modal');
    if (modal) {
        modal.classList.add('hidden');
        // Clear chart to stop resource usage?
        // document.getElementById('tv-chart-container').innerHTML = '';
        // Keeping it might be faster if re-opened. Let's leave it.
    }
}

function loadTradingViewChart(ticker) {
    const containerId = 'tv-chart-container';
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = ''; // Clear previous

    // Determine exchange (heuristic)
    let symbol = ticker;
    if (/^\d{6}$/.test(ticker)) {
        // Korean stock usually 6 digits
        symbol = `KRX:${ticker}`;
    } else {
        // For US/Overseas, simply use the ticker. TradingView is smart enough to find the main listing.
        // This solves issues where ETFs are on NYSE Arca (e.g. SOXL) instead of NASDAQ.
        symbol = ticker;
    }

    new TradingView.widget({
        "autosize": true,
        "symbol": symbol,
        "interval": "D",
        "timezone": "Asia/Seoul",
        "theme": "dark",
        "style": "1",
        "locale": "en",
        "enable_publishing": false,
        "allow_symbol_change": true,
        "container_id": containerId,
        "studies": [
            { "id": "MASimple@tv-basicstudies", "inputs": { "length": 5 } },
            { "id": "MASimple@tv-basicstudies", "inputs": { "length": 20 } },
            { "id": "MASimple@tv-basicstudies", "inputs": { "length": 100 } },
            { "id": "MASimple@tv-basicstudies", "inputs": { "length": 125 } },
            { "id": "MASimple@tv-basicstudies", "inputs": { "length": 200 } }
        ]
    });
}

async function loadHoldingsData(ticker) {
    const container = document.getElementById('modal-holdings');
    if (!container) return;

    container.innerHTML = '<div class="loading-holdings">Loading holdings data...</div>';

    try {
        const response = await fetch(`/api/holdings/${ticker}`);
        const data = await response.json();

        if (data.error || !data.found) {
            container.innerHTML = '<div class="empty-state">No holdings found for this asset.</div>';
            return;
        }

        // Build Table Structure
        let html = `
            <table class="holdings-table">
                <thead>
                    <tr>
                        <th>Account</th>
                        <th>Total Value</th>
                        <th>Avg Price</th>
                        <th>Quantity</th>
                        <th>P/L</th>
                    </tr>
                </thead>
                <tbody>
        `;

        // 1. Summary Row
        const pnlColor = data.pnl >= 0 ? 'var(--accent-success)' : 'var(--accent-danger)';
        html += `
            <tr class="summary-row">
                <td>Total</td>
                <td>${formatPrice(data.total_val, data.currency)}</td>
                <td>${formatPrice(data.avg_price, data.currency)}</td>
                <td>${data.qty}</td>
                <td><span style="color:${pnlColor}">${formatPrice(data.pnl, data.currency)} (${data.pnl_rate.toFixed(2)}%)</span></td>
            </tr>
        `;

        // 2. Account Rows
        if (data.accounts && data.accounts.length > 0) {
            data.accounts.forEach(acc => {
                const qty = acc.qty || 0;
                const avg = acc.avg_price || 0;
                const cur = data.cur_price || 0; // Use aggregate current price

                const val = qty * cur;
                const invest = qty * avg;
                const pnl = val - invest;
                const pnlRate = invest > 0 ? (pnl / invest * 100) : 0;
                const accPnlColor = pnl >= 0 ? 'var(--accent-success)' : 'var(--accent-danger)';

                html += `
                    <tr>
                        <td>${acc.account_name || acc.account_id || 'Unknown'}</td>
                        <td>${formatPrice(val, data.currency)}</td>
                        <td>${formatPrice(avg, data.currency)}</td>
                        <td>${qty}</td>
                        <td><span style="color:${accPnlColor}">${formatPrice(pnl, data.currency)} (${pnlRate.toFixed(2)}%)</span></td>
                    </tr>
                `;
            });
        }

        html += `
                </tbody>
            </table>
        `;

        container.innerHTML = html;

    } catch (e) {
        container.innerHTML = `<div class="log-entry error">Error loading data: ${e.message}</div>`;
    }
}

function createCard(label, value) {
    return `
        <div class="holding-card">
            <span class="label">${label}</span>
            <span class="value">${value}</span>
        </div>
    `;
}

function formatPrice(val, currency) {
    // Simple formatter, can be improved based on currency properties
    if (typeof val !== 'number') return val;
    return val.toLocaleString('en-US', {
        style: 'currency',
        currency: currency || 'USD',
        minimumFractionDigits: 2
    });
}

// --- Cancel Order Modal Logic ---

function showCancelConfirm(orderId, ticker) {
    pendingCancelOrderId = orderId;
    pendingCancelTicker = ticker;

    const modal = document.getElementById('cancel-confirm-modal');
    const tickerSpan = document.getElementById('cancel-ticker');

    if (tickerSpan) tickerSpan.textContent = ticker;
    if (modal) modal.classList.remove('hidden');
}

function closeCancelModal() {
    pendingCancelOrderId = null;
    pendingCancelTicker = null;

    const modal = document.getElementById('cancel-confirm-modal');
    if (modal) modal.classList.add('hidden');
}

async function confirmCancel() {
    if (!pendingCancelOrderId) {
        closeCancelModal();
        return;
    }

    const orderId = pendingCancelOrderId;
    const ticker = pendingCancelTicker;
    closeCancelModal();

    addLog(`Cancelling order for ${ticker}...`, 'info');

    try {
        const response = await fetch(`/api/orders/${orderId}/cancel`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const result = await response.json();

        if (result.success) {
            addLog(`Order cancelled: ${ticker}`, 'success');
            // Remove from local orders map
            orders.delete(orderId);
            updateOrdersPanel();
        } else {
            addLog(`Cancel failed: ${result.error || 'Unknown error'}`, 'error');
        }
    } catch (e) {
        addLog(`Cancel error: ${e.message}`, 'error');
    }
}

// Close modal on outside click
document.addEventListener('click', (e) => {
    const tickerModal = document.getElementById('ticker-modal');
    const cancelModal = document.getElementById('cancel-confirm-modal');

    if (e.target === tickerModal) {
        closeTickerModal();
    }
    if (e.target === cancelModal) {
        closeCancelModal();
    }
});


// --- Memo Logic ---

async function fetchMemos() {
    if (!elements.memosPanel) return;
    elements.memosPanel.innerHTML = '<div class="empty-state">Loading...</div>';

    try {
        const response = await fetch('/api/memos');
        const data = await response.json();
        renderMemos(data);
    } catch (e) {
        elements.memosPanel.innerHTML = `<div class="log-entry error">Error: ${e.message}</div>`;
    }
}

function renderMemos(data) {
    if (!elements.memosPanel) return;

    if (!data || Object.keys(data).length === 0) {
        elements.memosPanel.innerHTML = '<div class="empty-state">No memos found.</div>';
        return;
    }

    let html = '';
    // Sort dates descending (newest first)
    const dates = Object.keys(data).sort().reverse();

    dates.forEach(date => {
        html += `<div class="memo-date-group">
            <div class="memo-date-header">${date}</div>`;

        const msgs = data[date];
        // Reverse messages to show newest first? Or keep chronological?
        // Usually chronological within a day is better for chat logs, but for memos maybe newest first?
        // Let's keep original order (chronological) as per user request "date order" (implicit)
        // actually user said "날짜순으로 표시하고" which usually means sorted by date.

        msgs.forEach((msg, index) => {
            // format: "HH:MM:SS : message text"
            // We need to be careful with splitting if the text contains " : "
            const firstColon = msg.indexOf(' : ');
            let time = '';
            let text = msg;

            if (firstColon !== -1) {
                time = msg.substring(0, firstColon);
                text = msg.substring(firstColon + 3);
            }

            // Truncate logic
            const maxLen = 60;
            let displayHeader = text;
            let isTruncated = false;

            if (text.length > maxLen) {
                displayHeader = text.substring(0, maxLen) + '...';
                isTruncated = true;
            }

            const safeTime = escapeHtml(time);
            const safeText = escapeHtml(text).replace(/\n/g, '<br>');
            const safeHeader = escapeHtml(displayHeader);

            // Use encodeURIComponent for safe passing to functions, replacing single quotes
            const encodedText = encodeURIComponent(msg).replace(/'/g, "%27");
            const entryId = `memo-${date.replace(/-/g, '')}-${index}`;

            // Click action: Copy to clipboard
            const clickAttr = `onclick="copyMemoToClipboard('${encodedText}')"`;
            const cursorClass = 'clickable';

            // Toggle Button
            const toggleBtn = isTruncated
                ? `<button class="memo-toggle-btn" onclick="toggleMemo('${entryId}', '${encodedText}', '${safeHeader.replace(/'/g, "\\'")}')">🔽</button>`
                : '';

            html += `
                <div class="memo-entry" id="${entryId}">
                    <span class="memo-time">${safeTime}</span>
                    <span class="memo-text ${cursorClass}" ${clickAttr} title="Click to copy">
                        ${safeHeader}
                    </span>
                    <div class="memo-actions">
                        ${toggleBtn}
                        <button class="memo-delete-btn" onclick="deleteMemo('${date}', '${encodedText}')" title="Delete">🗑️</button>
                    </div>
                </div>`;
        });

        html += `</div>`;
    });

    elements.memosPanel.innerHTML = html;
}

function toggleMemo(elementId, encodedText, shortHeader) {
    const entry = document.getElementById(elementId);
    if (!entry) return;

    const textSpan = entry.querySelector('.memo-text');
    const toggleBtn = entry.querySelector('.memo-toggle-btn');

    const isExpanded = entry.classList.contains('expanded');
    // Actually msg includes timestamp. Let's start clean.

    // We need just the text part.
    // The encodedText passed to toggleMemo is the FULL msg (Time : Text).
    // But we usually want to toggle the TEXT part.
    // In render loop, we extracted `text`. We should pass THAT or re-extract.
    // Simpler: Just toggle CSS class and use data attribute?
    // Or swap content.

    if (isExpanded) {
        // Collapse
        textSpan.innerHTML = shortHeader; // Revert to truncated
        entry.classList.remove('expanded');
        toggleBtn.textContent = '🔽';
    } else {
        // Expand
        // We need the full text without timestamp
        const fullMsg = decodeURIComponent(encodedText);
        const firstColon = fullMsg.indexOf(' : ');
        let content = fullMsg;
        if (firstColon !== -1) content = fullMsg.substring(firstColon + 3);

        textSpan.innerHTML = escapeHtml(content).replace(/\n/g, '<br>');
        entry.classList.add('expanded');
        toggleBtn.textContent = '🔼';
    }
}

async function copyMemoToClipboard(encodedText) {
    const text = decodeURIComponent(encodedText);
    try {
        await navigator.clipboard.writeText(text);
        addLog('✅ Memo copied to clipboard', 'success');
    } catch (err) {
        // Fallback for non-secure contexts
        const textArea = document.createElement("textarea");
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.select();
        try {
            document.execCommand('copy');
            addLog('✅ Memo copied to clipboard', 'success');
        } catch (err2) {
            addLog(`❌ Failed to copy: ${err}`, 'error');
        }
        document.body.removeChild(textArea);
    }
}

async function deleteMemo(date, encodedText) {
    if (!confirm('Delete this memo?')) return;

    const text = decodeURIComponent(encodedText);

    try {
        const response = await fetch('/api/memos/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ date, text })
        });
        const result = await response.json();
        if (result.success) {
            fetchMemos(); // Refresh list
        } else {
            alert('Failed to delete: ' + (result.error || 'Unknown error'));
        }
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

