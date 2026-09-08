/**
 * Research execute graph helpers.
 * Keeps graph payload recovery and rerender scheduling out of the main research flow file.
 */
(function () {
    'use strict';

    window.MAARS = window.MAARS || {};

    function createResearchExecutionGraphHelpers(deps) {
        let renderedKey = '';
        let renderTimerIds = [];

        function resolvePayload() {
            const current = deps.getPayload?.();
            if (current?.layout && Array.isArray(current?.treeData) && current.treeData.length) {
                return current;
            }
            const sharedState = window.MAARS?.state || {};
            const layoutState = sharedState.executionLayout;
            const treeData = Array.isArray(layoutState?.treeData) ? layoutState.treeData : [];
            const layout = layoutState?.layout || null;
            if (!treeData.length || !layout) return null;
            const nextPayload = { treeData, layout };
            deps.setPayload?.(nextPayload);
            treeData.forEach((task) => deps.upsertTaskMeta?.(task));
            return nextPayload;
        }

        function buildRenderKey(payload) {
            if (!payload?.layout || !Array.isArray(payload?.treeData)) return '';
            const ids = payload.treeData.map((task) => String(task?.task_id || '')).filter(Boolean).join('|');
            const width = Number(payload.layout?.width || 0);
            const height = Number(payload.layout?.height || 0);
            return `${ids}::${width}x${height}`;
        }

        function syncNodeStatuses() {
            const statuses = deps.getStatuses?.();
            if (!statuses || typeof statuses.forEach !== 'function') return;
            const updates = [];
            statuses.forEach((status, taskId) => {
                const id = String(taskId || '').trim();
                const nextStatus = String(status || '').trim();
                if (!id) return;
                updates.push({ task_id: id, status: nextStatus || 'undone' });
            });
            if (!updates.length) return;
            window.MAARS?.taskTree?.updateTaskStates?.(updates);
        }

        function clearTimers() {
            renderTimerIds.forEach((timerId) => {
                try {
                    window.clearTimeout(timerId);
                } catch (_) { }
            });
            renderTimerIds = [];
        }

        function ensure(force, options = {}) {
            const allowInactive = options?.allowInactive === true;
            if (!allowInactive && deps.getActiveStage?.() !== 'execute') return;
            const payload = resolvePayload();
            if (!payload?.layout || !Array.isArray(payload?.treeData) || !payload.treeData.length) return;
            const nextKey = buildRenderKey(payload);
            const treeArea = document.querySelector('.plan-agent-execution-tree-area');
            const existingNodes = treeArea?.querySelectorAll('.tasks-tree .tree-task')?.length || 0;
            if (!force && renderedKey === nextKey && existingNodes > 0) {
                syncNodeStatuses();
                return;
            }
            const render = () => window.MAARS?.taskTree?.renderExecutionTree?.(payload.treeData, payload.layout);
            if (typeof window.requestAnimationFrame === 'function') {
                window.requestAnimationFrame(() => {
                    render();
                    renderedKey = nextKey;
                    syncNodeStatuses();
                });
                return;
            }
            render();
            renderedKey = nextKey;
            syncNodeStatuses();
        }

        function schedule(options = {}) {
            const force = options.force === true;
            const allowInactive = options.allowInactive === true;
            const delays = Array.isArray(options.delays) && options.delays.length
                ? options.delays
                : [0, 80, 240, 600];
            const payload = resolvePayload();
            if (!payload?.layout || !Array.isArray(payload?.treeData) || !payload.treeData.length) return;

            clearTimers();
            delays.forEach((delayMs) => {
                const timerId = window.setTimeout(() => {
                    if (typeof window.requestAnimationFrame === 'function') {
                        window.requestAnimationFrame(() => ensure(force, { allowInactive }));
                        return;
                    }
                    ensure(force, { allowInactive });
                }, Math.max(0, Number(delayMs) || 0));
                renderTimerIds.push(timerId);
            });
        }

        function invalidate() {
            renderedKey = '';
            clearTimers();
        }

        return {
            ensure,
            invalidate,
            schedule,
        };
    }

    window.MAARS.createResearchExecutionGraphHelpers = createResearchExecutionGraphHelpers;
})();