/* ═══════════════════════════════════════════════════════════════════════
   MOP Dynamic Custom Adjustment Engine & Live Real-Time Calculation
   ═══════════════════════════════════════════════════════════════════════ */
(function () {
    const BASE_OPTIONS = [
        ['gross_amount', 'Gross RA Bill'],
        ['basic_work', 'Basic Work Value'],
        ['net_work_done', 'Net Work (A-B)'],
        ['our_bill_gross', 'Our Bill Amount'],
        ['our_basic', 'Our Basic Amount']
    ];

    const QUICK_TEMPLATES = [
        'SD for Project',
        'Security Deposit',
        'Testing Charges',
        'Royalty Deduction',
        'Penalty'
    ];

    function adjustmentMarkup(item = {}) {
        const id = `mop-adj-${Date.now()}-${Math.random().toString(16).slice(2)}`;
        const operation = item.operation === 'add' ? 'add' : 'deduct';
        const calculation = item.calculation === 'percent' ? 'percent' : 'fixed';
        const base = item.base || 'gross_amount';
        const labelVal = item.label || '';
        const numVal = (item.value !== undefined && item.value !== null && item.value !== 0) ? item.value : '';

        return `
            <div class="mop-adjustment-row" id="${id}">
                <div class="mop-adjustment-topline">
                    <input class="mop-adj-label" type="text" maxlength="90"
                        value="${escapeHtml(labelVal)}" placeholder="Field name e.g. SD for Project, Security Deposit">
                    <button type="button" class="mop-adj-remove" aria-label="Remove adjustment"
                        onclick="removeMopAdjustment('${id}')">&times;</button>
                </div>
                <div class="mop-adjustment-grid">
                    <select class="mop-adj-operation" title="Deduction or Addition">
                        <option value="deduct" ${operation === 'deduct' ? 'selected' : ''}>Deduction (-)</option>
                        <option value="add" ${operation === 'add' ? 'selected' : ''}>Addition (+)</option>
                    </select>
                    <select class="mop-adj-calculation" title="Fixed INR or Percentage">
                        <option value="fixed" ${calculation === 'fixed' ? 'selected' : ''}>Fixed INR (₹)</option>
                        <option value="percent" ${calculation === 'percent' ? 'selected' : ''}>Percent (%)</option>
                    </select>
                    <input class="mop-adj-value" type="number" min="0" step="0.01"
                        value="${numVal}" placeholder="Amount ₹">
                    <select class="mop-adj-base" ${calculation === 'fixed' ? 'disabled' : ''} title="Base for % calculation">
                        ${BASE_OPTIONS.map(([key, label]) => `<option value="${key}" ${base === key ? 'selected' : ''}>${label}</option>`).join('')}
                    </select>
                </div>
            </div>`;
    }

    function escapeHtml(value) {
        return String(value || '').replace(/[&<>'"]/g, char => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
        })[char]);
    }

    function readRows() {
        return [...document.querySelectorAll('.mop-adjustment-row')].map(row => ({
            label: row.querySelector('.mop-adj-label')?.value.trim() || 'Custom Deduction',
            operation: row.querySelector('.mop-adj-operation')?.value || 'deduct',
            calculation: row.querySelector('.mop-adj-calculation')?.value || 'fixed',
            value: Math.max(0, parseFloat(row.querySelector('.mop-adj-value')?.value) || 0),
            base: row.querySelector('.mop-adj-base')?.value || 'gross_amount'
        })).filter(item => item.label && item.value > 0);
    }

    window.addMopAdjustment = function (item = {}) {
        const list = document.getElementById('mop-adjustments-list');
        if (!list || list.children.length >= 30) return;
        list.insertAdjacentHTML('beforeend', adjustmentMarkup(item));
        const row = list.lastElementChild;
        row.querySelectorAll('input, select').forEach(control => {
            control.addEventListener('input', window.syncMopAdjustments);
            control.addEventListener('change', event => {
                if (event.target.classList.contains('mop-adj-calculation')) {
                    const baseSelect = row.querySelector('.mop-adj-base');
                    if (baseSelect) baseSelect.disabled = event.target.value === 'fixed';
                }
                window.syncMopAdjustments();
            });
        });
        window.syncMopAdjustments();
        const labelInput = row.querySelector('.mop-adj-label');
        const valInput = row.querySelector('.mop-adj-value');
        if (!item.label && labelInput) {
            labelInput.focus();
        } else if (item.label && valInput) {
            valInput.focus();
        }
        window.Telegram?.WebApp?.HapticFeedback?.impactOccurred('light');
    };

    window.addMopQuickTemplate = function (templateName) {
        window.addMopAdjustment({
            label: templateName,
            operation: 'deduct',
            calculation: 'fixed',
            value: 0
        });
    };

    window.removeMopAdjustment = function (id) {
        document.getElementById(id)?.remove();
        window.syncMopAdjustments();
        window.Telegram?.WebApp?.HapticFeedback?.impactOccurred('medium');
    };

    window.syncMopAdjustments = function () {
        state.mop_adjustments = readRows();
        window.updateMopPreview();
    };

    function computedAdjustment(item, bases) {
        const baseValue = Number(bases[item.base]) || 0;
        return item.calculation === 'percent' ? (baseValue * item.value / 100) : item.value;
    }

    window.updateMopPreview = function () {
        const amount = parseFloat(document.getElementById('bill-amount')?.value);
        const preview = document.getElementById('mop-preview');
        if (!amount || amount <= 0) {
            if (preview) preview.style.display = 'none';
            return;
        }

        const cfg = state.mop_config || {};
        const basicWork = amount / 1.18;
        const agencyTds = basicWork * ((cfg.agency_tds_pct || 2) / 100);
        const agencySgst = basicWork * ((cfg.agency_sgst_tds_pct || 1) / 100);
        const agencyCgst = basicWork * ((cfg.agency_cgst_tds_pct || 1) / 100);
        const agencyDeductions = agencyTds + agencySgst + agencyCgst;
        const netWork = amount - agencyDeductions;
        const adminExpense = amount * ((cfg.admin_expense_pct || 3.25) / 100);
        const ourGross = netWork - adminExpense;
        const ourBasic = ourGross / 1.18;
        const ourSgst = ourBasic * 0.09;
        const ourCgst = ourBasic * 0.09;
        const itTds = ourBasic * ((cfg.it_tds_pct || 1) / 100);
        const retention = amount * ((cfg.retention_pct || 2) / 100);
        const labourCess = basicWork * ((cfg.labour_cess_pct || 1) / 100);
        const testingFee = amount * ((cfg.testing_fee_pct || 0.5) / 100);

        const bases = {
            gross_amount: amount,
            basic_work: basicWork,
            net_work_done: netWork,
            our_bill_gross: ourGross,
            our_basic: ourBasic
        };

        const adjustments = state.mop_adjustments || [];
        let customAdditions = 0;
        let customDeductions = 0;
        const previewRows = adjustments.map(item => {
            const computed = computedAdjustment(item, bases);
            if (item.operation === 'add') customAdditions += computed;
            else customDeductions += computed;
            return { ...item, computed };
        });

        const coreDeductions = itTds + retention + labourCess + testingFee;
        const rawNet = ourGross - coreDeductions + customAdditions - customDeductions;
        const autoRoundOff = Math.round(rawNet) - rawNet;
        const effectiveRoundOff = state.is_manual_round_off && state.custom_round_off !== null
            ? state.custom_round_off : autoRoundOff;
        const netPayable = state.is_manual_round_off && state.custom_round_off !== null
            ? Math.round((rawNet + effectiveRoundOff) * 100) / 100 : Math.round(rawNet);

        const setText = (id, value) => {
            const node = document.getElementById(id);
            if (node) node.textContent = value;
        };
        setText('mop-pv-gross', `INR ${fmt(amount)}`);
        setText('mop-pv-agency-ded', `- INR ${fmt(agencyDeductions)}`);
        setText('mop-pv-agency-tds', `INR ${fmt(agencyTds)}`);
        setText('mop-pv-agency-gst', `INR ${fmt(agencySgst + agencyCgst)}`);
        setText('mop-pv-net-ab', `INR ${fmt(netWork)}`);
        setText('mop-pv-admin', `- INR ${fmt(adminExpense)}`);
        setText('mop-pv-our-bill', `INR ${fmt(ourGross)}`);
        setText('mop-pv-our-breakdown', `Basic INR ${fmt(ourBasic)} + GST INR ${fmt(ourSgst + ourCgst)}`);
        setText('mop-pv-our-ded', `- INR ${fmt(coreDeductions + customDeductions - customAdditions)}`);
        setText('mop-pv-net-payable', `INR ${fmt(netPayable)}`);
        setText('mop-pv-words', `"${numToWordsIndian(netPayable)}"`);

        const customPreview = document.getElementById('mop-pv-custom-adjustments');
        if (customPreview) {
            customPreview.innerHTML = previewRows.map(row => `
                <div class="mop-pv-subrow mop-pv-custom-${row.operation}">
                    <span>${escapeHtml(row.label)}</span>
                    <span>${row.operation === 'add' ? '+' : '-'} INR ${fmt(row.computed)}</span>
                </div>`).join('');
            customPreview.style.display = previewRows.length ? 'block' : 'none';
        }

        const roInput = document.getElementById('mop-pv-roundoff-input');
        const badge = document.getElementById('mop-ro-mode-badge');
        const reset = document.getElementById('btn-mop-ro-reset');
        if (roInput && !state.is_manual_round_off) {
            roInput.value = `${autoRoundOff >= 0 ? '+' : ''}${autoRoundOff.toFixed(2)}`;
            roInput.classList.remove('is-custom');
            if (badge) { badge.textContent = 'AUTO'; badge.className = 'ro-badge ro-badge-auto'; }
            if (reset) reset.style.display = 'none';
        }

        lastPreviewData = {
            grand_total: fmt(netPayable),
            grand_total_raw: netPayable,
            mop_raw_net: rawNet,
            mop_calcs: { gross: amount, raw_net: rawNet, round_off: effectiveRoundOff, net_payable: netPayable, our_bill_gross: ourGross }
        };
        if (preview) preview.style.display = 'block';
    };

    function init() {
        state.mop_adjustments = state.mop_adjustments || [];
        const roundOffRow = document.getElementById('mop-pv-roundoff-row');
        if (roundOffRow && !document.getElementById('mop-pv-custom-adjustments')) {
            roundOffRow.insertAdjacentHTML('beforebegin', '<div id="mop-pv-custom-adjustments" style="display:none"></div>');
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
