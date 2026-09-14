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
        const labels = {
            refine: '问题细化', plan: '研究规划', execute: '实验执行', paper: '论文撰写', review: '论文审查',
            idle: '未开始', pending: '等待中', queued: '已入队', running: '执行中', completed: '已完成',
            passed: '已通过', blocked: '被阻塞', failed: '失败', stopped: '已停止', needs_revision: '需要修改',
            supervisor: '总监', lead: '负责人', worker: '执行 Agent',
        };
        const raw = String(value || 'pending');
        return labels[raw] || raw.replace(/_/g, ' ');
    }

    function renderOrganization(nodes) {
        organizationEl.innerHTML = (Array.isArray(nodes) ? nodes : []).map((node) => {
            const kind = String(node?.kind || 'worker');
            return `<div class="control-tower-node control-tower-node--${escapeHtml(kind)}">
                <span>${escapeHtml(node?.name || 'Unnamed agent')}</span>
                <span class="control-tower-node-kind">${escapeHtml(kind)}</span>
            </div>`;
        }).join('') || '<div class="control-tower-caption">暂时没有可展示的委派关系。</div>';
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
        }).join('') || '<div class="control-tower-caption">暂时没有可展示的质量门。</div>';
    }

    function renderContracts(contracts) {
        contractsEl.innerHTML = (Array.isArray(contracts) ? contracts : []).map((contract) => {
            const dependencies = (contract?.dependsOn || []).join(', ') || '无';
            const outputs = (contract?.expectedOutputs || []).join(', ') || '产物';
            const status = String(contract?.status || 'pending');
            return `<div class="control-tower-contract">
                <div class="control-tower-contract-copy">
                    <div class="control-tower-contract-title">${escapeHtml(contract?.owner || 'Worker')} · ${escapeHtml(contract?.goal || '')}</div>
                    <div class="control-tower-contract-meta">编号：${escapeHtml(contract?.contractId || '')} · 依赖：${escapeHtml(dependencies)} · 交付：${escapeHtml(outputs)}</div>
                </div>
                <span class="control-tower-contract-status" data-status="${escapeHtml(status)}">${escapeHtml(label(status))}</span>
            </div>`;
        }).join('') || '<div class="control-tower-caption">暂时没有可展示的阶段交接契约。</div>';
    }

    function renderEvidence(trail) {
        evidenceEl.innerHTML = (Array.isArray(trail) ? trail : []).map((artifact) => {
            const dependencies = (artifact?.dependsOn || []).join(', ') || '源产物';
            return `<div class="control-tower-evidence-item">
                <div class="control-tower-evidence-label">${escapeHtml(artifact?.label || artifact?.artifactId || 'Artifact')}</div>
                <div class="control-tower-evidence-meta">${escapeHtml(artifact?.kind || '产物')} · 由 ${escapeHtml(artifact?.producedBy || '执行 Agent')} 生成 · 依赖 ${escapeHtml(dependencies)}</div>
            </div>`;
        }).join('') || '<div class="control-tower-caption">Agent 持久化文献、实验或论文产物后，证据链会显示在这里。</div>';
    }

    function render(snapshot) {
        const director = snapshot?.director || {};
        const artifacts = snapshot?.artifactSummary || {};
        const stageStatus = String(director.stageStatus || 'idle');
        host.hidden = false;
        statusEl.textContent = `${director.activeStage || 'refine'} · ${label(stageStatus)}`;
        statusEl.dataset.status = stageStatus;
        decisionEl.textContent = director.decision || '研究总监正在准备阶段交接契约。';
        const metrics = [
            `${Number(artifacts.literatureCount || 0)} 篇文献`,
            `${Number(artifacts.planTaskCount || 0)} 个规划任务`,
            `${Number(artifacts.executionOutputCount || 0)} 个实验产物`,
            artifacts.hasPaperDraft ? '论文草稿已生成' : '暂无论文草稿',
            artifacts.hasPaperQualityReview ? `${Number(artifacts.paperReviewBlockingIssueCount || 0)} 个审查阻塞项` : '论文审查待执行',
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
