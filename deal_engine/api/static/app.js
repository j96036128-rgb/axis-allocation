/**
 * Axis Deal Engine - Mandate Management UI
 * Phase 5: Internal mandate creation and management
 * Phase 7: Planning context input and UI surfacing
 */

const API_BASE = '/api';

// State
let mandates = [];
let enums = {};
let selectedMandateIds = new Set();
let precedentCount = 0;

// DOM Elements
const elements = {
    mandatesList: document.getElementById('mandates-list'),
    mandateModal: document.getElementById('mandate-modal'),
    mandateForm: document.getElementById('mandate-form'),
    modalTitle: document.getElementById('modal-title'),
    createBtn: document.getElementById('create-mandate-btn'),
    cancelBtn: document.getElementById('cancel-btn'),
    compareCheckboxes: document.getElementById('compare-checkboxes'),
    compareBtn: document.getElementById('run-compare-btn'),
    compareResults: document.getElementById('compare-results'),
    searchMandate: document.getElementById('search-mandate'),
    listingsJson: document.getElementById('listings-json'),
    searchBtn: document.getElementById('run-search-btn'),
    sampleBtn: document.getElementById('load-sample-btn'),
    searchResults: document.getElementById('search-results'),
};

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    await loadEnums();
    await loadMandates();
    setupEventListeners();
    setupTabs();
    setupWeightCalculation();
    setupPlanningContext();
});

// API Functions
async function apiGet(path) {
    const response = await fetch(`${API_BASE}${path}`);
    return response.json();
}

async function apiPost(path, data) {
    const response = await fetch(`${API_BASE}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
    return response.json();
}

async function apiPut(path, data) {
    const response = await fetch(`${API_BASE}${path}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
    return response.json();
}

async function apiDelete(path) {
    const response = await fetch(`${API_BASE}${path}`, {
        method: 'DELETE',
    });
    return response.json();
}

// Load Functions
async function loadEnums() {
    enums = await apiGet('/enums');
    populateEnumDropdowns();
}

async function loadMandates() {
    const result = await apiGet('/mandates');
    mandates = result.mandates || [];
    renderMandates();
    renderCompareCheckboxes();
    renderSearchDropdown();
}

// Render Functions
function renderMandates() {
    if (mandates.length === 0) {
        elements.mandatesList.innerHTML = `
            <div class="empty-state" style="grid-column: 1 / -1;">
                <h3>No mandates yet</h3>
                <p>Create your first mandate to get started.</p>
            </div>
        `;
        return;
    }

    elements.mandatesList.innerHTML = mandates.map(m => `
        <div class="mandate-card" data-id="${m.mandate_id}">
            <div class="mandate-card-header">
                <div>
                    <h3>${escapeHtml(m.investor_name)}</h3>
                    <span class="mandate-id">${m.mandate_id}</span>
                </div>
                <span class="mandate-status ${m.is_active ? 'active' : 'inactive'}">
                    ${m.is_active ? 'Active' : 'Inactive'}
                </span>
            </div>
            <div class="mandate-card-body">
                <div class="mandate-detail">
                    <span class="mandate-detail-label">Investor Type</span>
                    <span class="mandate-detail-value">${formatEnum(m.investor_type)}</span>
                </div>
                <div class="mandate-detail">
                    <span class="mandate-detail-label">Risk Profile</span>
                    <span class="mandate-detail-value">${formatEnum(m.risk_profile)}</span>
                </div>
                <div class="mandate-detail">
                    <span class="mandate-detail-label">Deal Size</span>
                    <span class="mandate-detail-value">
                        ${formatCurrency(m.financial.min_deal_size)} - ${formatCurrency(m.financial.max_deal_size)}
                    </span>
                </div>
                <div class="mandate-detail">
                    <span class="mandate-detail-label">Target Yield</span>
                    <span class="mandate-detail-value">
                        ${m.financial.min_yield || '-'}% - ${m.financial.target_yield || '-'}%
                    </span>
                </div>
                <div class="mandate-tags">
                    ${m.asset_classes.map(ac => `<span class="tag primary">${formatEnum(ac)}</span>`).join('')}
                    ${m.geographic.regions.slice(0, 2).map(r => `<span class="tag">${r}</span>`).join('')}
                </div>
            </div>
            <div class="mandate-card-actions">
                <button class="btn btn-secondary btn-sm" onclick="editMandate('${m.mandate_id}')">Edit</button>
                <button class="btn btn-danger btn-sm" onclick="deleteMandate('${m.mandate_id}')">Delete</button>
            </div>
        </div>
    `).join('');
}

function renderCompareCheckboxes() {
    elements.compareCheckboxes.innerHTML = mandates.map(m => `
        <label>
            <input type="checkbox" value="${m.mandate_id}"
                   onchange="toggleCompareSelection('${m.mandate_id}')">
            ${escapeHtml(m.investor_name)}
        </label>
    `).join('');
}

function renderSearchDropdown() {
    elements.searchMandate.innerHTML = mandates.map(m =>
        `<option value="${m.mandate_id}">${escapeHtml(m.investor_name)}</option>`
    ).join('');
}

function populateEnumDropdowns() {
    // Investor type
    const investorTypeSelect = document.getElementById('investor_type');
    investorTypeSelect.innerHTML = enums.investor_types.map(t =>
        `<option value="${t}">${formatEnum(t)}</option>`
    ).join('');

    // Risk profile
    const riskProfileSelect = document.getElementById('risk_profile');
    riskProfileSelect.innerHTML = enums.risk_profiles.map(r =>
        `<option value="${r}">${formatEnum(r)}</option>`
    ).join('');

    // Asset classes checkboxes
    const assetClassContainer = document.getElementById('asset_classes_checkboxes');
    assetClassContainer.innerHTML = enums.asset_classes.map(ac => `
        <label>
            <input type="checkbox" name="asset_classes" value="${ac}">
            ${formatEnum(ac)}
        </label>
    `).join('');
}

// Event Listeners
function setupEventListeners() {
    // Navigation
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(`${btn.dataset.view}-view`).classList.add('active');
        });
    });

    // Modal
    elements.createBtn.addEventListener('click', () => openModal());
    elements.cancelBtn.addEventListener('click', () => closeModal());
    document.querySelector('.close-btn').addEventListener('click', () => closeModal());
    elements.mandateModal.addEventListener('click', (e) => {
        if (e.target === elements.mandateModal) closeModal();
    });

    // Form submission
    elements.mandateForm.addEventListener('submit', handleFormSubmit);

    // Compare
    elements.compareBtn.addEventListener('click', runComparison);

    // Search
    elements.searchBtn.addEventListener('click', runSearch);
    elements.sampleBtn.addEventListener('click', loadSampleListings);
}

function setupTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            document.querySelector(`.tab-content[data-tab="${tab}"]`).classList.add('active');
        });
    });
}

function setupWeightCalculation() {
    const weightInputs = document.querySelectorAll('[id^="weight_"]');
    weightInputs.forEach(input => {
        input.addEventListener('input', () => {
            const sum = Array.from(weightInputs).reduce((acc, i) => acc + (parseFloat(i.value) || 0), 0);
            document.getElementById('weight-sum').textContent = sum.toFixed(2);
        });
    });
}

// Modal Functions
function openModal(mandate = null) {
    elements.mandateForm.reset();

    if (mandate) {
        elements.modalTitle.textContent = 'Edit Mandate';
        populateForm(mandate);
    } else {
        elements.modalTitle.textContent = 'New Mandate';
        // Reset weights to defaults
        document.getElementById('weight_location_region').value = '0.15';
        document.getElementById('weight_location_postcode').value = '0.10';
        document.getElementById('weight_price_range').value = '0.20';
        document.getElementById('weight_price_psf').value = '0.05';
        document.getElementById('weight_yield_minimum').value = '0.15';
        document.getElementById('weight_yield_target').value = '0.10';
        document.getElementById('weight_property_size').value = '0.05';
        document.getElementById('weight_property_condition').value = '0.10';
        document.getElementById('weight_property_tenure').value = '0.05';
        document.getElementById('weight_risk_profile').value = '0.05';
    }

    // Reset to first tab
    document.querySelector('.tab-btn').click();

    elements.mandateModal.classList.add('active');
}

function closeModal() {
    elements.mandateModal.classList.remove('active');
}

function populateForm(m) {
    document.getElementById('mandate_id').value = m.mandate_id;
    document.getElementById('investor_name').value = m.investor_name;
    document.getElementById('investor_type').value = m.investor_type;
    document.getElementById('risk_profile').value = m.risk_profile;
    document.getElementById('priority').value = m.priority;
    document.getElementById('is_active').value = m.is_active.toString();
    document.getElementById('notes').value = m.notes || '';

    // Asset classes
    document.querySelectorAll('[name="asset_classes"]').forEach(cb => {
        cb.checked = m.asset_classes.includes(cb.value);
    });

    // Financial
    document.getElementById('min_deal_size').value = m.financial.min_deal_size || '';
    document.getElementById('max_deal_size').value = m.financial.max_deal_size || '';
    document.getElementById('min_yield').value = m.financial.min_yield || '';
    document.getElementById('target_yield').value = m.financial.target_yield || '';
    document.getElementById('max_ltv').value = m.financial.max_ltv || '';
    document.getElementById('max_price_psf').value = m.financial.max_price_psf || '';
    document.getElementById('total_allocation').value = m.financial.total_allocation || '';

    // Geographic
    document.getElementById('regions').value = (m.geographic.regions || []).join(', ');
    document.getElementById('postcodes').value = (m.geographic.postcodes || []).join(', ');
    document.getElementById('exclude_regions').value = (m.geographic.exclude_regions || []).join(', ');
    document.getElementById('exclude_postcodes').value = (m.geographic.exclude_postcodes || []).join(', ');

    // Property
    document.getElementById('min_units').value = m.property.min_units || '';
    document.getElementById('max_units').value = m.property.max_units || '';
    document.getElementById('min_sqft').value = m.property.min_sqft || '';
    document.getElementById('max_sqft').value = m.property.max_sqft || '';
    document.getElementById('accept_turnkey').checked = m.property.accept_turnkey;
    document.getElementById('accept_refurbishment').checked = m.property.accept_refurbishment;
    document.getElementById('accept_development').checked = m.property.accept_development;
    document.getElementById('freehold_only').checked = m.property.freehold_only;
    document.getElementById('min_lease_years').value = m.property.min_lease_years || '';

    // Weights
    if (m.scoring_weights) {
        document.getElementById('weight_location_region').value = m.scoring_weights.location_region;
        document.getElementById('weight_location_postcode').value = m.scoring_weights.location_postcode;
        document.getElementById('weight_price_range').value = m.scoring_weights.price_range;
        document.getElementById('weight_price_psf').value = m.scoring_weights.price_psf;
        document.getElementById('weight_yield_minimum').value = m.scoring_weights.yield_minimum;
        document.getElementById('weight_yield_target').value = m.scoring_weights.yield_target;
        document.getElementById('weight_property_size').value = m.scoring_weights.property_size;
        document.getElementById('weight_property_condition').value = m.scoring_weights.property_condition;
        document.getElementById('weight_property_tenure').value = m.scoring_weights.property_tenure;
        document.getElementById('weight_risk_profile').value = m.scoring_weights.risk_profile;
    }

    // Deal criteria
    if (m.deal_criteria) {
        document.getElementById('min_bmv_percent').value = m.deal_criteria.min_bmv_percent || '';
        document.getElementById('pursue_score_threshold').value = m.deal_criteria.pursue_score_threshold;
        document.getElementById('consider_score_threshold').value = m.deal_criteria.consider_score_threshold;
        document.getElementById('min_overall_score').value = m.deal_criteria.min_overall_score;
        document.getElementById('max_days_on_market').value = m.deal_criteria.max_days_on_market || '';
        document.getElementById('high_conviction_threshold').value = m.deal_criteria.high_conviction_threshold;
        document.getElementById('medium_conviction_threshold').value = m.deal_criteria.medium_conviction_threshold;
    }
}

// Form Submission
async function handleFormSubmit(e) {
    e.preventDefault();

    const mandateId = document.getElementById('mandate_id').value;
    const isEdit = !!mandateId;

    const data = buildMandateData();

    try {
        if (isEdit) {
            await apiPut(`/mandates/${mandateId}`, data);
        } else {
            await apiPost('/mandates', data);
        }

        closeModal();
        await loadMandates();
    } catch (error) {
        alert('Error saving mandate: ' + error.message);
    }
}

function buildMandateData() {
    const data = {
        investor_name: document.getElementById('investor_name').value,
        investor_type: document.getElementById('investor_type').value,
        risk_profile: document.getElementById('risk_profile').value,
        priority: parseInt(document.getElementById('priority').value) || 1,
        is_active: document.getElementById('is_active').value === 'true',
        notes: document.getElementById('notes').value,
        asset_classes: Array.from(document.querySelectorAll('[name="asset_classes"]:checked'))
            .map(cb => cb.value),
        geographic: {
            regions: parseCommaSeparated(document.getElementById('regions').value),
            postcodes: parseCommaSeparated(document.getElementById('postcodes').value),
            exclude_regions: parseCommaSeparated(document.getElementById('exclude_regions').value),
            exclude_postcodes: parseCommaSeparated(document.getElementById('exclude_postcodes').value),
        },
        financial: {
            min_deal_size: parseNumber(document.getElementById('min_deal_size').value),
            max_deal_size: parseNumber(document.getElementById('max_deal_size').value),
            min_yield: parseFloat(document.getElementById('min_yield').value) || null,
            target_yield: parseFloat(document.getElementById('target_yield').value) || null,
            max_ltv: parseFloat(document.getElementById('max_ltv').value) || null,
            max_price_psf: parseFloat(document.getElementById('max_price_psf').value) || null,
            total_allocation: parseNumber(document.getElementById('total_allocation').value),
        },
        property: {
            min_units: parseNumber(document.getElementById('min_units').value),
            max_units: parseNumber(document.getElementById('max_units').value),
            min_sqft: parseNumber(document.getElementById('min_sqft').value),
            max_sqft: parseNumber(document.getElementById('max_sqft').value),
            accept_turnkey: document.getElementById('accept_turnkey').checked,
            accept_refurbishment: document.getElementById('accept_refurbishment').checked,
            accept_development: document.getElementById('accept_development').checked,
            freehold_only: document.getElementById('freehold_only').checked,
            min_lease_years: parseNumber(document.getElementById('min_lease_years').value),
        },
        scoring_weights: {
            location_region: parseFloat(document.getElementById('weight_location_region').value) || 0.15,
            location_postcode: parseFloat(document.getElementById('weight_location_postcode').value) || 0.10,
            price_range: parseFloat(document.getElementById('weight_price_range').value) || 0.20,
            price_psf: parseFloat(document.getElementById('weight_price_psf').value) || 0.05,
            yield_minimum: parseFloat(document.getElementById('weight_yield_minimum').value) || 0.15,
            yield_target: parseFloat(document.getElementById('weight_yield_target').value) || 0.10,
            property_size: parseFloat(document.getElementById('weight_property_size').value) || 0.05,
            property_condition: parseFloat(document.getElementById('weight_property_condition').value) || 0.10,
            property_tenure: parseFloat(document.getElementById('weight_property_tenure').value) || 0.05,
            risk_profile: parseFloat(document.getElementById('weight_risk_profile').value) || 0.05,
        },
        deal_criteria: {
            min_bmv_percent: parseFloat(document.getElementById('min_bmv_percent').value) || null,
            pursue_score_threshold: parseFloat(document.getElementById('pursue_score_threshold').value) || 75,
            consider_score_threshold: parseFloat(document.getElementById('consider_score_threshold').value) || 60,
            min_overall_score: parseFloat(document.getElementById('min_overall_score').value) || 40,
            max_days_on_market: parseNumber(document.getElementById('max_days_on_market').value),
            high_conviction_threshold: parseFloat(document.getElementById('high_conviction_threshold').value) || 0.80,
            medium_conviction_threshold: parseFloat(document.getElementById('medium_conviction_threshold').value) || 0.60,
            low_conviction_threshold: 0.40,
        },
    };

    const mandateId = document.getElementById('mandate_id').value;
    if (mandateId) {
        data.mandate_id = mandateId;
    }

    return data;
}

// CRUD Operations
async function editMandate(mandateId) {
    const mandate = mandates.find(m => m.mandate_id === mandateId);
    if (mandate) {
        openModal(mandate);
    }
}

async function deleteMandate(mandateId) {
    if (!confirm('Are you sure you want to delete this mandate?')) {
        return;
    }

    try {
        await apiDelete(`/mandates/${mandateId}`);
        await loadMandates();
    } catch (error) {
        alert('Error deleting mandate: ' + error.message);
    }
}

// Compare Functions
function toggleCompareSelection(mandateId) {
    if (selectedMandateIds.has(mandateId)) {
        selectedMandateIds.delete(mandateId);
    } else {
        selectedMandateIds.add(mandateId);
    }

    elements.compareBtn.disabled = selectedMandateIds.size < 2;
}

async function runComparison() {
    if (selectedMandateIds.size < 2) return;

    try {
        const result = await apiPost('/compare', {
            mandate_ids: Array.from(selectedMandateIds),
        });

        renderComparisonResults(result);
    } catch (error) {
        alert('Error comparing mandates: ' + error.message);
    }
}

function renderComparisonResults(result) {
    const { comparison } = result;

    elements.compareResults.innerHTML = `
        <div class="comparison-table">
            <h4>Price Ranges</h4>
            <table>
                <thead>
                    <tr>
                        <th>Investor</th>
                        <th>Min Size</th>
                        <th>Max Size</th>
                    </tr>
                </thead>
                <tbody>
                    ${comparison.price_ranges.map(p => `
                        <tr>
                            <td>${escapeHtml(p.investor)}</td>
                            <td>${formatCurrency(p.min)}</td>
                            <td>${formatCurrency(p.max)}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>

        <div class="comparison-table">
            <h4>Yield Requirements</h4>
            <table>
                <thead>
                    <tr>
                        <th>Investor</th>
                        <th>Min Yield</th>
                        <th>Target Yield</th>
                    </tr>
                </thead>
                <tbody>
                    ${comparison.yield_requirements.map(y => `
                        <tr>
                            <td>${escapeHtml(y.investor)}</td>
                            <td>${y.min_yield || '-'}%</td>
                            <td>${y.target_yield || '-'}%</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>

        <div class="comparison-table">
            <h4>Locations</h4>
            <table>
                <thead>
                    <tr>
                        <th>Investor</th>
                        <th>Regions</th>
                        <th>Postcodes</th>
                        <th>Exclusions</th>
                    </tr>
                </thead>
                <tbody>
                    ${comparison.locations.map(l => `
                        <tr>
                            <td>${escapeHtml(l.investor)}</td>
                            <td>${l.regions.join(', ') || '-'}</td>
                            <td>${l.postcodes.join(', ') || '-'}</td>
                            <td>${l.excludes.join(', ') || '-'}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>

        <div class="comparison-table">
            <h4>Asset Classes & Risk</h4>
            <table>
                <thead>
                    <tr>
                        <th>Investor</th>
                        <th>Asset Classes</th>
                        <th>Risk Profile</th>
                    </tr>
                </thead>
                <tbody>
                    ${comparison.asset_classes.map((ac, i) => `
                        <tr>
                            <td>${escapeHtml(ac.investor)}</td>
                            <td>${ac.classes.map(formatEnum).join(', ')}</td>
                            <td>${formatEnum(comparison.risk_profiles[i].profile)}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
}

// Planning Context Functions
function setupPlanningContext() {
    const toggle = document.getElementById('planning-toggle');
    const form = document.getElementById('planning-context-form');
    const addPrecedentBtn = document.getElementById('add-precedent-btn');

    if (toggle && form) {
        toggle.addEventListener('click', () => {
            form.classList.toggle('collapsed');
            const icon = toggle.querySelector('.toggle-icon');
            icon.textContent = form.classList.contains('collapsed') ? '+' : '-';
        });
    }

    if (addPrecedentBtn) {
        addPrecedentBtn.addEventListener('click', addPrecedentRow);
    }
}

function addPrecedentRow() {
    const list = document.getElementById('precedents-list');
    const id = precedentCount++;

    const row = document.createElement('div');
    row.className = 'precedent-row';
    row.id = `precedent-${id}`;
    row.innerHTML = `
        <div class="form-row">
            <div class="form-group">
                <label>Reference</label>
                <input type="text" class="precedent-ref" placeholder="APP/2023/001">
            </div>
            <div class="form-group">
                <label>Type</label>
                <select class="precedent-type">
                    <option value="extension_loft">Loft Conversion</option>
                    <option value="extension_rear">Rear Extension</option>
                    <option value="extension_side">Side Extension</option>
                    <option value="conversion_flats">Convert to Flats</option>
                    <option value="conversion_hmo">Convert to HMO</option>
                    <option value="change_of_use">Change of Use</option>
                    <option value="other">Other</option>
                </select>
            </div>
        </div>
        <div class="form-row">
            <div class="form-group">
                <label>Approved?</label>
                <select class="precedent-approved">
                    <option value="true">Yes</option>
                    <option value="false">No</option>
                </select>
            </div>
            <div class="form-group">
                <label>Distance (m)</label>
                <input type="number" class="precedent-distance" min="0" placeholder="50">
            </div>
            <div class="form-group">
                <label>Recency (years)</label>
                <input type="number" class="precedent-recency" min="0" step="0.5" placeholder="1">
            </div>
            <button type="button" class="btn btn-danger btn-sm remove-precedent" onclick="removePrecedent(${id})">X</button>
        </div>
    `;
    list.appendChild(row);
}

function removePrecedent(id) {
    const row = document.getElementById(`precedent-${id}`);
    if (row) row.remove();
}

function collectPlanningContext() {
    const propertyType = document.getElementById('planning-property-type')?.value;
    const proposedType = document.getElementById('planning-proposed-type')?.value;

    // If no meaningful data entered, return null (skip planning analysis)
    if (!propertyType && !proposedType) {
        return null;
    }

    // Collect precedents
    const precedents = [];
    document.querySelectorAll('.precedent-row').forEach(row => {
        const ref = row.querySelector('.precedent-ref')?.value;
        const type = row.querySelector('.precedent-type')?.value;
        const approved = row.querySelector('.precedent-approved')?.value === 'true';
        const distance = parseFloat(row.querySelector('.precedent-distance')?.value) || null;
        const recency = parseFloat(row.querySelector('.precedent-recency')?.value) || null;

        if (ref || type) {
            const precedent = {
                reference: ref || `PREC-${precedents.length + 1}`,
                precedent_type: type || 'other',
                approved: approved,
                similarity_score: 0.8,  // Default high similarity
            };
            if (distance !== null) precedent.distance_meters = distance;
            if (recency !== null) {
                // Convert recency years to date
                const date = new Date();
                date.setFullYear(date.getFullYear() - recency);
                precedent.decision_date = date.toISOString();
            }
            precedents.push(precedent);
        }
    });

    return {
        property_type: propertyType || '',
        tenure: document.getElementById('planning-tenure')?.value || '',
        current_sqft: parseNumber(document.getElementById('planning-current-sqft')?.value),
        plot_size_sqft: parseNumber(document.getElementById('planning-plot-size')?.value),
        listed_building: document.getElementById('planning-listed')?.checked || false,
        listed_grade: document.getElementById('planning-listed-grade')?.value || '',
        conservation_area: document.getElementById('planning-conservation')?.checked || false,
        article_4_direction: document.getElementById('planning-article4')?.checked || false,
        green_belt: document.getElementById('planning-greenbelt')?.checked || false,
        tree_preservation_orders: document.getElementById('planning-tpo')?.checked || false,
        flood_zone: parseInt(document.getElementById('planning-flood-zone')?.value) || 1,
        proposed_type: proposedType || 'other',
        nearby_precedents: precedents,
    };
}

function resetPlanningContext() {
    // Reset all planning inputs
    document.getElementById('planning-property-type').value = '';
    document.getElementById('planning-tenure').value = '';
    document.getElementById('planning-current-sqft').value = '';
    document.getElementById('planning-plot-size').value = '';
    document.getElementById('planning-listed').checked = false;
    document.getElementById('planning-listed-grade').value = '';
    document.getElementById('planning-conservation').checked = false;
    document.getElementById('planning-article4').checked = false;
    document.getElementById('planning-greenbelt').checked = false;
    document.getElementById('planning-tpo').checked = false;
    document.getElementById('planning-flood-zone').value = '1';
    document.getElementById('planning-proposed-type').value = '';
    document.getElementById('precedents-list').innerHTML = '';
    precedentCount = 0;
}

// Search Functions
async function runSearch() {
    const mandateId = elements.searchMandate.value;
    const listingsJson = elements.listingsJson.value;

    if (!mandateId) {
        alert('Please select a mandate');
        return;
    }

    let listings;
    try {
        listings = JSON.parse(listingsJson);
    } catch (e) {
        alert('Invalid JSON format for listings');
        return;
    }

    // Collect planning context (optional)
    const planningContext = collectPlanningContext();

    try {
        const requestData = {
            mandate_id: mandateId,
            listings: listings,
        };

        // Add planning context if provided
        if (planningContext) {
            requestData.planning_context = planningContext;
        }

        const result = await apiPost('/search', requestData);

        renderSearchResults(result);
    } catch (error) {
        alert('Error running search: ' + error.message);
    }
}

function loadSampleListings() {
    const sampleListings = [
        {
            listing_id: "LST-001",
            source: "manual",
            title: "Prime BTR Block - 8 Units",
            asset_class: "residential",
            tenure: "freehold",
            address: {
                street: "123 High Street",
                city: "London",
                region: "Greater London",
                postcode: "SW1 1AA"
            },
            financial: {
                asking_price: 3500000,
                current_rent: 210000,
                gross_yield: 6.0
            },
            property_details: {
                unit_count: 8,
                total_sqft: 4800,
                condition: "turnkey",
                has_tenants: true
            }
        },
        {
            listing_id: "LST-002",
            source: "manual",
            title: "Licensed HMO - Strong Yield",
            asset_class: "hmo",
            tenure: "freehold",
            address: {
                street: "45 Oak Road",
                city: "Birmingham",
                region: "West Midlands",
                postcode: "B1 2AA"
            },
            financial: {
                asking_price: 550000,
                current_rent: 52000,
                gross_yield: 9.5
            },
            property_details: {
                unit_count: 7,
                condition: "light_refurb",
                has_tenants: true
            }
        },
        {
            listing_id: "LST-003",
            source: "manual",
            title: "Mixed Use - Retail & Residential",
            asset_class: "mixed_use",
            tenure: "leasehold",
            address: {
                street: "78 Station Road",
                city: "London",
                region: "Greater London",
                postcode: "W2 3BA"
            },
            financial: {
                asking_price: 4200000,
                current_rent: 180000,
                gross_yield: 4.3,
                lease_years_remaining: 85
            },
            property_details: {
                unit_count: 4,
                total_sqft: 5200,
                condition: "turnkey",
                has_tenants: true
            }
        }
    ];

    elements.listingsJson.value = JSON.stringify(sampleListings, null, 2);
}

function renderSearchResults(result) {
    const summary = result.summary || {};
    const recommendations = result.recommendations || [];

    elements.searchResults.innerHTML = `
        <div class="search-summary">
            <h3>Search Results for ${escapeHtml(result.mandate_name)}</h3>
            <div class="summary-stats">
                <div class="stat-box">
                    <div class="stat-value pursue">${summary.pursue || 0}</div>
                    <div class="stat-label">Pursue</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value consider">${summary.consider || 0}</div>
                    <div class="stat-label">Consider</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value watch">${summary.watch || 0}</div>
                    <div class="stat-label">Watch</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value pass">${summary.pass || 0}</div>
                    <div class="stat-label">Pass</div>
                </div>
            </div>
        </div>

        ${recommendations.map(r => renderRecommendationCard(r)).join('')}
    `;
}

function renderRecommendationCard(r) {
    const hasBMV = r.bmv_opportunity === true;
    const hasPlanning = r.planning && r.planning.planning_score;
    const planningScore = hasPlanning ? r.planning.planning_score.score : 0;
    const hasPlanningUpside = planningScore >= 60;
    const hasCombinedOpportunity = hasBMV && hasPlanningUpside;

    let cardClass = 'recommendation-card';
    if (hasCombinedOpportunity) {
        cardClass += ' combined-opportunity';
    } else if (hasPlanningUpside) {
        cardClass += ' planning-upside';
    }

    return `
        <div class="${cardClass}">
            ${hasCombinedOpportunity ? `
                <div class="combined-opportunity-banner">
                    <strong>COMBINED OPPORTUNITY</strong>: BMV + Planning Upside
                </div>
            ` : ''}
            <div class="recommendation-header">
                <h4>${escapeHtml(r.headline)}</h4>
                <div class="badges">
                    <span class="action-badge ${r.action}">${r.action.toUpperCase()}</span>
                    ${hasBMV ? '<span class="tag bmv">BMV</span>' : ''}
                    ${hasPlanningUpside ? `<span class="tag planning-tag">${r.planning.planning_score.label.toUpperCase()}</span>` : ''}
                </div>
            </div>
            <div class="recommendation-body">
                <div class="recommendation-meta">
                    <span>Score: ${r.score}/100</span>
                    <span>Grade: ${r.grade}</span>
                    <span>Conviction: ${r.conviction}</span>
                    <span>Priority: ${r.priority_rank}</span>
                </div>
                ${hasPlanning ? renderPlanningSection(r.planning) : ''}
            </div>
        </div>
    `;
}

function renderPlanningSection(planning) {
    const score = planning.planning_score;
    const uplift = planning.uplift_estimate;
    const hasUplift = uplift && (uplift.percent_range.mid > 0 || uplift.value_range.mid > 0);

    return `
        <div class="planning-section">
            <div class="planning-header">
                <div class="planning-score-display">
                    <span class="planning-score ${score.label}">${score.score}</span>
                    <span class="planning-label">${formatEnum(score.label)} Planning Potential</span>
                </div>
                ${hasUplift ? `
                    <div class="planning-uplift">
                        <span class="uplift-value">+${uplift.percent_range.low.toFixed(0)}% - ${uplift.percent_range.high.toFixed(0)}%</span>
                        <span class="uplift-label">Est. Uplift</span>
                    </div>
                ` : ''}
            </div>

            <div class="planning-details">
                <div class="planning-components">
                    <span title="Precedent Score">Precedent: ${score.components.precedent_score}</span>
                    <span title="Feasibility Score">Feasibility: ${score.components.feasibility_score}</span>
                    <span title="Uplift Score">Uplift: ${score.components.uplift_score}</span>
                </div>

                ${planning.positive_factors && planning.positive_factors.length > 0 ? `
                    <div class="planning-factors positive">
                        <strong>Positives:</strong>
                        <ul>${planning.positive_factors.slice(0, 3).map(f => `<li>${escapeHtml(f)}</li>`).join('')}</ul>
                    </div>
                ` : ''}

                ${planning.negative_factors && planning.negative_factors.length > 0 ? `
                    <div class="planning-factors negative">
                        <strong>Concerns:</strong>
                        <ul>${planning.negative_factors.slice(0, 3).map(f => `<li>${escapeHtml(f)}</li>`).join('')}</ul>
                    </div>
                ` : ''}

                ${planning.rationale && planning.rationale.length > 0 ? `
                    <div class="planning-rationale">
                        <strong>Analysis:</strong> ${escapeHtml(planning.rationale[0])}
                    </div>
                ` : ''}
            </div>

            <div class="planning-disclaimer-inline">
                ${escapeHtml(planning.disclaimer)}
            </div>
        </div>
    `;
}

// Utility Functions
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatEnum(value) {
    if (!value) return '-';
    return value.split('_').map(word =>
        word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');
}

function formatCurrency(value) {
    if (!value) return '-';
    return '£' + value.toLocaleString();
}

function parseCommaSeparated(value) {
    if (!value) return [];
    return value.split(',').map(s => s.trim()).filter(s => s.length > 0);
}

function parseNumber(value) {
    if (!value) return null;
    const num = parseInt(value, 10);
    return isNaN(num) ? null : num;
}
