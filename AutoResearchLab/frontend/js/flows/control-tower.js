/**
 * Research Control Tower - an inspectable control-plane view.
 * It intentionally renders organization, gates, and task contracts separately
 * from the workbench's task DAG and persisted evidence artifacts.
 */
(function () {
    'use strict';

    const cfg = window.MAARS?.config;
    const host = document.getElementById('researchControlTower');
    const decisionEl = document.getElementById('controlTowerDecision');
    const statusEl = document.getElementById('controlTowerStageStatus');
    const summaryEl = document.getElementById('controlTowerSummary');
    const organizationEl = document.getElementById('controlTowerOrganization');
    const gatesEl = document.getElementById('controlTowerGates');
    const contractsEl = document.getElementById('controlTowerContracts');
    const evidenceEl = document.getElementById('controlTowerEvidence');
    if (!cfg || !host || !decisionEl || !statusEl || !summaryEl || !organizationEl || !gatesEl || !contractsEl || !evidenceEl) return;

    function escapeHtml(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function label(value) {
        return String(value || 'pending').replace(/_/g, ' ');
    }

    function renderOrganization(nodes) {
        organizationEl.innerHTML = (Array.isArray(nodes) ? nodes : []).map((node) => {
            const kind = String(node?.kind || 'worker');
            return `<div class="control-tower-node control-tower-node--${escapeHtml(kind)}">
                <span>${escapeHtml(node?.name || 'Unnamed agent')}</span>
                <span class="control-tower-node-kind">${escapeHtml(kind)}</span>
            </div>`;
        }).join('') || '<div class="control-tower-caption">No delegation map available.</div>';
    }

    function renderGates(gates) {
        gatesEl.innerHTML = (Array.isArray(gates) ? gates : []).map((gate) => {
            const status = String(gate?.status || 'pending');
            return `<div class="control-tower-gate">
                <div class="control-tower-gate-copy">
                    <div class="control-tower-gate-title">${escapeHtml(gate?.stage || 'stage')}</div>
                    <div class="control-tower-gate-reason">${escapeHtml(gate?.reason || '')}</div>
                </div>
                <span class="control-tower-gate-status" data-status="${escapeHtml(status)}">${escapeHtml(label(status))}</span>
            </div>`;
        }).join('') || '<div class="control-tower-caption">No quality gates available.</div>';
    }

    function renderContracts(contracts) {
        contractsEl.innerHTML = (Array.isArray(contracts) ? contracts : []).map((contract) => {
            const dependencies = (contract?.dependsOn || []).join(', ') || 'none';
            const outputs = (contract?.expectedOutputs || []).join(', ') || 'artifact';
            const status = String(contract?.status || 'pending');
            return `<div class="control-tower-contract">
                <div class="control-tower-contract-copy">
                    <div class="control-tower-contract-title">${escapeHtml(contract?.owner || 'Worker')} · ${escapeHtml(contract?.goal || '')}</div>
                    <div class="control-tower-contract-meta">ID: ${escapeHtml(contract?.contractId || '')} · depends on: ${escapeHtml(dependencies)} · delivers: ${escapeHtml(outputs)}</div>
                </div>
                <span class="control-tower-contract-status" data-status="${escapeHtml(status)}">${escapeHtml(label(status))}</span>
            </div>`;
        }).join('') || '<div class="control-tower-caption">No task contracts available.</div>';
    }

    function renderEvidence(trail) {
        evidenceEl.innerHTML = (Array.isArray(trail) ? trail : []).map((artifact) => {
            const dependencies = (artifact?.dependsOn || []).join(', ') || 'source artifact';
            return `<div class="control-tower-evidence-item">
                <div class="control-tower-evidence-label">${escapeHtml(artifact?.label || artifact?.artifactId || 'Artifact')}</div>
                <div class="control-tower-evidence-meta">${escapeHtml(artifact?.kind || 'artifact')} · by ${escapeHtml(artifact?.producedBy || 'worker')} · from ${escapeHtml(dependencies)}</div>
            </div>`;
        }).join('') || '<div class="control-tower-caption">Evidence will appear as agents persist artifacts.</div>';
    }

    function render(snapshot) {
        const director = snapshot?.director || {};
        const artifacts = snapshot?.artifactSummary || {};
        const stageStatus = String(director.stageStatus || 'idle');
        host.hidden = false;
        statusEl.textContent = `${director.activeStage || 'refine'} · ${label(stageStatus)}`;
        statusEl.dataset.status = stageStatus;
        decisionEl.textContent = director.decision || 'The Research Director is preparing delegation contracts.';
        const metrics = [
            `${Number(artifacts.literatureCount || 0)} literature items`,
            `${Number(artifacts.planTaskCount || 0)} planned tasks`,
            `${Number(artifacts.executionOutputCount || 0)} evidence outputs`,
            artifacts.hasPaperDraft ? 'paper draft available' : 'no paper draft',
            artifacts.hasPaperQualityReview ? `${Number(artifacts.paperReviewBlockingIssueCount || 0)} blocking review issues` : 'review pending',
        ];
        summaryEl.innerHTML = metrics.map((metric) => `<span class="control-tower-metric">${escapeHtml(metric)}</span>`).join('');
        renderOrganization(snapshot?.agentOrganization);
        renderGates(snapshot?.qualityGates);
        renderContracts(snapshot?.taskContracts);
        renderEvidence(snapshot?.evidenceTrail);
    }

    async function refresh(researchId) {
        const id = String(researchId || cfg.getCurrentResearchId?.() || '').trim();
        if (!id) return null;
        const response = await cfg.fetchWithSession(`${cfg.API_BASE_URL}/research/${encodeURIComponent(id)}/control-tower`, { cache: 'no-store' });
        if (!response.ok) throw new Error(`Control Tower ${response.status}`);
        const snapshot = await response.json();
        if (id === String(cfg.getCurrentResearchId?.() || id)) render(snapshot);
        return snapshot;
    }

    function refreshCurrent() {
        refresh().catch((error) => console.warn('Control Tower refresh failed', error));
    }

    document.addEventListener('maars:research-stage', (event) => {
        const id = String(event?.detail?.researchId || '').trim();
        if (!id || id === String(cfg.getCurrentResearchId?.() || '')) refreshCurrent();
    });
    document.addEventListener('maars:paper-complete', refreshCurrent);
    document.addEventListener('maars:paper-review-complete', refreshCurrent);

    window.MAARS = window.MAARS || {};
    window.MAARS.controlTower = { refresh, render };
})();
