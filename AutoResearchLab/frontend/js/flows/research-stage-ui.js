/**
 * Stage/UI/navigation logic extracted from research.js.
 */
(function () {
    'use strict';
    const toast = window.MAARS.toast;

    function _isStagePrerequisiteCompleted(ctx, stage) {
        const order = ['refine', 'plan', 'execute', 'paper'];
        const idx = order.indexOf(String(stage || '').trim());
        if (idx <= 0) return true;
        const stageStatusDetails = ctx.getStageStatusDetails();
        for (let i = 0; i < idx; i += 1) {
            const prev = order[i];
            const prevStatus = String(stageStatusDetails?.[prev]?.status || 'idle').trim() || 'idle';
            if (prevStatus !== 'completed') return false;
        }
        return true;
    }

    function renderStageStatusDetails(ctx) {
        const stageStatusDetails = ctx.getStageStatusDetails();
        const currentStageState = ctx.getCurrentStageState();
        const runningStage = Object.entries(stageStatusDetails).find(([, info]) => String(info?.status || '') === 'running')?.[0] || '';

        Object.entries(ctx.stageMetaEls || {}).forEach(([stage, metaEl]) => {
            if (!metaEl) return;
            const info = stageStatusDetails[stage] || { status: 'idle', message: 'idle' };
            const status = String(info.status || 'idle').trim() || 'idle';
            const message = String(info.message || status).trim() || status;
            metaEl.textContent = `${status} · ${message}`;
        });

        Object.entries(ctx.stageActionBtns || {}).forEach(([stage, actions]) => {
            const info = stageStatusDetails[stage] || { status: 'idle' };
            const status = String(info.status || 'idle').trim() || 'idle';
            const stageStarted = !!currentStageState?.[stage]?.started;
            const isRunningSelf = status === 'running';
            const executeRunnerActive = stage === 'execute' && !!(ctx.getExecutionRuntimeStatus()?.running);
            const isBusySelf = isRunningSelf || executeRunnerActive;
            const hasOtherRunning = !!runningStage && runningStage !== stage;
            const blocked = hasOtherRunning;
            const prereqOk = _isStagePrerequisiteCompleted(ctx, stage);
            if (actions?.run) actions.run.disabled = blocked || !prereqOk || isBusySelf;
            if (actions?.resume) actions.resume.disabled = blocked || !prereqOk || isBusySelf || !(status === 'stopped' || status === 'failed');
            if (actions?.retry) actions.retry.disabled = blocked || !prereqOk || isBusySelf || !(stageStarted || status === 'failed' || status === 'stopped');
            if (actions?.stop) actions.stop.disabled = blocked || !(isRunningSelf || executeRunnerActive);
        });
    }

    function renderStageButtons(ctx, activeStage) {
        const order = ['refine', 'plan', 'execute', 'paper'];
        const current = String(activeStage || '').trim() || String(window.MAARS?.researchCurrentStage || '') || 'refine';
        const currentStageState = ctx.getCurrentStageState();
        const currentRank = order.indexOf(current);

        Object.entries(ctx.stageButtons || {}).forEach(([stage, btn]) => {
            if (!btn) return;
            const started = !!currentStageState?.[stage]?.started;
            const stageRank = order.indexOf(stage);
            btn.disabled = !started;
            btn.setAttribute('aria-disabled', started ? 'false' : 'true');
            btn.classList.toggle('is-started', started);
            btn.classList.toggle('is-active', stage === current);
            btn.classList.toggle('is-completed', started && currentRank >= 0 && stageRank >= 0 && stageRank < currentRank);
        });

        renderStageStatusDetails(ctx);
    }

    function setStageStarted(ctx, stage, started) {
        const current = ctx.getCurrentStageState();
        if (!current?.[stage]) return;
        ctx.setCurrentStageState({
            ...current,
            [stage]: {
                ...(current[stage] || {}),
                started: !!started,
            },
        });
        renderStageButtons(ctx);
    }

    function _setPanelActive(panelEl, on) {
        if (!panelEl) return;
        panelEl.classList.toggle('is-active', !!on);
    }

    function _loadExecuteSplitRatio(ctx) {
        try {
            const raw = localStorage.getItem('maars-execute-split-ratio');
            const val = Number(raw);
            if (Number.isFinite(val)) ctx.setExecuteSplitRatio(Math.max(35, Math.min(90, val)));
        } catch (_) { }
    }

    function _saveExecuteSplitRatio(ctx) {
        try {
            localStorage.setItem('maars-execute-split-ratio', String(ctx.getExecuteSplitRatio()));
        } catch (_) { }
    }

    function _applyExecuteSplitRatio(ctx) {
        if (!ctx.panelWorkbench) return;
        ctx.panelWorkbench.style.setProperty('--execute-left-ratio', String(ctx.getExecuteSplitRatio()));
    }

    function setTreeView(ctx, view) {
        const v = String(view || '').trim();
        (ctx.treeTabButtons || []).forEach((btn) => {
            const isActive = (btn.getAttribute('data-view') || '') === v;
            btn.classList.toggle('active', isActive);
            btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
        });
        (ctx.treePanels || []).forEach((p) => {
            const isActive = (p.getAttribute('data-view-panel') || '') === v;
            p.classList.toggle('active', isActive);
        });
    }

    function setActiveStage(ctx, stage) {
        const s = String(stage || '').trim();
        ctx.setActiveStageValue(s);
        window.MAARS = window.MAARS || {};
        window.MAARS.researchCurrentStage = s;
        renderStageButtons(ctx, s);
        ctx.syncExecuteElapsedTicker();

        _setPanelActive(ctx.panelRefine, s === 'refine');
        _setPanelActive(ctx.panelWorkbench, s === 'plan' || s === 'execute');
        _setPanelActive(ctx.panelPaper, s === 'paper');

        if (ctx.panelWorkbench) {
            ctx.panelWorkbench.classList.toggle('research-workbench--plan', s === 'plan');
            ctx.panelWorkbench.classList.toggle('research-workbench--execute', s === 'execute');
        }

        if (ctx.executeStreamEl) {
            ctx.executeStreamEl.hidden = !(s === 'execute');
        }

        if (s === 'plan') {
            setTreeView(ctx, 'decomposition');
        } else if (s === 'execute') {
            _applyExecuteSplitRatio(ctx);
            setTreeView(ctx, 'execution');
            ctx.scheduleExecutionGraphRender({ force: true, delays: [0, 100, 320, 700] });
            ctx.renderExecuteStream();
            ctx.refreshExecutionRuntimeStatus();
        }

        if (s === 'refine') ctx.renderRefinePanel();
        if (s === 'paper') ctx.renderPaperPanel();
    }

    function _getQueryParam(ctx, name) {
        const navUtils = ctx.navUtils || {};
        if (typeof navUtils.getQueryParam === 'function') return navUtils.getQueryParam(name);
        try {
            const params = new URLSearchParams(window.location.search || '');
            return (params.get(name) || '').trim();
        } catch (_) {
            return '';
        }
    }

    function getResearchIdFromUrl(ctx) {
        const navUtils = ctx.navUtils || {};
        if (typeof navUtils.getResearchIdFromUrl === 'function') return navUtils.getResearchIdFromUrl();
        const byQuery = _getQueryParam(ctx, 'researchId') || _getQueryParam(ctx, 'rid');
        if (byQuery) return byQuery;
        const hash = (window.location.hash || '').replace(/^#/, '');
        const m = hash.match(/^\/r\/(.+)$/);
        if (m) return decodeURIComponent(m[1]);
        return '';
    }

    function navigateToCreateResearch(ctx) {
        const navUtils = ctx.navUtils || {};
        if (typeof navUtils.navigateToCreateResearch === 'function') {
            navUtils.navigateToCreateResearch();
            return;
        }
        window.location.href = 'research.html';
    }

    function navigateToResearch(ctx, researchId) {
        const navUtils = ctx.navUtils || {};
        if (typeof navUtils.navigateToResearch === 'function') {
            navUtils.navigateToResearch(researchId);
            return;
        }
        if (!researchId) return;
        window.location.href = `research_detail.html?researchId=${encodeURIComponent(researchId)}`;
    }

    function scrollToDetails(ctx) {
        const navUtils = ctx.navUtils || {};
        if (typeof navUtils.scrollToDetails === 'function') {
            navUtils.scrollToDetails();
            return;
        }
        const host = document.getElementById('researchDetailHost');
        if (!host) return;
        host.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function initStageNav(ctx) {
        Object.entries(ctx.stageButtons || {}).forEach(([stage, btn]) => {
            if (!btn) return;
            btn.addEventListener('click', () => {
                if (btn.disabled) return;
                setActiveStage(ctx, stage);
            });
        });
    }

    function initTreeTabs(ctx) {
        const treeTabButtons = ctx.treeTabButtons || [];
        if (!treeTabButtons.length) return;
        treeTabButtons.forEach((btn) => {
            btn.addEventListener('click', () => {
                const view = String(btn.getAttribute('data-view') || '').trim();
                if (!view) return;
                setTreeView(ctx, view);
            });
        });
        document.addEventListener('maars:switch-to-output-tab', () => {
            if (ctx.getActiveStage() === 'execute') setTreeView(ctx, 'output');
        });
    }

    function initExecuteSplitter(ctx) {
        if (!ctx.executeSplitterEl || !ctx.panelWorkbench) return;

        _loadExecuteSplitRatio(ctx);
        _applyExecuteSplitRatio(ctx);

        let dragging = false;

        const onPointerMove = (e) => {
            if (!dragging) return;
            const rect = ctx.panelWorkbench.getBoundingClientRect();
            if (!rect || rect.width <= 0) return;
            const x = Number(e.clientX || 0);
            const pct = ((x - rect.left) / rect.width) * 100;
            ctx.setExecuteSplitRatio(Math.max(35, Math.min(90, pct)));
            _applyExecuteSplitRatio(ctx);
        };

        const stopDrag = () => {
            if (!dragging) return;
            dragging = false;
            document.body.style.userSelect = '';
            document.body.style.cursor = '';
            _saveExecuteSplitRatio(ctx);
            window.removeEventListener('pointermove', onPointerMove);
            window.removeEventListener('pointerup', stopDrag);
            window.removeEventListener('pointercancel', stopDrag);
        };

        ctx.executeSplitterEl.addEventListener('pointerdown', (e) => {
            if (ctx.getActiveStage() !== 'execute') return;
            dragging = true;
            document.body.style.userSelect = 'none';
            document.body.style.cursor = 'col-resize';
            try { ctx.executeSplitterEl.setPointerCapture(e.pointerId); } catch (_) { }
            window.addEventListener('pointermove', onPointerMove);
            window.addEventListener('pointerup', stopDrag);
            window.addEventListener('pointercancel', stopDrag);
        });
    }

    async function createResearchFromHome(ctx) {
        const prompt = (ctx.promptInput?.value || '').trim();
        if (!prompt) return;
        if (ctx.createBtn) ctx.createBtn.disabled = true;
        try {
            const { researchId } = await ctx.api.createResearch(prompt);
            if (!researchId) throw new Error('Create failed');
            document.dispatchEvent(new CustomEvent('maars:research-list-refresh'));
            navigateToResearch(ctx, researchId);
        } catch (e) {
            console.error(e);
            toast.error(e?.message || 'Failed to create research');
        } finally {
            if (ctx.createBtn) ctx.createBtn.disabled = false;
        }
    }

    function initDetailControls(ctx, researchId) {
        const bindStageAction = (stage, action, handler) => {
            const btn = ctx.stageActionBtns?.[stage]?.[action];
            if (!btn) return;
            btn.addEventListener('click', async () => {
                if (!researchId) return;
                if (action !== 'stop' && !_isStagePrerequisiteCompleted(ctx, stage)) {
                    toast.warning(`Cannot start ${stage} stage before previous stage is completed.`);
                    renderStageStatusDetails(ctx);
                    return;
                }
                btn.disabled = true;
                try {
                    await handler();
                    document.dispatchEvent(new CustomEvent('maars:research-list-refresh'));
                } catch (e) {
                    console.error(e);
                    const msg = String(e?.message || '').trim();
                    if (/already running|409/i.test(msg)) {
                        // Keep UI in sync with backend state and avoid noisy alerts.
                        ctx.loadResearch?.(researchId).catch(() => {});
                    } else {
                        toast.error(msg || `Failed to ${action} stage`);
                    }
                } finally {
                    renderStageStatusDetails(ctx);
                }
            });
        };

        ['refine', 'plan', 'execute', 'paper'].forEach((stage) => {
            bindStageAction(stage, 'run', async () => {
                await ctx.api.runResearchStage(researchId, stage);
                if (stage === 'execute') {
                    ctx.resetExecuteTimelineForNewRun();
                    if (ctx.getActiveStage() === 'execute') {
                        ctx.scheduleExecutionGraphRender({ force: true, delays: [0, 100, 320, 700] });
                        ctx.renderExecuteStream();
                    }
                }
                setActiveStage(ctx, stage);
            });
            bindStageAction(stage, 'resume', async () => {
                await ctx.api.resumeResearchStage(researchId, stage);
                setActiveStage(ctx, stage);
            });
            bindStageAction(stage, 'retry', async () => {
                await ctx.api.retryResearchStage(researchId, stage);
                if (stage === 'execute') {
                    ctx.resetExecuteTimelineForNewRun();
                    if (ctx.getActiveStage() === 'execute') {
                        ctx.scheduleExecutionGraphRender({ force: true, delays: [0, 100, 320, 700] });
                        ctx.renderExecuteStream();
                    }
                }
                setActiveStage(ctx, stage);
            });
            bindStageAction(stage, 'stop', async () => {
                await ctx.api.stopResearchStage(researchId, stage);
            });
        });
    }

    function init(ctx) {
        initStageNav(ctx);
        initTreeTabs(ctx);
        initExecuteSplitter(ctx);
        ctx.initExecuteStreamControls();
        ctx.initEventBridges();

        if (ctx.homeView && ctx.promptInput && ctx.createBtn) {
            ctx.createBtn.addEventListener('click', () => createResearchFromHome(ctx));
            try {
                if (/research\.html$/.test(window.location.pathname || '')) {
                    ctx.promptInput.focus();
                }
            } catch (_) { }
        }

        if (ctx.researchView) {
            const rid = getResearchIdFromUrl(ctx);
            if (rid) {
                initDetailControls(ctx, rid);
                setActiveStage(ctx, 'refine');
                ctx.renderExecutionRuntimeStatus({ enabled: true, available: true, connected: false });
                ctx.loadResearch(rid).catch((e) => {
                    console.error(e);
                    toast.error(e?.message || 'Failed to load research');
                    navigateToCreateResearch(ctx);
                });
            } else {
                navigateToCreateResearch(ctx);
            }
        }
    }

    window.MAARS = window.MAARS || {};
    window.MAARS.researchStageUI = {
        setStageStarted,
        isStagePrerequisiteCompleted: _isStagePrerequisiteCompleted,
        renderStageButtons,
        renderStageStatusDetails,
        setTreeView,
        setActiveStage,
        getQueryParam: _getQueryParam,
        getResearchIdFromUrl,
        navigateToCreateResearch,
        navigateToResearch,
        scrollToDetails,
        initStageNav,
        initTreeTabs,
        initExecuteSplitter,
        createResearchFromHome,
        initDetailControls,
        init,
    };
})();
