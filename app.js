/* ═══════════════════════════════════════════════════════
   JKE Tax Invoice Generator — Telegram Mini App Logic
   ═══════════════════════════════════════════════════════ */

const getApiUrl = () => {
    const host = window.location.hostname || 'localhost';
    const port = '8031';
    return `${window.location.protocol}//${host}:${port}`;
};
const API = getApiUrl();
const tg = window.Telegram?.WebApp;

// ─── State ────────────────────────────────────────────────────────────────────
let currentStep = 1;
const TOTAL_STEPS = 5;
let amountMode = 'taxable';
let previewDebounce = null;
let lastPreviewData = null;

const state = {
    contractor: '',
    customer: '',
    project: '',
    inv_no: '',
    inv_date: '',
    amount: 0,
    amount_mode: 'taxable',
    include_stamp: true
};

// Master data cache
let contractorList = [];
let customerList = [];
let projectList = [];

// ─── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    if (tg) {
        tg.ready();
        tg.expand();
        tg.MainButton.setText('Next →');
        tg.MainButton.show();
        tg.MainButton.onClick(handleMainButton);
        tg.BackButton.onClick(handleBackButton);
    }

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
        clearTimeout(previewDebounce);
        previewDebounce = setTimeout(fetchPreview, 600);
    });

    // Update step UI
    updateStepUI();
});

// ─── Load Dropdowns ───────────────────────────────────────────────────────────
async function loadDropdowns() {
    try {
        const [cRes, custRes, projRes] = await Promise.all([
            fetch(`${API}/api/contractors`),
            fetch(`${API}/api/customers`),
            fetch(`${API}/api/projects`)
        ]);
        contractorList = await cRes.json();
        customerList = await custRes.json();
        projectList = await projRes.json();
    } catch (e) {
        // Fallback static data if API not running
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
    document.getElementById('mode-taxable').classList.toggle('active', mode === 'taxable');
    document.getElementById('mode-total').classList.toggle('active', mode === 'total');
    if (tg) tg.HapticFeedback.selectionChanged();
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

    try {
        const res = await fetch(`${API}/api/preview`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ amount: amtVal, amount_mode: amountMode })
        });
        const data = await res.json();
        lastPreviewData = data;

        document.getElementById('pv-taxable').textContent = `₹ ${data.taxable}`;
        document.getElementById('pv-cgst').textContent = `₹ ${data.cgst}`;
        document.getElementById('pv-sgst').textContent = `₹ ${data.sgst}`;
        document.getElementById('pv-subtotal').textContent = `₹ ${data.subtotal}`;
        document.getElementById('pv-grand').textContent = `₹ ${data.grand_total}`;

        const roundRow = document.getElementById('pv-roundoff-row');
        if (data.round_off) {
            document.getElementById('pv-roundoff').textContent = `${data.round_off}`;
            roundRow.style.display = 'flex';
        } else {
            roundRow.style.display = 'none';
        }

        document.getElementById('tax-preview').style.display = 'block';
    } catch (e) {
        // Fallback local calculation if API offline
        const taxable = amountMode === 'total' ? Math.round(amtVal) / 1.18 : amtVal;
        const cgst = Math.round(taxable * 0.09 * 100) / 100;
        const sgst = cgst;
        const subtotal = taxable + cgst + sgst;
        const grand = Math.round(subtotal);
        const ro = Math.round((grand - subtotal) * 100) / 100;

        document.getElementById('pv-taxable').textContent = `₹ ${fmt(taxable)}`;
        document.getElementById('pv-cgst').textContent = `₹ ${fmt(cgst)}`;
        document.getElementById('pv-sgst').textContent = `₹ ${fmt(sgst)}`;
        document.getElementById('pv-subtotal').textContent = `₹ ${fmt(subtotal)}`;
        document.getElementById('pv-grand').textContent = `₹ ${fmt(grand)}`;

        lastPreviewData = { grand_total: fmt(grand) };

        const roundRow = document.getElementById('pv-roundoff-row');
        if (ro !== 0) {
            document.getElementById('pv-roundoff').textContent = `${ro >= 0 ? '+' : ''}${ro.toFixed(2)}`;
            roundRow.style.display = 'flex';
        } else {
            roundRow.style.display = 'none';
        }
        document.getElementById('tax-preview').style.display = 'block';
    }
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
    document.getElementById(`step-${currentStep}`)?.classList.remove('active');

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

    updateStepUI();

    if (tg) tg.HapticFeedback.impactOccurred('light');
}

function updateStepUI() {
    // Progress bar
    const pct = (currentStep / TOTAL_STEPS) * 100;
    document.getElementById('progress-fill').style.width = `${pct}%`;

    // Step badge
    document.getElementById('step-badge').textContent = `Step ${currentStep} / ${TOTAL_STEPS}`;

    // Telegram back button
    if (tg) {
        if (currentStep > 1) tg.BackButton.show();
        else tg.BackButton.hide();

        // Telegram main button
        if (currentStep < TOTAL_STEPS) {
            tg.MainButton.setText('Next →');
            tg.MainButton.show();
        } else {
            tg.MainButton.hide(); // Using custom button on Step 5
        }
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
                include_stamp: state.include_stamp
            }),
            signal: controller.signal
        });

        clearTimeout(timeoutId);

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.error || `Server error (${res.status})`);
        }

        // Trigger PDF download
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        
        const safeProject = (state.project || 'Project').trim().replace(/[\/\\?%*:|"<>]/g, '').replace(/\s+/g, '_');
        const safeInv = (state.inv_no || 'Invoice').trim().replace(/[\/\\?%*:|"<>]/g, '').replace(/\s+/g, '_');
        const fname = `${safeProject}_${safeInv}_Tax_Invoice.pdf`;

        // Show success screen
        showSuccess(url, fname);

        if (tg) {
            tg.HapticFeedback.notificationOccurred('success');
            tg.MainButton.hide();
            tg.BackButton.hide();
        }

    } catch (e) {
        clearTimeout(timeoutId);
        const msg = e.name === 'AbortError'
            ? 'Request timed out. Please verify API server connection.'
            : e.message;
        showError(`Failed to generate invoice: ${msg}`);
        btn.disabled = false;
        document.getElementById('btn-gen-icon').textContent = '⚡';
        document.getElementById('btn-gen-text').textContent = 'Generate Tax Invoice PDF';
        if (tg) tg.HapticFeedback.notificationOccurred('error');
    } finally {
        isGenerating = false;
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
    
    document.getElementById('view-generator').classList.toggle('hidden', !isGen);
    document.getElementById('view-master-data').classList.toggle('hidden', isGen);

    ['generator', 'contractors', 'customers', 'projects'].forEach(tab => {
        const btn = document.getElementById(`nav-btn-${tab}`);
        if (btn) btn.classList.toggle('active', tab === viewName);
    });

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
