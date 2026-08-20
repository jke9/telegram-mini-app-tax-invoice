/* ═══════════════════════════════════════════════════════
   JKE Tax Invoice Generator — Telegram Mini App Logic
   ═══════════════════════════════════════════════════════ */

const getApiUrl = () => {
    const host = window.location.hostname;
    if (!host || host === 'localhost' || host === '127.0.0.1') {
        return 'http://localhost:8031';
    }
    // On Vercel or remote host, use relative path (/api/...)
    return '';
};
const API = getApiUrl();
const tg = window.Telegram?.WebApp;

// ─── State ────────────────────────────────────────────────────────────────────
let currentStep = 1;
const TOTAL_STEPS = 5;
let amountMode = 'taxable';
let previewDebounce = null;
let lastPreviewData = null;

// Document Type State ('tax_invoice' or 'proforma_invoice')
let currentDocType = localStorage.getItem('jke_doc_type') || 'tax_invoice';

const state = {
    contractor: '',
    customer: '',
    project: '',
    inv_no: '',
    inv_date: '',
    amount: 0,
    amount_mode: 'taxable',
    include_stamp: true,
    doc_type: currentDocType,
    custom_round_off: null,
    is_manual_round_off: false
};

// Master data cache
let contractorList = [];
let customerList = [];
let projectList = [];

// 🔒 Passcode Configuration (Default Passcode: 0101)
const REQUIRED_PASSCODE = '0101';
let currentPin = '';
let generatedPdfData = null;

// ─── Document Type Selector Logic ─────────────────────────────────────────────
function getDocTypeInfo(type = currentDocType) {
    const isProforma = type === 'proforma_invoice' || type === 'proforma';
    return {
        type: isProforma ? 'proforma_invoice' : 'tax_invoice',
        title: isProforma ? 'Proforma Invoice' : 'Tax Invoice',
        icon: isProforma ? '📋' : '🧾',
        badge: isProforma ? 'Proforma' : 'Tax',
        fileSuffix: isProforma ? 'Proforma_Invoice' : 'Tax_Invoice',
        desc: isProforma ? 'Preliminary estimated bill' : 'Final GST compliant invoice',
        btnText: isProforma ? 'Generate Proforma Invoice PDF' : 'Generate Tax Invoice PDF'
    };
}

function toggleDocTypeDropdown(e) {
    if (e) e.stopPropagation();
    const dropdown = document.getElementById('invoice-type-dropdown');
    const btn = document.getElementById('btn-doc-type-selector');
    if (!dropdown || !btn) return;

    const isHidden = dropdown.classList.contains('hidden');
    if (isHidden) {
        dropdown.classList.remove('hidden');
        btn.classList.add('active-open');
        btn.setAttribute('aria-expanded', 'true');
        if (tg) tg.HapticFeedback?.impactOccurred('light');
    } else {
        closeDocTypeDropdown();
    }
}

function closeDocTypeDropdown() {
    const dropdown = document.getElementById('invoice-type-dropdown');
    const btn = document.getElementById('btn-doc-type-selector');
    if (dropdown) dropdown.classList.add('hidden');
    if (btn) {
        btn.classList.remove('active-open');
        btn.setAttribute('aria-expanded', 'false');
    }
}

function selectDocType(type) {
    currentDocType = (type === 'proforma_invoice' || type === 'proforma') ? 'proforma_invoice' : 'tax_invoice';
    state.doc_type = currentDocType;
    localStorage.setItem('jke_doc_type', currentDocType);
    closeDocTypeDropdown();
    updateDocTypeUI();
    if (tg) tg.HapticFeedback?.notificationOccurred('success');
}

function updateDocTypeUI() {
    const info = getDocTypeInfo(currentDocType);

    // Header title & icon
    const titleEl = document.getElementById('header-doc-title');
    if (titleEl) titleEl.textContent = info.title;

    const iconEl = document.getElementById('header-type-icon');
    if (iconEl) iconEl.textContent = info.icon;

    // Dropdown selection states
    const taxItem = document.getElementById('type-opt-tax');
    const proformaItem = document.getElementById('type-opt-proforma');
    const checkTax = document.getElementById('check-tax');
    const checkProforma = document.getElementById('check-proforma');

    if (currentDocType === 'proforma_invoice') {
        taxItem?.classList.remove('active');
        proformaItem?.classList.add('active');
        if (checkTax) checkTax.style.display = 'none';
        if (checkProforma) checkProforma.style.display = 'inline';
    } else {
        taxItem?.classList.add('active');
        proformaItem?.classList.remove('active');
        if (checkTax) checkTax.style.display = 'inline';
        if (checkProforma) checkProforma.style.display = 'none';
    }

    // Update Action Button in Step 5 (if not currently generating)
    const btnGenText = document.getElementById('btn-gen-text');
    if (btnGenText && !btnGenText.textContent.includes('Generating') && !btnGenText.textContent.includes('Closing') && !btnGenText.textContent.includes('Sent')) {
        btnGenText.textContent = info.btnText;
    }

    // Update page title
    document.title = `${info.title} Generator`;
}

// Close dropdown when clicking anywhere outside
document.addEventListener('click', (e) => {
    const wrapper = document.querySelector('.header-type-wrapper');
    if (wrapper && !wrapper.contains(e.target)) {
        closeDocTypeDropdown();
    }
});

// ─── Passcode Lock Logic ──────────────────────────────────────────────────────
function checkPasscodeOnStart() {
    const isUnlocked = localStorage.getItem('jke_passcode_unlocked') === REQUIRED_PASSCODE;
    const passcodeOverlay = document.getElementById('passcode-screen');
    if (isUnlocked && passcodeOverlay) {
        passcodeOverlay.classList.add('hidden');
    } else if (passcodeOverlay) {
        passcodeOverlay.classList.remove('hidden');
    }
}

function pressPin(num) {
    if (currentPin.length < 4) {
        currentPin += num;
        updatePinDots();
        if (tg) tg.HapticFeedback.impactOccurred('light');
        if (currentPin.length === 4) {
            setTimeout(verifyPin, 150);
        }
    }
}

function clearPin() {
    currentPin = '';
    updatePinDots();
    document.getElementById('passcode-error')?.classList.add('hidden');
    if (tg) tg.HapticFeedback.impactOccurred('medium');
}

function backspacePin() {
    if (currentPin.length > 0) {
        currentPin = currentPin.slice(0, -1);
        updatePinDots();
        document.getElementById('passcode-error')?.classList.add('hidden');
        if (tg) tg.HapticFeedback.impactOccurred('light');
    }
}

function updatePinDots() {
    for (let i = 1; i <= 4; i++) {
        const dot = document.getElementById(`pdot-${i}`);
        if (dot) {
            if (i <= currentPin.length) dot.classList.add('filled');
            else dot.classList.remove('filled');
        }
    }
}

function verifyPin() {
    if (currentPin === REQUIRED_PASSCODE) {
        localStorage.setItem('jke_passcode_unlocked', REQUIRED_PASSCODE);
        document.getElementById('passcode-screen')?.classList.add('hidden');
        document.getElementById('passcode-error')?.classList.add('hidden');
        if (tg) tg.HapticFeedback.notificationOccurred('success');
    } else {
        document.getElementById('passcode-error')?.classList.remove('hidden');
        if (tg) tg.HapticFeedback.notificationOccurred('error');
        currentPin = '';
        updatePinDots();
    }
}

function lockApp() {
    localStorage.removeItem('jke_passcode_unlocked');
    currentPin = '';
    updatePinDots();
    document.getElementById('passcode-error')?.classList.add('hidden');
    document.getElementById('passcode-screen')?.classList.remove('hidden');
    if (tg) tg.HapticFeedback.notificationOccurred('warning');
}

// ─── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    // Check Security Passcode Lock Screen
    checkPasscodeOnStart();

    if (tg) {
        tg.ready();
        tg.expand();
        tg.MainButton.hide(); // Hide native MainButton to prevent overlap with bottom navigation bar
        tg.BackButton.onClick(handleBackButton);
    }

    // Initialize Document Type UI (Tax vs Proforma)
    updateDocTypeUI();

    // Set today's date as default
    const today = new Date();
    const dd = String(today.getDate()).padStart(2, '0');
    const mm = String(today.getMonth() + 1).padStart(2, '0');
    const yyyy = today.getFullYear();
    document.getElementById('inv-date').value = `${dd}/${mm}/${yyyy}`;

    // Load all dropdown data
    await loadDropdowns();

    // Attach stamp toggle listener
    document.getElementById('stamp-toggle').addEventListener('change', function() {
        const on = this.checked;
        document.getElementById('stamp-toggle-label').textContent = on ? 'Include Stamp & Sign' : 'Without Stamp & Sign';
        document.getElementById('stamp-toggle-sub').textContent = on
            ? 'Official stamp will appear on invoice'
            : 'Clean invoice without stamp';
        state.include_stamp = on;
    });

    // Amount input: live preview on change
    document.getElementById('bill-amount').addEventListener('input', () => {
        // When amount changes, reset manual flag so auto-roundoff recalculates
        if (state.is_manual_round_off) {
            state.is_manual_round_off = false;
            state.custom_round_off = null;
        }
        clearTimeout(previewDebounce);
        previewDebounce = setTimeout(fetchPreview, 400);
    });

    // Round-off editable input: live update
    const roInput = document.getElementById('pv-roundoff-input');
    if (roInput) {
        roInput.addEventListener('input', onRoundOffInput);
    }

    // Update step UI
    updateStepUI();
});

// ─── Load Dropdowns ───────────────────────────────────────────────────────────
async function loadDropdowns() {
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 2500);

        const [cRes, custRes, projRes] = await Promise.all([
            fetch(`${API}/api/contractors`, { signal: controller.signal }),
            fetch(`${API}/api/customers`, { signal: controller.signal }),
            fetch(`${API}/api/projects`, { signal: controller.signal })
        ]);
        clearTimeout(timeoutId);

        if (!cRes.ok || !custRes.ok || !projRes.ok) throw new Error('API response not ok');

        contractorList = await cRes.json();
        customerList = await custRes.json();
        projectList = await projRes.json();
    } catch (e) {
        // Fallback static data if API not running or timing out
        contractorList = ['Shivam Builders', 'Jay Khodiyar Enterprise', 'Jay Varudi', 'JNP INFRASTRUCTURE', 'YOGI CONSTRUCTION CO.', 'Sarthi Construction'];
        customerList = ['Ahmedabad Municipal Corporation', 'GUDC', 'GWSSB', 'Anjar Nagarpalika', 'GUDA'];
        projectList = [
            { key: 'AMC ASARWA 4', label: 'AMC ASARWA 4' },
            { key: 'AMC ASARWA 3', label: 'AMC ASARWA 3' },
            { key: 'AMC  Kali Lake', label: 'AMC Kali Lake' },
            { key: 'GUDC Zalod', label: 'GUDC Zalod' },
            { key: 'GWSSSB Zalod', label: 'GWSSSB Zalod' },
            { key: 'ANJAR', label: 'ANJAR' },
            { key: 'AMC Vatva', label: 'AMC Vatva' },
            { key: 'AMC Sardarnagar', label: 'AMC Sardarnagar' },
            { key: 'AMC Science City', label: 'AMC Science City' },
            { key: 'GUDC Kheda', label: 'GUDC Kheda' },
            { key: 'GUDC Mahemdabad', label: 'GUDC Mahemdabad' },
            { key: 'AMC Muthiya', label: 'AMC Muthiya' },
            { key: 'AMC Chiloda', label: 'AMC Chiloda' },
            { key: 'AMC ARC', label: 'AMC ARC' },
            { key: 'AMC Partheshwer', label: 'AMC Partheshwer' },
            { key: 'AMC Piplaj', label: 'AMC Piplaj' },
        ];
        log('API server not detected — using cached data', 'warn');
    }

    // Populate contractor select
    const cSel = document.getElementById('sel-contractor');
    cSel.innerHTML = contractorList.map(n => `<option value="${n}">${n}</option>`).join('');
    cSel.addEventListener('change', onContractorChange);

    // Populate customer select
    const custSel = document.getElementById('sel-customer');
    custSel.innerHTML = customerList.map(n => `<option value="${n}">${n}</option>`).join('');
    custSel.addEventListener('change', onCustomerChange);

    // Populate project select
    const projSel = document.getElementById('sel-project');
    projSel.addEventListener('change', onProjectChange);

    // Initial cascade trigger
    onContractorChange();
}

// ─── Contractor / Customer / Project Cascading Rules ───────────────────────────
const CONTRACTOR_MAP = {
    'Shivam Builders': {
        defaultCustomer: 'Ahmedabad Municipal Corporation',
        allowedPrefixes: ['AMC', 'GUDC', 'GWSSSB', 'GWSSB'],
        allowedProjects: ['AMC ASARWA 3', 'AMC ASARWA 4', 'AMC  Kali Lake', 'AMC Kali Lake', 'GUDC Zalod', 'GWSSSB Zalod', 'GWSSB Zalod']
    },
    'YOGI CONSTRUCTION CO.': {
        defaultCustomer: 'Ahmedabad Municipal Corporation',
        allowedPrefixes: ['AMC', 'ANJAR'],
        allowedProjects: ['ANJAR', 'AMC Vatva', 'AMC Sardarnagar', 'AMC Science City']
    },
    'Jay Varudi': {
        defaultCustomer: 'GUDC',
        allowedPrefixes: ['GUDC'],
        allowedProjects: ['GUDC Kheda', 'GUDC Mahemdabad']
    },
    'JNP INFRASTRUCTURE': {
        defaultCustomer: 'Ahmedabad Municipal Corporation',
        allowedPrefixes: ['AMC'],
        allowedProjects: ['AMC Muthiya', 'AMC Chiloda']
    },
    'Jay Khodiyar Enterprise': {
        defaultCustomer: 'Ahmedabad Municipal Corporation',
        allowedPrefixes: ['AMC'],
        allowedProjects: ['AMC ARC', 'AMC Partheshwer']
    },
    'Sarthi Construction': {
        defaultCustomer: 'Ahmedabad Municipal Corporation',
        allowedPrefixes: ['AMC'],
        allowedProjects: ['AMC Piplaj']
    }
};

const CUSTOMER_PREFIX_MAP = {
    'Ahmedabad Municipal Corporation': ['AMC'],
    'GUDC': ['GUDC'],
    'GWSSB': ['GWSSSB', 'GWSSB'],
    'Anjar Nagarpalika': ['ANJAR'],
    'GUDA': ['ANJAR', 'GUDA']
};

function getCustomerForProject(projKey) {
    if (!projKey) return null;
    if (projKey.startsWith('AMC')) return 'Ahmedabad Municipal Corporation';
    if (projKey.startsWith('GUDC')) return 'GUDC';
    if (projKey.startsWith('GWSSSB') || projKey.startsWith('GWSSB')) return 'GWSSB';
    if (projKey === 'ANJAR') return 'Anjar Nagarpalika';
    return null;
}

function updateFilteredProjects() {
    const contractorName = document.getElementById('sel-contractor').value;
    const customerName = document.getElementById('sel-customer').value;
    const projSel = document.getElementById('sel-project');
    const currProj = projSel.value;

    const cRule = CONTRACTOR_MAP[contractorName] || { allowedPrefixes: [], allowedProjects: [] };
    const custPrefixes = CUSTOMER_PREFIX_MAP[customerName] || [];

    const filtered = projectList.filter(p => {
        if (cRule.allowedProjects && cRule.allowedProjects.length > 0) {
            if (!cRule.allowedProjects.includes(p.key)) return false;
        }
        if (cRule.allowedPrefixes && cRule.allowedPrefixes.length > 0) {
            const matchesPrefix = cRule.allowedPrefixes.some(px => p.key.startsWith(px));
            if (!matchesPrefix) return false;
        }
        if (custPrefixes.length > 0) {
            const matchesCustPrefix = custPrefixes.some(px => p.key.startsWith(px));
            if (!matchesCustPrefix) return false;
        }
        return true;
    });

    projSel.innerHTML = filtered.map(p => `<option value="${p.key}">${p.label}</option>`).join('');

    if (filtered.some(p => p.key === currProj)) {
        projSel.value = currProj;
    } else if (filtered.length > 0) {
        projSel.value = filtered[0].key;
    }
}

function onContractorChange() {
    const contractorName = document.getElementById('sel-contractor').value;
    updateContractorPreview();

    const cRule = CONTRACTOR_MAP[contractorName];
    if (cRule && cRule.defaultCustomer) {
        const custSel = document.getElementById('sel-customer');
        if ([...custSel.options].some(opt => opt.value === cRule.defaultCustomer)) {
            custSel.value = cRule.defaultCustomer;
        }
    }

    updateFilteredProjects();
    clearTimeout(previewDebounce);
    previewDebounce = setTimeout(fetchPreview, 200);
}

function onCustomerChange() {
    updateFilteredProjects();
    clearTimeout(previewDebounce);
    previewDebounce = setTimeout(fetchPreview, 200);
}

function onProjectChange() {
    const projKey = document.getElementById('sel-project').value;
    const matchedCust = getCustomerForProject(projKey);
    if (matchedCust) {
        const custSel = document.getElementById('sel-customer');
        if ([...custSel.options].some(opt => opt.value === matchedCust)) {
            custSel.value = matchedCust;
        }
    }
    clearTimeout(previewDebounce);
    previewDebounce = setTimeout(fetchPreview, 200);
}

// ─── Contractor Preview ───────────────────────────────────────────────────────
const CONTRACTOR_META = {
    'Shivam Builders':        { gstin: '24ABDFS4611H1ZG', bank: 'ICICI BANK — MAKARBA' },
    'Jay Khodiyar Enterprise':{ gstin: '24BJHPP5061K1ZZ', bank: 'ICICI BANK — BAPUNAGAR' },
    'Jay Varudi':             { gstin: '24AAECJ3981C1ZR', bank: '—' },
    'JNP INFRASTRUCTURE':     { gstin: '24AADFJ3113C1Z6', bank: 'DCB BANK — SURAT' },
    'YOGI CONSTRUCTION CO.':  { gstin: '24AAAFY3044N1Z1', bank: 'PNB — Gandhinagar' },
    'Sarthi Construction':    { gstin: '24ALRPG2118D1ZI', bank: 'Bank of India — BAPUNAGAR' },
};

function updateContractorPreview() {
    const name = document.getElementById('sel-contractor').value;
    const meta = CONTRACTOR_META[name];
    const prev = document.getElementById('contractor-preview');
    if (meta && name) {
        document.getElementById('prev-c-gstin').textContent = meta.gstin;
        document.getElementById('prev-c-bank').textContent = meta.bank;
        prev.classList.remove('hidden');
    } else {
        prev.classList.add('hidden');
    }
}

// ─── Mode Toggle ─────────────────────────────────────────────────────────────
function setMode(mode) {
    amountMode = mode;
    state.amount_mode = mode;
    state.is_manual_round_off = false;
    state.custom_round_off = null;
    document.getElementById('mode-taxable').classList.toggle('active', mode === 'taxable');
    document.getElementById('mode-total').classList.toggle('active', mode === 'total');
    const hint = document.getElementById('amount-type-hint');
    if (hint) hint.textContent = mode === 'taxable'
        ? 'GST (18%) will be added on top of this amount'
        : 'GST (18%) is already included in this amount';
    if (tg) tg.HapticFeedback?.selectionChanged();
    // Re-trigger preview
    clearTimeout(previewDebounce);
    previewDebounce = setTimeout(fetchPreview, 300);
}

// ─── Live Tax Preview ─────────────────────────────────────────────────────────
async function fetchPreview() {
    const amtVal = parseFloat(document.getElementById('bill-amount').value);
    if (!amtVal || amtVal <= 0) {
        document.getElementById('tax-preview').style.display = 'none';
        return;
    }

    const payload = {
        amount: amtVal,
        amount_mode: amountMode,
        custom_round_off: state.is_manual_round_off ? state.custom_round_off : null
    };

    try {
        const res = await fetch(`${API}/api/preview`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        lastPreviewData = data;

        document.getElementById('pv-taxable').textContent = `₹ ${data.taxable}`;
        document.getElementById('pv-cgst').textContent = `₹ ${data.cgst}`;
        document.getElementById('pv-sgst').textContent = `₹ ${data.sgst}`;
        const stEl = document.getElementById('pv-subtotal');
        if (stEl) stEl.textContent = `₹ ${data.subtotal}`;
        document.getElementById('pv-grand').textContent = `₹ ${data.grand_total}`;

        const roundRow = document.getElementById('pv-roundoff-row');
        const roInput = document.getElementById('pv-roundoff-input');
        const badge = document.getElementById('ro-mode-badge');
        const resetBtn = document.getElementById('btn-ro-reset');

        if (roundRow) roundRow.style.display = 'flex';

        if (roInput) {
            if (!state.is_manual_round_off) {
                roInput.value = data.round_off || '+0.00';
                roInput.classList.remove('is-custom');
                if (badge) {
                    badge.textContent = 'AUTO';
                    badge.className = 'ro-badge ro-badge-auto';
                }
                if (resetBtn) resetBtn.style.display = 'none';
            } else {
                roInput.classList.add('is-custom');
                if (badge) {
                    badge.textContent = 'EDITED';
                    badge.className = 'ro-badge ro-badge-edit';
                }
                if (resetBtn) resetBtn.style.display = 'inline-flex';
            }
        }

        document.getElementById('tax-preview').style.display = 'block';
    } catch (e) {
        // Fallback local calculation if API offline
        const taxable = amountMode === 'total' ? Math.round(amtVal) / 1.18 : amtVal;
        const cgst = Math.round(taxable * 0.09 * 100) / 100;
        const sgst = cgst;
        const subtotal = taxable + cgst + sgst;
        let grand = Math.round(subtotal);
        let ro = Math.round((grand - subtotal) * 100) / 100;

        if (state.is_manual_round_off && state.custom_round_off !== null) {
            ro = state.custom_round_off;
            grand = Math.round((subtotal + ro) * 100) / 100;
        }

        document.getElementById('pv-taxable').textContent = `₹ ${fmt(taxable)}`;
        document.getElementById('pv-cgst').textContent = `₹ ${fmt(cgst)}`;
        document.getElementById('pv-sgst').textContent = `₹ ${fmt(sgst)}`;
        const stEl2 = document.getElementById('pv-subtotal');
        if (stEl2) stEl2.textContent = `₹ ${fmt(subtotal)}`;
        document.getElementById('pv-grand').textContent = `₹ ${fmt(grand)}`;

        lastPreviewData = {
            taxable_raw: taxable,
            cgst_raw: cgst,
            sgst_raw: sgst,
            subtotal_raw: subtotal,
            grand_total: fmt(grand),
            grand_total_raw: grand,
            round_off: `${ro >= 0 ? '+' : ''}${ro.toFixed(2)}`,
            round_off_raw: ro
        };

        const roundRow = document.getElementById('pv-roundoff-row');
        const roInput = document.getElementById('pv-roundoff-input');
        const badge = document.getElementById('ro-mode-badge');
        const resetBtn = document.getElementById('btn-ro-reset');

        if (roundRow) roundRow.style.display = 'flex';
        if (roInput) {
            if (!state.is_manual_round_off) {
                roInput.value = `${ro >= 0 ? '+' : ''}${ro.toFixed(2)}`;
                roInput.classList.remove('is-custom');
                if (badge) {
                    badge.textContent = 'AUTO';
                    badge.className = 'ro-badge ro-badge-auto';
                }
                if (resetBtn) resetBtn.style.display = 'none';
            } else {
                roInput.classList.add('is-custom');
                if (badge) {
                    badge.textContent = 'EDITED';
                    badge.className = 'ro-badge ro-badge-edit';
                }
                if (resetBtn) resetBtn.style.display = 'inline-flex';
            }
        }
        document.getElementById('tax-preview').style.display = 'block';
    }
}

// ─── Live Edit Handler for Round Off Input ───────────────────────────────────
function onRoundOffInput(e) {
    const rawVal = e.target.value;
    const badge = document.getElementById('ro-mode-badge');
    const resetBtn = document.getElementById('btn-ro-reset');

    if (rawVal.trim() === '' || isNaN(parseFloat(rawVal))) {
        return;
    }

    const customRo = parseFloat(rawVal);
    state.is_manual_round_off = true;
    state.custom_round_off = customRo;

    if (badge) {
        badge.textContent = 'EDITED';
        badge.className = 'ro-badge ro-badge-edit';
    }
    if (resetBtn) resetBtn.style.display = 'inline-flex';
    e.target.classList.add('is-custom');

    // Real-time local recalculation of Grand Total
    if (lastPreviewData) {
        const taxableRaw = parseFloat(lastPreviewData.taxable_raw || 0);
        const cgstRaw = parseFloat(lastPreviewData.cgst_raw || 0);
        const sgstRaw = parseFloat(lastPreviewData.sgst_raw || 0);
        const subtotalRaw = taxableRaw + cgstRaw + sgstRaw;
        const newGrand = Math.round((subtotalRaw + customRo) * 100) / 100;

        document.getElementById('pv-grand').textContent = `₹ ${fmt(newGrand)}`;
        lastPreviewData.grand_total = fmt(newGrand);
        lastPreviewData.grand_total_raw = newGrand;
        lastPreviewData.round_off = `${customRo >= 0 ? '+' : ''}${customRo.toFixed(2)}`;
        lastPreviewData.round_off_raw = customRo;
    }
}

function resetRoundOffToAuto() {
    state.is_manual_round_off = false;
    state.custom_round_off = null;
    if (tg) tg.HapticFeedback?.selectionChanged();
    fetchPreview();
}

// ─── Local Indian Number Formatter (fallback) ────────────────────────────────
function fmt(val) {
    const fval = Math.abs(parseFloat(val) || 0);
    const isNeg = parseFloat(val) < 0;
    const s = fval.toFixed(2);
    const [intPart, decPart] = s.split('.');
    let res;
    if (intPart.length <= 3) {
        res = intPart;
    } else {
        const last3 = intPart.slice(-3);
        let rest = intPart.slice(0, -3);
        const groups = [];
        while (rest.length > 2) {
            groups.unshift(rest.slice(-2));
            rest = rest.slice(0, -2);
        }
        if (rest) groups.unshift(rest);
        res = groups.join(',') + ',' + last3;
    }
    return (isNeg ? '-' : '') + res + '.' + decPart;
}

// ─── Step Navigation ──────────────────────────────────────────────────────────
function handleMainButton() {
    if (currentStep < TOTAL_STEPS) {
        if (!validateStep(currentStep)) return;
        goToStep(currentStep + 1);
    } else {
        generateInvoice();
    }
}

function handleBackButton() {
    if (currentStep > 1) {
        goToStep(currentStep - 1);
    }
}

function goToStep(step) {
    // Hide current step
    const currCard = document.getElementById(`step-${currentStep}`);
    if (currCard) {
        currCard.classList.remove('active');
        currCard.style.display = 'none';
    }

    // Update dot states
    const prevDot = document.getElementById(`dot-${currentStep}`);
    if (prevDot) { prevDot.classList.remove('active'); prevDot.classList.add('done'); }

    currentStep = step;

    // Show new step
    const card = document.getElementById(`step-${step}`);
    if (card) { card.style.display = 'block'; card.classList.add('active'); }

    // Activate new dot
    const newDot = document.getElementById(`dot-${step}`);
    if (newDot) { newDot.classList.remove('done'); newDot.classList.add('active'); }

    // Scroll to top instantly for smooth page transition
    window.scrollTo(0, 0);
    document.body.scrollTop = 0;
    document.documentElement.scrollTop = 0;

    updateStepUI();

    if (tg) tg.HapticFeedback.impactOccurred('light');
}

function updateStepUI() {
    // Progress bar (element may not exist if removed)
    const pf = document.getElementById('progress-fill');
    if (pf) pf.style.width = `${(currentStep / TOTAL_STEPS) * 100}%`;

    // Step badge
    const badge = document.getElementById('step-badge');
    if (badge) badge.textContent = `Step ${currentStep} / ${TOTAL_STEPS}`;

    // Telegram back button
    if (tg) {
        if (currentStep > 1) tg.BackButton.show();
        else tg.BackButton.hide();
        tg.MainButton.hide();
    }

    // On Step 5: populate summary
    if (currentStep === TOTAL_STEPS) {
        populateSummary();
    }
}

// ─── Validation ───────────────────────────────────────────────────────────────
function validateStep(step) {
    hideError();
    if (step === 1) {
        state.contractor = document.getElementById('sel-contractor').value;
        if (!state.contractor) { showError('Please select a contractor.'); return false; }
    }
    if (step === 2) {
        state.customer = document.getElementById('sel-customer').value;
        state.project = document.getElementById('sel-project').value;
        if (!state.customer) { showError('Please select a customer.'); return false; }
        if (!state.project) { showError('Please select a project.'); return false; }
    }
    if (step === 3) {
        state.inv_no = document.getElementById('inv-no').value.trim();
        state.inv_date = document.getElementById('inv-date').value.trim();
        if (!state.inv_no) { showError('Please enter an Invoice Number.'); return false; }
        if (!state.inv_date) { showError('Please enter an Invoice Date (DD/MM/YYYY).'); return false; }
    }
    if (step === 4) {
        const amtVal = parseFloat(document.getElementById('bill-amount').value);
        if (!amtVal || amtVal <= 0) { showError('Please enter a valid Bill Amount.'); return false; }
        state.amount = amtVal;
        state.amount_mode = amountMode;
    }
    return true;
}

// ─── Summary Population ───────────────────────────────────────────────────────
function populateSummary() {
    document.getElementById('sum-contractor').textContent = state.contractor || '—';
    document.getElementById('sum-customer').textContent = state.customer || '—';
    document.getElementById('sum-invno').textContent = state.inv_no || '—';
    document.getElementById('sum-date').textContent = state.inv_date || '—';
    document.getElementById('sum-grand').textContent = lastPreviewData
        ? `₹ ${lastPreviewData.grand_total}`
        : `₹ ${fmt(state.amount)}`;
}

let isGenerating = false;

// ─── Generate Invoice ─────────────────────────────────────────────────────────
async function generateInvoice() {
    if (isGenerating) return;
    if (!validateStep(4)) { goToStep(4); return; }

    isGenerating = true;
    state.include_stamp = document.getElementById('stamp-toggle').checked;
    state.contractor = document.getElementById('sel-contractor').value;
    state.customer = document.getElementById('sel-customer').value;
    state.project = document.getElementById('sel-project').value;
    state.inv_no = document.getElementById('inv-no').value.trim();
    state.inv_date = document.getElementById('inv-date').value.trim();

    // Show loading state
    const btn = document.getElementById('btn-generate');
    btn.disabled = true;
    document.getElementById('btn-gen-icon').innerHTML = '<span class="spinner"></span>';
    document.getElementById('btn-gen-text').textContent = 'Generating PDF...';
    hideError();

    if (tg) tg.HapticFeedback.impactOccurred('medium');

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 12000);

    const docInfo = getDocTypeInfo(currentDocType);

    try {
        const res = await fetch(`${API}/api/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                contractor: state.contractor,
                customer: state.customer,
                project: state.project,
                inv_no: state.inv_no,
                inv_date: state.inv_date,
                amount: state.amount,
                amount_mode: state.amount_mode,
                include_stamp: state.include_stamp,
                doc_type: currentDocType,
                custom_round_off: state.is_manual_round_off ? state.custom_round_off : null,
                user_id: tg?.initDataUnsafe?.user?.id,
                return_json: true
            }),
            signal: controller.signal
        });

        clearTimeout(timeoutId);

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.error || `Server error (${res.status})`);
        }

        const resData = await res.json();
        const safeProject = (state.project || 'Project').trim().replace(/[\/\\?%*:|"<>]/g, '').replace(/\s+/g, '_');
        const safeInv = (state.inv_no || 'Invoice').trim().replace(/[\/\\?%*:|"<>]/g, '').replace(/\s+/g, '_');
        const fname = resData.filename || `${safeProject}_${safeInv}_${docInfo.fileSuffix}.pdf`;
        
        generatedPdfData = {
            url: resData.data_url || `data:application/pdf;base64,${resData.pdf_base64}`,
            filename: fname,
            sent_to_telegram: resData.sent_to_telegram
        };

        // Pre-convert base64 data URL → Blob URL for reliable opening in all contexts
        try {
            const rawUrl = generatedPdfData.url;
            if (rawUrl.startsWith('data:')) {
                const base64 = rawUrl.split(',')[1];
                const byteChars = atob(base64);
                const byteArr = new Uint8Array(byteChars.length);
                for (let i = 0; i < byteChars.length; i++) {
                    byteArr[i] = byteChars.charCodeAt(i);
                }
                const blob = new Blob([byteArr], { type: 'application/pdf' });
                generatedPdfData.blobUrl = URL.createObjectURL(blob);
            }
        } catch (_) { /* keep using data URL if blob fails */ }

        // ✅ PDF Generated — Update button and Auto close app to return to Telegram chat
        if (btn) {
            document.getElementById('btn-gen-icon').textContent = '✅';
            document.getElementById('btn-gen-text').textContent = 'PDF Sent to Chat! Closing...';
        }

        if (tg) {
            tg.HapticFeedback?.notificationOccurred('success');
            tg.MainButton.hide();
            tg.BackButton.hide();
            // Close app to return user directly to chat
            setTimeout(() => {
                tg.close();
            }, 800);
        } else {
            // Desktop fallback: show brief alert then reset
            alert(`✅ ${docInfo.title} Generated!\n${resData.sent_to_telegram ? 'PDF sent to Telegram chat.' : 'PDF ready.'}`);
            resetForm();
        }

    } catch (e) {
        clearTimeout(timeoutId);
        const msg = e.name === 'AbortError'
            ? 'Request timed out. Please verify API server connection.'
            : e.message;
        showError(`Failed to generate invoice: ${msg}`);
        btn.disabled = false;
        document.getElementById('btn-gen-icon').textContent = '⚡';
        document.getElementById('btn-gen-text').textContent = docInfo.btnText;
        if (tg) tg.HapticFeedback.notificationOccurred('error');
    } finally {
        isGenerating = false;
    }
}

function closeAppAndGoToChat() {
    if (tg) {
        tg.HapticFeedback?.notificationOccurred('success');
        tg.close();
    } else {
        alert('Invoice generated & sent to Telegram chat!');
    }
}

function openPdfViewer() {
    if (!generatedPdfData || !generatedPdfData.url) {
        alert('No PDF generated yet. Please generate an invoice first.');
        return;
    }

    // Prefer pre-built Blob URL (most reliable)
    const openUrl = generatedPdfData.blobUrl || generatedPdfData.url;

    // If it's a blob:// or http(s):// URL, open directly
    if (openUrl.startsWith('blob:') || openUrl.startsWith('http://') || openUrl.startsWith('https://')) {
        const win = window.open(openUrl, '_blank');
        if (!win) {
            // Pop-up blocked: fallback to download
            const a = document.createElement('a');
            a.href = openUrl;
            a.target = '_blank';
            a.download = generatedPdfData.filename || 'invoice.pdf';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        }
        return;
    }

    // Last resort: convert data URL on-the-fly
    try {
        const base64 = openUrl.split(',')[1];
        const byteChars = atob(base64);
        const byteArr = new Uint8Array(byteChars.length);
        for (let i = 0; i < byteChars.length; i++) {
            byteArr[i] = byteChars.charCodeAt(i);
        }
        const blob = new Blob([byteArr], { type: 'application/pdf' });
        const blobUrl = URL.createObjectURL(blob);
        const win = window.open(blobUrl, '_blank');
        if (!win) {
            const a = document.createElement('a');
            a.href = blobUrl;
            a.download = generatedPdfData.filename || 'invoice.pdf';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        }
    } catch (e) {
        alert('Could not open PDF: ' + e.message);
    }
}

async function sendPdfToChat() {
    if (!tg?.initDataUnsafe?.user?.id) {
        alert('Telegram Chat Delivery requires opening this app inside Telegram!');
        return;
    }
    const btn = document.getElementById('btn-chat-send');
    try {
        if (btn) btn.textContent = '⏳ Sending to Telegram Chat...';
        
        const res = await fetch(`${API}/api/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                contractor: state.contractor,
                customer: state.customer,
                project: state.project,
                inv_no: state.inv_no,
                inv_date: state.inv_date,
                amount: state.amount,
                amount_mode: state.amount_mode,
                include_stamp: state.include_stamp,
                user_id: tg.initDataUnsafe.user.id
            })
        });
        
        if (btn) btn.textContent = '✅ Sent to Telegram Chat!';
        if (tg) tg.HapticFeedback.notificationOccurred('success');
    } catch (e) {
        alert('Failed to send to Telegram chat: ' + e.message);
        if (btn) btn.textContent = '💬 Send PDF directly to Telegram Chat';
    }
}

// ─── Reset Form ───────────────────────────────────────────────────────────────
function resetForm() {
    currentStep = 1;
    lastPreviewData = null;

    // Hide success
    const sc = document.getElementById('step-success');
    sc.style.display = 'none'; sc.classList.remove('active');

    // Reset all dots
    for (let i = 1; i <= TOTAL_STEPS; i++) {
        const dot = document.getElementById(`dot-${i}`);
        if (dot) dot.classList.toggle('active', i === 1);
    }
    showStep(1);

    // Reset inputs
    document.getElementById('inv-no').value = 'RA BILL 1';
    document.getElementById('inv-date').value = getTodayDDMMYYYY();
    document.getElementById('bill-amount').value = '25000.24';
    setMode('taxable');
}

// ─── Modal & Custom Data Handlers ─────────────────────────────────────────────
function openAddDataModal(defaultTab = 'contractor') {
    const currC = document.getElementById('sel-contractor').value;
    const currCust = document.getElementById('sel-customer').value;

    const addCustC = document.getElementById('add-cust-contractor');
    if (addCustC) {
        addCustC.innerHTML = `<option value="">All Contractors</option>` + contractorList.map(n => `<option value="${n}">${n}</option>`).join('');
        if (currC) addCustC.value = currC;
    }

    const addC = document.getElementById('add-proj-contractor');
    if (addC) {
        addC.innerHTML = `<option value="">All Contractors</option>` + contractorList.map(n => `<option value="${n}">${n}</option>`).join('');
        if (currC) addC.value = currC;
    }

    const addCust = document.getElementById('add-proj-customer');
    if (addCust) {
        addCust.innerHTML = `<option value="">All Customers</option>` + customerList.map(n => `<option value="${n}">${n}</option>`).join('');
        if (currCust) addCust.value = currCust;
    }

    document.getElementById('add-data-modal').classList.remove('hidden');
    switchModalTab(defaultTab);
}

function closeAddDataModal() {
    document.getElementById('add-data-modal').classList.add('hidden');
}

function switchModalTab(tabKey) {
    ['contractor', 'customer', 'project'].forEach(t => {
        const btn = document.getElementById(`tab-btn-${t}`);
        const content = document.getElementById(`modal-tab-${t}`);
        if (btn) btn.classList.toggle('active', t === tabKey);
        if (content) content.classList.toggle('active', t === tabKey);
    });
}

async function submitAddContractor(e) {
    e.preventDefault();
    const btn = document.getElementById('btn-save-contractor');
    btn.disabled = true;
    btn.textContent = '⏳ Saving Contractor...';

    try {
        const formData = new FormData();
        const name = document.getElementById('add-c-name').value.trim();
        const gstin = document.getElementById('add-c-gstin').value.trim();
        const bank = document.getElementById('add-c-bank').value.trim();
        const acc = document.getElementById('add-c-acc').value.trim();
        const ifsc = document.getElementById('add-c-ifsc').value.trim();
        const branch = document.getElementById('add-c-branch').value.trim();
        const addr = document.getElementById('add-c-addr').value.trim();
        const stampFile = document.getElementById('add-c-stamp').files[0];

        formData.append('name', name);
        formData.append('gstin', gstin);
        formData.append('bank_name', bank);
        formData.append('account_no', acc);
        formData.append('ifsc', ifsc);
        formData.append('branch', branch);
        formData.append('address', addr);
        if (stampFile) {
            formData.append('stamp_file', stampFile);
        }

        const res = await fetch(`${API}/api/add-contractor`, {
            method: 'POST',
            body: formData
        });
        const result = await res.json();

        if (res.ok && result.status === 'success') {
            log(`Contractor '${name}' saved!`, 'success');
            CONTRACTOR_META[name] = {
                gstin: gstin,
                bank: `${bank}${branch ? ' — ' + branch : ''}`
            };
            if (!contractorList.includes(name)) {
                contractorList.push(name);
            }
            const cSel = document.getElementById('sel-contractor');
            cSel.innerHTML = contractorList.map(n => `<option value="${n}">${n}</option>`).join('');
            cSel.value = name;
            onContractorChange();
            closeAddDataModal();
            document.getElementById('form-add-contractor').reset();
        } else {
            showError(result.error || 'Failed to save contractor');
        }
    } catch (err) {
        showError('Network error while saving contractor: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '💾 Save Contractor';
    }
}

async function submitAddCustomer(e) {
    e.preventDefault();
    const btn = document.getElementById('btn-save-customer');
    btn.disabled = true;
    btn.textContent = '⏳ Saving Customer...';

    try {
        const name = document.getElementById('add-cust-name').value.trim();
        const contractor_name = document.getElementById('add-cust-contractor') ? document.getElementById('add-cust-contractor').value : '';
        const gstin = document.getElementById('add-cust-gstin').value.trim();
        const addr = document.getElementById('add-cust-addr').value.trim();

        const res = await fetch(`${API}/api/add-customer`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, gstin, address: addr, contractor_name })
        });
        const result = await res.json();

        if (res.ok && result.status === 'success') {
            log(`Customer '${name}' saved!`, 'success');
            if (!customerList.includes(name)) {
                customerList.push(name);
            }

            if (contractor_name) {
                if (!CONTRACTOR_MAP[contractor_name]) {
                    CONTRACTOR_MAP[contractor_name] = { defaultCustomer: name, allowedPrefixes: [], allowedProjects: [] };
                } else {
                    CONTRACTOR_MAP[contractor_name].defaultCustomer = name;
                }
            }

            const custSel = document.getElementById('sel-customer');
            custSel.innerHTML = customerList.map(n => `<option value="${n}">${n}</option>`).join('');
            custSel.value = name;
            onCustomerChange();
            closeAddDataModal();
            document.getElementById('form-add-customer').reset();
        } else {
            showError(result.error || 'Failed to save customer');
        }
    } catch (err) {
        showError('Network error while saving customer: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '💾 Save Customer';
    }
}

async function submitAddProject(e) {
    e.preventDefault();
    const btn = document.getElementById('btn-save-project');
    btn.disabled = true;
    btn.textContent = '⏳ Saving Project...';

    try {
        const location_key = document.getElementById('add-proj-key').value.trim();
        const description = document.getElementById('add-proj-desc').value.trim();
        const contractor_name = document.getElementById('add-proj-contractor').value;
        const customer_name = document.getElementById('add-proj-customer').value;

        const res = await fetch(`${API}/api/add-project`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ location_key, description, contractor_name, customer_name })
        });
        const result = await res.json();

        if (res.ok && result.status === 'success') {
            log(`Project '${location_key}' saved!`, 'success');
            if (!projectList.some(p => p.key === location_key)) {
                projectList.push({ key: location_key, label: location_key });
            }

            if (contractor_name) {
                if (!CONTRACTOR_MAP[contractor_name]) {
                    CONTRACTOR_MAP[contractor_name] = { defaultCustomer: customer_name || '', allowedPrefixes: [], allowedProjects: [] };
                }
                if (CONTRACTOR_MAP[contractor_name].allowedProjects && !CONTRACTOR_MAP[contractor_name].allowedProjects.includes(location_key)) {
                    CONTRACTOR_MAP[contractor_name].allowedProjects.push(location_key);
                }
            }

            updateFilteredProjects();
            const projSel = document.getElementById('sel-project');
            projSel.value = location_key;
            onProjectChange();
            closeAddDataModal();
            document.getElementById('form-add-project').reset();
        } else {
            showError(result.error || 'Failed to save project');
        }
    } catch (err) {
        showError('Network error while saving project: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '💾 Save Project';
    }
}

// ─── Success Screen ───────────────────────────────────────────────────────────
function showSuccess(pdfUrl, fname) {
    // Hide all step cards
    for (let i = 1; i <= TOTAL_STEPS; i++) {
        const el = document.getElementById(`step-${i}`);
        if (el) { el.classList.remove('active'); el.style.display = 'none'; }
    }
    document.getElementById('progress-fill').style.width = '100%';
    document.getElementById('step-badge').textContent = '✅ Complete';

    // Set download link
    const link = document.getElementById('download-link');
    link.href = pdfUrl;
    link.setAttribute('download', fname);

    // Details
    document.getElementById('success-details').innerHTML = `
        <strong>Contractor:</strong> ${state.contractor}<br>
        <strong>Customer:</strong> ${state.customer}<br>
        <strong>Invoice No:</strong> ${state.inv_no}<br>
        <strong>Date:</strong> ${state.inv_date}<br>
        <strong>Grand Total:</strong> ₹ ${lastPreviewData ? lastPreviewData.grand_total : fmt(state.amount)}<br>
        <strong>Stamp:</strong> ${state.include_stamp ? 'With Stamp & Sign ✒️' : 'Without Stamp'}
    `;

    const sc = document.getElementById('step-success');
    sc.style.display = 'block';
    sc.classList.add('active');

    log(`Invoice generated: ${fname}`, 'success');
}

// ─── Reset Form ───────────────────────────────────────────────────────────────
function resetForm() {
    currentStep = 1;
    lastPreviewData = null;

    // Hide success
    const sc = document.getElementById('step-success');
    sc.style.display = 'none'; sc.classList.remove('active');

    // Reset all dots
    for (let i = 1; i <= TOTAL_STEPS; i++) {
        const dot = document.getElementById(`dot-${i}`);
        if (dot) { dot.classList.remove('active', 'done'); }
        const card = document.getElementById(`step-${i}`);
        if (card) { card.style.display = 'none'; card.classList.remove('active'); }
    }

    // Reset form fields
    document.getElementById('bill-amount').value = '';
    document.getElementById('tax-preview').style.display = 'none';

    // Activate step 1
    document.getElementById('step-1').style.display = 'block';
    document.getElementById('step-1').classList.add('active');
    document.getElementById('dot-1').classList.add('active');

    updateStepUI();

    if (tg) {
        tg.MainButton.show();
        tg.BackButton.hide();
        tg.HapticFeedback.impactOccurred('light');
    }
}

// ─── Error Helpers ────────────────────────────────────────────────────────────
function showError(msg) {
    const el = document.getElementById('error-banner');
    if (el) {
        document.getElementById('error-msg').textContent = msg;
        el.classList.remove('hidden');
    }
    log(msg, 'error');
}

function hideError() {
    const el = document.getElementById('error-banner');
    if (el) el.classList.add('hidden');
}

// ─── Native App Navigation View Switcher ───────────────────────────────────────
let currentAppView = 'generator';
let currentMasterCategory = 'contractors';
let fullContractorsData = [];
let fullCustomersData = [];
let fullProjectsData = [];

function switchAppView(viewName) {
    currentAppView = viewName;
    const isGen = viewName === 'generator';

    // Strictly show/hide views using style.display for guaranteed separation
    const generatorView = document.getElementById('view-generator');
    const masterView = document.getElementById('view-master-data');

    if (generatorView) generatorView.style.display = isGen ? 'flex' : 'none';
    if (masterView) masterView.style.display = isGen ? 'none' : 'flex';

    // Update active state on nav buttons
    ['generator', 'contractors', 'customers', 'projects'].forEach(tab => {
        const btn = document.getElementById(`nav-btn-${tab}`);
        if (btn) btn.classList.toggle('active', tab === viewName);
    });

    // Update app header title to reflect active section
    const headerTextEl = document.querySelector('#app-header .header-text p');
    const headerTitleMap = {
        generator: 'Generator',
        contractors: 'Contractors',
        customers: 'Customers',
        projects: 'Projects'
    };
    if (headerTextEl) headerTextEl.textContent = headerTitleMap[viewName] || 'Generator';

    // Update step badge visibility
    const stepBadge = document.getElementById('step-badge');
    if (stepBadge) stepBadge.style.display = isGen ? 'flex' : 'none';

    // Load master data for the selected category
    if (!isGen) {
        switchMasterCategory(viewName);
    }
}

function switchMasterCategory(category) {
    currentMasterCategory = category;
    ['contractors', 'customers', 'projects'].forEach(cat => {
        const pill = document.getElementById(`pill-${cat}`);
        if (pill) pill.classList.toggle('active', cat === category);
    });

    const titleMap = {
        contractors: '🏢 Contractors List',
        customers: '🏛️ Customers List',
        projects: '🚧 Projects List'
    };
    document.getElementById('master-view-title').textContent = titleMap[category] || 'Master Data';

    loadMasterCards(category);
}

function handleHeaderAddClick() {
    const tabMap = {
        contractors: 'contractor',
        customers: 'customer',
        projects: 'project'
    };
    openAddDataModal(tabMap[currentMasterCategory] || 'contractor');
}

async function loadMasterCards(category) {
    const listContainer = document.getElementById('master-cards-list');
    listContainer.innerHTML = `<div style="text-align:center; padding: 20px; color: var(--tg-theme-hint-color);">⏳ Loading ${category}...</div>`;

    try {
        if (category === 'contractors') {
            const res = await fetch(`${API}/api/contractors/full`);
            fullContractorsData = await res.json();
            renderContractorCards(fullContractorsData);
        } else if (category === 'customers') {
            const res = await fetch(`${API}/api/customers/full`);
            fullCustomersData = await res.json();
            renderCustomerCards(fullCustomersData);
        } else if (category === 'projects') {
            const res = await fetch(`${API}/api/projects/full`);
            fullProjectsData = await res.json();
            renderProjectCards(fullProjectsData);
        }
    } catch (e) {
        listContainer.innerHTML = `<div class="error-banner">⚠️ Failed to load ${category}: ${e.message}</div>`;
    }
}

function renderContractorCards(contractors) {
    const listContainer = document.getElementById('master-cards-list');
    if (!contractors || contractors.length === 0) {
        listContainer.innerHTML = '<div style="text-align:center; padding:20px;">No contractors found. Click ➕ Add New to create one!</div>';
        return;
    }

    listContainer.innerHTML = contractors.map(c => `
        <div class="master-card">
            <div class="card-top">
                <div>
                    <div class="card-title">${c.name}</div>
                    <div class="card-sub">GSTIN: ${c.gstin || '—'}</div>
                </div>
                <button type="button" class="btn-edit-card" onclick="editContractor('${encodeURIComponent(JSON.stringify(c))}')">
                    ✏️ Edit
                </button>
            </div>
            <div class="card-detail-row">
                <span>Bank</span>
                <span>${c.bank_name || '—'} (${c.branch || '—'})</span>
            </div>
            <div class="card-detail-row">
                <span>Account No</span>
                <span>${c.account_no || '—'}</span>
            </div>
        </div>
    `).join('');
}

function renderCustomerCards(customers) {
    const listContainer = document.getElementById('master-cards-list');
    if (!customers || customers.length === 0) {
        listContainer.innerHTML = '<div style="text-align:center; padding:20px;">No customers found. Click ➕ Add New to create one!</div>';
        return;
    }

    listContainer.innerHTML = customers.map(c => `
        <div class="master-card">
            <div class="card-top">
                <div>
                    <div class="card-title">${c.name}</div>
                    <div class="card-sub">GSTIN: ${c.gstin || '—'}</div>
                </div>
                <button type="button" class="btn-edit-card" onclick="editCustomer('${encodeURIComponent(JSON.stringify(c))}')">
                    ✏️ Edit
                </button>
            </div>
            <div class="card-detail-row">
                <span>Address</span>
                <span>${(c.address || '—').substring(0, 45)}...</span>
            </div>
        </div>
    `).join('');
}

function renderProjectCards(projects) {
    const listContainer = document.getElementById('master-cards-list');
    if (!projects || projects.length === 0) {
        listContainer.innerHTML = '<div style="text-align:center; padding:20px;">No projects found. Click ➕ Add New to create one!</div>';
        return;
    }

    listContainer.innerHTML = projects.map(p => `
        <div class="master-card">
            <div class="card-top">
                <div>
                    <div class="card-title">${p.location_key}</div>
                </div>
                <button type="button" class="btn-edit-card" onclick="editProject('${encodeURIComponent(JSON.stringify(p))}')">
                    ✏️ Edit
                </button>
            </div>
            <div class="card-detail-row">
                <span>Description</span>
                <span>${(p.description || '—').substring(0, 45)}...</span>
            </div>
        </div>
    `).join('');
}

function editContractor(encodedJson) {
    const c = JSON.parse(decodeURIComponent(encodedJson));
    document.getElementById('add-c-name').value = c.name || '';
    document.getElementById('add-c-gstin').value = c.gstin || '';
    document.getElementById('add-c-bank').value = c.bank_name || '';
    document.getElementById('add-c-acc').value = c.account_no || '';
    document.getElementById('add-c-ifsc').value = c.ifsc || '';
    document.getElementById('add-c-branch').value = c.branch || '';
    document.getElementById('add-c-addr').value = c.address || '';
    openAddDataModal('contractor');
}

function editCustomer(encodedJson) {
    const c = JSON.parse(decodeURIComponent(encodedJson));
    document.getElementById('add-cust-name').value = c.name || '';
    document.getElementById('add-cust-gstin').value = c.gstin || '';
    document.getElementById('add-cust-addr').value = c.address || '';
    openAddDataModal('customer');
}

function editProject(encodedJson) {
    const p = JSON.parse(decodeURIComponent(encodedJson));
    document.getElementById('add-proj-key').value = p.location_key || '';
    document.getElementById('add-proj-desc').value = p.description || '';
    openAddDataModal('project');
}

// ─── Log ──────────────────────────────────────────────────────────────────────
function log(msg, type = 'info') {
    console[type === 'error' ? 'error' : type === 'warn' ? 'warn' : 'log'](`[Invoice App] ${msg}`);
}
