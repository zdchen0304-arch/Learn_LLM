/**
 * Core research state helpers extracted from research.js.
 */
(function () {
    'use strict';

    function stringifyOutput(ctx, val) {
        if (typeof ctx.executeUtils.stringifyOutput === 'function') {
            return ctx.executeUtils.stringifyOutput(val);
        }
        return String(val || '');
    }

    function ensureTaskInOrder(ctx, taskId) {
        const id = String(taskId || '').trim();
        if (!id) return '';
        if (!ctx.executeState.order.includes(id)) ctx.executeState.order.push(id);
        if (!ctx.executeState.taskExpandedById.has(id)) ctx.executeState.taskExpandedById.set(id, true);
        return id;
    }

    function updateExecuteToggleAllButton(ctx) {
        if (!ctx.executeToggleAllBtnEl) return;
        const taskIds = ctx.executeState.order || [];
        if (!taskIds.length) {
            ctx.executeToggleAllBtnEl.textContent = 'Collapse All';
            return;
        }
        const allCollapsed = taskIds.every((taskId) => ctx.executeState.taskExpandedById.get(taskId) === false);
        ctx.executeToggleAllBtnEl.textContent = allCollapsed ? 'Expand All' : 'Collapse All';
    }

    function setAllExecuteTaskExpanded(ctx, expanded) {
        (ctx.executeState.order || []).forEach((taskId) => {
            ctx.executeState.taskExpandedById.set(taskId, !!expanded);
        });
        updateExecuteToggleAllButton(ctx);
        if (ctx.getActiveStage() === 'execute') ctx.renderExecuteStream();
    }

    function upsertTaskMeta(ctx, task) {
        const id = String(task?.task_id || '').trim();
        if (!id) return;
        const current = ctx.executeState.taskMetaById.get(id) || {};
        const outputFormat = String(task?.output?.format || task?.outputFormat || current.outputFormat || '').trim();
        ctx.executeState.taskMetaById.set(id, {
            ...current,
            task_id: id,
            title: String(task?.title || current.title || '').trim(),
            description: String(task?.description || task?.objective || current.description || '').trim(),
            status: String(task?.status || current.status || '').trim(),
            outputFormat,
        });
        ensureTaskInOrder(ctx, id);
    }

    function getTaskMetaById(ctx, taskId) {
        const id = String(taskId || '').trim();
        if (!id) return null;
        return ctx.executeState.taskMetaById.get(id) || null;
    }

    function pushRecentOutput(ctx, taskId, outputText) {
        const id = String(taskId || '').trim();
        if (!id) return;
        const text = String(outputText || '').trim();
        if (!text) return;
        const list = ctx.executeState.recentOutputsByTask.get(id) || [];
        list.push(text);
        while (list.length > 8) list.shift();
        ctx.executeState.recentOutputsByTask.set(id, list);
    }

    function statusLabel(ctx, status) {
        if (typeof ctx.executeUtils.statusLabel === 'function') {
            return ctx.executeUtils.statusLabel(status);
        }
        return String(status || 'undone');
    }

    function statusTone(ctx, status) {
        if (typeof ctx.executeUtils.statusTone === 'function') {
            return ctx.executeUtils.statusTone(status);
        }
        return 'pending';
    }

    function extractValidationDirectReason(ctx, reportText) {
        if (typeof ctx.executeUtils.extractValidationDirectReason === 'function') {
            return ctx.executeUtils.extractValidationDirectReason(reportText);
        }
        return 'Validation gate failed.';
    }

    function buildValidationSummaryBody(ctx, taskId, detail, meta, options = {}) {
        if (typeof ctx.executeUtils.buildValidationSummaryBody === 'function') {
            return ctx.executeUtils.buildValidationSummaryBody({
                taskId,
                detail,
                meta,
                statusLabel: options.statusLabel,
                latestStepBByTask: ctx.executeState.latestStepBByTask,
            });
        }
        return 'Validation report unavailable.';
    }

    function renderExecutionRuntimeStatus(ctx, status) {
        ctx.setExecutionRuntimeStatus(status && typeof status === 'object' ? status : null);
        if (!ctx.executeRuntimeBadgeEl || !ctx.executeRuntimeMetaEl) return;

        const viewModel = (typeof ctx.executeUtils.buildRuntimeStatusViewModel === 'function')
            ? ctx.executeUtils.buildRuntimeStatusViewModel(ctx.getExecutionRuntimeStatus())
            : {
                badgeText: 'Docker: checking...',
                tone: 'is-warn',
                shortMetaText: '',
                detailMetaText: '',
            };

        ctx.executeRuntimeBadgeEl.textContent = viewModel.badgeText;
        ctx.executeRuntimeBadgeEl.classList.remove('is-ok', 'is-warn', 'is-error');
        ctx.executeRuntimeBadgeEl.classList.add(viewModel.tone);
        ctx.executeRuntimeMetaEl.textContent = viewModel.shortMetaText;
        ctx.executeRuntimeMetaEl.title = viewModel.detailMetaText;
    }

    function hasActiveExecuteBubble(ctx) {
        return ctx.executeState.messages.some((msg) => {
            if (msg.kind !== 'assistant') return false;
            const taskId = String(msg.taskId || '').trim();
            if (!taskId) return false;
            const status = String(ctx.executeState.statuses.get(taskId) || '').trim();
            return status === 'doing' || status === 'validating';
        });
    }

    function syncExecuteElapsedTicker(ctx) {
        const shouldRun = ctx.getActiveStage() === 'execute' && hasActiveExecuteBubble(ctx);
        if (!shouldRun) {
            if (ctx.getExecuteElapsedTimerId()) {
                window.clearInterval(ctx.getExecuteElapsedTimerId());
                ctx.setExecuteElapsedTimerId(0);
            }
            return;
        }
        if (ctx.getExecuteElapsedTimerId()) return;
        const timerId = window.setInterval(() => {
            if (ctx.getActiveStage() !== 'execute' || !hasActiveExecuteBubble(ctx)) {
                syncExecuteElapsedTicker(ctx);
                return;
            }
            ctx.renderExecuteStream();
        }, 1000);
        ctx.setExecuteElapsedTimerId(timerId);
    }

    function getAttemptKey(ctx, taskId, attempt) {
        if (typeof ctx.executeUtils.getAttemptKey === 'function') {
            return ctx.executeUtils.getAttemptKey(taskId, attempt);
        }
        return `${String(taskId || '').trim()}:${Number(attempt) || 1}`;
    }

    function getCurrentAttempt(ctx, taskId) {
        const id = String(taskId || '').trim();
        if (!id) return 1;
        const current = Number(ctx.executeState.currentAttemptByTask.get(id));
        return Number.isFinite(current) && current > 0 ? current : 1;
    }

    function setCurrentAttempt(ctx, taskId, attempt) {
        const id = String(taskId || '').trim();
        const n = Number(attempt);
        if (!id || !Number.isFinite(n) || n < 1) return;
        const current = getCurrentAttempt(ctx, id);
        const next = Math.max(current, n);
        ctx.executeState.currentAttemptByTask.set(id, next);
        const key = getAttemptKey(ctx, id, next);
        if (!ctx.executeState.attemptExpandedById.has(key)) {
            ctx.executeState.attemptExpandedById.set(key, true);
        }
    }

    function replayPersistedStepEvents(ctx, stepEvents) {
        if (typeof ctx.executeUtils.replayPersistedStepEvents === 'function') {
            ctx.executeUtils.replayPersistedStepEvents(stepEvents);
        }
    }

    window.MAARS = window.MAARS || {};
    window.MAARS.researchCoreUtils = {
        stringifyOutput,
        ensureTaskInOrder,
        updateExecuteToggleAllButton,
        setAllExecuteTaskExpanded,
        upsertTaskMeta,
        getTaskMetaById,
        pushRecentOutput,
        statusLabel,
        statusTone,
        extractValidationDirectReason,
        buildValidationSummaryBody,
        renderExecutionRuntimeStatus,
        syncExecuteElapsedTicker,
        getAttemptKey,
        getCurrentAttempt,
        setCurrentAttempt,
        replayPersistedStepEvents,
    };
})();
