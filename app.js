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

// Document Type State ('tax_invoice', 'proforma_invoice', or 'mop')
let currentDocType = localStorage.getItem('jke_doc_type') || 'tax_invoice';

const state = {
    contractor: '',
    customer: '',
    project: '',
    inv_no: '',
    inv_date: '',
    bill_sr_no: '15/26-27',
    date_of_record: '',
    amount: 0,
    amount_mode: 'taxable',
    include_stamp: true,
    doc_type: currentDocType,
    custom_round_off: null,
    is_manual_round_off: false,
    mop_config: {
        agency_tds_pct: 2.0,
        agency_sgst_tds_pct: 1.0,
        agency_cgst_tds_pct: 1.0,
        admin_expense_pct: 3.25,
        it_tds_pct: 1.0,
        retention_pct: 2.0,
        labour_cess_pct: 1.0,
        testing_fee_pct: 0.5
    }
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
    if (type === 'e_invoice' || type === 'einvoice' || type === 'e-invoice') {
        return {
            type: 'e_invoice',
            title: 'E-Invoice (NIC)',
            icon: '⚡',
            badge: 'E-Invoice',
            fileSuffix: 'E_Invoice',
            desc: 'Official GST E-Invoice with IRN & QR',
            btnText: 'Generate E-Invoice PDF'
        };
    }
    if (type === 'mop' || type === 'memorandum_of_payment') {
        return {
            type: 'mop',
            title: 'Memorandum of Payment',
            icon: '📑',
            badge: 'MOP',
            fileSuffix: 'MOP_Statement',
            desc: 'Sublet billing & deduction statement',
            btnText: 'Generate MOP Statement PDF'
        };
    }
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
    if (type === 'e_invoice' || type === 'einvoice' || type === 'e-invoice') {
        currentDocType = 'e_invoice';
    } else if (type === 'mop' || type === 'memorandum_of_payment') {
        currentDocType = 'mop';
    } else if (type === 'proforma_invoice' || type === 'proforma') {
        currentDocType = 'proforma_invoice';
    } else {
        currentDocType = 'tax_invoice';
    }
    state.doc_type = currentDocType;
    localStorage.setItem('jke_doc_type', currentDocType);
    closeDocTypeDropdown();
    updateDocTypeUI();
    fetchPreview();
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
    const mopItem = document.getElementById('type-opt-mop');
    const einvItem = document.getElementById('type-opt-einv');
    const checkTax = document.getElementById('check-tax');
    const checkProforma = document.getElementById('check-proforma');
    const checkMop = document.getElementById('check-mop');
    const checkEinv = document.getElementById('check-einv');

    [taxItem, proformaItem, mopItem, einvItem].forEach(el => el?.classList.remove('active'));
    if (checkTax) checkTax.style.display = 'none';
    if (checkProforma) checkProforma.style.display = 'none';
    if (checkMop) checkMop.style.display = 'none';
    if (checkEinv) checkEinv.style.display = 'none';

    if (currentDocType === 'e_invoice') {
        einvItem?.classList.add('active');
        if (checkEinv) checkEinv.style.display = 'inline';
    } else if (currentDocType === 'mop') {
        mopItem?.classList.add('active');
        if (checkMop) checkMop.style.display = 'inline';
    } else if (currentDocType === 'proforma_invoice') {
        proformaItem?.classList.add('active');
        if (checkProforma) checkProforma.style.display = 'inline';
    } else {
        taxItem?.classList.add('active');
        if (checkTax) checkTax.style.display = 'inline';
    }

    // Step 2 Labels and Dropdown Adaptations (MOP vs E-Invoice vs Standard)
    const step2Heading = document.getElementById('step-2-heading');
    const step2Sub = document.getElementById('step-2-sub');
    const labelSelCustomer = document.getElementById('label-sel-customer');
    const projectFieldGroup = document.getElementById('project-field-group');

    if (currentDocType === 'e_invoice') {
        if (step2Heading) step2Heading.textContent = 'Customer / Client';
        if (step2Sub) step2Sub.textContent = 'Select the buyer / recipient organization';
        if (labelSelCustomer) labelSelCustomer.textContent = 'Customer / Client';
        if (projectFieldGroup) projectFieldGroup.style.display = 'none';
    } else if (currentDocType === 'mop') {
        if (step2Heading) step2Heading.textContent = 'Agency & Project';
        if (step2Sub) step2Sub.textContent = 'Who is the main agency and for what project?';
        if (labelSelCustomer) labelSelCustomer.textContent = 'Agency / Main Contractor';
        if (projectFieldGroup) projectFieldGroup.style.display = 'block';
    } else {
        if (step2Heading) step2Heading.textContent = 'Customer & Project';
        if (step2Sub) step2Sub.textContent = 'Who are you billing and for what work?';
        if (labelSelCustomer) labelSelCustomer.textContent = 'Customer / Client';
        if (projectFieldGroup) projectFieldGroup.style.display = 'block';
    }
    populateCustomerDropdown();
    updateFilteredProjects();

    // Step 3 Labels, Placeholders & Extra Fields
    const invNoLabel = document.getElementById('inv-no-label');
    const invNoInput = document.getElementById('inv-no');
    if (currentDocType === 'e_invoice') {
        if (invNoLabel) invNoLabel.textContent = 'Document Number';
        if (invNoInput) {
            invNoInput.placeholder = 'e.g. 2026/27-16';
            if (invNoInput.value === 'RA BILL 1') invNoInput.value = '2026/27-16';
        }
    } else {
        if (invNoLabel) invNoLabel.textContent = 'Invoice / RA Bill Number';
        if (invNoInput) {
            invNoInput.placeholder = 'e.g. RA BILL 1';
            if (invNoInput.value === '2026/27-16') invNoInput.value = 'RA BILL 1';
        }
    }

    const mopExtraFields = document.getElementById('mop-extra-fields');
    if (mopExtraFields) {
        mopExtraFields.style.display = currentDocType === 'mop' ? 'block' : 'none';
    }

    const einvExtraFields = document.getElementById('einv-extra-fields');
    if (einvExtraFields) {
        einvExtraFields.style.display = currentDocType === 'e_invoice' ? 'block' : 'none';
    }

    // Step 4 UI Adaptations
    const amountTypeToggleWrap = document.getElementById('amount-type-toggle-wrap');
    const amountTypeHint = document.getElementById('amount-type-hint');
    const billAmountLabel = document.getElementById('bill-amount-label');
    const step4Heading = document.getElementById('step-4-heading');
    const step4Sub = document.getElementById('step-4-sub');
    const mopConfigCard = document.getElementById('mop-config-card');
    const mopPreview = document.getElementById('mop-preview');
    const taxPreview = document.getElementById('tax-preview');

    if (currentDocType === 'mop') {
        if (amountTypeToggleWrap) amountTypeToggleWrap.style.display = 'none';
        if (amountTypeHint) amountTypeHint.style.display = 'none';
        if (billAmountLabel) billAmountLabel.textContent = 'Total Work Done Amount as per RA Bill (₹)';
        if (step4Heading) step4Heading.textContent = 'RA Bill Work Amount';
        if (step4Sub) step4Sub.textContent = 'Enter gross work done and adjust deductions';
        if (mopConfigCard) mopConfigCard.style.display = 'block';
        if (mopPreview) mopPreview.style.display = 'block';
        if (taxPreview) taxPreview.style.display = 'none';
        fetchMopDefaults();
    } else {
        if (amountTypeToggleWrap) amountTypeToggleWrap.style.display = 'flex';
        if (amountTypeHint) amountTypeHint.style.display = 'block';
        if (billAmountLabel) billAmountLabel.textContent = 'Amount (INR)';
        if (step4Heading) step4Heading.textContent = 'Bill Amount';
        if (step4Sub) step4Sub.textContent = 'Enter amount and select type';
        if (mopConfigCard) mopConfigCard.style.display = 'none';
        if (mopPreview) mopPreview.style.display = 'none';
        if (taxPreview) taxPreview.style.display = 'block';
    }

    // Step 5 Stamp & Sign Toggle and Summary Labels
    const stampPillWrap = document.getElementById('stamp-pill-wrap');
    const sumInvLbl = document.getElementById('sum-invno-lbl');
    if (currentDocType === 'e_invoice') {
        if (stampPillWrap) stampPillWrap.style.display = 'none';
        state.include_stamp = false;
        if (sumInvLbl) sumInvLbl.textContent = '📄 Doc No. / Date';
    } else {
        if (stampPillWrap) stampPillWrap.style.display = 'flex';
        if (sumInvLbl) sumInvLbl.textContent = currentDocType === 'mop' ? '📄 Bill No. / Date' : '📄 Invoice / Date';
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

    // Set today's date as default for all date fields
    const today = new Date();
    const dd = String(today.getDate()).padStart(2, '0');
    const mm = String(today.getMonth() + 1).padStart(2, '0');
    const yyyy = today.getFullYear();
    const todayStr = `${dd}/${mm}/${yyyy}`;

    const invDateEl = document.getElementById('inv-date');
    if (invDateEl) invDateEl.value = todayStr;

    initDatePicker();
    initTimePicker();

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
    const mopRoInput = document.getElementById('mop-pv-roundoff-input');
    if (mopRoInput) {
        mopRoInput.addEventListener('input', onMopRoundOffInput);
    }

    // Update step UI
    updateStepUI();

    // Set initial view
    switchAppView('generator');
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

    // Populate customer select (Client for Tax/Proforma/E-Invoice, Agency Contractor for MOP)
    const custSel = document.getElementById('sel-customer');
    populateCustomerDropdown();
    custSel.addEventListener('change', onCustomerChange);

    // Populate project select
    const projSel = document.getElementById('sel-project');
    projSel.addEventListener('change', onProjectChange);

    // Initial cascade trigger
    onContractorChange();
}

function populateCustomerDropdown() {
    const custSel = document.getElementById('sel-customer');
    if (!custSel) return;
    const currVal = custSel.value;
    const isMop = currentDocType === 'mop';

    // In MOP mode, populate with Contractor List (the Main Agency / Contractor)
    // In other modes (Tax / Proforma / E-Invoice), populate with Customer List (Client)
    const list = isMop ? contractorList : customerList;

    custSel.innerHTML = list.map(n => `<option value="${n}">${n}</option>`).join('');

    if (list.includes(currVal)) {
        custSel.value = currVal;
    } else if (isMop && list.includes('JNP INFRASTRUCTURE')) {
        custSel.value = 'JNP INFRASTRUCTURE';
    } else if (list.length > 0) {
        custSel.value = list[0];
    }
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
        allowedProjects: ['AMC Muthiya', 'AMC Chiloda', 'AMC  Kali Lake', 'AMC Kali Lake']
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
    const contractorName = document.getElementById('sel-contractor')?.value || '';
    const customerName = document.getElementById('sel-customer')?.value || '';
    const projSel = document.getElementById('sel-project');
    if (!projSel) return;
    const currProj = projSel.value;

    let filtered = [];

    if (currentDocType === 'mop') {
        // In MOP mode: customer dropdown holds the Agency / Main Contractor
        const agencyRule = CONTRACTOR_MAP[customerName] || {};
        if (agencyRule.allowedProjects && agencyRule.allowedProjects.length > 0) {
            filtered = projectList.filter(p => {
                const cleanKey = (p.key || '').replace(/\s+/g, ' ').trim().toUpperCase();
                return agencyRule.allowedProjects.some(ap => ap.replace(/\s+/g, ' ').trim().toUpperCase() === cleanKey);
            });
        }
        // Fallback if no specific mapped project for agency
        if (filtered.length === 0) {
            filtered = [...projectList];
        }
    } else {
        // In Standard modes (Tax / Proforma / E-Invoice): customerName is Client (e.g. AMC, GUDC)
        const cRule = CONTRACTOR_MAP[contractorName] || {};
        const custPrefixes = CUSTOMER_PREFIX_MAP[customerName] || [];

        if (custPrefixes.length > 0) {
            filtered = projectList.filter(p => {
                const cleanKey = (p.key || '').replace(/\s+/g, ' ').trim().toUpperCase();
                return custPrefixes.some(px => cleanKey.startsWith(px.toUpperCase()));
            });
        }

        // If contractor has preferred projects under this customer, sort them to top
        if (filtered.length > 0 && cRule.allowedProjects && cRule.allowedProjects.length > 0) {
            const preferred = [];
            const others = [];
            filtered.forEach(p => {
                const cleanKey = (p.key || '').replace(/\s+/g, ' ').trim().toUpperCase();
                const isPref = cRule.allowedProjects.some(ap => ap.replace(/\s+/g, ' ').trim().toUpperCase() === cleanKey);
                if (isPref) preferred.push(p);
                else others.push(p);
            });
            filtered = [...preferred, ...others];
        }

        // Fallback: if no project matches the customer filter or projectList was empty, use all projects
        if (filtered.length === 0) {
            filtered = [...projectList];
        }
    }

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

    if (currentDocType !== 'mop') {
        const cRule = CONTRACTOR_MAP[contractorName];
        if (cRule && cRule.defaultCustomer) {
            const custSel = document.getElementById('sel-customer');
            if ([...custSel.options].some(opt => opt.value === cRule.defaultCustomer)) {
                custSel.value = cRule.defaultCustomer;
            }
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

// ─── Indian Words Converter for Frontend ──────────────────────────────────────
function numToWordsIndian(number) {
    const n = Math.round(Math.abs(Number(number) || 0));
    if (n === 0) return 'Zero Rupees Only';
    const ones = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen'];
    const tens = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety'];
    function twoDigits(num) {
        if (num === 0) return '';
        if (num < 20) return ones[num];
        const t = Math.floor(num / 10), o = num % 10;
        return tens[t] + (o !== 0 ? ' ' + ones[o] : '');
    }
    function threeDigits(num) {
        const h = Math.floor(num / 100), r = num % 100;
        let str = '';
        if (h > 0) str += ones[h] + ' Hundred';
        if (r > 0) str += (str ? ' ' : '') + twoDigits(r);
        return str;
    }
    const crore = Math.floor(n / 10000000);
    let rem = n % 10000000;
    const lakh = Math.floor(rem / 100000);
    rem %= 100000;
    const thousand = Math.floor(rem / 1000);
    rem %= 1000;
    const parts = [];
    if (crore > 0) parts.push(twoDigits(crore) + ' Crore');
    if (lakh > 0) parts.push(twoDigits(lakh) + ' Lakh');
    if (thousand > 0) parts.push(twoDigits(thousand) + ' Thousand');
    if (rem > 0) parts.push(threeDigits(rem));
    return parts.join(' ').trim() + ' Rupees Only';
}

// ─── MOP Dynamic Configuration & Calculation Logic ────────────────────────────
function toggleMopConfigCollapse() {
    const body = document.getElementById('mop-config-body');
    const arrow = document.getElementById('mop-cfg-arrow');
    if (!body) return;
    const isHidden = body.style.display === 'none';
    body.style.display = isHidden ? 'block' : 'none';
    if (arrow) arrow.textContent = isHidden ? '▴' : '▾';
    if (tg) tg.HapticFeedback?.impactOccurred('light');
}

async function fetchMopDefaults() {
    const contractor = document.getElementById('sel-contractor')?.value || '';
    const project = document.getElementById('sel-project')?.value || '';
    try {
        const res = await fetch(`${API}/api/mop/config?contractor=${encodeURIComponent(contractor)}&project=${encodeURIComponent(project)}`);
        if (res.ok) {
            const data = await res.json();
            const cfg = data.effective_config || {};
            if (cfg.admin_expense_pct !== undefined && document.getElementById('mop-pct-admin')) document.getElementById('mop-pct-admin').value = cfg.admin_expense_pct;
            if (cfg.it_tds_pct !== undefined && document.getElementById('mop-pct-it-tds')) document.getElementById('mop-pct-it-tds').value = cfg.it_tds_pct;
            if (cfg.retention_pct !== undefined && document.getElementById('mop-pct-retention')) document.getElementById('mop-pct-retention').value = cfg.retention_pct;
            if (cfg.labour_cess_pct !== undefined && document.getElementById('mop-pct-cess')) document.getElementById('mop-pct-cess').value = cfg.labour_cess_pct;
            if (cfg.testing_fee_pct !== undefined && document.getElementById('mop-pct-testing')) document.getElementById('mop-pct-testing').value = cfg.testing_fee_pct;
            if (cfg.agency_tds_pct !== undefined && document.getElementById('mop-pct-agency-tds')) document.getElementById('mop-pct-agency-tds').value = cfg.agency_tds_pct;
            if (cfg.agency_sgst_tds_pct !== undefined && document.getElementById('mop-pct-agency-sgst')) document.getElementById('mop-pct-agency-sgst').value = cfg.agency_sgst_tds_pct;
            if (cfg.agency_cgst_tds_pct !== undefined && document.getElementById('mop-pct-agency-cgst')) document.getElementById('mop-pct-agency-cgst').value = cfg.agency_cgst_tds_pct;
            onMopConfigChange();
        }
    } catch (e) {
        onMopConfigChange();
    }
}

function onMopConfigChange() {
    state.mop_config = {
        admin_expense_pct: parseFloat(document.getElementById('mop-pct-admin')?.value) || 3.25,
        it_tds_pct: parseFloat(document.getElementById('mop-pct-it-tds')?.value) || 1.0,
        retention_pct: parseFloat(document.getElementById('mop-pct-retention')?.value) || 2.0,
        labour_cess_pct: parseFloat(document.getElementById('mop-pct-cess')?.value) || 1.0,
        testing_fee_pct: parseFloat(document.getElementById('mop-pct-testing')?.value) || 0.5,
        agency_tds_pct: parseFloat(document.getElementById('mop-pct-agency-tds')?.value) || 2.0,
        agency_sgst_tds_pct: parseFloat(document.getElementById('mop-pct-agency-sgst')?.value) || 1.0,
        agency_cgst_tds_pct: parseFloat(document.getElementById('mop-pct-agency-cgst')?.value) || 1.0
    };
    updateMopPreview();
}

function resetMopPercentages() {
    fetchMopDefaults();
    if (tg) tg.HapticFeedback?.notificationOccurred('success');
}

function updateMopPreview() {
    const amtVal = parseFloat(document.getElementById('bill-amount')?.value);
    const mopPv = document.getElementById('mop-preview');
    if (!amtVal || amtVal <= 0) {
        if (mopPv) mopPv.style.display = 'none';
        return;
    }

    const cfg = state.mop_config || {};
    const G = amtVal;
    const b_work = G / 1.18;

    const agency_tds = b_work * ((cfg.agency_tds_pct || 2.0) / 100.0);
    const agency_sgst = b_work * ((cfg.agency_sgst_tds_pct || 1.0) / 100.0);
    const agency_cgst = b_work * ((cfg.agency_cgst_tds_pct || 1.0) / 100.0);
    const agency_ded_total = agency_tds + agency_sgst + agency_cgst;

    const net_ab = G - agency_ded_total;
    const admin_exp = G * ((cfg.admin_expense_pct || 3.25) / 100.0);

    const our_gross = net_ab - admin_exp;
    const our_basic = our_gross / 1.18;
    const our_sgst = our_basic * 0.09;
    const our_cgst = our_basic * 0.09;

    const it_tds = our_basic * ((cfg.it_tds_pct || 1.0) / 100.0);
    const retention = G * ((cfg.retention_pct || 2.0) / 100.0);
    const labour_cess = b_work * ((cfg.labour_cess_pct || 1.0) / 100.0);
    const testing_fee = G * ((cfg.testing_fee_pct || 0.5) / 100.0);

    const our_ded_total = it_tds + retention + labour_cess + testing_fee;
    const raw_net = our_gross - our_ded_total;

    const auto_ro = Math.round(raw_net) - raw_net;
    let effective_ro = auto_ro;
    let net_payable = Math.round(raw_net);

    if (state.is_manual_round_off && state.custom_round_off !== null) {
        effective_ro = state.custom_round_off;
        net_payable = Math.round((raw_net + effective_ro) * 100) / 100;
    }

    // Update DOM elements
    if (document.getElementById('mop-pv-gross')) document.getElementById('mop-pv-gross').textContent = `₹ ${fmt(G)}`;
    if (document.getElementById('mop-pv-agency-ded')) document.getElementById('mop-pv-agency-ded').textContent = `- ₹ ${fmt(agency_ded_total)}`;
    if (document.getElementById('mop-pv-agency-tds')) document.getElementById('mop-pv-agency-tds').textContent = `₹ ${fmt(agency_tds)}`;
    if (document.getElementById('mop-pv-agency-gst')) document.getElementById('mop-pv-agency-gst').textContent = `₹ ${fmt(agency_sgst + agency_cgst)}`;
    if (document.getElementById('mop-pv-net-ab')) document.getElementById('mop-pv-net-ab').textContent = `₹ ${fmt(net_ab)}`;
    if (document.getElementById('mop-pv-admin')) document.getElementById('mop-pv-admin').textContent = `- ₹ ${fmt(admin_exp)}`;
    if (document.getElementById('mop-pv-our-bill')) document.getElementById('mop-pv-our-bill').textContent = `₹ ${fmt(our_gross)}`;
    if (document.getElementById('mop-pv-our-breakdown')) document.getElementById('mop-pv-our-breakdown').textContent = `Basic: ₹${fmt(our_basic)} + GST: ₹${fmt(our_sgst + our_cgst)}`;
    if (document.getElementById('mop-pv-our-ded')) document.getElementById('mop-pv-our-ded').textContent = `- ₹ ${fmt(our_ded_total)}`;

    // Interactive Round Off Controls
    const mopRoInput = document.getElementById('mop-pv-roundoff-input');
    const mopBadge = document.getElementById('mop-ro-mode-badge');
    const mopResetBtn = document.getElementById('btn-mop-ro-reset');

    if (mopRoInput) {
        if (!state.is_manual_round_off) {
            mopRoInput.value = `${auto_ro >= 0 ? '+' : ''}${auto_ro.toFixed(2)}`;
            mopRoInput.classList.remove('is-custom');
            if (mopBadge) {
                mopBadge.textContent = 'AUTO';
                mopBadge.className = 'ro-badge ro-badge-auto';
            }
            if (mopResetBtn) mopResetBtn.style.display = 'none';
        } else {
            mopRoInput.classList.add('is-custom');
            if (mopBadge) {
                mopBadge.textContent = 'EDITED';
                mopBadge.className = 'ro-badge ro-badge-edit';
            }
            if (mopResetBtn) mopResetBtn.style.display = 'inline-flex';
        }
    }

    if (document.getElementById('mop-pv-net-payable')) document.getElementById('mop-pv-net-payable').textContent = `₹ ${fmt(net_payable)}`;
    if (document.getElementById('mop-pv-words')) document.getElementById('mop-pv-words').textContent = `"${numToWordsIndian(net_payable)}"`;

    lastPreviewData = {
        grand_total: fmt(net_payable),
        grand_total_raw: net_payable,
        mop_raw_net: raw_net,
        mop_calcs: {
            gross: G,
            raw_net: raw_net,
            round_off: effective_ro,
            net_payable: net_payable,
            our_bill_gross: our_gross
        }
    };

    if (mopPv) mopPv.style.display = 'block';
}

// ─── Live Tax Preview ─────────────────────────────────────────────────────────
async function fetchPreview() {
    if (currentDocType === 'mop') {
        updateMopPreview();
        return;
    }

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
    const rawVal = (e.target.value || '').trim();
    const badge = document.getElementById('ro-mode-badge');
    const resetBtn = document.getElementById('btn-ro-reset');

    if (rawVal === '' || rawVal === '+' || rawVal === '-') {
        return;
    }

    const cleanNum = parseFloat(rawVal.replace(/^\+/, ''));
    if (isNaN(cleanNum)) {
        return;
    }

    const customRo = cleanNum;
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

// ─── Live Edit Handler for MOP Round Off Input ───────────────────────────────
function onMopRoundOffInput(e) {
    const rawVal = (e.target.value || '').trim();
    const badge = document.getElementById('mop-ro-mode-badge');
    const resetBtn = document.getElementById('btn-mop-ro-reset');

    if (rawVal === '' || rawVal === '+' || rawVal === '-') {
        return;
    }

    const cleanNum = parseFloat(rawVal.replace(/^\+/, ''));
    if (isNaN(cleanNum)) {
        return;
    }

    const customRo = cleanNum;
    state.is_manual_round_off = true;
    state.custom_round_off = customRo;

    if (badge) {
        badge.textContent = 'EDITED';
        badge.className = 'ro-badge ro-badge-edit';
    }
    if (resetBtn) resetBtn.style.display = 'inline-flex';
    e.target.classList.add('is-custom');

    // Real-time local recalculation of Net Payable & Words
    if (lastPreviewData && lastPreviewData.mop_raw_net !== undefined) {
        const rawNet = lastPreviewData.mop_raw_net;
        const newNet = Math.round((rawNet + customRo) * 100) / 100;
        if (document.getElementById('mop-pv-net-payable')) document.getElementById('mop-pv-net-payable').textContent = `₹ ${fmt(newNet)}`;
        if (document.getElementById('mop-pv-words')) document.getElementById('mop-pv-words').textContent = `"${numToWordsIndian(newNet)}"`;
        lastPreviewData.grand_total = fmt(newNet);
        lastPreviewData.grand_total_raw = newNet;
    } else {
        updateMopPreview();
    }
}

function resetMopRoundOffToAuto() {
    state.is_manual_round_off = false;
    state.custom_round_off = null;
    if (tg) tg.HapticFeedback?.selectionChanged();
    updateMopPreview();
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

    // Refresh project dropdown if entering Step 2
    if (step === 2) {
        updateFilteredProjects();
    }

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
        if (!state.customer) { showError(currentDocType === 'mop' ? 'Please select an agency / main contractor.' : 'Please select a customer.'); return false; }
        if (currentDocType !== 'e_invoice') {
            state.project = document.getElementById('sel-project').value;
            if (!state.project) { showError('Please select a project.'); return false; }
        } else {
            state.project = '';
        }
    }
    if (step === 3) {
        state.inv_no = document.getElementById('inv-no').value.trim();
        state.inv_date = document.getElementById('inv-date').value.trim();
        if (!state.inv_no) { showError(currentDocType === 'e_invoice' ? 'Please enter a Document Number.' : 'Please enter an Invoice / RA Bill Number.'); return false; }
        if (!state.inv_date) { showError('Please enter a Date (DD/MM/YYYY).'); return false; }
        if (currentDocType === 'mop') {
            state.bill_sr_no = document.getElementById('mop-bill-sr-no')?.value.trim() || '15/26-27';
            state.date_of_record = state.inv_date;
        }
        if (currentDocType === 'e_invoice') {
            state.hsn = document.getElementById('einv-hsn')?.value.trim() || '995424';
            state.inv_time = document.getElementById('einv-time')?.value.trim() || '11:15:30';
        }
    }
    if (step === 4) {
        const amtVal = parseFloat(document.getElementById('bill-amount').value);
        if (!amtVal || amtVal <= 0) { showError('Please enter a valid Bill Amount.'); return false; }
        state.amount = amtVal;
        state.amount_mode = amountMode;
        if (currentDocType === 'mop') {
            onMopConfigChange();
        }
    }
    return true;
}

// ─── Summary Population ───────────────────────────────────────────────────────
function populateSummary() {
    document.getElementById('sum-contractor').textContent = state.contractor || '—';
    document.getElementById('sum-customer').textContent = state.customer || '—';
    document.getElementById('sum-invno').textContent = state.inv_no || '—';
    if (currentDocType === 'e_invoice') {
        document.getElementById('sum-date').textContent = `${state.inv_date} • ${state.inv_time || ''}`.trim();
    } else {
        document.getElementById('sum-date').textContent = state.inv_date || '—';
    }
    document.getElementById('sum-grand').textContent = lastPreviewData
        ? `₹ ${lastPreviewData.grand_total}`
        : `₹ ${fmt(state.amount)}`;
}

let isGenerating = false;

// ─── Generate Invoice / MOP / E-Invoice ──────────────────────────────────────
async function generateInvoice() {
    if (isGenerating) return;
    if (!validateStep(4)) { goToStep(4); return; }

    isGenerating = true;
    state.contractor = document.getElementById('sel-contractor').value;
    state.customer = document.getElementById('sel-customer').value;
    state.inv_no = document.getElementById('inv-no').value.trim();
    state.inv_date = document.getElementById('inv-date').value.trim();

    if (currentDocType === 'e_invoice') {
        state.project = '';
        state.include_stamp = false;
        state.hsn = document.getElementById('einv-hsn')?.value.trim() || '995424';
        state.inv_time = document.getElementById('einv-time')?.value.trim() || '11:15:30';
    } else {
        state.include_stamp = document.getElementById('stamp-toggle').checked;
        state.project = document.getElementById('sel-project').value;
    }

    if (currentDocType === 'mop') {
        state.bill_sr_no = document.getElementById('mop-bill-sr-no')?.value.trim() || '15/26-27';
        state.date_of_record = state.inv_date;
    }

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
        const payload = {
            contractor: state.contractor,
            customer: state.customer,
            agency: state.customer,
            project: state.project,
            inv_no: state.inv_no,
            inv_date: state.inv_date,
            inv_time: state.inv_time,
            bill_sr_no: state.bill_sr_no,
            date_of_record: state.date_of_record,
            hsn: state.hsn || '995424',
            amount: state.amount,
            amount_mode: state.amount_mode,
            include_stamp: state.include_stamp,
            doc_type: currentDocType,
            config: state.mop_config,
            custom_round_off: state.is_manual_round_off ? state.custom_round_off : null,
            user_id: tg?.initDataUnsafe?.user?.id,
            return_json: true
        };

        const res = await fetch(`${API}/api/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
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

// ─── Modal & Custom Data Handlers ─────────────────────────────────────────────
function openAddDataModal(defaultTab = 'contractor', isNew = true) {
    if (isNew) {
        document.getElementById('form-add-contractor')?.reset();
        document.getElementById('form-add-customer')?.reset();
        document.getElementById('form-add-project')?.reset();
        const ac = document.getElementById('add-c-active'); if (ac) ac.checked = true;
        const acust = document.getElementById('add-cust-active'); if (acust) acust.checked = true;
        const ap = document.getElementById('add-proj-active'); if (ap) ap.checked = true;
    }

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
        const isActive = document.getElementById('add-c-active')?.checked ?? true;
        formData.append('active', isActive);
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
            await loadDropdowns();
            const cSel = document.getElementById('sel-contractor');
            if (isActive) {
                cSel.value = name;
                onContractorChange();
            }
            closeAddDataModal();
            document.getElementById('form-add-contractor').reset();
            if (currentMasterCategory === 'contractors') loadMasterCards('contractors');
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
        const isActive = document.getElementById('add-cust-active')?.checked ?? true;

        const res = await fetch(`${API}/api/add-customer`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, gstin, address: addr, contractor_name, active: isActive })
        });
        const result = await res.json();

        if (res.ok && result.status === 'success') {
            log(`Customer '${name}' saved!`, 'success');
            await loadDropdowns();

            if (contractor_name) {
                if (!CONTRACTOR_MAP[contractor_name]) {
                    CONTRACTOR_MAP[contractor_name] = { defaultCustomer: name, allowedPrefixes: [], allowedProjects: [] };
                } else {
                    CONTRACTOR_MAP[contractor_name].defaultCustomer = name;
                }
            }

            const custSel = document.getElementById('sel-customer');
            if (isActive) {
                custSel.value = name;
                onCustomerChange();
            }
            closeAddDataModal();
            document.getElementById('form-add-customer').reset();
            if (currentMasterCategory === 'customers') loadMasterCards('customers');
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
        const isActive = document.getElementById('add-proj-active')?.checked ?? true;

        const res = await fetch(`${API}/api/add-project`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ location_key, description, contractor_name, customer_name, active: isActive })
        });
        const result = await res.json();

        if (res.ok && result.status === 'success') {
            log(`Project '${location_key}' saved!`, 'success');
            await loadDropdowns();

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
            if (isActive) {
                projSel.value = location_key;
                onProjectChange();
            }
            closeAddDataModal();
            document.getElementById('form-add-project').reset();
            if (currentMasterCategory === 'projects') loadMasterCards('projects');
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
    for (let i = 1; i <= TOTAL_STEPS; i++) {
        const el = document.getElementById(`step-${i}`);
        if (el) { el.classList.remove('active'); el.style.display = 'none'; }
    }
    document.getElementById('progress-fill').style.width = '100%';
    document.getElementById('step-badge').textContent = '✅ Complete';

    const link = document.getElementById('download-link');
    if (link) {
        link.href = pdfUrl;
        link.setAttribute('download', fname);
    }

    const detailsEl = document.getElementById('success-details');
    if (detailsEl) {
        detailsEl.innerHTML = `
            <strong>Contractor:</strong> ${state.contractor}<br>
            <strong>Customer:</strong> ${state.customer}<br>
            <strong>Invoice No:</strong> ${state.inv_no}<br>
            <strong>Date:</strong> ${state.inv_date}<br>
            <strong>Grand Total:</strong> ₹ ${lastPreviewData ? lastPreviewData.grand_total : fmt(state.amount)}<br>
            <strong>Stamp:</strong> ${state.include_stamp ? 'With Stamp & Sign ✒️' : 'Without Stamp'}
        `;
    }

    const sc = document.getElementById('step-success');
    if (sc) {
        sc.style.display = 'block';
        sc.classList.add('active');
    }

    log(`Invoice generated: ${fname}`, 'success');
}

// ─── Reset Form ───────────────────────────────────────────────────────────────
function resetForm() {
    currentStep = 1;
    lastPreviewData = null;

    const sc = document.getElementById('step-success');
    if (sc) {
        sc.style.display = 'none';
        sc.classList.remove('active');
    }

    for (let i = 1; i <= TOTAL_STEPS; i++) {
        const dot = document.getElementById(`dot-${i}`);
        if (dot) { dot.classList.remove('active', 'done'); }
        const card = document.getElementById(`step-${i}`);
        if (card) { card.style.display = 'none'; card.classList.remove('active'); }
    }

    document.getElementById('bill-amount').value = '';
    document.getElementById('tax-preview').style.display = 'none';

    document.getElementById('step-1').style.display = 'block';
    document.getElementById('step-1').classList.add('active');
    document.getElementById('dot-1').classList.add('active');

    updateStepUI();

    if (tg) {
        tg.MainButton.hide();
        tg.BackButton.hide();
        tg.HapticFeedback?.impactOccurred('light');
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

    const generatorView = document.getElementById('view-generator');
    const masterView = document.getElementById('view-master-data');

    if (generatorView) generatorView.style.display = isGen ? 'block' : 'none';
    if (masterView) masterView.style.display = isGen ? 'none' : 'block';

    ['generator', 'contractors', 'customers', 'projects'].forEach(tab => {
        const btn = document.getElementById(`nav-btn-${tab}`);
        if (btn) btn.classList.toggle('active', tab === viewName);
    });

    const headerTextEl = document.querySelector('#app-header .header-text p');
    const headerTitleMap = {
        generator: 'Generator',
        contractors: 'Contractors',
        customers: 'Customers',
        projects: 'Projects'
    };
    if (headerTextEl) headerTextEl.textContent = headerTitleMap[viewName] || 'Generator';

    const stepBadge = document.getElementById('step-badge');
    if (stepBadge) stepBadge.style.display = isGen ? 'flex' : 'none';

    if (!isGen) {
        switchMasterCategory(viewName);
    }
    if (tg) tg.HapticFeedback?.selectionChanged();
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
    const titleEl = document.getElementById('master-view-title');
    if (titleEl) titleEl.textContent = titleMap[category] || 'Master Data';

    loadMasterCards(category);
}

function handleHeaderAddClick() {
    const tabMap = {
        contractors: 'contractor',
        customers: 'customer',
        projects: 'project'
    };
    openAddDataModal(tabMap[currentMasterCategory] || 'contractor', true);
}

async function loadMasterCards(category) {
    const listContainer = document.getElementById('master-cards-list');
    if (!listContainer) return;
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

// ─── Master Item Status Toggle Handler ────────────────────────────────────────
async function onToggleMasterItemStatus(category, encodedItemId, isActive) {
    const itemId = decodeURIComponent(encodedItemId);
    if (tg) tg.HapticFeedback?.impactOccurred('medium');

    try {
        const res = await fetch(`${API}/api/master/toggle-status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ category, id: itemId, active: isActive })
        });
        const result = await res.json();

        if (res.ok && result.status === 'success') {
            log(`${category} '${itemId}' active status set to ${isActive}`, 'success');
            // Refresh dropdown lists for generator immediately
            await loadDropdowns();
            // Reload master cards for current category to update UI seamlessly
            loadMasterCards(currentMasterCategory);
            if (tg) tg.HapticFeedback?.notificationOccurred('success');
        } else {
            showError(result.error || 'Failed to update active status');
            loadMasterCards(currentMasterCategory);
        }
    } catch (err) {
        showError('Network error updating status: ' + err.message);
        loadMasterCards(currentMasterCategory);
    }
}

function renderContractorCards(contractors) {
    const listContainer = document.getElementById('master-cards-list');
    if (!contractors || contractors.length === 0) {
        listContainer.innerHTML = '<div style="text-align:center; padding:20px;">No contractors found. Click ➕ Add New to create one!</div>';
        return;
    }

    listContainer.innerHTML = contractors.map(c => {
        const isActive = c.active !== false;
        return `
        <div class="master-card ${isActive ? '' : 'is-inactive'}">
            <div class="card-top">
                <div>
                    <div class="card-title">${c.name}</div>
                    <div class="card-sub">GSTIN: ${c.gstin || '—'}</div>
                    <span class="status-badge ${isActive ? 'active' : 'inactive'}">
                        ${isActive ? '🟢 Active' : '⚪ Inactive'}
                    </span>
                </div>
                <div class="card-actions-group">
                    <label class="master-active-toggle" title="Toggle active status in generator dropdowns">
                        <input type="checkbox" ${isActive ? 'checked' : ''} onchange="onToggleMasterItemStatus('contractor', '${encodeURIComponent(c.name)}', this.checked)">
                        <span class="mat-slider"></span>
                    </label>
                    <button type="button" class="btn-edit-card" onclick="editContractor('${encodeURIComponent(JSON.stringify(c))}')">
                        ✏️ Edit
                    </button>
                </div>
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
    `;
    }).join('');
}

function renderCustomerCards(customers) {
    const listContainer = document.getElementById('master-cards-list');
    if (!customers || customers.length === 0) {
        listContainer.innerHTML = '<div style="text-align:center; padding:20px;">No customers found. Click ➕ Add New to create one!</div>';
        return;
    }

    listContainer.innerHTML = customers.map(c => {
        const isActive = c.active !== false;
        return `
        <div class="master-card ${isActive ? '' : 'is-inactive'}">
            <div class="card-top">
                <div>
                    <div class="card-title">${c.name}</div>
                    <div class="card-sub">GSTIN: ${c.gstin || '—'}</div>
                    <span class="status-badge ${isActive ? 'active' : 'inactive'}">
                        ${isActive ? '🟢 Active' : '⚪ Inactive'}
                    </span>
                </div>
                <div class="card-actions-group">
                    <label class="master-active-toggle" title="Toggle active status in generator dropdowns">
                        <input type="checkbox" ${isActive ? 'checked' : ''} onchange="onToggleMasterItemStatus('customer', '${encodeURIComponent(c.name)}', this.checked)">
                        <span class="mat-slider"></span>
                    </label>
                    <button type="button" class="btn-edit-card" onclick="editCustomer('${encodeURIComponent(JSON.stringify(c))}')">
                        ✏️ Edit
                    </button>
                </div>
            </div>
            <div class="card-detail-row">
                <span>Address</span>
                <span>${(c.address || '—').substring(0, 45)}...</span>
            </div>
        </div>
    `;
    }).join('');
}

function renderProjectCards(projects) {
    const listContainer = document.getElementById('master-cards-list');
    if (!projects || projects.length === 0) {
        listContainer.innerHTML = '<div style="text-align:center; padding:20px;">No projects found. Click ➕ Add New to create one!</div>';
        return;
    }

    listContainer.innerHTML = projects.map(p => {
        const isActive = p.active !== false;
        return `
        <div class="master-card ${isActive ? '' : 'is-inactive'}">
            <div class="card-top">
                <div>
                    <div class="card-title">${p.location_key}</div>
                    <span class="status-badge ${isActive ? 'active' : 'inactive'}">
                        ${isActive ? '🟢 Active' : '⚪ Inactive'}
                    </span>
                </div>
                <div class="card-actions-group">
                    <label class="master-active-toggle" title="Toggle active status in generator dropdowns">
                        <input type="checkbox" ${isActive ? 'checked' : ''} onchange="onToggleMasterItemStatus('project', '${encodeURIComponent(p.location_key)}', this.checked)">
                        <span class="mat-slider"></span>
                    </label>
                    <button type="button" class="btn-edit-card" onclick="editProject('${encodeURIComponent(JSON.stringify(p))}')">
                        ✏️ Edit
                    </button>
                </div>
            </div>
            <div class="card-detail-row">
                <span>Description</span>
                <span>${(p.description || '—').substring(0, 45)}...</span>
            </div>
        </div>
    `;
    }).join('');
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
    const activeBox = document.getElementById('add-c-active');
    if (activeBox) activeBox.checked = c.active !== false;
    openAddDataModal('contractor', false);
}

function editCustomer(encodedJson) {
    const c = JSON.parse(decodeURIComponent(encodedJson));
    document.getElementById('add-cust-name').value = c.name || '';
    document.getElementById('add-cust-gstin').value = c.gstin || '';
    document.getElementById('add-cust-addr').value = c.address || '';
    const activeBox = document.getElementById('add-cust-active');
    if (activeBox) activeBox.checked = c.active !== false;
    openAddDataModal('customer', false);
}

function editProject(encodedJson) {
    const p = JSON.parse(decodeURIComponent(encodedJson));
    document.getElementById('add-proj-key').value = p.location_key || '';
    document.getElementById('add-proj-desc').value = p.description || '';
    const activeBox = document.getElementById('add-proj-active');
    if (activeBox) activeBox.checked = p.active !== false;
    openAddDataModal('project', false);
}

// ─── Log ──────────────────────────────────────────────────────────────────────
function log(msg, type = 'info') {
    console[type === 'error' ? 'error' : type === 'warn' ? 'warn' : 'log'](`[Invoice App] ${msg}`);
}

// ─── 📅 Theme-Aligned Custom Date Picker Engine ───────────────────────────────
let activeDateInputId = null;
let dpViewYear = new Date().getFullYear();
let dpViewMonth = new Date().getMonth();
let dpSelectedDate = new Date();

const MONTH_NAMES = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
];

const MONTH_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const DAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

function initDatePicker() {
    const yearSel = document.getElementById('dp-year-select');
    if (yearSel) {
        const currY = new Date().getFullYear();
        let options = '';
        for (let y = currY - 5; y <= currY + 10; y++) {
            options += `<option value="${y}" ${y === currY ? 'selected' : ''}>${y}</option>`;
        }
        yearSel.innerHTML = options;
    }
}

function parseDateStr(str) {
    if (!str || typeof str !== 'string') return new Date();
    const parts = str.trim().split(/[\/\-\.]/);
    if (parts.length === 3) {
        const d = parseInt(parts[0], 10);
        const m = parseInt(parts[1], 10) - 1;
        const y = parseInt(parts[2], 10);
        if (!isNaN(d) && !isNaN(m) && !isNaN(y) && y > 1900 && m >= 0 && m <= 11 && d >= 1 && d <= 31) {
            return new Date(y, m, d);
        }
    }
    return new Date();
}

function formatDateStr(date) {
    const d = String(date.getDate()).padStart(2, '0');
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const y = date.getFullYear();
    return `${d}/${mmFormat(m)}/${y}`;
}

function mmFormat(val) {
    return String(val).padStart(2, '0');
}

function openCustomDatePicker(inputId) {
    activeDateInputId = inputId;
    const inputEl = document.getElementById(inputId);
    const initialDate = parseDateStr(inputEl?.value);

    dpSelectedDate = new Date(initialDate.getTime());
    dpViewYear = dpSelectedDate.getFullYear();
    dpViewMonth = dpSelectedDate.getMonth();

    updateDatePickerNavControls();
    renderDatePickerGrid();

    const modal = document.getElementById('custom-datepicker-modal');
    if (modal) {
        modal.classList.remove('hidden');
        if (tg) tg.HapticFeedback?.impactOccurred('light');
    }
}

function closeCustomDatePicker() {
    const modal = document.getElementById('custom-datepicker-modal');
    if (modal) {
        modal.classList.add('hidden');
    }
    activeDateInputId = null;
}

function handleDatePickerBackdrop(e) {
    if (e.target.id === 'custom-datepicker-modal') {
        closeCustomDatePicker();
    }
}

function updateDatePickerNavControls() {
    const mSel = document.getElementById('dp-month-select');
    const ySel = document.getElementById('dp-year-select');
    if (mSel) mSel.value = dpViewMonth;
    if (ySel) ySel.value = dpViewYear;
}

function onDatePickerMonthYearChange() {
    const mSel = document.getElementById('dp-month-select');
    const ySel = document.getElementById('dp-year-select');
    if (mSel) dpViewMonth = parseInt(mSel.value, 10);
    if (ySel) dpViewYear = parseInt(ySel.value, 10);
    renderDatePickerGrid();
}

function prevDatePickerMonth() {
    dpViewMonth--;
    if (dpViewMonth < 0) {
        dpViewMonth = 11;
        dpViewYear--;
    }
    updateDatePickerNavControls();
    renderDatePickerGrid();
    if (tg) tg.HapticFeedback?.selectionChanged();
}

function nextDatePickerMonth() {
    dpViewMonth++;
    if (dpViewMonth > 11) {
        dpViewMonth = 0;
        dpViewYear++;
    }
    updateDatePickerNavControls();
    renderDatePickerGrid();
    if (tg) tg.HapticFeedback?.selectionChanged();
}

function renderDatePickerGrid() {
    const grid = document.getElementById('dp-days-grid');
    const headerDisplay = document.getElementById('dp-header-display');
    if (!grid) return;

    if (headerDisplay && dpSelectedDate) {
        const dayName = DAY_NAMES[dpSelectedDate.getDay()];
        const dateNum = dpSelectedDate.getDate();
        const monthName = MONTH_SHORT[dpSelectedDate.getMonth()];
        const yearNum = dpSelectedDate.getFullYear();
        headerDisplay.textContent = `${dayName}, ${dateNum} ${monthName} ${yearNum}`;
    }

    const firstDayIndex = new Date(dpViewYear, dpViewMonth, 1).getDay();
    const daysInMonth = new Date(dpViewYear, dpViewMonth + 1, 0).getDate();
    const prevMonthDays = new Date(dpViewYear, dpViewMonth, 0).getDate();

    const today = new Date();
    const isCurrentMonthToday = today.getFullYear() === dpViewYear && today.getMonth() === dpViewMonth;

    let cellsHtml = '';

    // Previous month tail days
    for (let x = firstDayIndex; x > 0; x--) {
        const dNum = prevMonthDays - x + 1;
        cellsHtml += `<div class="dp-day-cell dp-other-month" onclick="selectDateFromGrid(${dNum}, -1)">${dNum}</div>`;
    }

    // Current month days
    for (let d = 1; d <= daysInMonth; d++) {
        const isToday = isCurrentMonthToday && today.getDate() === d;
        const isSelected = dpSelectedDate &&
            dpSelectedDate.getFullYear() === dpViewYear &&
            dpSelectedDate.getMonth() === dpViewMonth &&
            dpSelectedDate.getDate() === d;

        let classList = 'dp-day-cell';
        if (isToday) classList += ' dp-today';
        if (isSelected) classList += ' dp-selected';

        cellsHtml += `<div class="${classList}" onclick="selectDateFromGrid(${d}, 0)">${d}</div>`;
    }

    // Next month head days (fill to 42 cells or minimum 35)
    const totalCells = firstDayIndex + daysInMonth;
    const nextDays = totalCells > 35 ? (42 - totalCells) : (35 - totalCells);
    for (let j = 1; j <= nextDays; j++) {
        cellsHtml += `<div class="dp-day-cell dp-other-month" onclick="selectDateFromGrid(${j}, 1)">${j}</div>`;
    }

    grid.innerHTML = cellsHtml;
}

function selectDateFromGrid(day, monthOffset = 0) {
    if (monthOffset === -1) {
        dpViewMonth--;
        if (dpViewMonth < 0) { dpViewMonth = 11; dpViewYear--; }
    } else if (monthOffset === 1) {
        dpViewMonth++;
        if (dpViewMonth > 11) { dpViewMonth = 0; dpViewYear++; }
    }

    dpSelectedDate = new Date(dpViewYear, dpViewMonth, day);
    updateDatePickerNavControls();
    renderDatePickerGrid();
    if (tg) tg.HapticFeedback?.impactOccurred('light');
}

function setDatePickerPreset(preset) {
    let d = new Date();
    if (preset === 'yesterday') {
        d = new Date(Date.now() - 86400000);
    }
    dpSelectedDate = d;
    dpViewYear = d.getFullYear();
    dpViewMonth = d.getMonth();
    applyCustomDatePicker();
}

function applyCustomDatePicker() {
    if (!activeDateInputId || !dpSelectedDate) {
        closeCustomDatePicker();
        return;
    }

    const dd = String(dpSelectedDate.getDate()).padStart(2, '0');
    const mm = String(dpSelectedDate.getMonth() + 1).padStart(2, '0');
    const yyyy = dpSelectedDate.getFullYear();
    const formatted = `${dd}/${mm}/${yyyy}`;

    const targetInput = document.getElementById(activeDateInputId);
    if (targetInput) {
        targetInput.value = formatted;
        targetInput.dispatchEvent(new Event('input', { bubbles: true }));
        targetInput.dispatchEvent(new Event('change', { bubbles: true }));
    }

    if (activeDateInputId === 'inv-date') {
        state.inv_date = formatted;
        state.date_of_record = formatted;
    }

    if (tg) tg.HapticFeedback?.notificationOccurred('success');
    closeCustomDatePicker();
}

// ─── 🕒 Theme-Aligned Custom Time Picker Engine ───────────────────────────────
let activeTimeInputId = null;
let tpHour = 11;
let tpMin = 15;
let tpSec = 30;

function initTimePicker() {
    const hSel = document.getElementById('tp-hour-select');
    const mSel = document.getElementById('tp-min-select');
    const sSel = document.getElementById('tp-sec-select');

    if (hSel) {
        let hOpts = '';
        for (let h = 0; h < 24; h++) {
            const hStr = String(h).padStart(2, '0');
            hOpts += `<option value="${hStr}">${hStr}</option>`;
        }
        hSel.innerHTML = hOpts;
    }

    if (mSel) {
        let mOpts = '';
        for (let m = 0; m < 60; m++) {
            const mStr = String(m).padStart(2, '0');
            mOpts += `<option value="${mStr}">${mStr}</option>`;
        }
        mSel.innerHTML = mOpts;
    }

    if (sSel) {
        let sOpts = '';
        for (let s = 0; s < 60; s++) {
            const sStr = String(s).padStart(2, '0');
            sOpts += `<option value="${sStr}">${sStr}</option>`;
        }
        sSel.innerHTML = sOpts;
    }

    // Set initial realistic time in #einv-time if empty
    const einvTimeEl = document.getElementById('einv-time');
    if (einvTimeEl && !einvTimeEl.value) {
        const randMin = String(Math.floor(Math.random() * 58) + 1).padStart(2, '0');
        const randSec = String(Math.floor(Math.random() * 55) + 5).padStart(2, '0');
        const defaultTime = `11:${randMin}:${randSec}`;
        einvTimeEl.value = defaultTime;
        state.inv_time = defaultTime;
    }
}

function parseTimeStr(str) {
    if (!str || typeof str !== 'string') return { h: 11, m: 15, s: 30 };
    const parts = str.trim().split(':');
    if (parts.length >= 2) {
        const h = parseInt(parts[0], 10);
        const m = parseInt(parts[1], 10);
        const s = parts.length > 2 ? parseInt(parts[2], 10) : 0;
        return {
            h: isNaN(h) ? 11 : Math.max(0, Math.min(23, h)),
            m: isNaN(m) ? 15 : Math.max(0, Math.min(59, m)),
            s: isNaN(s) ? 30 : Math.max(0, Math.min(59, s))
        };
    }
    return { h: 11, m: 15, s: 30 };
}

function openCustomTimePicker(inputId) {
    activeTimeInputId = inputId;
    const inputEl = document.getElementById(inputId);
    const parsed = parseTimeStr(inputEl?.value);

    tpHour = parsed.h;
    tpMin = parsed.m;
    tpSec = parsed.s;

    updateTimePickerControls();

    const modal = document.getElementById('custom-timepicker-modal');
    if (modal) {
        modal.classList.remove('hidden');
        if (tg) tg.HapticFeedback?.impactOccurred('light');
    }
}

function closeCustomTimePicker() {
    const modal = document.getElementById('custom-timepicker-modal');
    if (modal) {
        modal.classList.add('hidden');
    }
    activeTimeInputId = null;
}

function handleTimePickerBackdrop(e) {
    if (e.target.id === 'custom-timepicker-modal') {
        closeCustomTimePicker();
    }
}

function updateTimePickerControls() {
    const hSel = document.getElementById('tp-hour-select');
    const mSel = document.getElementById('tp-min-select');
    const sSel = document.getElementById('tp-sec-select');
    const display = document.getElementById('tp-header-display');

    const hStr = String(tpHour).padStart(2, '0');
    const mStr = String(tpMin).padStart(2, '0');
    const sStr = String(tpSec).padStart(2, '0');

    if (hSel) hSel.value = hStr;
    if (mSel) mSel.value = mStr;
    if (sSel) sSel.value = sStr;

    if (display) {
        display.textContent = `${hStr} : ${mStr} : ${sStr}`;
    }
}

function onTimePickerSelectChange() {
    const hSel = document.getElementById('tp-hour-select');
    const mSel = document.getElementById('tp-min-select');
    const sSel = document.getElementById('tp-sec-select');

    tpHour = parseInt(hSel?.value || '11', 10);
    tpMin = parseInt(mSel?.value || '15', 10);
    tpSec = parseInt(sSel?.value || '30', 10);

    updateTimePickerControls();
    if (tg) tg.HapticFeedback?.selectionChanged();
}

function setTimePickerPreset(preset) {
    const now = new Date();
    if (preset === 'now') {
        tpHour = now.getHours();
        tpMin = now.getMinutes();
        tpSec = now.getSeconds();
    } else if (preset === 'random') {
        tpHour = Math.floor(Math.random() * 8) + 10; // 10 to 17
        tpMin = Math.floor(Math.random() * 58) + 1;  // 1 to 58
        tpSec = Math.floor(Math.random() * 55) + 5;  // 5 to 59
    } else if (preset === 'morning') {
        tpHour = 11;
        tpMin = Math.floor(Math.random() * 30) + 10;
        tpSec = Math.floor(Math.random() * 55) + 5;
    } else if (preset === 'afternoon') {
        tpHour = 15;
        tpMin = Math.floor(Math.random() * 30) + 15;
        tpSec = Math.floor(Math.random() * 55) + 5;
    }

    updateTimePickerControls();
    applyCustomTimePicker();
}

function applyCustomTimePicker() {
    if (!activeTimeInputId) {
        activeTimeInputId = 'einv-time';
    }

    const hStr = String(tpHour).padStart(2, '0');
    const mStr = String(tpMin).padStart(2, '0');
    const sStr = String(tpSec).padStart(2, '0');
    const formatted = `${hStr}:${mStr}:${sStr}`;

    const targetInput = document.getElementById(activeTimeInputId);
    if (targetInput) {
        targetInput.value = formatted;
        targetInput.dispatchEvent(new Event('input', { bubbles: true }));
        targetInput.dispatchEvent(new Event('change', { bubbles: true }));
    }

    state.inv_time = formatted;

    if (tg) tg.HapticFeedback?.notificationOccurred('success');
    closeCustomTimePicker();
}


