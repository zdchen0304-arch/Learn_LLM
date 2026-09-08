/**
 * MAARS Settings sync helpers.
 * Handles UI syncing and form-to-state reading for settings modal.
 */
(function () {
    'use strict';

    function syncThemeCardsActive() {
        const current = document.documentElement.getAttribute('data-theme') || 'light';
        document.querySelectorAll('.settings-theme-card').forEach((el) => {
            el.classList.toggle('active', el.dataset.pick === current);
        });
    }

    function syncMatrixActive(agentMode) {
        const am = agentMode || {};
        document.querySelectorAll('#settingsModeMatrix .settings-mode-cell').forEach((el) => {
            el.classList.toggle('active', am[el.dataset.row] === el.dataset.col);
        });
    }

    function syncReflectionUI(reflection) {
        const r = reflection || {};
        const cb = document.getElementById('reflectionEnabled');
        const mi = document.getElementById('reflectionMaxIterations');
        const qt = document.getElementById('reflectionQualityThreshold');
        if (cb) cb.checked = !!r.enabled;
        if (mi) mi.value = r.maxIterations ?? 2;
        if (qt) qt.value = r.qualityThreshold ?? 70;
    }

    function syncIdeaRAGUI(agentMode) {
        const cb = document.getElementById('ideaRAGEnabled');
        if (cb) cb.checked = !!(agentMode || {}).ideaRAG;
    }

    function syncLiteratureSourceUI(agentMode) {
        const select = document.getElementById('ideaLiteratureSource');
        if (!select) return;
        const value = String((agentMode || {}).literatureSource || 'openalex').trim().toLowerCase();
        select.value = value === 'arxiv' ? 'arxiv' : 'openalex';
    }

    function readIdeaRAGFromUI(agentMode, defaults) {
        const cb = document.getElementById('ideaRAGEnabled');
        const merged = { ...(defaults || {}), ...(agentMode || {}) };
        merged.ideaRAG = cb ? cb.checked : false;
        return merged;
    }

    function readLiteratureSourceFromUI(agentMode, defaults) {
        const select = document.getElementById('ideaLiteratureSource');
        const merged = { ...(defaults || {}), ...(agentMode || {}) };
        const value = String(select?.value || 'openalex').trim().toLowerCase();
        merged.literatureSource = (value === 'arxiv') ? 'arxiv' : 'openalex';
        return merged;
    }

    function readReflectionFromUI(defaults) {
        const cb = document.getElementById('reflectionEnabled');
        const mi = document.getElementById('reflectionMaxIterations');
        const qt = document.getElementById('reflectionQualityThreshold');
        const base = { ...(defaults || {}) };
        return {
            ...base,
            enabled: cb ? cb.checked : false,
            maxIterations: mi ? Math.max(1, Math.min(5, parseInt(mi.value, 10) || 2)) : 2,
            qualityThreshold: qt ? Math.max(0, Math.min(100, parseInt(qt.value, 10) || 70)) : 70,
        };
    }

    window.MAARS = window.MAARS || {};
    window.MAARS.settingsSyncHelpers = {
        syncThemeCardsActive,
        syncMatrixActive,
        syncReflectionUI,
        syncIdeaRAGUI,
        syncLiteratureSourceUI,
        readIdeaRAGFromUI,
        readLiteratureSourceFromUI,
        readReflectionFromUI,
    };
})();
